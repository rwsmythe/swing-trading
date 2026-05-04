# Phase 7 — Trade Lifecycle State Machine + Fills First-Class — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author the Phase 7 implementation plan from the locked spec; wrap with `copowers:writing-plans` for adversarial Codex review of the plan; iterate to `NO_NEW_CRITICAL_MAJOR`. Brainstorm is **shipped** — operator + adversarial-critic locked the spec at `c926f01`; the plan author's job is to convert spec → plan, not to re-design.

**Expected duration:** ~4-7 hours including 5-7 Codex rounds. Phase 7 has materially more design surface than Phase 6 (state machine + Fills + 18 new thesis fields + premortem + gate + status drop + ~37 carve-out files). Bug-surface density predicts ≥5 rounds; the spec's 3-round NO_NEW_CRITICAL_MAJOR posture means design-level issues are resolved, but plan-level issues (test discriminating-power; migration sequencing; per-task scope; predicate-rewrite per-call-site enumeration) will surface in plan-phase Codex review.

**Dispatch type:** `copowers:writing-plans` wrapper (writing-plans is single-pass; marker-file workflow is NOT needed — that's executing-plans-only).

---

## §0 Read first

Required (in order):

1. **[CLAUDE.md](../CLAUDE.md)** (root) — project conventions, gotchas. Re-skim every gotcha; especially the 2026-05-04 ones (`HX-Redirect target route must be verified to exist`, `Python ... or "" vs ... or None for SQL CHECK-constrained nullable columns`), plus the 5-VM rule, HTMX OOB-swap drift, HX-Request header propagation, weather-lookup-by-action_session, OHLCV fetch scope, `pipeline_runs` ORDER BY mask, and `Connection.backup()` vs shutil. All bear on Phase 7.
2. **[docs/orchestrator-context.md](orchestrator-context.md)** — durable orchestrator framing. Read §"Currently in-flight work" (Phase 7 row + Phase 6 paragraph), §"Recent decisions and framings", §"Binding conventions" (especially `worktree-isolated executing-plans + marker-file Codex-blocking workflow` 2026-05-02), §"Lessons captured" entries dated 2026-04-26 onward — pay particular attention to the 3 Phase 7 brainstorm lessons just captured (operation-vs-invariant; status→state predicate non-uniform rewrite; operationalize-in-code-not-spec) and the Phase 6 lessons (state-bearing entity transition-paths; cfg-X 3-edit cascade; closed_date derived; or-empty vs or-None; test-count-projections-bias-high; HX-Redirect target).
3. **[docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md](superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md)** — THIS IS THE SPEC. ~1069 lines, ~75kb. Read end-to-end; do NOT skim. Spec is the source-of-truth for every design decision. The plan converts spec → tasks; spec is NOT to be re-designed.
4. **[docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md](phase7-trade-lifecycle-state-machine-brainstorm-brief.md)** — the brainstorm brief that produced the spec. §2 (locked constraints) is binding; the spec implements §2's locks. The hard-conflict escape from §2 of the brainstorm brief carries forward to writing-plans (see §8 below).
5. **[docs/phase3e-todo.md](phase3e-todo.md)** — search for "Phase 7 — Trade lifecycle state machine + Fills first-class (BRAINSTORM SHIPPED 2026-05-04...". The entry summarizes locked design decisions, in-flight migration plan (VIR / DHC / CC), phase carve-out, and the open questions writing-plans must resolve.
6. **[future/swing_trading_journal_ai_ingestion_v1.2.md](../future/swing_trading_journal_ai_ingestion_v1.2.md)** — the source spec being adapted. §3.3 (premortem), §4.1 (`trade_origin` enum — note we use 4-value variant not 7-value), §5 (state machine + §5.1 Required Fields), §7.5 (Trade_Log fields — 18 KEPT + 12 DROPPED in our spec; verify the spec's per-field rationale matches v1.2 source), §7.6 (Fills), §10.1 (Pre-Trade Gate), §10.2 (Pre-Trade Lock).
7. **Empirical audit (do this BEFORE drafting plan tasks):**
   - **`grep -rn "trades.status\|t\.status\|status='open'\|status='closed'\|status = 'open'\|status = 'closed'" swing/ tests/`** — enumerate EVERY call-site of the `trades.status` column. Per the Phase 7 brainstorm spec §5.2 + lesson "Status→state predicate rewrite is not uniform substitution", classify EACH occurrence into one of 4 operation-specific predicate categories: (a) active-trade filter; (b) closed-but-not-reviewed predicate; (c) closed-or-reviewed aggregator; (d) write-path predicate. The spec said "12 production files + 43 test files identified; full enumeration deferred to plan." Plan must do the enumeration.
   - **`grep -rn "exits\b\|repos\.exits\|EXIT_REASON\|ExitReason" swing/ tests/`** — enumerate every reader/writer of the existing `exits` table. Spec § migration plan replaces `exits` with `fills`; every reader migrates.
   - **`grep -rn "record_entry\|insert_trade_with_event\|trade_events\.\|EntryRationale" swing/ tests/`** — entry-path call-sites. Plan must wire the new `MissingPreTradeFieldsException` gate at every entry surface (CLI / web / hyp-recs Take-this-trade).
   - **`ls swing/data/migrations/`** — confirm next migration is `0014_*.sql` (last is `0013_phase6_post_trade_review.sql`).
   - **Read [swing/data/models.py:61-104](../swing/data/models.py#L61-L104)** (`Trade` dataclass — has Phase 6's 10 review fields already; Phase 7 adds 18 thesis + 4 premortem + state + pre_trade_locked_at + 3 aggregate cols + trade_origin = ~28 new fields).
   - **Read [swing/data/repos/trades.py](../swing/data/repos/trades.py)** end-to-end — every public function gets a state-aware update.
   - **Read [swing/trades/entry.py](../swing/trades/entry.py)**, **[swing/trades/exit.py](../swing/trades/exit.py)**, **[swing/trades/stop_adjust.py](../swing/trades/stop_adjust.py)**, **[swing/trades/review.py](../swing/trades/review.py)** — every service module touches state transitions.
   - **Read [swing/web/routes/trades.py](../swing/web/routes/trades.py)** end-to-end — entry/exit/stop-adjust + Phase 6 review routes; Phase 7 expands the entry form with the new pre-trade fields and adds the gate failure rendering.
   - **Read [swing/cli.py](../swing/cli.py)** `trade_group` commands — Phase 7 CLI changes mirror web changes.
   - **Read [swing/journal/stats.py](../swing/journal/stats.py), [swing/journal/flags.py](../swing/journal/flags.py), [swing/journal/analyze.py](../swing/journal/analyze.py), [swing/journal/tos_import.py](../swing/journal/tos_import.py)** — these 4 files have status='open|closed' predicates that need rewriting per the 4-category classification (carve-out per spec).
   - **Verify production data state for in-flight migration:** `python -c "import sqlite3, os; c=sqlite3.connect(os.path.expanduser('~/swing-data/swing.db')); print(c.execute('SELECT id, ticker, status, entry_date FROM trades').fetchall()); print(c.execute('SELECT * FROM exits').fetchall())"`. Confirm 3 trades (VIR/DHC/CC) + 1 exit (VIR's). Spec migration plan assumes this state.

Reference (read-as-needed, not required upfront):

- **[docs/phase6-post-trade-review-writing-plans-brief.md](phase6-post-trade-review-writing-plans-brief.md)** — the most-recent writing-plans brief precedent. Mirror its structure + binding-conventions section.
- **[docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md](superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md)** — Phase 6 plan; reference for plan structure/depth/per-task pattern.
- **[docs/phase6-post-trade-review-executing-plans-brief.md](phase6-post-trade-review-executing-plans-brief.md)** — for the executing-plans-side patterns the plan must accommodate (worktree isolation; marker-file Codex-blocking; per-task discriminating-test discipline).

---

## §0.5 Skill posture

**Invoke:** `copowers:writing-plans` (wraps `superpowers:writing-plans` + adversarial Codex review on the plan). Iterate Codex rounds to `NO_NEW_CRITICAL_MAJOR`.

**Do NOT invoke:** `copowers:brainstorming` (brainstorm shipped; spec locked). Do NOT invoke `superpowers:brainstorming` either. Do NOT invoke `copowers:executing-plans` / `superpowers:subagent-driven-development` / TDD / `using-git-worktrees` — those are downstream of this dispatch.

**Worktree isolation:** NOT required for writing-plans (no code commits — only the plan document). The plan you author MUST specify worktree isolation for the executing-plans dispatches (Phase 7 hits all triggers per binding-convention: ~37 files; >5 task commits per sub-dispatch expected; base-layout-VM additions; new HTMX surfaces).

**Expectations from the wrapper:**

- The wrapper invokes `superpowers:writing-plans`, which produces an implementation plan from the spec.
- The wrapper then invokes `copowers:adversarial-critic` on the plan; you fix findings; iterate.
- **5-7 Codex rounds expected.** Phase 6's plan needed 5 rounds; Phase 7's larger surface predicts more. Don't be alarmed if you hit R6 or R7 — the spec just shipped at 3 design-rounds (R1 Critical + R2 Major + R3 Minor); plan-level issues are a separate axis (test discriminating-power; per-task TDD red-phase; migration step ordering; predicate-rewrite per-call-site coverage).

---

## §1 Strategic context (compressed)

**Why Phase 7 now.** Phase 6 (post-trade review surface) shipped 2026-05-04 at `51c79ed`. Sequencing alternative (A) per `docs/phase3e-todo.md` Modification Rationale: "ship Phase 6, re-evaluate before committing to Phase 7's larger schema disruption." Operator's re-evaluation lifted the gate; Phase 7 brainstorm shipped 2026-05-04 at `c926f01`. This dispatch is the next link in the chain.

**What Phase 7 IS.** Per spec §1: trade-lifecycle state machine (5-state: `entered → managing → partial_exited → closed → reviewed`) replacing the binary `status open|closed`; Fills as canonical execution log replacing `exits`; `pre_trade_locked_at` immutability discipline; 18 new pre-trade thesis fields; 3-named premortem fields with optional 4th; 4-value pipeline-aware `trade_origin` enum; non-bypassable `MissingPreTradeFieldsException` pre-trade gate; aggregate denormalization on `trades` (`current_size`/`current_avg_cost`/`last_fill_at`).

**What Phase 7 is NOT** (deferred to Phase 8 / Phase 9):

- Daily_Management snapshot/event_log → Phase 8.
- MFE/MAE precision computation → Phase 8.
- In-Trade Review workflow → Phase 8.
- Risk_Policy DB entity → Phase 9.
- Reconciliation_Run / Reconciliation_Discrepancy → Phase 9 (subsumes 2026-04-30 TOS reconciliation depth bundle).
- Drawdown circuit breaker activation (schema accommodates; activation Phase 9).
- Multi-entry-fill operator workflow (spec §4.3.1 authoritative selector pre-locks the trade-level reader contract; actual multi-entry-fill workflow Phase 9).
- Edit-after-lock UI (schema fully supports via `trade_events.event_type='pre_trade_edit'`; UI ships V2).
- HTMX progressive disclosure for conditional fields (UX polish; V2).

---

## §2 Locked from spec — do NOT relitigate in plan

The spec at `c926f01` is the binding source-of-truth. Key decisions (NOT exhaustive — read the spec):

1. **5-state minimal:** `entered → managing → partial_exited → closed → reviewed`. NO `planned/triggered/canceled` (watchlist + watchlist_archive serves "plan and abandon").
2. **Unidirectional graph:** no `partial_exited → managing` (no pyramiding). Same-day stop-out = `entered → managing → closed` atomic double-transition.
3. **`status` DROPPED entirely** — Trade dataclass no longer carries the field; every call-site must use the new state column with the appropriate per-purpose predicate (4 categories).
4. **Fills replaces exits:** drop `exits` table after migration. 4-action enum `(entry, trim, exit, stop)` — drops `cover` (long-only) and `add` (no pyramiding). 1:1 backfill with `ORDER BY exit_date ASC, id ASC`. Preservation invariant test gate with 4 explicit fixtures (singleton/multi-date/same-date/notes-merged).
5. **Aggregate denormalization on `trades`:** `current_size REAL NOT NULL`, `current_avg_cost REAL`, `last_fill_at TEXT` — recomputed by fills-write service after every insert. Single-write-path consistency invariant. (REAL on `current_size` future-proofs fractional shares without operational cost today.)
6. **`pre_trade_locked_at`:** set atomically at first `action='entry'` fill. Locked field set defined in spec; edit-after-lock via `trade_events.event_type='pre_trade_edit'`. V1 ships READ-ONLY display + audit visible; edit UI deferred V2.
7. **Premortem schema:** 3 named NULLABLE TEXT columns (`premortem_technical`, `premortem_market_sector`, `premortem_execution`) + 1 optional NULLABLE (`premortem_additional`). Min-1-per-category enforced at app layer.
8. **Thesis fields:** 18 KEPT + 12 DROPPED with per-field rationale in spec. All schema-NULLABLE. App-layer enforces non-empty for new entries; legacy NULL persists.
9. **Pre-trade gate:** existing checks preserved (HardCap / SoftWarn / Duplicate / stop<entry / risk-pct) + new `MissingPreTradeFieldsException` (NOT force-bypassable). Single source of truth in `record_entry()`.
10. **`trade_origin` derivation:** 5-bucket × 4-entry-path → 4-value enum mapping. `EntryPath` enum on `EntryRequest`. Frozen-at-entry per `hypothesis_label` precedent.
11. **Operation-contextual validation** (spec §3.5.1): `entry_create` enforces full required set; `transition_managing/partial_exited/closed` triggers suffice; `transition_reviewed` enforces Phase 6 review-completion fields only; legacy rows exempt by NULLABLE schema. **Plan tasks must encode operations, not states.**
12. **Migration runner backup discipline** (spec §12.1): SQLite-native ONLY (`Connection.backup()` / `VACUUM INTO`); `shutil.copy2` explicitly REJECTED. 4 binding integrity checks (PRAGMA integrity_check; expected-table set; row-count parity for migrated tables; size advisory ≥80%). Plan task wires the runner-discipline section.
13. **Multi-entry-fill authoritative selector** (spec §4.3.1): `ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1` deterministic — even though V1 service-layer constraint is "single entry fill," the trade-level reader contract is defined now to pre-empt Phase 9 ambiguity.
14. **In-flight migration plan** (verify production data state at empirical-audit time):
    - **VIR (closed+reviewed):** `state='reviewed'`, `pre_trade_locked_at = entry_date+T16:00:00`, `trade_origin='manual_off_pipeline'` (pre-engine), 1 entry-fill + 1 exit-fill backfilled.
    - **DHC (open):** `state='managing'`, `pre_trade_locked_at='2026-04-27T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'` **FIRM** (operator confirmed: hyp-rec Take-this-trade-equivalent on row labeled "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"), 1 entry-fill, current_size=39.
    - **CC (open):** `state='managing'`, `pre_trade_locked_at='2026-04-30T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'` **FIRM** (Take-this-trade on hyp-recs panel; phase3e-todo entry confirms via stop-form-bug observation), 1 entry-fill, current_size=5.

**Hard-conflict escape:** if a locked decision in the spec genuinely BLOCKS plan authoring (not merely creates tension — actually blocks), pause the writing-plans dispatch, send an interim outbrief describing the conflict, and standby for an orchestrator path-forward brief. This is the only relitigation channel; surfacing the conflict in the final return report is too late. (Same pattern as the brainstorm brief §2.)

---

## §3 Open questions — writing-plans MUST resolve in plan

These were intentionally deferred from spec to plan (per the brainstorm return report):

1. **Vocabulary lists.** Spec sketched but did not lock: `catalyst` 9 values; `emotional_state_pre_trade` 8 values; `event_type` 7 values. Plan must:
   - Quote the v1.2 source values (§4.6 catalyst, §7.5 emotional_state, §7.5 event_type).
   - Propose final lists for plan-review.
   - Add an explicit operator-confirm checkpoint in the plan's review section: plan-level Codex review proceeds; operator approval of vocabulary is a separate gate before executing-plans dispatch.
2. **`status`→state predicate rewrite enumeration.** Spec said "12 production files + 43 test files identified; full enumeration deferred to plan." Plan must:
   - Run the grep enumeration in §0 empirical audit.
   - Classify EVERY occurrence into one of the 4 operation-specific predicate categories (active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths).
   - Specify per-file the rewrite (which predicate goes where).
   - Bundle the test-file rewrites into a single per-sub-dispatch task to minimize cross-cutting churn.
3. **Migration sequencing — single 0014 vs multi-step 0014-001x.** Spec leaves it open; plan picks. Phase 6's 0013 was single (operator + reviewer comfortable). Phase 7 is bigger; multi-step (0014 = state column add + backfill from status; 0015 = Fills create + backfill from entries+exits; 0016 = drop status + drop exits) gives reviewability at the cost of atomicity. Plan justifies the choice; reviewer agrees or pushes back.
4. **Sub-dispatch decomposition.** Spec estimated 2-3 executing-plans sub-dispatches. Plan organizes tasks into clean sub-dispatch boundaries:
   - **Sub-A (schema + repos + state-machine):** Migration(s); models.py + db.py; repos/trades.py + repos/fills.py; services/state.py + services/origin.py + services/derived_metrics.py.
   - **Sub-B (services + CLI):** entry.py + exit.py + stop_adjust.py + review.py service refactors; cli.py expansion.
   - **Sub-C (web):** routes/trades.py + view_models/trades.py + view_models/open_positions_row.py + 3 templates.
   - Plan tasks within each sub-dispatch are INDEPENDENT of other sub-dispatches' in-flight state (Sub-B can ship without Sub-C if needed). Cross-cutting test rewrites (43 test files) bundle inside the sub-dispatch that owns the predicate.
5. **Test count band.** Plan estimates +150-250 fast tests. Per Phase 6 lesson "test-count-projections-bias-high": don't tighten executing-plans dispatch acceptance criteria around an optimistic projection. Acceptable surplus IF discriminating-test discipline justifies. Plan explicitly sets the band wide.
6. **Test fixture refactor scope.** Existing trade-fixture builders (`make_trade`, `seed_trade`, etc.) need state-aware additions. Plan enumerates affected fixture files; each sub-dispatch uses the updated fixtures. Bundle fixture updates into Sub-A task 0 to gate downstream sub-dispatch task fixtures on the updated builder.

---

## §4 Plan structure expectations

The plan you author MUST:

### Per-task discipline

- **TDD discipline:** every task has explicit RED test (failing on baseline; explain WHY it fails) → minimal implementation → GREEN → commit.
- **Discriminating-test gate:** for every test, the plan task body must answer "would this test fail if the implementation never actually called the new code?" If the answer is "yes, even without the fix, the test passes" — the test is vacuous; redesign it. Per the chart-pattern flag-v1 Phase 4 lesson "compounding-confound test fixtures can pass despite a vacuous primary discriminator" — applies HERE.
- **Per-task expected test count** stated in the task header (e.g., `Expected new tests: 4 (3 RED → GREEN; 1 discriminator)`). Total at end of plan.
- **Conventional commit message** specified per-task (`feat(area): Task X.Y — short description`).

### Sub-dispatch organization

Plan tasks organized by sub-dispatch (Sub-A / Sub-B / Sub-C per §3 above). Each sub-dispatch:

- Has its own task numbering (e.g., A.1, A.2, ..., B.1, B.2, ..., C.1, ...).
- Specifies the worktree branch name (e.g., `phase7-sub-a-schema`, `phase7-sub-b-services`, `phase7-sub-c-web`).
- Has its own `BASELINE_SHA` (Sub-A from current main; Sub-B from Sub-A merge; Sub-C from Sub-B merge — OR Sub-B + Sub-C parallelizable from Sub-A merge if file-disjoint).
- Specifies the marker-file Codex-blocking workflow for executing-plans dispatch (per binding convention 2026-05-02): orchestrator (1) creates worktree; (2) `touch .copowers-subagent-active`; (3) invokes `superpowers:subagent-driven-development` directly; (4) `rm .copowers-subagent-active`; (5) invokes `copowers:adversarial-critic`; (6) operator-witnessed verification gate; (7) merges to main.

### Carve-out enumeration

Plan §"Phase 7 carve-out" lists EVERY file added or modified, justified per file. Spec sketched ~37 files in §15; plan refines this list per empirical audit. For each file:

- File path.
- New / Modified.
- Sub-dispatch (A / B / C).
- One-line justification.
- Test file(s) affected (if any).

### Migration runner discipline

Plan task for `swing/data/db.py` migration runner expansion (per spec §12.1):

- Add backup-before-migrate hook (SQLite-native; `Connection.backup()` to a timestamped path under the DB dir).
- Add 4 integrity-check assertions (PRAGMA integrity_check on backup; expected-table set against backup; row-count parity for migrated tables (`trades`, `exits`, `trade_events`); size advisory ≥80%).
- Test: run migration → verify backup exists + passes integrity checks; corrupt backup → verify pre-migration abort.

### In-flight migration backfill

Plan task for migration 0014 (or 0014/0015/0016):

- Backfill VIR/DHC/CC with the locked values from §2 #14.
- Verify-via-pytest: post-migration query reproduces the spec's expected values exactly (binding test).

### Discriminating-test fixtures for invariants

- 4-fixture preservation invariant test gate (spec §4.4.1): singleton, multi-date, same-date multi-exit, notes-merged. Each fixture's plan-task body must specify the EXACT expected backfilled fills row contents.
- State-machine all-transition-paths enumeration (per Phase 6 lesson): every allowed transition + every rejected transition has a test. With 5 states, allowed graph has 6 edges (entered→managing; managing→partial_exited; managing→closed; partial_exited→closed; closed→reviewed; entered→managing→closed atomic) + 25 rejected pairs (5×5 minus 6 allowed minus 5 self-loops). Plan parametrizes if practical.
- Pre-trade-gate per-component-blocks test surface: each gate component (`MissingPreTradeFieldsException` per missing field; HardCap; SoftWarn; Duplicate; stop<entry; risk-pct) has a positive AND negative test.

### Backwards-compat verification

Plan §"Backwards-compat verification" specifies:

- Every existing query that uses `trades.status` is identified in the plan's per-call-site enumeration.
- Every test fixture that sets `status='open'|'closed'` is identified.
- Migration-runner test: post-migration, every existing test row's state column has a valid value (state IN (5 enum values)) AND the appropriate state for its data shape.

---

## §5 Adversarial review (handled by copowers:writing-plans wrapper)

The `copowers:writing-plans` wrapper invokes Codex MCP review on the plan. The wrapper iterates rounds until `NO_NEW_CRITICAL_MAJOR`. Pass these specific watch items via the wrapper's standard mechanism:

- **Operation-contextual validation correctness.** Plan tasks must encode operations (not states); legacy rows exempt by NULLABLE schema. Reviewer flags any plan task that asserts "all rows in state X must have all required fields" — that's a data-invariant claim; correct framing is operation-enforcement.
- **`status`→state predicate rewrite uniformity violation.** Per the Phase 7 brainstorm lesson: rewrites are NOT uniform substitutions. Reviewer flags any plan task that rewrites `status='open'` → `state='managing'` without verifying the call-site's semantic purpose. Each call-site classifies into one of 4 categories.
- **Migration runner discipline coded, not stated.** Reviewer flags any plan task that says "backup before migrate" without specifying the runner code path that creates the backup. SQLite-native methods ONLY; shutil.copy2 explicitly rejected.
- **4-fixture preservation invariant complete.** Reviewer verifies all 4 explicit fixtures (singleton/multi-date/same-date/notes-merged) appear in the plan with EXACT expected backfilled fills row contents.
- **State-machine all-transition-paths enumeration.** Per Phase 6 lesson: every transition pair (allowed + rejected) appears in the plan's transition matrix. Reviewer flags missing pairs.
- **Discriminating-test discipline.** For every test, would the test under post-fix code produce a different outcome than under pre-fix code? Reviewer flags vacuous-test risk.
- **HX-Redirect target validation.** Per fresh CLAUDE.md gotcha (2026-05-04): any new HTMX POST emitting HX-Redirect must have a registered target route + a test that verifies target resolves (`assert any(r.path == target for r in app.routes)` or follow with second TestClient call).
- **`... or None` for nullable CHECK columns** (CLAUDE.md gotcha 2026-05-04). Plan tasks using `or ""` for nullable+CHECK fields are bugs. Reviewer flags every such occurrence.
- **base-layout shared VM rule** (CLAUDE.md gotcha). Phase 7 likely adds new fields the base layout dereferences (state badge, gate-error banner). Plan enumerates every base-layout VM that gains the field with safe default.
- **OOB-swap partial drift** (CLAUDE.md gotcha). New partials that share markup with existing partials must use shared `{% include %}`.
- **HTMX `<tr>`-leading makeFragment pathology** (CLAUDE.md gotcha). Any new HTMX endpoint returning content with leading `<tr>` is a bug; pure-OOB response architecture or `<div>`/`<section>` root.
- **HX-Request header propagation** (CLAUDE.md gotcha). Embedded forms inside HTMX-rendered fragments need `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode passing.
- **Aggregate denormalization recompute correctness.** Plan specifies the recompute formula for `current_size` / `current_avg_cost` / `last_fill_at` after EVERY fill insert (entry / trim / exit / stop). Reviewer verifies formula handles all 4 actions correctly.
- **Multi-entry-fill authoritative selector test.** Plan has a discriminating test for spec §4.3.1: trade with 2+ entry fills resolves to the one with min `(fill_datetime, fill_id)`. Reviewer flags absence.
- **Phase carve-out enumeration completeness.** Every file in carve-out has one-line justification. No missing file. No unjustified file.
- **Sub-dispatch boundary cleanliness.** Cross-cutting tasks (43 test files) bundle inside the owning sub-dispatch. No task spans sub-dispatches.
- **Test count discipline.** Plan estimates wide band (+150-250). Don't tighten acceptance criteria to optimistic estimate.
- **Vocabulary checkpoint mechanism.** Plan has explicit operator-confirm gate for catalyst / emotional_state / event_type vocabulary BEFORE executing-plans dispatch. Reviewer verifies presence.
- **Phase 6 invariants survive.** Phase 6 added 10 nullable trade-row fields + Review_Log entity; Phase 7 must NOT regress (e.g., review-precondition rewrite must use `state='closed'` only — not `state IN ('closed','reviewed')` which would let reviewed trades through review again).
- **Phase 8 / Phase 9 readiness.** Schema must accommodate Daily_Management / Risk_Policy / Reconciliation_Log additions WITHOUT requiring further state-machine changes. Reviewer flags painted-into-corner risks.
- **No-main-commits-during-in-flight discipline.** Plan specifies that during executing-plans dispatch worktrees, no main-side commits land except verified-non-overlapping pure-docs edits. Documented in plan's pre-flight section.

---

## §6 Done criteria

The writing-plans dispatch is done when ALL of the following hold:

- [ ] Plan exists at `docs/superpowers/plans/YYYY-MM-DD-phase7-trade-lifecycle-state-machine-plan.md` (substitute today's date).
- [ ] Plan committed to `main` via conventional commit `docs(plans): phase 7 trade lifecycle state machine plan`.
- [ ] Plan respects all locked spec decisions in §2.
- [ ] Plan resolves all open questions in §3 (or escalates via the §2 hard-conflict escape).
- [ ] Plan organizes tasks into 2-3 sub-dispatch groups with clean boundaries.
- [ ] Plan enumerates the carve-out file list (one-line per file).
- [ ] Plan includes the per-call-site `status`→state predicate rewrite mapping (4 operation categories).
- [ ] Plan includes the 4-fixture preservation invariant test gate (singleton/multi-date/same-date/notes-merged) with EXACT expected backfilled fills row contents.
- [ ] Plan includes the state-machine all-transition-paths matrix (allowed + rejected).
- [ ] Plan includes the migration runner discipline section (SQLite-native backup; 4 integrity checks).
- [ ] Plan includes the in-flight migration backfill specification (VIR/DHC/CC) with verify-via-pytest tests.
- [ ] Plan includes the vocabulary operator-confirm checkpoint mechanism.
- [ ] Plan total expected new fast tests stated (range OK; per Phase 6 lesson don't pin to optimistic).
- [ ] Plan specifies worktree isolation + marker-file Codex-blocking workflow per sub-dispatch.
- [ ] Adversarial Codex review reached `NO_NEW_CRITICAL_MAJOR` verdict.
- [ ] Operator approved the plan via the writing-plans skill's review gate.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
PLAN: docs/superpowers/plans/<filename>.md
COMMITS: <initial> → <final>
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

KEY PLAN DECISIONS (resolutions to §3 open questions):
- Vocabulary lists: <catalyst N values + emotional_state N + event_type N; final-confirm-by-operator checkpoint mechanism>
- status→state predicate rewrite: <4-category enumeration; total file count covered>
- Migration sequencing: <single 0014 / multi-step 0014-001x + rationale>
- Sub-dispatch decomposition: <Sub-A scope; Sub-B scope; Sub-C scope; ordering serial vs parallelizable>
- Test count estimate: <wide band + rationale>
- Test fixture refactor scope: <which fixture files updated when>

CARVE-OUT (one-line per file): <see plan §X>

PER-CALL-SITE PREDICATE REWRITE (one-line per file): <see plan §Y>

ADVERSARIAL FINDINGS (each with disposition):
- R1: <count critical / major / minor>
  - <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>
- R2: ...

LESSONS WORTH CAPTURING (process insights from plan-authoring):
- <bullet list — what was surprising, what design pattern emerged, etc.>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any blocker or unresolved framing issue not covered by §2 hard-conflict escape>
- Vocabulary lists awaiting operator confirmation (specifying which decision points they unblock)

NEXT-STEP HANDOFF NOTES:
- Sub-A executing-plans baseline SHA: <main HEAD at plan-commit time>
- Sub-B + Sub-C ordering: <serial vs parallel + rationale>
- Operator pre-conditions before Sub-A dispatch: <vocabulary confirmation; backup baseline DB; etc.>
```

---

## §8 If you get stuck

- **If a plan task requires re-designing the spec,** invoke the §2 hard-conflict escape: pause, send an interim outbrief describing the conflict, standby for orchestrator path-forward. Do NOT relitigate the spec in the plan.
- **If a §3 open question can't be resolved with available evidence** (e.g., vocabulary list values can't be sourced from v1.2 §4.6 unambiguously), capture the question in the plan with explicit "DEFERRED — operator decision required" status + the decision-point. Don't force a decision the operator hasn't made.
- **If Codex review surfaces a finding that contradicts a locked spec decision,** apply receiving-code-review discipline. Verify the finding against the spec FIRST. If the finding is correct AND the spec is wrong, escalate via §2 hard-conflict escape. If the finding is wrong, document why it's rejected with rationale.
- **If pre-existing code surprises you** (e.g., the empirical audit reveals 60 status occurrences instead of the spec's ~55), trust what you observe. Update plan task scope to match reality.
- **If the empirical audit reveals an in-flight migration corner case** (e.g., VIR's exit row has malformed data; production DB has a stale state from a partial Phase 6 SPY-cleanup run), surface immediately to operator for backfill data verification BEFORE locking the migration plan.
- **If a Codex round produces 0/0/0 advisory only, but you suspect issue,** trust the empirical evidence. NO_NEW_CRITICAL_MAJOR is the gate; you may stop after a clean round even if you wonder whether you missed something. Subsequent dispatch (executing-plans Codex on the actual diff) is a second safety net.

---

## §9 Anti-patterns specific to this dispatch

These have caused real problems in past sessions; resist:

- **Drifting into spec re-design.** Plan converts spec → tasks. If the plan is changing what gets built (not how), you've crossed the line. STOP; escalate via §2.
- **Re-litigating locked decisions.** §2 + spec + brainstorm-brief §2 burned context settling these. Don't reopen.
- **Padding the plan.** A focused plan beats a comprehensive one. Each task earns its space. Past plans (Phase 5: 1730 lines; Phase 6: 3429 lines) demonstrate the right ballpark for substantial scope; don't blow past 4000 lines without good cause.
- **Vague TBD placeholders.** If a question can't be resolved, mark explicitly DEFERRED with rationale + decision-point.
- **Designing for hypothetical future requirements.** Phase 7 doesn't implement Phase 8 / 9. Schema accommodates them; plan doesn't.
- **Inflating test count without discriminating-test value.** Per the lesson "test-count-projections-bias-high" — the surplus over plan estimate is acceptable IF discriminating-test value justifies. Each test must answer "would this test fail if the implementation never actually called the new code?"
- **Cross-cutting tasks that span sub-dispatches.** If a task touches files in Sub-A AND Sub-B scope, redesign the task or the boundary. Sub-dispatch boundary cleanliness pre-empts merge complexity at executing-plans time.
- **Test fixtures without per-call-site classification.** The 43 test files for `status`→state need predicate-rewrite-mapping in the plan, NOT a handwave "plan covers test rewrites." Bundle in Sub-A task 0 fixture refactor.
- **Plan-time assertions about column-vs-derived semantics.** Per Phase 6 lesson "closed_date is derived not stored" — verify empirically (read the column or the function). Spec at `c926f01` does this for all the columns; plan tasks must continue the discipline for any new derived value.
- **Skipping the migration runner backup.** Spec §12.1 is binding. Plan task wires the runner-discipline section in code; not in spec text alone.
- **Assuming the production DB state matches expectations without checking.** Plan-empirical-audit step `python -c "..."` (§0 #7) is binding. If the DB doesn't match (e.g., a 4th trade exists; VIR's exit was deleted), plan adjusts before locking migration backfill.

---

## §10 Closing note

This is the largest plan-writing dispatch the project has commissioned. Phase 7's design surface (5-state machine + Fills + 18 thesis fields + premortem + gate + status drop + ~37 carve-out files) is materially bigger than Phase 5 or Phase 6.

The spec is locked at `c926f01` after 3 Codex rounds. The plan's job is to convert spec → concrete tasks that the executing-plans dispatches can pick up and ship. Adversarial review on the PLAN catches plan-level issues (test discriminating-power; per-call-site predicate-rewrite coverage; migration sequencing; sub-dispatch boundary cleanliness); design-level issues are already resolved in the spec.

Take the time to get it right. One slow careful plan + 5-7 Codex rounds beats a rushed plan that surfaces design issues at executing-plans time (where they're 10x more expensive to fix). The Phase 6 plan needed 5 Codex rounds; Phase 7 will likely need more. That's the cost of this scope; budget for it.

When done, return the structured report and stop. The orchestrator triages the result and decides when to commission the first executing-plans sub-dispatch.
