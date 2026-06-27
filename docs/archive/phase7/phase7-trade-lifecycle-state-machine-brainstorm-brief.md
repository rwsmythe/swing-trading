# Phase 7 — Trade Lifecycle State Machine + Fills First-Class: Brainstorm Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Run a brainstorm-only session for Phase 7 of the journal-v1.2 incorporation sub-bundle (per `docs/phase3e-todo.md:1002-1075`) via the project's `copowers:brainstorming` discipline. Produce a design spec, get adversarial Codex review on it, stop. Do NOT proceed to implementation, planning, or coding.
**Expected duration:** ~2-4 hours of operator-interactive brainstorming + 2-5 rounds of Codex review on the resulting spec. This is a materially larger design surface than Phase 5 or Phase 6 — expect substantive Q&A.
**Drives an implementation later:** A separate, future writing-plans dispatch will consume this spec; an executing-plans dispatch after that will ship the code. Don't pre-empt either.

---

## §0 Read first

In order:

1. **`docs/orchestrator-context.md`** — project framing, operator-drives discipline, copowers workflow, anti-patterns, the 16-phase track record, and the §"Lessons captured" tail (27 lessons; the last 10 are 2026-05-04 from Phase 6 cycle). Pay particular attention to the 2026-05-04 entries on "state-bearing-entity all-transition-paths enumeration" + "cfg-X 3-edit cascade" + "test-count-projections-bias-high" + "no-main-commits-during-in-flight-dispatch discipline."
2. **`docs/phase3e-todo.md`** — search for "Journal v1.2 incorporation" section + "Phase 7 — Trade lifecycle state machine + Fills first-class" subsection (line ~1002). Also read the §"Modification rationale" table (line ~1064) — it lists v1.2 design choices we're explicitly NOT adopting.
3. **`CLAUDE.md`** at repo root — project conventions, gotchas, the freshly-added 2026-05-04 ones (`HX-Redirect target must be verified to exist`, `Python ... or "" vs ... or None for SQL CHECK-constrained nullable columns`).
4. **`reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md`** — the source spec being adapted. Read §3.3 (premortem), §4.1 (`trade_origin` enum — note we're using a 4-value variant, NOT the 7-value discretionary one), §5 (state machine + Required Fields by State), §7.5 (Trade_Log fields), §7.6 (Fills), §10.1 (Pre-Trade Gate), §10.2 (Pre-Trade Lock). Skim §7.7 (Daily_Management — Phase 8), §7.8 (Risk_Policy — Phase 9), §7.9 (Reconciliation_Log — Phase 9), §10.3 (In-Trade Review — Phase 8), §10.5 (Reconciliation Workflow — Phase 9) to know what's NEXT and therefore NOT in scope here.
5. **Existing schema:**
   - `swing/data/migrations/0003_phase2_pipeline_trades.sql` — `trades` + `exits` + `trade_events` original schema.
   - `swing/data/migrations/0007_trade_hypothesis_label.sql` (precedent: nullable text frozen-at-entry).
   - `swing/data/migrations/0010_trade_chart_pattern.sql` (precedent: chart_pattern_* fields frozen-at-entry, with a pipeline-run-id link).
   - `swing/data/migrations/0012_sector_industry.sql` (precedent: sector/industry frozen-at-entry, default empty-string).
   - `swing/data/migrations/0013_phase6_post_trade_review.sql` (precedent: 10 nullable trade-row fields + new `review_log` entity, just shipped 2026-05-04).
   - **Next migration is 0014.**
6. **Existing service layer:**
   - `swing/data/models.py` — current `Trade` dataclass (note: post-Phase-6, has 10 review-surface fields already nullable on it; the field-population pattern is established).
   - `swing/data/repos/trades.py` — `insert_trade_with_event`, `list_open_trades`, etc.
   - `swing/data/repos/exits.py` — exits-table reader/writer.
   - `swing/trades/entry.py` — entry service with `EntryRationale` enum (closed taxonomy) + watchlist archival; `record_entry` calls into repos.
   - `swing/trades/exit.py` — exit service with `ExitReason` enum.
   - `swing/trades/stop_adjust.py` — stop-update service with `update_stop_with_event`.
   - `swing/trades/review.py` — Phase 6 review service (NEW; has `ReviewWindowSoftWarn` semantics + cadence completion).
7. **Existing UX surfaces:**
   - `swing/web/routes/trades.py` — entry / exit / stop-adjust web routes (HTMX + form-driven).
   - `swing/web/routes/reviews.py` — Phase 6 reviews routes (NEW; pattern for state-aware route handlers).
   - `swing/web/view_models/trades.py` — TradeVM + open-positions-card VM.
   - `swing/cli.py` — click-based CLI (`swing trade entry/exit/stop-adjust`, `swing trade review` is Phase 6 NEW).

---

## §0.5 Skill posture

**INVOKE:**

- `copowers:brainstorming` — this brief's primary skill. The wrapper handles operator-interactive design, spec-doc writing, internal completeness review (spec-document-reviewer), AND adversarial Codex review on the spec. Iterates rounds until `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE (V1 STOP after spec is reviewed):**

- `copowers:writing-plans` / `superpowers:writing-plans` — implementation planning is NOT part of this dispatch. Orchestrator triages the spec; operator decides whether to commission a plan-and-execute dispatch.
- `copowers:executing-plans` / `superpowers:executing-plans` / `superpowers:subagent-driven-development` — no implementation in this dispatch.
- `superpowers:test-driven-development` — no code in this dispatch.
- `superpowers:using-git-worktrees` — no code, so no worktree.

The brainstorming skill itself will engage the operator interactively. You (the implementer) drive the brainstorm conversation; the operator answers, redirects, and approves. Use the operator's own framing where it differs from yours.

---

## §1 Strategic context

This phase is **Phase 7 of the journal-v1.2 incorporation sub-bundle.** The full sub-bundle is decomposed (per `docs/phase3e-todo.md`) as:

- **Phase 6 — Post-trade review surface.** SHIPPED 2026-05-04 at `51c79ed`. Mistake_Tags + Process Grade + mistake_cost_R / lucky_violation_R + Review_Log entity. Provided the structured behavioral data surface that Phase 7 builds onto.
- **Phase 7 — Trade lifecycle state machine + Fills first-class.** ← THIS DISPATCH.
- **Phase 8 — Daily_Management + MFE/MAE precision.** GATED on Phase 7.
- **Phase 9 — Risk_Policy entity + reconciliation depth.** GATED on Phase 7. Subsumes the queued 2026-04-30 TOS reconciliation depth bundle.

The journal-v1.2 spec was authored agnostic of our platform. Several v1.2 design choices encode discretionary-trader assumptions that don't fit our framework-research-loop posture; the §"Modification rationale" table in `docs/phase3e-todo.md` is the binding adaptation framework. This brainstorm respects that table — see §2 below.

**Why now:** Phase 6 just shipped. Phase 6 evaluation gate (operator-paced) opens immediately upon shipping; operator has signalled to begin Phase 7 brainstorm. The orchestrator's recommended sequencing alternative (A) — "ship Phase 6, then re-evaluate" — has been resolved: re-evaluation favors proceeding to Phase 7 design exploration.

**Why bigger than Phase 5/6:** Phase 5 added 3 config fields. Phase 6 added 10 nullable trade-row fields + 1 new entity. Phase 7 introduces a state machine touching every trade-write path AND replaces the binary `status` column with an 8-state ENUM AND introduces Fills as the canonical execution log AND migrates existing entry/exits-table data into the new shape AND formalizes pre-trade lock semantics AND adds premortem + thesis fields AND adds a pre-trade gate. Estimated 4-6 implementation dispatches downstream of this brainstorm.

---

## §2 Locked constraints (operator + orchestrator decided; do NOT re-litigate in brainstorm)

The following decisions were made before this dispatch, in the orchestrator thread or in the binding source documents. The brainstorm must respect them. If the operator brings them up during brainstorm, acknowledge they're settled and refocus on the open design questions.

**Hard-conflict escape:** if a locked decision genuinely blocks Phase 7 implementation (not merely creates tension — actually blocks), pause the brainstorm, send an interim outbrief describing the conflict, and standby for an orchestrator path-forward brief. This is the only relitigation channel; surfacing the conflict in the final return report is too late.

### Sequencing locks

1. **Phase 7 scope is state machine + Fills + pre_trade_locked_at + premortem + thesis + pre-trade gate trim.** NOT Daily_Management (Phase 8). NOT Risk_Policy DB entity (Phase 9). NOT Reconciliation_Run / Reconciliation_Discrepancy (Phase 9). NOT MFE/MAE precision (Phase 8). NOT drawdown circuit breaker activation (Phase 9 — it stays opt-in disabled).
2. **Phase 8 + Phase 9 are GATED on Phase 7 shipping.** This brainstorm produces design that LANDS gracefully ahead of those phases — it must not paint into corners that block them, but it also must not implement them.

### v1.2 modification table — adopted in full (per `docs/phase3e-todo.md` Modification rationale)

3. **`trade_origin` is a 4-value pipeline-aware enum**, NOT v1.2's 7-value discretionary enum. The 4 values are:
   - `pipeline_aplus` — bucket==`aplus` for the candidate at entry time.
   - `pipeline_watch_hyp_recs` — bucket==`watch` AND entry came via the hyp-recs panel (Take-this-trade button).
   - `pipeline_watch_manual` — bucket==`watch` AND entry came via the manual web form (operator types the ticker).
   - `manual_off_pipeline` — ticker not in current `candidates` table (e.g., operator enters ticker absent from today's screen).
4. **DROP self-rated `pre_trade_quality_score` (0-10).** Pipeline already computes A+/watch/skip + criteria pass/fail — self-rating duplicates and conflicts. Keep `emotional_state_pre_trade`, `manual_entry_confidence`, manual override fields (these are NOT self-rated quality scores).
5. **DROP `Setup_Playbook` as DB entity.** Our setups are encoded in `swing/evaluation/` (TT criteria, VCP criteria, A+ identification). Trader doesn't manage setups as data. When setup-attribution is needed, reference `hypothesis_id` (already in DB).
6. **DROP pyramiding R-views.** Operator at $7,500 capital with ~5 concurrent positions doesn't pyramid. Indefinite drop.
7. **DROP `Screen_Definitions` versioning.** Mismatches our pipeline-driven ingestion (Finviz CSV → `_step_evaluate`).
8. **Drawdown circuit breaker stays opt-in disabled by default** (matches our caution + matches v1.2 default). The activation switch is a Phase 9 concern; Phase 7 should not implement enforcement, but the schema must accommodate it (so the `risk_policy` table — Phase 9 — can flip a flag without further state-machine changes).

### Project conventions

9. **Phase isolation default = read-only on `swing/data/` and `swing/trades/`.** Phase 7 explicitly carves out:
   - New schema migration(s) under `swing/data/migrations/`.
   - New / modified repos under `swing/data/repos/`.
   - Modifications to `swing/trades/entry.py`, `swing/trades/exit.py`, `swing/trades/stop_adjust.py`.
   - A new state-machine service module (path TBD by brainstorm; suggested `swing/trades/state.py` or `swing/trades/lifecycle.py`).
   - The brainstorm spec MUST enumerate every file added/modified in `swing/data/` + `swing/trades/`, with justification per file.
10. **DB is at `%USERPROFILE%/swing-data/swing.db` — outside Drive sync.** Hard invariant.
11. **TDD discipline on the eventual implementation.** Brainstorm doesn't write tests, but it MUST identify the testability story for each design decision (especially state-transition validation; see §3).
12. **No Claude co-author footer. No `--no-verify`. No amending. Conventional commits only.** Applies to the spec commit produced by this brainstorm.
13. **Test count baseline at HEAD = 1587 fast tests** (1 skipped — Phase 7 operator-only fixture test). Phase 7 implementation will likely add +150-300 tests; the brainstorm doesn't size, but flags any design decision that would inflate the test count without proportional discriminating-test value.

### In-flight production data (binding constraint on migration design)

14. **Three trades exist in the production DB at HEAD `e48586c`:**
    - **VIR** — closed (single full exit at -0.33R) + reviewed via Phase 6 surface 2026-05-04. `hypothesis_label = "inaugural trade test"`. realized_R_if_plan_followed ≈ 0; derived mistake_cost_R = 0.33.
    - **DHC** — open (entry 2026-04-27 @ $7.58 × 39 shares); `hypothesis_label = "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)"`.
    - **CC** — open (entry 2026-04-30 @ $26.97 × 5 shares); `hypothesis_label = "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"`.
    - **Migration must derive the new state column for each without operator data entry.** Brainstorm decides the derivation rules. (Sketch: VIR → `reviewed`; DHC + CC → `managing`. Pre-trade fields populate as NULL or empty for these — operator historical memory not retroactive.)
15. **The `pre_trade_locked_at` field on existing trades** must take a sensible default at migration. (Sketch: set equal to `entry_date` for already-entered trades; brainstorm confirms.)
16. **No data loss permitted on `exits` table content.** If `exits` is replaced by Fills, every existing exit row must round-trip into Fills via the migration. Backup-then-migrate per existing project pattern (`swing-pre-*` backups precedent).

### Out of scope (explicit)

17. **Production scoring/bucketing changes** — V2.1 §VII.F territory; out of Phase 7.
18. **New advisory rules** — out of scope (advisory state-machine work is the separate Tier-3 #6 backlog item).
19. **Schwab API / Finviz Elite API integrations** — separate 2026-05-04 backlog entries, brainstorm-needed but NOT this one.
20. **Daily snapshot / event log generation** — Phase 8.

---

## §3 Open design questions (the brainstorm's actual job)

These are the questions the brainstorm conversation should explore with the operator and resolve in the spec. NOT exhaustive — discover others as they emerge.

### State enum + transition graph

- **Adopt v1.2's 8-state enum verbatim, or refine?** v1.2 §5 has: `planned, triggered, entered, managing, partial_exited, closed, reviewed, canceled`. Discuss with operator whether `planned` and `triggered` are useful given operator's actual workflow (does operator track ideas as `planned` records, or does a record only exist once entry conditions are met?). Possible simplification: collapse `planned + triggered → ready`. Possible expansion: leave as-is for v1.2 fidelity. Operator decides.
- **Reversibility rules.** v1.2 allows `partial_exited → managing` (re-add scenario). Does operator's actual workflow ever re-add to a partial_exited position at $7,500 capital? Discuss; if no, brainstorm proposes simpler unidirectional graph.
- **Is `reviewed` terminal?** Phase 9 reconciliation may reopen reviewed trades on material discrepancy (v1.2 §10.5). Phase 7 doesn't implement that — but does the schema permit `reviewed → managing` transition for future use, OR enforce `reviewed` as terminal at the DB CHECK level?
- **DB-level vs app-level enforcement.** State transitions can be enforced via SQL CHECK + trigger, OR via a Python state-machine service that's the single write path. Tradeoffs: CHECK is bulletproof but adds migration complexity; service-level is more flexible but requires every write path to route through it. Discuss.
- **Per state, the required-field invariant** (v1.2 §5.1). Does this validation fire at WRITE time (pre-insert / pre-update) or at READ time (lazy validation)? Recommend write-time — discuss.

### `status open|closed` integration

- **Drop `trades.status` after migration**, OR keep as derived view? Keeping `status` requires triggers to keep it in sync; dropping requires every reader to update predicates.
- **Backwards-compat for `journal/stats` predicates** (`status='closed'` in many journal/dashboard queries). Migration must rewrite or alias. Enumerate every query.
- **Dashboard "Open Positions" card semantics** — currently shows `status='open'`. New surface = `state IN ('entered', 'managing', 'partial_exited')`? Or new "Active Trades" card with state breakdown? UX implications.

### Fills schema

- **Replace `exits` table OR coexist?**
  - Option A: Drop `exits`; all reads go through `fills`. Cleanest long-term; biggest migration scope.
  - Option B: Keep `exits` as a SQL view backed by Fills. Reader-compat preserved; double-storage-on-write avoided.
  - Option C: Keep both during transition window; deprecate `exits` in a later phase.
  - Discuss tradeoffs; operator preference matters here.
- **Field mapping.** v1.2 §7.6 Fills shape vs current `exits` shape:
  - `exits.shares` ↔ `fills.quantity`. Type harmonize (REAL on Fills since v1.2 says numeric — does that allow fractional shares? Operator currently trades whole shares only; discuss).
  - `exits.exit_date` ↔ `fills.fill_datetime` (date vs datetime — implications for sort + reconciliation; v1.2 wants datetime).
  - `exits.reason` ↔ `fills.reason` (free text both).
  - `exits.realized_pnl` + `exits.r_multiple` are DERIVED from fill data — discuss whether to keep on `exits`/Fills or compute on read.
  - `fills.action` enum: `entry, add, trim, exit, stop, cover` — `cover` is short-cover (we're long-only V1; discuss whether to include).
  - `fills.rule_based`, `fills.fees`, `fills.manual_entry_confidence`, `fills.reconciliation_status`, `fills.tos_match_id` — all new. Reconciliation fields are Phase 9 concern but schema must accommodate.
- **Existing `trades.entry_date / entry_price / initial_shares` columns.** After Fills is canonical, these become DERIVED from the first fill (action=entry). Drop from `trades`? Keep as denormalized cache? Operator preference for read efficiency vs schema hygiene.
- **Aggregate denormalization.** `current_size`, `current_avg_cost`, `last_fill_at` — computed from Fills on every read, or denormalized onto `trades` and updated on each fill insert? Discuss perf implications (operator workflow has at most ~5 concurrent open trades; reads are infrequent).
- **`fill_id` type.** v1.2 says `string` for fill_id. Our convention is INTEGER PRIMARY KEY everywhere. Adopt INT (operator-internal IDs) and reserve `tos_match_id` for external string IDs.

### `pre_trade_locked_at` semantics

- **Trigger.** v1.2 §10.2 says "first Fill with action=entry." Confirm.
- **Which fields lock?** v1.2 implies the entire pre-trade decision-field set (thesis, why_now, expected_scenario, invalidation, premortem, planned_entry, initial_stop, planned_position_size, planned_risk_dollars, event_risk_*, gap_risk_*, emotional_state_pre_trade, manual_entry_confidence, final_pre_trade_decision, market_regime, catalyst). Discuss the exact list.
- **Existing already-frozen fields** (`hypothesis_label`, `chart_pattern_*`, `sector`, `industry`) are pre-trade fields by precedent. Do they participate in the lock too, or remain field-level frozen as-is?
- **Edit-after-lock mechanism.** v1.2 says "Pre_Trade_Edit_Audit row." We have `trade_events` (audit log infrastructure already exists from Phase 3b). REUSE `trade_events` with a new `event_type='pre_trade_edit'` value, OR create a new `pre_trade_edit_audit` table?
- **Migration handling.** For VIR/DHC/CC at migration time: set `pre_trade_locked_at = entry_date`; pre-trade fields stay NULL (operator history not retroactive). What does the entry-form / dashboard show for these legacy-NULL trades?

### Premortem schema

v1.2 §3.3 requires minimum 3 failure reasons across 3 categories: technical, market_sector, execution.

- **Schema shape options:**
  - (a) Separate `premortem_reasons` table (1-to-many): `(premortem_id, trade_id, category, reason_text, sort_order)`. Min-3 enforced at app level on entry submit.
  - (b) JSON column on `trades`: `premortem_json TEXT NOT NULL CHECK (json_array_length(premortem_json) >= 3)`. Atomic with trade.
  - (c) 3 separate columns: `premortem_technical TEXT`, `premortem_market_sector TEXT`, `premortem_execution TEXT`. Simple, schema-clean, but loses the "minimum 3 across categories" composability if operator wants 2 technical + 1 execution.
- **Validation layer.** Min-3 enforcement at DB CHECK constraint vs app-layer (entry service / web form) — recommend app-layer with explicit error message; discuss.
- **Migration default for VIR/DHC/CC.** NULL or empty? If NOT NULL, write a "n/a — pre-Phase-7 trade" placeholder?

### Thesis + decision fields

v1.2 §7.5 Pre-Trade Decision Fields include: `thesis`, `why_now`, `expected_scenario`, `invalidation_condition`, `event_risk_present (bool)`, `event_handling`, `gap_risk_present (bool)`, `gap_risk_handling`, `emotional_state_pre_trade (list[enum])`, `final_pre_trade_decision (enum)`, `manual_entry_confidence (enum: high|normal|low)`. Plus: `catalyst (enum)`, `market_regime (enum at planning time)`.

- **DB shape.** Mostly nullable text columns + a few enums. Enumerate exact column-by-column schema. CHECK constraints for the enum-typed ones — and remember the recent CLAUDE.md gotcha: nullable text columns with CHECK enum constraints must use `... or None` not `... or ""` in form-input fallback paths.
- **`emotional_state_pre_trade` is a list[enum].** SQLite has no list type. Options: comma-separated text + CHECK validates each entry; JSON array; separate junction table. v1.2 doesn't dictate; discuss.
- **`market_regime` and `catalyst` enum.** v1.2 §4.2 + §4.6 list values. Adopt verbatim, or trim?
- **Overlap with existing `trades.notes` (free text).** Phase 6 added `lesson_learned` (review-time field, separate purpose). Phase 7 thesis fields are pre-trade. Discuss the field-purpose taxonomy so it stays clean.

### Pre-trade gate

v1.2 §10.1 Pre-Trade Gate components are listed. Phase 7 adopts the structural gate, but per `docs/phase3e-todo.md`:

- **DROP `pre_trade_quality_score` check** (locked, §2 above).
- **`portfolio_heat_check` and `consecutive_loss_pause_check`** are "mostly already served by hard_cap + soft_warn." Confirm where exactly in the codebase. The gate version may be a wrapper or a no-op if the existing checks fire upstream.
- **Skip checks redundant with pipeline.** Pipeline already validates many things at evaluation time — gate shouldn't re-check these.
- **Gate firing surface.** Does the gate fire at:
  - CLI `swing trade entry` submit?
  - Web POST `/trades/entry/form` submit?
  - hyp-recs Take-this-trade route?
  - All three? (Likely — but how is the gate logic factored to avoid drift across surfaces?)
- **Failure mode.** Gate fail → form error + reject? Gate soft-warn (like Phase 6 soft-warn at close)? Discuss.

### `trade_origin` derivation

The 4 values are locked (§2). The DERIVATION at entry time is open:

- `pipeline_aplus`: `candidate.bucket == 'aplus'` at entry time. Direct lookup.
- `pipeline_watch_hyp_recs`: bucket==`watch` AND entry came via Take-this-trade button on hyp-recs panel. Detect via route entry path + form-field carrier.
- `pipeline_watch_manual`: bucket==`watch` AND entry via manual web form.
- `manual_off_pipeline`: ticker NOT in today's `candidates` table (or candidates table absent for this run).
- **Edge cases.** What if a ticker was bucket=`aplus` yesterday but bucket=`watch` today? (Use today's bucket — reflect entry-time state.) What if pipeline hasn't run today? (Treat as `manual_off_pipeline`.) What if ticker is in candidates but bucket=`skip`? (Discuss — probably blocked from entry by gate.) What if ticker is in candidates but bucket=`error`? (Discuss.)
- **Persistence.** Frozen-at-entry per the `hypothesis_label` precedent. Single TEXT NOT NULL column with CHECK enum.
- **Migration for VIR/DHC/CC.** VIR predates the engine — `manual_off_pipeline`. DHC + CC entered via... need to look at entry path; brainstorm spec decides the assignment rule (maybe `pipeline_watch_hyp_recs` if recently in `daily_recommendations` table, else `manual_off_pipeline`).

### UX surfaces — new and modified

- **`planned` and `triggered` states UX.** If retained, do they require new web pages (planning UI, trigger watcher)? Or do they exist only as DB rows created implicitly when operator clicks "plan a trade" on a hyp-recs row? Operator-facing complexity vs internal-state-only is a real choice.
- **`canceled` state UX.** Cancel-a-planned-trade button. Where? Required cancellation reason free-text? CHECK enum?
- **Entry form additions.** Premortem (3 inputs minimum) + thesis + why_now + invalidation + emotional_state_pre_trade (multi-select) + manual_entry_confidence (radio). The form gets significantly larger. Consider tabbed / sectioned form. (Operator loathes form bloat — discuss UX heuristics.)
- **Web base-layout VM gotcha** (CLAUDE.md). Adding a new field that the base-layout dereferences requires every base-layout VM to gain the field with a safe default. Phase 7 likely adds at least 1 (e.g., portfolio-heat soft-warn banner). Enumerate.
- **HX-Redirect target route gotcha** (CLAUDE.md, freshly added 2026-05-04). Any HTMX POST handler emitting HX-Redirect must point at a registered route. Phase 7 introduces several new routes (state transitions, planned-trade lifecycle, fills CRUD). Pre-empt with explicit test pattern.
- **OOB-swap partial drift gotcha** (CLAUDE.md). Phase 7 likely touches multiple tables of trades by state. New partials that share markup with existing partials must use shared `{% include %}`, not hand-duplicated markup.

### Test strategy (the brainstorm doesn't write tests; it scopes the strategy)

- **State machine validity tests.** Every valid transition + every invalid transition (rejected). Per the orchestrator-context lesson 2026-05-04 (state-bearing-entity all-transition-paths enumeration): the spec MUST enumerate every transition pair; tests cover both directions explicitly.
- **Migration safety tests.** Every existing trade row migrates to a valid (state, required-fields) tuple. VIR/DHC/CC test fixtures.
- **Discriminating-test discipline** (CLAUDE.md feedback memory). For each test that asserts on a state-machine invariant, the test under post-fix code must produce a different outcome than under pre-fix code. The spec should call this out with examples.
- **Per-state required-field validation tests.** Every state's required-field set; missing-field tests reject; complete-field-set tests succeed.
- **Pre-trade gate tests.** Each component blocks separately; complete-gate-pass tests succeed at all 3 entry surfaces (CLI, web form, hyp-recs).
- **Existing test fixture updates.** All existing trade-fixture builders need state-aware additions — this is a meaningful refactor scope item; flag to writing-plans.

### Migration sequencing

- **Single migration 0014, OR multi-step 0014/0015/0016?** Tradeoffs: atomicity vs reviewability. Phase 6's `0013` was single — operator + reviewer comfortable with that pattern. Phase 7 is bigger — discuss.
- **Rollback.** SQLite + ALTER TABLE has limits. The migration likely rebuilds `trades` (CREATE new table → INSERT FROM old → DROP old → RENAME) per the project's existing pattern. Backup-before-migrate (`swing-pre-phase7-migration-*.db`) is binding.
- **Order.** State column add → backfill from status → drop status. Fills create → backfill from entries+exits → drop exits. Or interleave? Discuss.

### Phase carve-out enumeration

The brainstorm spec MUST list every file added or modified, with one-line justification per file. At minimum (sketch):

- `swing/data/migrations/0014_*.sql` (or multi-step 0014-001x).
- `swing/data/models.py` — Trade dataclass field additions; new Fill dataclass; possibly Premortem dataclass.
- `swing/data/repos/trades.py` — state-aware insert/update/list queries.
- `swing/data/repos/fills.py` — NEW.
- `swing/data/repos/exits.py` — modified or deleted.
- `swing/trades/state.py` (or `lifecycle.py`) — NEW state-machine service.
- `swing/trades/entry.py` — emit Fill on entry; set pre_trade_locked_at; gate validation.
- `swing/trades/exit.py` — emit Fill on exit; state transition.
- `swing/trades/stop_adjust.py` — state predicate (only fires in managing/partial_exited states).
- `swing/web/routes/trades.py` — new state-aware paths.
- `swing/web/view_models/trades.py` — state field on TradeVM; base-layout VM updates.
- `swing/web/templates/...` — state badges, planning UI, gate error display.
- `swing/cli.py` — new state-transition commands; entry form expansion.
- Tests across all of the above.

The spec lists each, justifies each, flags the carve-out scope explicitly to writing-plans.

---

## §4 Conventions for the brainstorm output

- **Spec doc location:** `docs/superpowers/specs/YYYY-MM-DD-phase7-trade-lifecycle-state-machine-design.md` (substitute today's date when brainstorm completes).
- **Spec follows project conventions** (see existing specs in `docs/superpowers/specs/` for shape — particularly `2026-04-26-chart-pattern-flag-v1-design.md` as a recent precedent for a multi-phase brainstorm).
- **Spec MUST include** §-headed sections covering: state enum + transition graph (with allowed-transition matrix); `status` integration / migration path; Fills schema + exits-table disposition + field mapping; pre_trade_locked_at semantics; premortem schema; thesis-field schema; pre-trade gate composition; trade_origin derivation rules; in-flight migration plan for VIR/DHC/CC; UX surface impact summary; phase carve-out file list (justified per file); test strategy scope.
- **Commit the spec doc when done.** Conventional-commit message: `docs(specs): phase 7 trade lifecycle state machine design`. Do NOT mark Phase 6 follow-ups, do NOT touch other docs.
- **No Claude co-author footer. No `--no-verify`. No amending.**

---

## §5 Adversarial review (handled by copowers wrapper)

The `copowers:brainstorming` wrapper automatically invokes Codex MCP review on the resulting spec. The wrapper iterates rounds until `NO_NEW_CRITICAL_MAJOR`. Pass these specific watch items to Codex via the wrapper's standard mechanism:

- **Locked-constraint violations.** Does the spec respect every constraint in §2? Especially: (a) the 4-value `trade_origin` enum (NOT 7-value); (b) DROP list (pre_trade_quality_score, Setup_Playbook, pyramiding, Screen_Definitions); (c) phase scope (no Daily_Management, Risk_Policy, Reconciliation_Run); (d) drawdown circuit breaker stays opt-in disabled.
- **In-flight trade migration safety.** Every existing trade (VIR closed+reviewed; DHC + CC open) migrates to a valid (state, required-fields) tuple WITHOUT data loss and WITHOUT requiring operator data entry. Backup precedes migration.
- **`exits` table data preservation.** If `exits` is dropped, every existing row round-trips into Fills via the migration. Verify with row-count assertion in test strategy.
- **State machine all-transition-paths enumeration.** Every transition pair (allowed + rejected) appears in the transition matrix in the spec. Per the 2026-05-04 lesson: state-bearing entities require explicit transition-path enumeration. Reviewer flags any missing pair.
- **Discriminating test scope.** For every test category proposed, would the test under post-fix code produce a different outcome than under pre-fix code? Reviewer flags vacuous-test risk.
- **Schema integrity.** Migration 0014+ is correctly sequenced; all new CHECK constraints validated; nullable text columns with enum CHECK use `... or None` (recent gotcha); all NOT NULL columns have migration defaults for legacy rows.
- **Phase carve-out enumeration completeness.** Every file in the carve-out list is justified. No missing file. No unjustified file (orchestrator pre-approves the carve-out, but the spec must enumerate so writing-plans doesn't stumble into surprise scope).
- **Backwards-compat / `status` rewrite completeness.** Every existing query that uses `trades.status` is identified in the spec. The grep+enumerate pattern is binding (per past phase precedents).
- **HX-Redirect target validation** (recent CLAUDE.md gotcha). Any new HTMX POST emitting HX-Redirect must specify a registered target route in the spec; spec calls out the test pattern.
- **OOB-swap partial drift** (CLAUDE.md gotcha). Any new partials that share markup with existing partials must use shared `{% include %}`.
- **`... or ""` vs `... or None` for nullable CHECK columns** (recent CLAUDE.md gotcha). Any new nullable text + CHECK enum field uses `... or None` in form fallback paths.
- **base-layout shared VM rule** (CLAUDE.md gotcha). Any new field the base layout dereferences must be added to ALL base-layout VMs with safe defaults — spec enumerates.
- **Test count discipline.** Spec doesn't size, but flags any design choice that inflates test count without proportional discriminating-test value (per 2026-05-04 lesson "test-count-projections-bias-high").
- **Phase 8/9 readiness.** Does the schema accommodate the future Daily_Management / Risk_Policy / Reconciliation_Log additions WITHOUT requiring further state-machine changes? Reviewer flags painted-into-corner risks.
- **Mistake_Tags / Process Grade compatibility.** Phase 6 added these to `trades`. Phase 7's state machine + Fills must NOT regress Phase 6's review surface. Reviewer verifies Phase 6 invariants survive.
- **No-main-commits-during-in-flight-dispatch discipline** (2026-05-04 lesson). Spec authoring is on `main`; OK because this is brainstorm, not implementation. Future writing-plans + executing-plans dispatches will use worktree isolation; spec should call out this expectation.

---

## §6 Done criteria

The brainstorm is done when ALL of the following hold:

- [ ] Spec doc exists at `docs/superpowers/specs/YYYY-MM-DD-phase7-trade-lifecycle-state-machine-design.md`.
- [ ] Spec is committed to `main` via conventional commit.
- [ ] Spec respects all locked constraints in §2.
- [ ] Spec addresses all open design questions in §3 (or explicitly defers any with rationale + decision-point that resolves the deferral).
- [ ] Spec includes the state-transition matrix (every allowed pair + every rejected pair).
- [ ] Spec includes the in-flight trade migration plan covering VIR + DHC + CC concretely.
- [ ] Spec includes the phase carve-out file list with one-line justification per file.
- [ ] Adversarial Codex review reached `NO_NEW_CRITICAL_MAJOR` verdict.
- [ ] Operator approved the spec via the brainstorming skill's review gate.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
SPEC: docs/superpowers/specs/<filename>.md
COMMIT: <SHA>
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

KEY DESIGN DECISIONS:
- State enum: <8-state v1.2 verbatim / refined / collapsed-to-N + rationale>
- Reversibility: <which transitions are bidirectional + rationale>
- `status` integration: <drop / view / both during transition + rationale>
- Fills vs exits: <replace / coexist / view + rationale>
- Aggregate denormalization: <on trades / computed-on-read + rationale>
- pre_trade_locked_at: <which fields lock + edit-after-lock mechanism>
- Premortem schema: <table / JSON / 3-columns + rationale>
- Thesis fields: <enumerated + each NOT NULL/nullable disposition>
- Pre-trade gate: <which checks + firing surface + soft vs hard>
- trade_origin derivation: <rule per value + ambiguity-resolution rule>
- Cancel UX: <button placement + reason capture>
- planned/triggered UX: <visible / internal-only + rationale>

IN-FLIGHT MIGRATION:
- VIR: <derived state + pre-trade fields disposition>
- DHC: <derived state + pre-trade fields disposition>
- CC: <derived state + pre-trade fields disposition>

PHASE CARVE-OUT (files added/modified):
- <enumerated list with one-line justification per file>

DEFERRED FROM SPEC (explicitly out of V1):
- <list of design questions deferred with rationale + decision-point>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any blocker or unresolved framing issue>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

LESSONS WORTH CAPTURING (process insights from this brainstorm):
- <bullet list — what was surprising, what design pattern emerged, etc.>

ESTIMATED IMPLEMENTATION DISPATCHES:
- <N writing-plans dispatches + N executing-plans dispatches; rationale>

TEST COUNT IMPACT (rough):
- <approximate +X to fast-test count; flag any design choice that inflates count>
```

---

## §8 If you get stuck

- **If a design question can't be resolved with the operator,** capture both options in the spec with explicit "DEFERRED — operator decision required" status and the decision-point (e.g., "resolve before writing-plans dispatch"). Don't force a decision the operator hasn't made.
- **If a locked constraint genuinely blocks Phase 7 implementation,** invoke the §2 hard-conflict escape: pause, send an interim outbrief describing the conflict, standby for an orchestrator path-forward brief. Do NOT defer the conflict to the final return report; do NOT relitigate in brainstorm.
- **If Codex review surfaces a finding that contradicts a locked constraint,** apply receiving-code-review discipline (verify before agreeing). If the finding is correct AND the constraint is wrong, surface to orchestrator. If the finding is wrong, document why it's rejected with rationale.
- **If pre-existing code surprises you** (e.g., entry service does something different than this brief describes), trust what you observe over what the docs say. Surface the doc/code drift in the return report.
- **If you find an obvious schema simplification** that wasn't anticipated (e.g., the existing `trade_events` table already covers what `pre_trade_edit_audit` would do), propose it — but make it visible to operator decision before committing to spec.

---

## §9 Anti-patterns specific to this brainstorm

These have caused real problems in past sessions; resist:

- **Drifting into implementation.** This is brainstorm-only. If you find yourself writing code, scaffolding directories, drafting migration SQL, or proposing exact line edits — stop. The spec describes shape and rationale; the future implementation dispatches execute.
- **Re-litigating locked constraints.** §2 burned context settling these. Don't reopen.
- **Padding the spec.** A focused spec beats a comprehensive one. Each section earns its space. Past readers (orchestrator + operator + Codex) read carefully; vague prose costs review rounds.
- **Vague "TBD" placeholders.** If the brainstorm couldn't resolve something, mark it explicitly DEFERRED with rationale + decision-point. Never leave silent ambiguity.
- **Adopting v1.2 verbatim where the §"Modification rationale" table says don't.** Re-check the table before any "v1.2 says…" statement in the spec.
- **Designing for Phase 8 or Phase 9 features.** Daily_Management, MFE/MAE precision, Risk_Policy entity, Reconciliation_Run — explicitly out of Phase 7. Schema must ACCOMMODATE them (no painted corners) but must NOT IMPLEMENT them.
- **Self-rated quality scores.** v1.2 has these (`pre_trade_quality_score`, `entry_quality_score`, etc.). The DROP-list constraint covers `pre_trade_quality_score`; brainstorm must surface and DROP any analogous self-rated scoring it discovers.
- **Inflating test scope without discriminating-test value.** Per 2026-05-04 lesson "test-count-projections-bias-high": Phase 6 added +115 tests against a +30-45 plan estimate; that surplus came from real Codex-driven discriminating-test discipline. Phase 7 will likely also exceed plan estimates — but only because of legitimate discriminating-test ROI, NOT because of redundant or vacuous tests. The brainstorm should say what's testable and discriminating, not how many tests.
- **Fields without a frozen-vs-mutable disposition.** Every new field on `trades` (or related tables) must declare: frozen-at-entry / mutable-during-management / written-at-review. Past phases had this discipline (hypothesis_label, chart_pattern_*, sector/industry, Phase 6 review fields). Phase 7 must continue it.
- **Database changes without a backup precedent.** Every Phase 7 migration must be preceded by a backup; the spec calls it out. Don't omit.

---

## §10 Closing note

Phase 7 is the structural backbone of the journal-v1.2 sub-bundle. It's the largest single design surface in the post-Phase-3d sequence. Take the time to get it right; one slow careful brainstorm beats three fast brainstorm rounds + one painful redispatch.

The operator-drives discipline applies throughout. When the operator's framing differs from yours, use theirs. When the operator defers a question, capture it explicitly. When the operator confirms a decision with "yes" or "concur," that's full approval — record it in the spec.

When done, return the report and stop. The orchestrator triages the result and decides whether to commission writing-plans dispatch immediately or defer.
