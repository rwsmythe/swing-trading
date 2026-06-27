# Phase 7 Sub-C — Web + UX + Shim Cleanup Sweep + Final Integration — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-C of `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md` end-to-end **with operator-authorized scope expansion 2026-05-04** (COA B per orchestrator triage of Sub-B return report). Sub-A SHIPPED on worktree `phase7-sub-a-schema` HEAD `78c7005`; Sub-B SHIPPED on chained worktree `phase7-sub-b-services` HEAD `71ddb95`. Sub-C is the FINAL Phase 7 sub-dispatch; chains from Sub-B; after Sub-C ships full suite green, operator executes integration merge to main bringing all 3 sub-dispatches' work in a single `git merge --no-ff phase7-sub-c-web` commit.

**Scope:** Sub-C extended scope = nominal Sub-C tasks (C.1-C.8 per plan §6 = web routes/trades.py + view_models/trades.py + open_positions_row.py + entry-form 7-fieldset expansion + state_badge partial + gate-failure rendering at 3 surfaces) **PLUS** operator-authorized extended scope (web extended consumers + out-of-Phase-7 shim consumer migrations + test fixture migrations + final shim deletion). Total ~12-16 tasks; ~80-120 expected new tests; ~4-7 Codex rounds.

**Expected duration:** ~7-10 hours. Sub-C is the largest sub-dispatch (web layer + shim sweep + integration gate).

**Dispatch type:** **Direct invocation of `superpowers:subagent-driven-development` followed by `copowers:adversarial-critic`** (NOT the `copowers:executing-plans` wrapper). Worktree isolation + global PreToolUse Codex-blocking hook both in effect — see §0 Skill posture for the 7-step workflow. Same pattern as Sub-A + Sub-B dispatches.

---

## §0 Read first

Read these in order before executing:

1. **`docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`** — THE PLAN. ~4172 lines. Pay particular attention to:
   - **§0** sub-dispatch ordering, worktree posture, BASELINE_SHAs, marker-file workflow.
   - **§1** vocabulary lists (CONFIRMED 2026-05-04; embedded in migration 0014 CHECK enums).
   - **§2.1** status→state per-call-site predicate rewrite mapping. Sub-C T1-T8 owns rewrites where the §2.1 column shows "Sub-C T1/T2/T6/T7". Sub-A + Sub-B entries are LANDED on the chained branch already.
   - **§2.3** broadened grep refresh — re-run at dispatch time + after every Sub-C task to catch any plan-time-missed call sites.
   - **§3** carve-out enumeration. Sub-C nominal scope is web routes/trades.py + view_models/trades.py + open_positions_row.py. **Operator-authorized extended scope (2026-05-04) ADDS the files enumerated in §3 of THIS brief below.**
   - **§6** Sub-C task list (C.1-C.8 nominal): TradeVM expansion (T1); open-positions row VM (T2); entry route + 7 fieldsets (T3); detail Pre-Trade Decision section + audit log (T4); state_badge partial + CSS (T5); routes (T6); templates touched by predicate rewrites (T7); gate-failure rendering at 3 surfaces (T8).
   - **§7** test strategy + +150-250 wide band (across all of Phase 7; Sub-C nominal projected ~50-60; extended scope adds ~30-60 → total ~80-120).
   - **§8** done criteria + return report format.

2. **`docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`** — the spec. ~1069 lines. Locked source of truth.

3. **`docs/phase7-sub-a-schema-executing-plans-brief.md`** + **`docs/phase7-sub-b-services-executing-plans-brief.md`** — prior sub-dispatch briefs. Sub-C inherits their patterns + binding conventions; the chained-branch posture established in Sub-A/Sub-B is preserved.

4. **`docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md`** + **`docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md`** — the brainstorm + writing-plans briefs. §2 hard-conflict escape carries forward to executing-plans (see §8 below).

5. **`CLAUDE.md`** at repo root — gotchas to pre-empt. Sub-C is **WEB-HEAVY** so all HTMX gotchas + base-layout VM rule apply:
   - **HTMX `<tr>`-leading makeFragment pathology** — any new HTMX endpoint returning content with leading `<tr>` is a bug; pure-OOB response architecture or `<div>`/`<section>` root.
   - **HTMX HX-Request header propagation on embedded forms** — embedded forms inside HTMX-rendered fragments need `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode passing.
   - **HTMX HX-Redirect for success vs 303 swap-target** — success-path response should be `204` + `HX-Redirect: <url>` header (browser re-navigates via htmx.js), NOT `303` → swap-target.
   - **HX-Redirect target route MUST be verified to exist** (2026-05-04 gotcha) — TestClient verifies header but doesn't follow; tests should either assert target route registered OR follow the redirect with a second TestClient call.
   - **HTMX OOB-swap partial drift** — use `{% include %}` to share partials between full-page and OOB-swap render paths; never hand-duplicate markup.
   - **base.html.j2 5-VM rule** — every base-layout VM that gains a new field must include it with a safe default. Sub-C likely adds `state_badge_label` or similar to TradeVM + DashboardVM + JournalVM + WatchlistVM + PageErrorVM.
   - **Python `... or ""` vs `... or None` for nullable CHECK columns** (2026-05-04 gotcha) — applies to web-form fallback paths on the new pre-trade fields. Use `... or None` per binding pattern.
   - **TestClient lifespan: `with TestClient(app) as client:`** for any route test.
   - **Starlette `TemplateResponse(request, "name", {...}, status_code=...)` signature.**

6. **`docs/orchestrator-context.md`** — focus on:
   - §"Currently in-flight work" — Phase 7 row reflects Sub-A + Sub-B SHIPPED on chained worktrees.
   - §"Binding conventions" — 4-tier commit-message convention; subject-only ERE grep observable verification; ruff baseline 79 (carried from Sub-B); worktree+editable-install verify-command convention; no-main-commits-during-in-flight-dispatch.
   - §"Lessons captured" — particularly the **Phase 7 Sub-A + Sub-B** lessons (10 entries dated 2026-05-04):
     - **Binding green gate at sub-dispatch boundary infeasible if cross-cutting predicate rewrites deferred.** Sub-C IS the integration gate — full-suite-green at end of Sub-C is binding.
     - **Datetime-column impedance mismatch.** Sub-C consumes Sub-B's `_normalize_trade_event_date_to_iso` helper; web form-input handlers must respect chronology-vs-creation-timestamp distinction.
     - **Lexicographic ordering on text-stored datetimes is a contract.** Web view models that display fills sorted by `fill_datetime` inherit this contract.
     - **Codex round count is wrong heuristic for thrash; chain-convergence shape is right.** Document any chain in your return report.
     - **Plan-authoring "illustrative" placeholders in tests are vacuous tests.** Per Phase 7 plan-authoring lesson — plan tasks already specify EXACT values; reject any "illustrative" / TODO placeholders at internal review.

7. **Production DB state verification** — at dispatch time, run from MAIN's working tree (NOT Sub-C's worktree) to confirm production hasn't drifted:
   ```python
   import sqlite3, os
   conn = sqlite3.connect(os.path.expanduser("~/swing-data/swing.db"))
   for ticker in ('VIR', 'DHC', 'CC', 'YOU'):
       trade = conn.execute("SELECT id, ticker, status, entry_date, entry_price, initial_shares, hypothesis_label FROM trades WHERE ticker = ?", (ticker,)).fetchone()
       print(f'{ticker}: {trade}')
   print('exits:', conn.execute("SELECT * FROM exits").fetchall())
   print('schema_version:', conn.execute("SELECT * FROM schema_version").fetchall())
   ```
   Expected: 4 trades (VIR closed+reviewed; DHC + CC + YOU open) + 1 exit (VIR's) + **schema_version=13** (Sub-A + Sub-B NOT yet merged per chained-branch posture). If state diverges (e.g., 5 trades, schema=14, additional exits), STOP and surface in return report — chained-branch posture requires production stays at v13 until Sub-C's final integration merge.

8. **Sub-A + Sub-B worktree state verification** — confirm both prior worktrees are intact:
   ```bash
   git worktree list
   ```
   Expected output includes:
   - `.worktrees/phase7-sub-a-schema  78c7005 [phase7-sub-a-schema]`
   - `.worktrees/phase7-sub-b-services  71ddb95 [phase7-sub-b-services]`

   If either is missing or HEAD differs, STOP and surface — chained-branch posture requires both intact for Sub-C's branch to chain from Sub-B's HEAD.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before executing the plan task.

---

## §0.5 Skill posture (7-step workflow — execute in order)

**Step 1 — Create chained worktree from Sub-B's HEAD.** INVOKE `superpowers:using-git-worktrees` to create an isolated worktree on a NEW branch `phase7-sub-c-web` based on **Sub-B's branch HEAD `71ddb95`** (NOT main HEAD; NOT Sub-A HEAD).

The git command for the chained-branch posture:

```bash
git worktree add -b phase7-sub-c-web .worktrees/phase7-sub-c-web phase7-sub-b-services
```

This creates `phase7-sub-c-web` branch starting from Sub-B's HEAD; the new worktree at `.worktrees/phase7-sub-c-web/` will see Sub-A's 14 commits + Sub-B's 15 commits (29 total) already landed. All your work commits onto `phase7-sub-c-web` and stacks on top.

**Step 2 — Activate the Codex-blocking marker.** From within the worktree: `touch .copowers-subagent-active`. Hook is harness-level and cannot be bypassed.

**Step 3 — Invoke subagent-driven-development DIRECTLY** (NOT via `copowers:executing-plans` wrapper):

- **INVOKE** `superpowers:subagent-driven-development` and execute Tasks C.1-C.8 (nominal) + C.9-C.16 (extended scope) per §3 below. Subagents will physically be unable to invoke Codex/copowers review while the marker is active.
- **DO NOT INVOKE** `copowers:executing-plans` / `copowers:adversarial-critic` / `mcp__plugin_copowers_codex__codex(-reply)` from within subagent dispatches.
- **DO NOT INVOKE** brainstorming / writing-plans skills — design is locked at spec `c926f01`; plan is locked at `251cc35`.

**Step 4 — Remove marker.** After all tasks complete + final code reviewer approves: `rm .copowers-subagent-active`. Verify: `ls .copowers-subagent-active` → `No such file`.

**Step 5 — Invoke Codex adversarial review.** INVOKE `copowers:adversarial-critic` directly with:
- `PHASE`: `executing-plans`
- `SPEC_PATH`: `docs/phase7-sub-c-web-executing-plans-brief.md` (this brief)
- `PLAN_PATH`: `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`
- `BASELINE_SHA`: `71ddb95` (Sub-B worktree HEAD = Sub-C's chained baseline; review covers all Sub-C worktree commits since this base)

Iterate Codex rounds to `NO_NEW_CRITICAL_MAJOR`. Internal-Codex pre-emption (commit message qualifier `(internal)`) is encouraged. Expect 4-7 rounds (Sub-C is the largest sub-dispatch + extended-scope shim cleanup adds Codex review surface; widened band per Sub-B's 6-round chain-convergence lesson).

**Step 6 — Operator-witnessed browser verification gate (BINDING).** Per Phase 7 binding convention + CLAUDE.md gotcha catalog: HTMX-driven UX cannot be verified by TestClient alone. Operator runs `swing web` against the dispatch's worktree (using `$env:PYTHONPATH = "."; python -m swing.cli web` per editable-install convention) and verifies:
- Entry form: 7 fieldset expansion renders correctly; embedded form `hx-headers` propagation works for OriginGuard strict-mode; submit succeeds + HX-Redirects to a registered route.
- Exit form: HTMX submit succeeds + HX-Redirects.
- Stop-adjust form: HTMX submit succeeds.
- Review form: HTMX submit succeeds + HX-Redirects to `/reviews/pending` (Phase 6 fix preserved).
- State badges render correctly per state value (5 colors: entered/managing/partial_exited/closed/reviewed).
- Dashboard "Open Positions" + "Active Trades" surfaces show state-aware filtering (`state IN ('entered','managing','partial_exited')`).
- Dashboard "needs review" badge renders for closed-but-not-reviewed trades only (state == 'closed', not state == 'reviewed').
- Cadence cards (Phase 6) render correctly + completion path works.
- No regressions to existing flows: trade-listing, hyp-recs panel, watchlist top-5, journal review, configuration page.

Operator surfaces PASS / FAIL per surface. Any FAIL → fix in worktree + re-verify before merge.

**Step 7 — Surface integration merge command + cleanup steps in return report.** Sub-C is the FINAL dispatch — operator executes the merge AFTER reviewing the return report:

```bash
cd c:/Users/rwsmy/swing-trading
git checkout main
git pull
git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"
git push
```

Bring all 3 sub-dispatches' work in single merge commit. Production DB triggers 0014 migration on first `swing` invocation post-merge (backup-runner discipline applies — Sub-A's T1 backup runner with 4 integrity checks fires automatically).

**Worktree cleanup (operator-paced post-merge):**

```bash
git worktree remove .worktrees/phase7-sub-c-web
git worktree remove .worktrees/phase7-sub-b-services
git worktree remove .worktrees/phase7-sub-a-schema
git branch -d phase7-sub-c-web phase7-sub-b-services phase7-sub-a-schema
```

If any worktree removal fails on `.tmp/pytest-of-rwsmy/` ACL-lock (recurrence pattern documented in `docs/phase3e-todo.md` 2026-05-04 trigger-gated entry), invoke takeown + icacls cleanup OR run `cleanup-locked-scratch-dirs.ps1` (note: 2026-05-02 extension covers Codex-sandbox patterns but NOT pytest-of-rwsmy patterns; cleanup-script extension is the trigger-gated backlog item).

---

## §1 Strategic context (compressed)

Phase 7 ships the trade lifecycle state machine + Fills first-class. Sub-A landed the data-layer foundation; Sub-B landed the service + CLI + journal layer. Sub-C is the web + UX layer + extended-scope shim cleanup sweep + final integration. After Sub-C ships green, Phase 7 is COMPLETE and main returns to a clean state machine + Fills semantics.

**Why extended scope (operator decision 2026-05-04):** Sub-B's return surfaced ~18 production-code consumer files of the legacy Exit class + list_all_exits + list_exits_for_trade + insert_exit_with_event APIs (web extended files NOT in plan §3 enumeration; out-of-Phase-7 modules — review_log, pipeline, recommendations/hypothesis, journal aggregation, cli list, trades/equity, trades/review). Shim full-deletion blocked on these consumer migrations. Operator chose COA B (Sub-C extended scope) over COA A (shims permanent) or COA C (separate Sub-D dispatch) — preserves clean Phase 7 endgame with no permanent shim debt.

**What ships in this dispatch:**

### Nominal Sub-C scope (per plan §6; tasks C.1-C.8)

- **C.1** `swing/web/view_models/trades.py` TradeVM expansion: state field + state_badge_label + ~28 new pre-trade fields (matching Trade dataclass post-Sub-A); migration to fills repo (`list_exits_for_trade` → `list_fills_for_trade(...).filter(action != 'entry')` analog).
- **C.2** `swing/web/view_models/open_positions_row.py`: predicate rewrite (active-trade `state IN ('entered','managing','partial_exited')`); fills repo migration; state badge in row VM.
- **C.3** `swing/web/routes/trades.py`: predicate rewrites at lines 844, 1082, 1198 (per plan §2.1); entry route + 7 fieldset rendering (per spec §11.1 — 18 new pre-trade fields organized into 7 themed sections); HX-Redirect to registered routes (HX-Redirect-target verification per CLAUDE.md gotcha).
- **C.4** `swing/web/templates/trades/detail.html.j2`: Pre-Trade Decision section (display 18 thesis fields + 4 premortem fields + emotional_state multi-select + manual_entry_confidence) + audit log display (trade_events with `event_type='pre_trade_edit'` rendering).
- **C.5** `swing/web/templates/partials/state_badge.html.j2` NEW + CSS: per-state colors (entered=blue/neutral; managing=green/active; partial_exited=yellow/in-progress; closed=gray/done; reviewed=purple/finalized; tweak per operator preference at browser gate).
- **C.6** `swing/web/routes/trades.py` state-aware route handlers (state predicate enforcement on transitions; gate-failure rendering for `MissingPreTradeFieldsException`).
- **C.7** `swing/web/templates/journal.html.j2:34` predicate-display rewrite + other state-display templates touched by predicate rewrites.
- **C.8** Gate-failure rendering at 3 surfaces (entry / exit / review): user-friendly error display when service raises `MissingPreTradeFieldsException` or other `ValueError` subclasses; `... or None` for nullable CHECK columns in form-input fallback paths.

### Extended scope (operator-authorized 2026-05-04; tasks C.9-C.16)

The implementer chunks these into ~4-8 tasks per practical groupings; commit message format is `feat(<area>): Task C.X — <subject>` per the 4-tier convention.

- **C.9** Web-extended consumer migrations (3 files):
  - `swing/web/routes/recommendations.py` (lines 33, 102 — `list_all_exits`)
  - `swing/web/view_models/dashboard.py` (lines 18, 608 — `list_all_exits`)
  - `swing/web/view_models/journal.py` (lines 11, 45 — `list_all_exits`)
  All three migrate from `list_all_exits(conn)` to fills repo helper (likely `list_all_fills(conn)` filtered to `action != 'entry'` or analogous; consult Sub-A's `swing/data/repos/fills.py` for canonical helper signatures).
- **C.10** Out-of-Phase-7 module migrations (5 files):
  - `swing/data/repos/review_log.py` (5 references at lines 102, 140, 302, 309, 312 — Phase 6 module; review aggregation)
  - `swing/pipeline/runner.py` (4 references at lines 27, 438, 571, 826 — pipeline orchestrator stats computation)
  - `swing/recommendations/hypothesis.py` (2 references at lines 386, 398 — hypothesis aggregation)
  - `swing/trades/equity.py` (1 import at line 6 — equity computation; verify usage + migrate)
  - `swing/trades/review.py` (1 import at line 20 — Sub-B touched but Exit import stayed)
  All migrate from Exit / list_all_exits / list_exits_for_trade / insert_exit_with_event references to fills equivalents.
- **C.11** CLI list migration:
  - `swing/cli.py` lines 709, 724, 1316, 1331 — `swing trade exits` listing CLI; Sub-B touched but list_all_exits import stayed. Migrate to fills repo. Operator-facing question: rename CLI subcommand from `swing trade exits` to `swing trade fills` for accuracy? (Default: KEEP `swing trade exits` for operator workflow continuity; output rendering can show fills filtered to non-entry actions. Surface in return report if implementer believes rename is warranted.)
- **C.12** Journal aggregation migration:
  - `swing/journal/stats.py` (3 references at lines 9, 262, 275 — Sub-B touched but Exit import + list_all_exits usage stayed)
  - `swing/journal/flags.py` (1 import at line 8 — Sub-B touched but Exit import stayed)
  - `swing/journal/analyze.py` (2 references at lines 17, 200 — Sub-B touched but list_exits_for_trade stayed)
  All migrate to fills repo. Verify journal stats computation produces identical numerical results post-migration (discriminating regression test; per the CLAUDE.md gotcha "compounding-confound test fixtures").
- **C.13** Test fixture migrations (3 files):
  - `tests/cli/test_cli_trade_analyze.py` (intentional skip-with-gate-task per Sub-B)
  - `tests/cli/test_review_complete_cli.py` (intentional skip-with-gate-task per Sub-B)
  - `tests/cli/test_trade_review_cli.py` (intentional skip-with-gate-task per Sub-B)
  All migrate fixtures from `Exit(...)` constructions + `insert_exit_with_event(...)` calls to `Fill(action='exit', ...)` constructions + `insert_fill_with_event(...)` calls. Test assertions stay the same (functional intent unchanged).
- **C.14** Final shim deletion (BINDING — single commit at end-of-Sub-C):
  - DELETE `Exit` dataclass from `swing/data/models.py` (line 161 stub).
  - DELETE `list_exits_for_trade`, `list_all_exits`, `insert_exit_with_event`, `_ExitLikeRow` from `swing/data/repos/trades.py`.
  - This is an authorized Sub-A territory exception per operator scope decision 2026-05-04 (extended-scope COA B).
  - Verify with `grep -rn "from swing\.data\.models import.*Exit\|list_all_exits\|list_exits_for_trade\|insert_exit_with_event\|_ExitLikeRow" swing/ tests/` — expected output: ZERO matches post-deletion.
  - Discriminating test: importing the deleted symbols raises `ImportError`.
  - Commit message: `refactor(data): Sub-C T14 — delete Exit class + list_all_exits + list_exits_for_trade + insert_exit_with_event + _ExitLikeRow shims (final deletion; all consumers migrated)`.

### What ships at integration

After Sub-C ships green + operator-witnessed browser gate PASSES:
- Operator executes `git merge --no-ff phase7-sub-c-web` to main.
- Production DB triggers 0014 migration on first `swing` invocation post-merge (backup-runner discipline fires automatically).
- All 4 production trades (VIR/DHC/CC/YOU) backfilled per Sub-A T10 in-flight migration with FIRM values.
- Operator's daily workflows resume against state-machine + Fills semantics.

**Production DB at brief-draft time (HEAD `8cbc296` on main; Sub-B worktree HEAD `71ddb95`):** schema_version=13 unchanged on production DB; 4 trades + 1 exit. Operator's trade workflows continue working through this dispatch.

**Test baseline at chained-baseline `71ddb95`:** 1605 fast tests passed; 130 failed + 6 errors all in `tests/web/` (Sub-C's starting point). After Sub-C: target is FULL-SUITE-GREEN (zero failures; zero errors).

---

## §2 Locked decisions (DO NOT re-litigate)

All design decisions locked in spec at `c926f01` + writing-plans brief §2 + plan §1-§7 + Sub-A executing-plans brief §2 + Sub-B executing-plans brief §2. Plan implements them as written; do NOT re-design. If a locked decision is impossible to implement as the plan specifies, STOP and surface in the return report.

Notable Sub-C-relevant locked decisions (NOT exhaustive — read spec + plan + prior briefs):

- **5-state minimal:** `entered → managing → partial_exited → closed → reviewed`. Unidirectional graph. Sub-C web surfaces enforce state predicate filtering.
- **Vocabulary CONFIRMED 2026-05-04** (catalyst-9 / emotional_state-8 / event_type-7) — entry form 7 fieldsets render against these enums; `... or None` for nullable text fallback.
- **Operation-contextual validation** (spec §3.5.1): web routes consume entry/exit/review services which call `validate_for_operation(...)` BEFORE `state_transition(...)`. Web doesn't validate; service layer does.
- **Pre-trade gate (`MissingPreTradeFieldsException`):** NOT force-bypassable. Web routes catch the exception + render user-friendly error display (T8 nominal scope).
- **`trade_origin` derivation:** web routes pass `EntryPath` enum on EntryRequest per the route's source (form vs hyp-recs Take-this-trade button); `derive_trade_origin(...)` computes value at service layer.
- **HX-Redirect target route MUST be verified to exist** (CLAUDE.md gotcha 2026-05-04): every HX-Redirect-emitting route in Sub-C tests asserts target route registered OR follows redirect with second TestClient call.
- **Operator-witnessed browser verification gate is BINDING** (per Phase 7 binding convention + CLAUDE.md HTMX gotcha catalog 2026-04-25 / 2026-04-29 / 2026-05-02 / 2026-05-04). Multiple browser-only failure surfaces TestClient cannot detect.
- **Sub-A territory exception (C.14 final shim deletion):** authorized per operator scope decision 2026-05-04 (COA B). DELETE `Exit` dataclass from `swing/data/models.py` + `list_all_exits` / `list_exits_for_trade` / `insert_exit_with_event` / `_ExitLikeRow` from `swing/data/repos/trades.py`. Single commit at end-of-Sub-C.
- **Chained-branch posture** (operator decision 2026-05-04): Sub-C is the FINAL dispatch. Sub-C's HEAD merges to main via `git merge --no-ff`. Production DB stays at v13 throughout this dispatch; v14 migration triggers on first post-merge `swing` invocation.
- **No-main-commits-during-in-flight-dispatch** (lesson 2026-05-04). Orchestrator holds main edits while this dispatch is in-flight; exception only for verified-non-overlapping pure-docs edits with operator awareness.

**Hard-conflict escape:** if a locked decision genuinely BLOCKS Sub-C implementation (not merely creates tension — actually blocks), pause the dispatch, send an interim outbrief describing the conflict, standby for an orchestrator path-forward brief. This is the only relitigation channel.

---

## §3 Scope

### In scope (this dispatch)

**Nominal Sub-C tasks (C.1-C.8 per plan §6):** TradeVM expansion; open-positions row VM; entry route + 7 fieldsets; detail Pre-Trade Decision section + audit log; state_badge partial + CSS; routes + state-aware handlers; templates touched by predicate rewrites; gate-failure rendering at 3 surfaces.

**Operator-authorized extended scope (2026-05-04; tasks C.9-C.14):**

- **C.9** Web-extended consumer migrations: `swing/web/routes/recommendations.py` + `swing/web/view_models/dashboard.py` + `swing/web/view_models/journal.py` (all `list_all_exits` → fills repo).
- **C.10** Out-of-Phase-7 module migrations: `swing/data/repos/review_log.py` + `swing/pipeline/runner.py` + `swing/recommendations/hypothesis.py` + `swing/trades/equity.py` + `swing/trades/review.py` (Sub-B-touched but stayed-imports cleanup).
- **C.11** CLI list migration: `swing/cli.py` lines 709, 724, 1316, 1331 (`swing trade exits` listing).
- **C.12** Journal aggregation migration: `swing/journal/stats.py` + `swing/journal/flags.py` + `swing/journal/analyze.py` (Sub-B-touched but stayed-imports cleanup); discriminating regression test for journal-stats numerical equivalence post-migration.
- **C.13** Test fixture migrations: 3 test files with intentional skip-with-gate-task markers from Sub-B.
- **C.14** Final shim deletion (BINDING; single commit; authorized Sub-A territory exception): DELETE Exit + list_all_exits + list_exits_for_trade + insert_exit_with_event + _ExitLikeRow.

The implementer is free to chunk C.9-C.14 into more or fewer tasks per practical groupings (e.g., grouping all web-extended into one task C.9; splitting C.10 by file if Codex review surface gets too dense). Brief enumerates the file scope; implementer chunks tasks.

### Out of scope (explicitly NOT this dispatch)

- **Re-litigating any locked decision** in spec / writing-plans brief / plan §1-§3 / Sub-A brief §2 / Sub-B brief §2. Hard-conflict escape applies if a locked decision genuinely BLOCKS implementation — see §8.
- **Sub-A territory beyond C.14 final shim deletion** — Sub-A's schema migration; repos/trades.py base APIs; repos/fills.py; state.py / origin.py / derived_metrics.py / db.py migration runner; preservation invariant fixtures; in-flight migration. ALREADY SHIPPED on chained-base; do NOT modify.
- **Sub-B territory** — entry/exit/stop_adjust/review services; CLI predicate rewrites + display + new options (already landed); journal predicate rewrites (already landed). ALREADY SHIPPED on chained-base; do NOT modify.
- **Phase 8 territory** — Daily_Management snapshots; MFE/MAE precision via OHLCV; In-Trade Review workflow.
- **Phase 9 territory** — Risk_Policy entity; Reconciliation_Run + Reconciliation_Discrepancy framework; drawdown circuit breaker activation.
- **Edit-after-lock UI** — schema fully supports via `trade_events.event_type='pre_trade_edit'`; UI ships V2.
- **Renaming `swing trade exits` CLI subcommand** unless implementer believes warranted (default: KEEP for operator workflow continuity; surface in return report with rationale if rename proposed).
- **Bumping schema version** — Sub-A landed 0014; Sub-C does NOT bump. Any schema change need surfaces as hard-conflict escape.
- **`.gitignore` updates for Sub-B's untracked manual_repro_*.db artifacts** — orchestrator will handle separately (cleanup item; not Sub-C scope).

---

## §4 Binding conventions

- **Worktree isolation:** all work commits within the dispatch's isolated worktree (per §0 Step 1) — `phase7-sub-c-web` branch chained from `phase7-sub-b-services`. DO NOT commit directly to `main`.
- **Marker-file management:** `touch .copowers-subagent-active` BEFORE Step 3; `rm` AFTER Step 3 / BEFORE Step 5. Binding.
- **Commits — 4-tier conventional:**
  - Task implementation: `feat(<area>): Task C.X — <subject>` or `refactor(<area>): Task C.X — <subject>` for predicate rewrites.
  - Codex review-fix: `fix(<area>): Codex R<N> <severity> <id> — <subject>`.
  - Internal-Codex (within-task): append `(internal)` qualifier.
  - Internal code-review fix: `fix(<area>): code-review I<N> — <subject>`.
  - Format-only cleanup (ruff): no task ID prefix.
- **Subject-only ERE grep observable verification** before EVERY task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task C\.X'
  ```
- **NO OVERWRITING LANDED-TASK COMMITS:** before each task, verify prior task's commit is present AND read the landed file to understand the existing API.
- **NO REGRESSING SUB-A or SUB-B's COMMITS:** Sub-A's 14 + Sub-B's 15 = 29 commits are landed on the chained base. Sub-C may CONSUME those APIs; Sub-C may NOT modify them EXCEPT the C.14 authorized Sub-A territory exception (final shim deletion).
- **TDD:** write failing test → run → see fail → minimal implementation → run → see pass → commit, per task.
- **Discriminating-test discipline (binding):** every test specifies EXACT field + EXACT pre-fix expected value + EXACT post-fix expected value. NO "illustrative" / TODO placeholders.
- **Ruff baseline ≤79** (carried forward from Sub-B `71ddb95`). New code MUST NOT increase baseline. `ruff check swing/` after each task.
- **No-amend.** Every commit is a NEW commit. Codex/code-review fixes are their own commits.
- **No `--no-verify`, no `--no-gpg-sign`, no Claude co-author footer.**
- **Browser verification gate evidence:** at end of dispatch (BEFORE Step 7 merge command surfacing), operator-witnessed gate runs against worktree using `$env:PYTHONPATH = "."; python -m swing.cli web` (PowerShell) or `PYTHONPATH=. python -m swing.cli web` (bash). Per-surface PASS/FAIL captured in return report.
- **HX-Redirect target verification:** every HX-Redirect-emitting route in Sub-C's tests asserts target route registered OR follows redirect with second TestClient call. Per CLAUDE.md gotcha 2026-05-04 (Phase 6 mid-verification fix learning).

---

## §5 Adversarial review watch items (for the post-dispatch Codex round)

The orchestrator-side `copowers:adversarial-critic` invocation (Step 5) covers these. Internal-Codex pre-emption is encouraged; pre-empt these in particular:

- **Sub-A + Sub-B test preservation.** Reviewer verifies all Sub-A + Sub-B tests REMAIN GREEN. Discriminating regression check at end of every task.
- **Predicate rewrite per §2.1 mapping** (C.1-C.7 + extended scope). Each rewrite preserves semantic purpose (active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths). Reviewer flags any rewrite that inverts semantics.
- **Shim deletion correctness** (C.14 BINDING). Post-deletion grep returns ZERO references to Exit / list_all_exits / list_exits_for_trade / insert_exit_with_event / _ExitLikeRow across `swing/` + `tests/`. Discriminating test: importing the deleted symbols raises `ImportError`.
- **No consumer left behind** (extended scope). Reviewer verifies the C.9-C.14 file enumeration in §3 of this brief is complete + each file is migrated (broadened-grep refresh per plan §2.3 catches plan-time-missed call sites).
- **HX-Redirect target validation.** Every new HTMX POST emitting HX-Redirect has registered target route + test that verifies target resolves.
- **HTMX `<tr>`-leading makeFragment pathology.** Any new HTMX endpoint returning content with leading `<tr>` is a bug; pure-OOB response architecture or `<div>`/`<section>` root.
- **HX-Request header propagation.** Embedded forms inside HTMX-rendered fragments need `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode passing.
- **HX-Redirect for success vs 303 swap-target.** Success-path response is `204` + `HX-Redirect: <url>` header, NOT `303` → swap-target.
- **OOB-swap partial drift.** New partials that share markup with existing partials use shared `{% include %}`.
- **base.html.j2 5-VM rule.** Any new field the base layout dereferences is added to ALL base-layout VMs (TradeVM, DashboardVM, JournalVM, WatchlistVM, PageErrorVM) with safe defaults.
- **`... or None` for nullable CHECK columns.** Web form-input fallback paths on the new pre-trade fields use `... or None`, NOT `... or ""`.
- **Phase 6 invariants survive.** Mistake_Tags vocabulary + Process Grade computation + Review_Log entity + cadence cards + soft-warn at trade close + dashboard "needs review" badge — all preserved post-Sub-C. Discriminating regression test per Phase 6 invariant.
- **Phase 7 invariants survive** (Sub-A + Sub-B). State machine all-transition-paths matrix; fills aggregate denormalization; pre_trade_locked_at; trade_origin derivation; operation-contextual validation; backup-runner discipline. All preserved post-Sub-C.
- **Datetime canonicalization respected** (Sub-B lesson). Web form-input handlers respect chronology-vs-creation-timestamp distinction; consume `_normalize_trade_event_date_to_iso` helper for any new datetime-emitting route.
- **Lexicographic ordering on text-stored datetimes.** Web view models that display fills sorted by `fill_datetime` use the canonical helper.
- **Operator-witnessed browser verification gate evidence.** Return report includes per-surface PASS/FAIL with one-sentence-each evidence (per Phase 7 mathtext-fix-dispatch lesson on rendering verification format).
- **Final shim deletion is at C.14 (single commit).** Reviewer verifies no piecemeal deletion across multiple tasks (would split the deletion across un-rebasable commit boundaries).
- **Test count discipline.** Plan estimates wide band (~80-120 for extended scope). Don't tighten acceptance criteria around optimistic estimate. Report new-test count + RED→GREEN closure count separately for clarity (per Sub-B return report's narrative-counting subtlety).

---

## §6 Done criteria

The Sub-C executing-plans dispatch is done when ALL of the following hold:

- [ ] All nominal tasks (C.1-C.8) + extended-scope tasks (C.9-C.14) committed on the chained worktree branch.
- [ ] Subject-only ERE grep verification clean (no duplicate Task C.X commits).
- [ ] **FULL-SUITE-GREEN**: `python -m pytest -m "not slow" -q` passes; ZERO failures; ZERO errors; test count delta within band.
- [ ] Sub-A + Sub-B test counts maintained or grown (no regressions).
- [ ] Ruff baseline ≤79 (no increase from chained-baseline `71ddb95`).
- [ ] Final shim deletion at C.14: post-deletion grep `grep -rn "from swing\.data\.models import.*Exit\|list_all_exits\|list_exits_for_trade\|insert_exit_with_event\|_ExitLikeRow" swing/ tests/` returns ZERO matches.
- [ ] Operator-witnessed browser verification gate PASS per all 7+ surfaces (entry form / exit form / stop-adjust / review / state badges / dashboard / journal review / cadence cards / hyp-recs panel / no regressions).
- [ ] Marker file removed (`ls .copowers-subagent-active` → No such file).
- [ ] Codex `copowers:adversarial-critic` round reached `NO_NEW_CRITICAL_MAJOR`.
- [ ] **Integration merge command + worktree cleanup steps surfaced in return report** (operator executes the merge after triage). Sub-C does NOT merge to main; surfaces the merge command for operator.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
DISPATCH: Phase 7 Sub-C (web + UX + extended-scope shim cleanup + final integration prep)
WORKTREE BRANCH: phase7-sub-c-web
WORKTREE PATH: C:/Users/rwsmy/swing-trading/.worktrees/phase7-sub-c-web
CHAINED-BASELINE_SHA: 71ddb95 (Sub-B worktree HEAD)
HEAD: <Sub-C HEAD SHA>

TASK COMMITS (~12-16):
  <commit list, C.1 through C.14 with implementer-chunked grouping>

CODE-REVIEW FIX COMMITS:
  <commit list>

CODEX FIX COMMITS:
  <commit list>

INTERNAL-CODEX FIX COMMITS (qualifier (internal)):
  <commit list>

CODEX ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TEST DELTA:
  baseline (71ddb95):  1605 passed, 130 failed, 6 errors, 21 skipped
  post-dispatch:       <N> passed, 0 failed, 0 errors, <N> skipped
  Sub-A + Sub-B tests preserved: <count regression check>
  New Sub-C tests added:        <+N> (vs ~80-120 plan estimate; bias-high acceptable)
  RED→GREEN closures:           <+N> (Sub-C territory previously RED, now GREEN)

RUFF DELTA:
  baseline:      79 errors at 71ddb95
  post-dispatch: <N>

SHIM DELETION VERIFICATION (C.14):
  grep result:           ZERO references to Exit / list_all_exits / list_exits_for_trade / insert_exit_with_event / _ExitLikeRow
  ImportError test:      <commit SHA> — confirms imports raise ImportError post-deletion

OPERATOR-WITNESSED BROWSER VERIFICATION GATE: <PASS / FAIL>
  S1 entry form 7 fieldsets render correctly:                <PASS/FAIL with evidence>
  S2 entry form HTMX submit + HX-Request propagation:        <PASS/FAIL>
  S3 entry form HX-Redirect to registered route:             <PASS/FAIL>
  S4 exit form HTMX submit + HX-Redirect:                    <PASS/FAIL>
  S5 stop-adjust form HTMX submit:                           <PASS/FAIL>
  S6 review form HTMX submit + HX-Redirect to /reviews/pending: <PASS/FAIL>
  S7 state badges render per state value (5 colors):         <PASS/FAIL>
  S8 dashboard state-aware filtering:                        <PASS/FAIL>
  S9 dashboard "needs review" badge (state == 'closed' only): <PASS/FAIL>
  S10 cadence cards + completion path:                       <PASS/FAIL>
  S11 no regressions (trade-listing, hyp-recs, watchlist, etc.): <PASS/FAIL>

PHASE 6 + PHASE 7 INVARIANTS PRESERVED:
  Mistake_Tags + Process Grade + Review_Log:                  <verification>
  State machine all-transition-paths matrix:                  <verification>
  Fills aggregate denormalization:                            <verification>
  pre_trade_locked_at + trade_origin derivation:              <verification>
  Operation-contextual validation:                            <verification>
  Backup-runner discipline:                                   <verification>

ADVERSARIAL FINDINGS (each with disposition):
  R1: <count critical / major / minor>
    - <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>
  R2: ...

LESSONS WORTH CAPTURING (process insights from this dispatch):
  - <bullet list>

OPEN QUESTIONS FOR ORCHESTRATOR:
  - <any blocker or unresolved framing issue>

INTEGRATION MERGE COMMAND (operator-executed):
  cd c:/Users/rwsmy/swing-trading
  git checkout main
  git pull
  git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"
  git push

POST-MERGE PRODUCTION DB MIGRATION:
  Triggers on first `swing` invocation post-merge (backup-runner discipline auto-fires);
  expected backup at `~/swing-data/swing-pre-migration-0014-<timestamp>.db`;
  4 integrity checks all pass; schema_version 13→14;
  4 production trades (VIR/DHC/CC/YOU) backfilled per Sub-A T10 in-flight migration.

WORKTREE CLEANUP (operator-paced post-merge):
  git worktree remove .worktrees/phase7-sub-c-web
  git worktree remove .worktrees/phase7-sub-b-services
  git worktree remove .worktrees/phase7-sub-a-schema
  git branch -d phase7-sub-c-web phase7-sub-b-services phase7-sub-a-schema
  # If `.tmp/pytest-of-rwsmy/` ACL-locks block removal, follow trigger-gated entry
  # at `docs/phase3e-todo.md` 2026-05-04.

SUB-A + SUB-B + SUB-C COMMIT SUMMARY (for the integration commit):
  Sub-A commits: 14 (78c7005..eba1625-base)
  Sub-B commits: 15 (71ddb95..78c7005-base)
  Sub-C commits: <N> (HEAD..71ddb95-base)
  Total: <N> commits across 3 sub-dispatches
```

---

## §8 If you get stuck

- **If a plan task requires re-designing the spec or plan,** invoke the §2 hard-conflict escape (carries forward from prior briefs): pause the dispatch, send an interim outbrief describing the conflict, standby for orchestrator path-forward. Do NOT relitigate the spec OR plan in the dispatch.
- **If the production DB state at empirical-audit time differs from §0 #7 expected state** (e.g., 5 trades exist; schema_version != 13), STOP IMMEDIATELY. Do NOT proceed with task implementation. Surface to orchestrator — chained-branch posture requires production stays at v13 until final integration.
- **If Sub-A or Sub-B worktree is missing or HEAD differs,** STOP — chained branch can't form correctly. Surface immediately.
- **If a Sub-A or Sub-B API needs adjusting for Sub-C** (e.g., fills repo helper missing a needed query for web view models), STOP. Do NOT silently modify Sub-A or Sub-B's files. Surface as hard-conflict escape — orchestrator decides whether to add a bridge commit on a prior worktree OR add to Sub-C's scope. The C.14 final shim deletion is the ONLY pre-authorized Sub-A territory exception.
- **If shim deletion at C.14 breaks tests unexpectedly,** investigate which consumer was missed in C.9-C.13; complete the missed migration first; THEN delete shims. Do NOT delete shims until grep returns zero references.
- **If browser verification gate FAILS on any surface,** fix in worktree + re-verify. Do NOT surface the merge command until ALL surfaces PASS.
- **If Codex review surfaces a finding that contradicts a locked decision,** apply receiving-code-review discipline. Verify the finding against the spec + plan + prior briefs FIRST. If finding is correct AND locked decision is wrong, escalate via §2 hard-conflict escape. If finding is wrong, document why it's rejected with rationale.
- **If the empirical audit broadened-grep refresh (per plan §2.3) finds new call sites not in this brief's §3 enumeration,** add to the appropriate Sub-C task's scope (extended scope is operator-authorized; new findings stay within Sub-C).
- **If Codex round count exceeds 7,** check chain-convergence shape (each round catches issue from prior fix = healthy convergence; each round catches unrelated issues = thrash). Healthy convergence is acceptable per Sub-B lesson; surface the chain in your return report so orchestrator can audit.

---

## §9 Anti-patterns specific to this dispatch

These have caused real problems in past sessions; resist:

- **Drifting into Phase 8/9 territory.** Sub-C is web + UX + shim cleanup; Daily_Management, Risk_Policy, Reconciliation_Log are out-of-Phase-7.
- **Modifying Sub-A or Sub-B files beyond C.14.** Sub-A's data layer + state/origin/derived_metrics; Sub-B's services + CLI + journal predicate rewrites — all LANDED on chained base; consume their APIs, do NOT modify. Hard-conflict escape if modification needed. C.14 final shim deletion is the ONLY pre-authorized exception.
- **Re-litigating locked decisions.** Spec at `c926f01` + plan at `251cc35` + Sub-A/B brief decisions burned context settling these. Don't reopen.
- **Silent merging to main during the dispatch.** Sub-C does NOT merge to main; surface the merge command for OPERATOR to execute after triage.
- **Piecemeal shim deletion across multiple tasks.** C.14 is a SINGLE commit deleting all 5 shim symbols. Splitting across tasks creates un-rebasable commit boundaries.
- **Skipping the operator-witnessed browser verification gate.** BINDING per Phase 7 binding convention + multiple browser-only HTMX failure surface lessons (Phase 5 R1 M1 + M2; Phase 6 mid-verification I3; etc.). TestClient cannot detect.
- **"Illustrative" / TODO placeholders in tests.** Per Phase 7 plan-authoring lesson — every test specifies EXACT values; if you find a placeholder, treat as a plan bug + surface in return report.
- **Cross-cutting tests that span Phase 8/9 boundaries.** Sub-C tests stop at the web layer + integration; do NOT test Phase 8 Daily_Management or Phase 9 Reconciliation paths.
- **Regex-replace status→state across web files.** Per §2.1 + Phase 7 brainstorm lesson — predicate rewrites are NOT uniform substitution; each call-site classifies into one of 4 operation categories.
- **Skipping the broadened-grep refresh.** Plan §2.3 + this brief §3 specify running grep at dispatch time AND after every Sub-C task to catch any plan-time-missed call sites.
- **Renaming `swing trade exits` CLI subcommand without operator surface.** Default is KEEP; surface with rationale if rename proposed (operator workflow continuity matters).

---

## §10 Closing note

Sub-C is the FINAL Phase 7 sub-dispatch. After Sub-C ships green + operator-witnessed browser gate PASSES + integration merge to main, Phase 7 is COMPLETE: trade lifecycle state machine + Fills first-class semantics live in production. Operator's daily workflows resume against the new shape.

The plan + spec + prior briefs are detailed; chained-branch posture is binding; extended scope is operator-authorized. Take the time to get the browser verification gate right — multiple browser-only HTMX failure surfaces in the project's catalog mean TestClient assertions are necessary-but-not-sufficient.

When done, return the structured report with browser verification gate evidence + integration merge command + worktree cleanup steps + post-merge production DB migration expectations. The orchestrator triages the result + relays to operator who executes the merge.
