# Phase 8 Daily_Management + MFE/MAE Precision Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 8 daily-management-design brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for the Swing Trading project's Phase 8 — `Daily_Management` snapshot/event-log table + per-day MFE/MAE precision-tier capture + dashboard tile for open-trade per-day metrics. The brainstorm IS schema-locking (writing-plans depends on locked schema for migration drafting). Lock the table shape + columns + CHECK constraints + FK relationships + capture cadence + lifecycle integration with Phase 7 state machine.

**Brief:** `docs/phase8-daily-management-brainstorm-brief.md` (this file).

**Sequencing:** Phase 10 brainstorm SHIPPED 2026-05-06 (`a46b458` + `fe6cb45`); its §6 enumerates Phase 8 capture-needs the dashboard layer requires — this brainstorm consumes those needs. Phase 9 brainstorm follows Phase 8 + builds on Phase 8's schema. Execution order is 8 → 9 → 10. **No ship-velocity pressure** (operator confirmed n=2 closed / n=3 open trades = 5 total; metric stability is the binding constraint).

**Expected duration:** 90–180 minutes including 3–6 adversarial Codex rounds. Phase 7 spec design saw 3 rounds; Phase 7 sub-dispatches saw 6 rounds (datetime canonicalization fan-out). Phase 8 has comparable complexity (schema + state-machine integration + capture cadence + precision-tier semantics) — budget 4–6 rounds.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas (especially yfinance regressions; SQLite + WAL discipline; HTMX failure surfaces; Windows paths).
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" — the LAST section has 30 active lessons including 12+ Phase 7 specific lessons that bind Phase 8 design (state-machine validation; predicate rewrite; foreign_keys=OFF runner discipline; lexicographic datetime ordering; table-rebuild constraint preservation).
3. **`docs/phase3e-todo.md`** sections "2026-05-01 Journal v1.2 incorporation" (Phase 8 scope is defined here) + "2026-05-04 Schwab API integration" (Phase B data-source replaces yfinance for OHLCV — Phase 8 needs OHLCV for MFE/MAE; coordinate) + "2026-05-04 Future schema migration: trade.entry_date datetime promotion" + "2026-05-05 Sector/industry tamper hardening" + "2026-05-05 Fill.quantity fractional-share forward-compat."
4. **`docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`** — **§6 capture-needs FOR PHASE 8 BRAINSTORM is binding input.** Read end-to-end; §3.5 maturity-stage metrics + §3.4 capital-friction metrics depend on Phase 8 capture; §6.1 enumerates the specific fields the dashboard needs.
5. **`reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md`** — §7.7 (Daily_Management) + §8.6 (MFE/MAE precision) + §10.3 (In-Trade Review workflow). The upstream spec; we adopt with our framework-fit DROP rules per `docs/phase3e-todo.md` "Cross-cutting framing."
6. **`docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`** — Phase 7 spec; binding for state-machine integration. Phase 8 snapshots fire on what state transitions? How do snapshots interact with Phase 7's `state ∈ {entered, managing, partial_exited, closed, reviewed}`?
7. **`swing/data/migrations/0014_phase7_state_machine_and_fills.sql`** — already-shipped Phase 7 schema. Don't propose anything that conflicts.
8. **`swing/data/migrations/0013_phase6_post_trade_review.sql`** — Phase 6 review_log + 10 trade-row review fields. Phase 8 freezes-at-review aggregates may consume Phase 8 daily_management_records data.
9. **`swing/data/ohlcv_archive.py`** + **`swing/data/repos/ohlcv_archive.py`** — Phase 3 OHLCV consolidated archive. MFE/MAE computation against this archive (free; no yfinance call) for `daily_approximate` precision tier; `intraday_estimated` and `intraday_exact` tiers may need new data sources.
10. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — for spec format reference (section-numbered, lock-decisions-vs-open-questions structure).

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — schema sketches in §2.1 are NOT plan tasks. Writing-plans dispatch comes after, separately.
- DO NOT invoke `superpowers:executing-plans` — design-only.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED — what's NOT in the journal/Phase-10 docs)

The following are accepted as **BINDING design constraints** without re-justification.

### §1.1 Distinguishing characteristics of our trading plan

1. **Framework-research-loop posture (NOT discretionary).** Pipeline asserts thesis; per-trade hypothesis_label drives cohort attribution.
2. **Capital tie-up = primary constraint** (not identification rate). $7,500 capital floor for sizing; ~50-trade/year ceiling.
3. **Sample size: n=2 closed, n=3 open (5 total) as of 2026-05-06.** Phase 8 capture starts populating from-day-one but the analytical surface is years away from statistical power. Schema must NOT prematurely optimize for high-n surfaces.
4. **Operator-paced cadence.** Pipeline runs daily; no intraday operator engagement; trail-MA decisions are weekly-or-slower decisions. **Daily snapshots are the right granularity; intraday is V2+.**
5. **Trail-MA gating is OPERATIONALLY URGENT** (Tier-3 #6 from operator-paced items per orchestrator-context). DHC + CC currently approaching trail-MA decision territory (+1.5R / +2R thresholds). Phase 8 surface is the operator-action prompt — design accordingly.

### §1.2 What Phase 8 needs to capture (binding from Phase 10 §6.1)

Per `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` §6.1 — the per-snapshot field list the dashboard requires:

- `maturity_stage` (enum: `pre_+1.5R` / `+1.5R_to_+2R` / `≥+2R_trail_eligible` / `closed`)
- `trail_MA_eligibility_flag` (boolean, derived but cached per snapshot)
- `open_MFE_R_to_date` / `open_MAE_R_to_date` (REAL, R units, running max/min)
- `position_capital_utilization_pct` (with PROVISIONAL fallback denominator note per Phase 10 §2 split-policy)
- `position_portfolio_heat_contribution_dollars`
- `intraday_high` / `intraday_low` (for tomorrow's MFE/MAE)
- `data_asof_session` (NYSE session date anchor)
- **NEW (Phase 10 R1 M5)**: `trail_MA_candidate_price` (REAL, per-position SMA reference price; Phase 8 to decide whether 10-day or 21-day SMA at session close — recommend 21-day per Tier-3 #6 doctrine "default 20MA early, upgrade to 10MA after ~+1.5-2R")
- **NEW (Phase 10 R1 M5)**: `planned_target_R` (REAL, pre-trade-locked target in R units; Phase 8 to decide whether on `trades` table or `daily_management_records`)

### §1.3 Phase 7 binding integrations

Phase 8 schema integrates with Phase 7's shipped state machine + fills:

- **`trades.state` (5-value: `entered` / `managing` / `partial_exited` / `closed` / `reviewed`)** — daily snapshots fire only when state ∈ `{entered, managing, partial_exited}` (open positions). State transition `closed` → freezes the trade's snapshot history (no new snapshots after close).
- **`fills` table** — provides effective-entry-basis for MFE/MAE computation. With multiple entry/add fills, R-multiple is computed against the trade's `planned_risk_budget_dollars` (single denominator per Phase 10 §1.3 DROP rule + Phase 7's collapsed model). Partial-exit fills reduce position size; remaining size's MFE/MAE continues against the original risk basis.
- **`trade_events` table** — Phase 7's audit trail for state transitions. Phase 8's event_log records (per-day discretionary actions, stop adjustments, etc.) are CONCEPTUALLY DIFFERENT from `trade_events` (lifecycle transitions). Phase 8 brainstorm decides: same table? Different table? CHECK-discriminated union?

### §1.4 Apply existing v1.2 DROP rules

Per `docs/phase3e-todo.md` "2026-05-01 Journal v1.2 incorporation" cross-cutting framing — DROP from v1.2 §7.7's Daily_Management spec:

- **Self-rated `pre_trade_quality_score` extension to daily_management** — DROP. Pipeline asserts thesis; daily snapshots don't re-rate.
- **`emotional_state` field** — KEEP (operator-only field; one of the few v1.2 fields that survives the framework adaptation per existing rule).
- **`rule_violation_suspected` flag** — KEEP (links to Phase 6 mistake-tag taxonomy on review).
- **Drawdown circuit breaker** — DEFAULT opt-in disabled (per existing rule).
- **Pyramiding R-views** — DROP. Single denominator (`planned_risk_budget_dollars`).

### §1.5 MFE/MAE precision tier semantics (Phase 10 §3.1 binding)

Three precision tiers per v1.2 §8.6 + Phase 10 §3.1 inventory:

- **`daily_approximate`** — uses daily OHLCV close-of-session high/low from `swing/data/ohlcv_archive`. Cheapest; computable today; ships immediately.
- **`intraday_estimated`** — uses estimated intraday high/low (e.g., yfinance 1-hour bars). NOT shipped today; gated on intraday data source decision.
- **`intraday_exact`** — uses exact intraday tick-or-minute data. NOT shipped today; gated on Schwab API Phase B (or equivalent intraday data source).

**Tier-upgrade-on-recompute policy:** brainstorm decides whether higher-precision data discovered later upgrades the historical record (intraday_exact found at end-of-day → replaces daily_approximate) OR is treated as additive (both tiers preserved). Recommend: tier-upgrade with audit trail (which tier was authoritative at time-of-use). Brainstorm finalizes.

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase8-daily-management-design.md` covering:

### §2.1 — Schema sketches (NOT migration SQL; that's writing-plans)

For each new table proposed:

- **Name** (reserve `daily_management_records` per phase3e-todo.md naming; brainstorm can refine).
- **Columns** with types + nullability + CHECK constraints + FK relationships.
- **Indexes** (which queries does each support; expected cardinality).
- **Discriminating-record-type semantics** (snapshot vs event_log; brainstorm decides one-table-with-discriminator vs separate tables — operator-actionability comparison required).
- **Phase 7 constraint preservation** (per existing lesson 2026-05-05: any table-rebuild migration MUST enumerate every CHECK + FK on the original table + per-constraint disposition; this is a Phase 8 NEW table so no rebuild concern, but if Phase 8 modifies `trades` table for fields like `planned_target_R`, that's a rebuild).

### §2.2 — Capture cadence design

- **Snapshot trigger:** pipeline-step (extends `_step_charts` family OR new `_step_daily_management`)? CLI-triggered? Both?
- **Snapshot timing:** end-of-NYSE-session (when daily OHLCV is final)? Pre-market open? Operator-pacing implication.
- **Idempotency policy:** if pipeline runs twice in same session, second run no-ops on the snapshot? OR overwrites? Per Phase 6 cadence-completion lesson family.
- **Back-fill policy:** if pipeline missed a day (operator skipped pipeline run), do we back-fill the missing day's snapshot from archive on next run? Or leave gap + flag?
- **Event_log trigger:** operator-discretionary (CLI / web form) vs auto-emitted (state transition co-emits event_log row)?

### §2.3 — Lifecycle integration with Phase 7 state machine

- **Snapshot creation:** which states fire daily snapshots? `entered` / `managing` / `partial_exited` only? When state transitions to `closed`, are pending snapshots cancelled?
- **Snapshot freeze:** when trade enters `closed`, do snapshots become read-only forever? Per Phase 7's pattern of frozen aggregates at review-completion.
- **Reviewed trades:** if a closed-then-reviewed trade has a Daily_Management history, does Phase 6 review_log surface it (cross-reference)? Or does Phase 8 stand alone?

### §2.4 — Lookback/replay policy for back-recorded trades

Phase 7 lesson family: trades can be back-recorded. If operator records a trade on 2026-05-10 with `pre_trade_locked_at = 2026-05-05`, does Phase 8 retroactively populate snapshots for 2026-05-05 through 2026-05-10? Or only forward from record-time?

### §2.5 — Read surfaces (dashboard tile + journal extension + per-trade detail)

Per Phase 10 §4.5 maturity-stage view sketch — Phase 8 produces the data; Phase 10 dashboard layer (eventual writing-plans) consumes. Brainstorm sketches:

- **Per-open-position dashboard tile** — composition + sample-size threshold (likely none — always shown when open positions exist).
- **Per-trade detail drill-down** — full snapshot timeline for a closed trade (informs Phase 6 review).
- **Journal stats integration** — does `swing journal review --period month` consume Phase 8 data? Or does Phase 10's metrics dashboard own this surface?

### §2.6 — Migration strategy

- **Schema bump:** v15 → v16 (current is v15 post-Finviz API integration).
- **Migration runner discipline** (Phase 7 lessons binding):
  - SQLite `executescript()` partial-failure rollback wrapper (Phase 7 R1 Major 3 lesson).
  - `foreign_keys=OFF` discipline at runner level (Phase 7 hotfix `283d4fa` lesson — required for any table-rebuild; if Phase 8 modifies `trades` for `planned_target_R`, this applies).
  - Backup gate ON `current_version == 15 AND target >= 16` ONLY (Phase 7 Sub-A code-review I1 lesson).
- **Test fixture PRAGMA discipline** — every Phase 8 migration test fixture sets `foreign_keys=ON` to mirror production (Phase 7 hotfix `283d4fa` lesson).

### §2.7 — Phase 9 hand-off (capture-needs feedback)

Phase 9 brainstorm follows Phase 8. Enumerate Phase 8 design choices that Phase 9 needs to know about:

- Risk_Policy versioning of MFE/MAE precision-tier defaults (which tiers does the policy mandate? Auto-upgrade?)
- Reconciliation of Daily_Management snapshots against broker-API-sourced position state (Schwab API Phase A overlap surface).
- `bootstrap_resample_count` / `low_sample_size_thresholds_class_*` (Phase 10 §6.2 already flags these for Phase 9; Phase 8 doesn't need them but should NOT block them).

### §2.8 — Open questions for orchestrator triage

Per Phase 10 brainstorm pattern (§2.6 — open questions enumerated; not all blocking on writing-plans dispatch).

---

## §3 OUT OF SCOPE (do not do)

- **Migration SQL drafting** — that's writing-plans territory. Schema SKETCHES (column lists + CHECK semantics) are in scope; full `CREATE TABLE` SQL is not.
- **Code drafting** — view-models, query implementations, Jinja templates, route handlers, repo functions.
- **Phase 8 task-decomposition into dispatches** — also writing-plans output.
- **Re-litigating §1 binding constraints** — accepted as given.
- **Re-deriving Phase 10 §6.1 capture-need list** — accept as given.
- **Phase 9 / Phase 10 design** — Phase 9 has its own brainstorm; Phase 10 already shipped.
- **Intraday data source decisions** (which provider, which API, which depth) — that's Schwab API Phase B / future-data-source brainstorm territory. Phase 8 designs the precision-tier ENUM + tier-upgrade policy, agnostic of source.
- **MFE/MAE precision-tier #2 (`intraday_estimated`) ship in V1** — V1 ships `daily_approximate` only; tiers 2+3 are schema-supported (enum value reserved) but not data-fed. Don't design ingestion pipelines for tiers we won't populate in V1.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit (or landing+fixes split per Phase 7/Phase 10 precedent if Codex finds substantive issues — operator-acceptable per established pattern).
- **Commit message:** `docs(phase8): Phase 8 daily-management brainstorm spec`. No Claude co-author footer. No `--no-verify`. No amending.
- **Spec format:** mirror `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` AND `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`. Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage.
- **Spec line target:** ~500–800 lines. Tight is better than padded; if exceeding 800, re-scope.
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget 4–6 rounds.
- **Schema sketches use simplified syntax** — column-name + type + CHECK descriptor + FK target, NOT full `CREATE TABLE` DDL. Example: `maturity_stage TEXT CHECK IN ('pre_+1.5R', '+1.5R_to_+2R', '≥+2R_trail_eligible', 'closed')` is acceptable; `CREATE TABLE daily_management_records (... PRIMARY KEY ... )` is not.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Phase 7 state-machine integration completeness.** Does §2.3 enumerate snapshot behavior for ALL state transitions (`entered → managing`, `managing → partial_exited`, `partial_exited → closed`, `closed → reviewed`, AND backwards transitions where applicable)? Cross-check with Phase 7 spec's state-transition table.
2. **Phase 7 lesson application — predicate rewrite per call-site.** Any place in Phase 8 design that filters by state should be evaluated per-purpose (per Phase 7 lesson "Status→state predicate rewrite is not uniform substitution"). Audit §2.3 + §2.5.
3. **Capture cadence idempotency under operator-paced reality.** §2.2 idempotency + back-fill design must handle: pipeline ran twice in same session (idempotent); pipeline missed a day (back-fill or gap?); operator deletes today's pipeline_run row to redo (snapshot tied to pipeline_run_id? Re-fires?). Per Phase 6 cadence-step idempotency precedent.
4. **MFE/MAE tier-upgrade policy completeness.** §1.5 + §2.x: when intraday_exact data arrives later for a snapshot already populated with daily_approximate, the upgrade decision must be specified — does it overwrite the original record? Add a new record with newer precision? Audit-trail the prior precision? Operator-actionability test: what does the operator SEE when looking at a closed trade's MFE/MAE history that has mixed-tier records?
5. **Discriminating-record-type semantics.** §2.1: if Phase 8 chooses one-table-with-discriminator (snapshot vs event_log via `record_type` CHECK), the brainstorm must enumerate which columns are required for each discriminator value (per Phase 7 brainstorm lesson "operation-contextual validation").
6. **Phase 10 §6.1 capture-need completeness.** Cross-check §2.1 schema sketch against §1.2 binding capture list — every Phase 10-listed field must have a target column in §2.1. If §2.1 chooses NOT to capture a Phase 10-listed field (e.g., decides intraday_high/intraday_low is V2), that's an explicit deviation flagged as open question for orchestrator triage AND surfaces a Phase 10 dashboard regression (the field will render as PROVISIONAL forever).
7. **Schema-rebuild constraint preservation (Phase 7 Sub-C R1 M1 lesson).** If Phase 8 modifies `trades` table to add `planned_target_R` (or any new column), the migration MUST enumerate every existing CHECK + FK on `trades` + carry them forward. Brainstorm flags this as a writing-plans-phase requirement.
8. **foreign_keys=OFF runner discipline (Phase 7 hotfix `283d4fa` lesson).** If §2.6 specifies any table-rebuild migration, it MUST inherit the runner-level foreign_keys=OFF discipline. Brainstorm calls this out explicitly.
9. **Datetime impedance mismatch (Phase 7 Sub-B R1 M1 lesson).** `daily_management_records.review_date` (chronology field — operator-meaningful date, e.g., 2026-05-12) vs creation-timestamp (when the snapshot was captured by the pipeline) are independent fields. Brainstorm enumerates which goes where; specifies validator policy (naive-only vs canonicalized-to-UTC) per the lexicographic-ordering lesson.
10. **Lexicographic datetime ordering on TEXT columns (Phase 7 Sub-B R3 M1 lesson).** Any new TEXT datetime column with `ORDER BY` consumers must specify naive-vs-canonicalized policy + validator.
11. **Test fixture PRAGMA state matches production (Phase 7 hotfix `283d4fa` lesson).** §2.6 migration-test discipline calls out `PRAGMA foreign_keys=ON` on every fixture connection.
12. **Operator-actionability test (Phase 10 watch-item 11 inheritance).** Each Phase 8 surface answers: "what action does the operator take based on reading X vs Y?" §2.5 read-surface sketches must enumerate per-surface action surfaces.
13. **JS-test-harness gap awareness (CLAUDE.md gotcha).** §2.5 dashboard tile sketches don't propose runtime-JS behavior that TestClient can't verify; HTMX patterns mirror existing dashboard tile precedent (e.g., hyp-recs panel, watchlist row).
14. **Schwab API Phase B coordination (`docs/phase3e-todo.md` 2026-05-04 entry).** Phase 8 MFE/MAE precision tiers 2+3 are conceptually gated on Schwab API Phase B (intraday data source). Brainstorm flags the dependency cleanly so the eventual Schwab-Phase-B brainstorm picks up the inheritance — but Phase 8 V1 ships tier 1 only without Schwab dependency.
15. **`trail_MA_candidate_price` reference period decision** (per §1.2 R1 M5 carry-over). 10-day vs 21-day SMA at session close. Brainstorm locks one + rationale (recommend 21-day per Tier-3 #6 doctrine).
16. **`planned_target_R` table-of-residence decision** (per §1.2 R1 M5 carry-over). Trades table (pre-trade-locked at trade entry) vs daily_management_records (per-snapshot-capture). Brainstorm locks + rationale (recommend trades table for pre-trade-locked discipline).

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase8-daily-management-design.md` covering §2.1–§2.8.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors prior brainstorm spec format; lock-decisions vs open-questions explicitly delimited.
4. Single commit OR landing+fixes split landed: `docs(phase8): Phase 8 daily-management brainstorm spec` (and follow-up commit `docs(phase8): Phase 8 daily-management spec — Codex R1-R<N> fixes` if applicable).
5. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 8 daily-management brainstorm

### Spec location
`docs/superpowers/specs/<YYYY-MM-DD>-phase8-daily-management-design.md` ({line count} lines)
Commits on main:
- {sha} `docs(phase8): Phase 8 daily-management brainstorm spec` (initial spec landing)
- (optional) {sha} `docs(phase8): Phase 8 daily-management spec — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### Snapshot vs event_log decision (§2.1)
Locked: one-table-with-discriminator OR two-table-split.
Rationale: ...

### Capture cadence decision (§2.2)
Locked: pipeline-step trigger / CLI / both. Idempotency policy. Back-fill policy.
Rationale: ...

### MFE/MAE tier-upgrade policy (§1.5 / §2.x)
Locked policy: ... (overwrite vs additive vs audit-trailed)
Rationale: ...

### `trail_MA_candidate_price` reference period (§1.2 carry-over)
Locked: 10-day SMA / 21-day SMA at session close.
Rationale: ...

### `planned_target_R` table-of-residence (§1.2 carry-over)
Locked: trades table / daily_management_records.
Rationale: ...

### Open questions for orchestrator triage
1. ...
2. ...

### Capture-needs feedback FOR PHASE 9 BRAINSTORM
- ...
- ...

### Outstanding capture-needs that DEFER to Phase 10+ (intraday-source-gated)
- ...
```

---

## §8 If you get stuck

- If §1 strategic-context constraints conflict with what v1.2 §7.7 or Phase 7 spec proposes, §1 wins.
- If a Codex round produces a finding you can't disposition without operator input, ACCEPT-with-rationale + flag explicitly in spec's "open questions" section + return report.
- If the spec exceeds ~800 lines, you're probably over-designing — re-scope.
- DO NOT propose migration SQL. DO NOT write code. If you start drafting `CREATE TABLE ...` or `class FooVM`, stop.
- If you encounter a Phase 7 lesson that seems to conflict with a Phase 8 design proposal, the Phase 7 lesson wins (those are validated by ship-experience). Surface the conflict as an explicit design constraint in the spec.
- If Phase 10 §6.1 capture-needs and §1.2 binding constraints conflict (shouldn't happen — §1.2 IS Phase 10 §6.1 — but if Codex spots a divergence), call it out explicitly.
