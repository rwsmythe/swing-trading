# Phase 9 Risk_Policy + Reconciliation Depth Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 9 risk-policy + reconciliation-depth brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for Phase 9 — versioned `risk_policy` entity + structured reconciliation framework (`reconciliation_runs` + `reconciliation_discrepancies`) + `hypothesis_status_history` audit + `account_equity_snapshots` capture surface + sector/industry tamper hardening + subsumption of the queued 2026-04-30 TOS reconciliation depth bundle. Brainstorm IS schema-locking (writing-plans depends on locked schema for migration drafting). Lock table shapes + columns + CHECK constraints + FK relationships + capture cadence + lifecycle integration with Phase 6 review_log + Phase 7 state machine + Phase 8 daily_management_records + queued Schwab API Phase A coordination.

**Brief:** `docs/phase9-risk-policy-reconciliation-brainstorm-brief.md` (this file).

**Sequencing:** Phase 10 brainstorm SHIPPED 2026-05-06 (`a46b458` + `fe6cb45`); Phase 8 brainstorm SHIPPED 2026-05-06 (`c2507d3..c954eef`). Both spec §6 + §11 capture-need feedback sections target Phase 9 as the consumer; this brainstorm consumes BOTH. Execution order is 8 → 9 → 10. **No ship-velocity pressure** (operator confirmed n=2 closed / n=3 open trades; metric stability is the binding constraint).

**Expected duration:** 120–240 minutes including 4–6 adversarial Codex rounds. Phase 9 has the largest design surface of the three brainstorms in this chain (5 new tables + cross-cutting versioning + Phase-7/8 lesson inheritance + Schwab API coordination). Convergent chain shape per Phase 7 Sub-B + Phase 8 R2-R5 lesson family — budget 5–6 rounds.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas (especially **NEW SQLite REPLACE gotcha 2026-05-06**; foreign_keys=OFF runner discipline; lexicographic datetime ordering; HTMX failure surfaces).
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" — the LAST section has 35+ active lessons including 12 Phase 7 lessons + 5 NEW Phase 8 lessons that are binding for Phase 9 schema design (state-bearing entity validation; status→state predicate rewrite; foreign_keys=OFF runner discipline; lexicographic datetime ordering; table-rebuild constraint preservation; SQLite REPLACE quirky semantics; is_superseded flag pattern; per-row policy-versioned value stamping; convergent multi-round Codex chains; brief-premise empirical-verification).
3. **`docs/phase3e-todo.md`** sections "2026-05-01 Journal v1.2 incorporation" (Phase 9 scope is defined here) + "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" (Phase 9 subsumes this bundle) + "2026-05-04 Schwab API integration" (Phase A reconciliation overlap; pre-reqs RESOLVED 2026-05-06) + "2026-05-05 Sector/industry tamper hardening" (in-Phase-9 scope per operator decision) + "2026-05-04 Future schema migration: trade.entry_date datetime promotion" + "2026-05-05 Fill.quantity fractional-share forward-compat."
4. **`docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`** — **§6.2 capture-needs FOR PHASE 9 BRAINSTORM is binding input.** Read end-to-end; §3.2 per-hypothesis cohort metrics depend on `hypothesis_status_history` audit; §3.4 capital-friction metrics depend on `account_equity_snapshots`; §5 low-sample-size policy parameters live in `risk_policy`.
5. **`docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md`** — **§11 capture-needs FOR PHASE 9 BRAINSTORM is binding input.** `mfe_mae_default_precision_level` versioning; `trail_MA_period_days` + V2 `trail_MA_post_2R_period_days`; `account_equity_snapshot_table` source enum; snapshot reconciliation flag.
6. **`reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md`** — §7.8 (Risk_Policy) + §7.9 (Reconciliation_Log) + §10.5 (Reconciliation Workflow). Upstream spec; we adopt with framework-fit DROP rules per `docs/phase3e-todo.md` "Cross-cutting framing."
7. **`docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`** — Phase 7 spec; binding for state-machine integration (reconciliation discrepancies on `reviewed` trades reopen review per §10.5; Phase 7 state transitions surface).
8. **`swing/data/migrations/0014_phase7_state_machine_and_fills.sql`** + **`0013_phase6_post_trade_review.sql`** + **`0008_hypothesis_registry.sql`** — already-shipped schemas. Don't propose anything that conflicts.
9. **`swing/journal/tos_import.py`** — `reconcile_tos` + `extract_cash_movements`; current TOS-CSV ingestion path. Phase 9 refactors this to write into `reconciliation_runs` + `reconciliation_discrepancies` instead of returning a one-shot result dict.
10. **`swing/web/routes/trades.py`** — `entry_post` route + chart_pattern hardening commits `117dc97` + `2b9d6f3`. Sector/industry tamper hardening (per 2026-05-05 entry) mirrors this exact pattern.
11. **`swing/config.py`** — current swing.config.toml fields that become risk_policy seed values for `policy_id=1`.
12. **One prior brainstorm spec for format reference** — `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md` (mirror its section-numbered + locked-decisions-vs-open-questions structure; its §6 transactional-sequence pattern is reusable for reconciliation_runs writes).

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — schema sketches in §2.1 are NOT plan tasks.
- DO NOT invoke `superpowers:executing-plans` — design-only.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED — what's NOT in the journal/Phase-8/Phase-10 docs)

The following are accepted as **BINDING design constraints** without re-justification.

### §1.1 Distinguishing characteristics of our trading plan

1. **Framework-research-loop posture (NOT discretionary).** Pipeline asserts thesis; per-trade hypothesis_label drives cohort attribution. risk_policy fields seed from `swing.config.toml` not from operator-discretionary inputs.
2. **Capital tie-up = primary constraint.** $7,500 capital floor for sizing; ~50-trade/year ceiling. Phase 9's `account_equity_snapshots` capture is the source-of-truth for `live_capital_denominator_dollars` (per Phase 10 §2 split-policy) — without it, Phase 8 + Phase 10 PROVISIONAL fallbacks remain in effect.
3. **Single operator at $7,500.** Drawdown circuit breaker DEFAULT opt-in disabled (per existing v1.2 framing rule). Concentration limits are advisory, not blocking.
4. **Sample size: n=2 closed, n=3 open (5 total) as of 2026-05-06.** Reconciliation framework ships from-day-one; analytical surfaces are years away from statistical power. Schema must NOT prematurely optimize for high-cardinality reconciliation discrepancy aggregation.
5. **Operator already on Schwab.** Pre-reqs (Dev Portal app + production-access approval) RESOLVED 2026-05-06 per `docs/phase3e-todo.md` Schwab API entry design Q4. Phase A reconciliation work is unblocked when sequenced. Phase 9 schema must accept Schwab as a `source` enum value cleanly.

### §1.2 What Phase 9 needs to capture (binding from Phase 10 §6.2 + Phase 8 §11)

**From Phase 10 §6.2** (versioning needs for risk_policy):
- `scratch_epsilon` (REAL, default 0.10R) — for Phase 10 §3.1 `win_rate` / `loss_rate` / `scratch_rate` thresholds.
- `review_lag_threshold_days` (INTEGER, default 7) — for Phase 6 dashboard "needs review" badge + soft-warn at trade close.
- `low_sample_size_thresholds_class_a/b/c/d` — for Phase 10 §5 policy (n<3 suppress; 3-5 point-estimate-with-warning; 5-20 Wilson CI; n≥20 headline).
- `global_confidence_floor_n` (INTEGER, default 20) — Phase 10 R3 Major 2 lock.
- `bootstrap_resample_count` (INTEGER, default 1000) — Phase 10 §3.3 cohort_expectancy_with_CI computation.
- `process_grade_weights_entry/management/exit` (REAL, currently 0.40/0.35/0.25 hardcoded) — for Phase 6 process_grade computation.
- `hypothesis_status_history` audit table — append-only on each `hypothesis_registry.status` UPDATE; columns suggested: `(hypothesis_id, status, effective_from, effective_to, change_reason, recorded_at)`. Mirrors v1.1-alternate F-022 pattern.
- `account_equity_snapshot_table` — versioned source enum if manual entry adopted (`source ∈ {manual, schwab_api, csv_import}`).
- `capital_floor_versioning` — version-stamped `capital_floor_constant_dollars` with `effective_from` / `effective_to` bounds; trade reads resolve at `pre_trade_locked_at`.
- `reconciliation_runs` discrepancy surface — for metrics-data-quality reporting (Phase 10+ follow-up).

**From Phase 8 §11** (versioning needs for risk_policy):
- `mfe_mae_default_precision_level` — Phase 9 versions; V2+ may default to `intraday_estimated`.
- `trail_MA_period_days` (default 21) — Phase 9 versions; V2's `trail_MA_post_2R_period_days` (default NULL = no upgrade) supports the 10-day post-+2R upgrade Tier-3 #6 doctrine.
- `account_equity_snapshot_table` — overlap with Phase 10 §6.2 same field.
- Snapshot reconciliation flag (V2+) — for Phase 9 reconciliation_runs surface to flag Phase 8 daily_management snapshot rows that disagree with broker-API position state.

### §1.3 Phase 7 + Phase 8 binding integrations

Phase 9 schema integrates with shipped Phase 6/7 + queued-but-spec'd Phase 8:

- **`trades.state` (Phase 7)** — reconciliation discrepancies on `reviewed` trades REOPEN review per v1.2 §10.5. State transition `reviewed → managing` (or equivalent reopen state) requires Phase 9 to extend Phase 7's state machine OR introduce a discriminator. Brainstorm decides.
- **`fills` table (Phase 7)** — TOS reconciliation close-fill price mismatch detection (per 2026-04-30 TOS bundle Gap 1) compares operator-reported close_price to TOS export's price; the diff lands in `reconciliation_discrepancies`.
- **`trade_events` table (Phase 7)** — Phase 9 `reconciliation_discrepancies` may emit `trade_event` rows for material-to-review discrepancies (audit chain). Brainstorm decides whether reconciliation surfaces are first-class trade_events or sit in their own audit chain.
- **`review_log` table (Phase 6)** — when reconciliation discrepancy reopens a review, the existing review_log row's frozen aggregates may need to be UN-frozen. Brainstorm decides freeze/unfreeze semantics.
- **`daily_management_records` (Phase 8 spec)** — Phase 9 reconciliation_runs may flag daily_management snapshots that disagree with broker-API position state; new `is_reconciliation_flagged` column on Phase 8 schema OR Phase 9-side discrepancy row. Brainstorm decides locus.

### §1.4 Apply existing v1.2 DROP rules

Per `docs/phase3e-todo.md` "2026-05-01 Journal v1.2 incorporation" cross-cutting framing — DROP from v1.2 §7.8 / §7.9:

- **Self-rated `pre_trade_quality_score`-style fields on risk_policy** — DROP. Pipeline asserts thesis.
- **Setup_Playbook references** — DROP per existing rule.
- **Pyramiding R-views (R_initial / R_effective / R_campaign) in risk_policy** — DROP. Single denominator (`planned_risk_budget_dollars`) per Phase 10 §1.3.
- **Drawdown circuit breaker** — DEFAULT opt-in disabled (matches v1.2 default + project posture).

### §1.5 Sector/industry tamper hardening — IN-PHASE-9 SCOPE

Per `docs/phase3e-todo.md` "2026-05-05 Sector/industry tamper vector hardening" entry — operator-decided 2026-05-05 to bundle into Phase 9 because Phase 9's risk_policy introduces sector concentration limits (`max_sector_concentration_positions` per v1.2 §7.8). Once sector becomes a gating dimension, the tamper vector becomes correctness-critical (currently low-stakes because sector/industry are descriptive metadata only).

V1 scope when triggered (executed within Phase 9):
1. Route-layer Finviz-snapshot existence check at trade entry POST (mirror chart_pattern pattern in `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`).
2. Reject if `(ticker, action_session)` sector/industry snapshot doesn't match cached candidate row.
3. Same-shape route + test pattern as chart_pattern hardening.

Brainstorm decides whether this hardening is in §2.1 schema scope (e.g., adds new audit columns) OR purely route-layer code (writing-plans territory). Recommend: route-layer code is writing-plans scope; if Phase 9 schema needs to support tamper-detection audit (e.g., `reconciliation_discrepancies.discrepancy_type='sector_tamper'` enum value), call out as in-scope.

### §1.6 Schwab API Phase A coordination (NOT Phase 9 dependency)

Per `docs/phase3e-todo.md` "2026-05-04 Schwab API integration" entry design Q9 — Phase 9 reconciliation depth + Schwab API Phase A have logical merger ("Phase 9 ships using Schwab API as the data layer"). **HOWEVER, Phase 9 must NOT be hard-dependent on Schwab API.** TOS-CSV path remains a fallback; Phase 9 `reconciliation_runs.source ∈ {tos_csv, schwab_api, ...}` enum supports both. Schwab API Phase A is a separate sequencing decision (see Schwab API entry); Phase 9 ships with TOS-CSV as the V1 source and Schwab as a V2-pluggable enum slot.

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase9-risk-policy-reconciliation-design.md` covering:

### §2.1 — Schema sketches (NOT migration SQL; that's writing-plans)

For each new table proposed:

- **Name** + columns (type + nullability + CHECK constraints + FK relationships) + indexes (which queries does each support; expected cardinality) + retention policy.

Likely tables (brainstorm refines):
- **`risk_policy`** — versioned (effective_from / effective_to / is_active discipline; same Phase-7-lesson family as state-bearing entity). Field list per §1.2 capture-needs aggregation. Existing `swing.config.toml` values seed `policy_id=1`.
- **`reconciliation_runs`** — per-reconciliation-event row; columns (run_id, source ∈ {tos_csv, schwab_api, ...}, source_artifact_path, started_ts, completed_ts, run_state, summary_json). Lifecycle: created → running → completed/failed.
- **`reconciliation_discrepancies`** — per-discrepancy row; columns (discrepancy_id, run_id FK, discrepancy_type ∈ {close_price_mismatch, stop_mismatch, position_qty_mismatch, sector_tamper, snapshot_mismatch, ...}, trade_id FK NULL, ticker, expected_value_json, actual_value_json, material_to_review BOOLEAN, resolved_at, resolution_action). Material-to-review semantics: discrepancies on `state='reviewed'` trades trigger review reopen (brainstorm decides exact mechanism — Phase 7 state extension OR Phase 6 review_log flag).
- **`hypothesis_status_history`** — append-only audit; columns (history_id, hypothesis_id FK, status, effective_from, effective_to NULL when current, change_reason, recorded_at, recorded_by_session_id). Mirrors v1.1-alternate F-022.
- **`account_equity_snapshots`** — daily account-balance capture; columns (snapshot_id, snapshot_date, equity_dollars, source ∈ {manual, schwab_api, csv_import}, source_artifact_path NULL, recorded_at, recorded_by). Cadence: manual entry V1 fallback; Schwab API Phase A pull when available; one row per snapshot_date.

### §2.2 — Capture cadence design

For each table:
- **risk_policy**: explicit operator action via CLI `swing config set ...` OR config-page edit (per Phase 5 infra) creates new policy row (with effective_from = now, prior policy gets effective_to = now). NO periodic refresh.
- **reconciliation_runs**: triggered by CLI `swing journal reconcile-tos` (existing CLI; refactor to write run+discrepancies) OR `swing journal reconcile-schwab` (V2 when Schwab API ships). NOT pipeline-step (operator-paced; reconciliation is post-export/post-trade-close, not nightly).
- **reconciliation_discrepancies**: emitted within reconciliation_run lifecycle (1:N child rows).
- **hypothesis_status_history**: append-only on EVERY `hypothesis_registry.status` UPDATE. Trigger: CLI `swing hypothesis update --status` OR direct UPDATE. Brainstorm decides whether SQL trigger OR application-layer enforcement.
- **account_equity_snapshots**: V1 manual entry (CLI `swing account snapshot --equity 1234.56` OR web form); V2 automated from Schwab API Phase A. Cadence: daily target; gaps allowed (per Phase 8 GAP-FLAGGED-no-auto-back-fill precedent).

Idempotency policy per table; back-fill policy; gap policy.

### §2.3 — Lifecycle integration with Phase 6 + Phase 7 + Phase 8

- **Phase 7 state machine integration:** reconciliation discrepancy on `state='reviewed'` trade — does it (a) extend Phase 7 with `reviewed → managing` reopen transition, OR (b) flag review_log without state change, OR (c) introduce new state `reviewed_with_pending_discrepancy`? Brainstorm decides per spec §3.5.1 operation-contextual validation pattern.
- **Phase 6 review_log integration:** if review reopened, do frozen aggregates UNFREEZE? OR retain frozen-then-mark-superseded pattern (per Phase 8 `is_superseded` flag)? Brainstorm picks per durable code-failure prevention.
- **Phase 8 daily_management_records integration:** `snapshot_reconciliation_flag` lives where — Phase 9 discrepancy row or Phase 8 schema column? Brainstorm picks.

### §2.4 — Migration strategy

- **Schema bump:** v15 → v16 (current is v15 post-Finviz API integration). Phase 8 ships first, will bump to v16; Phase 9 bumps to v17 in writing-plans-time.
- **Migration runner discipline (Phase 7 lessons binding):**
  - SQLite `executescript()` partial-failure rollback wrapper (Phase 7 R1 Major 3 lesson).
  - `foreign_keys=OFF` discipline at runner level for any table-rebuild (Phase 7 hotfix `283d4fa` lesson). Phase 9 likely doesn't rebuild Phase 7's `trades` table, so this primarily applies if Phase 9 needs to rebuild `hypothesis_registry` (unlikely).
  - Backup gate ON `current_version == (target - 1)` ONLY (Phase 7 Sub-A code-review I1 lesson).
  - **NEW (Phase 8 lesson, 2026-05-06):** SQLite `INSERT OR REPLACE` DELETE+INSERT semantics — Phase 9's UPSERT patterns (e.g., risk_policy effective_to update, hypothesis_status_history append) MUST use SELECT-then-UPDATE-or-INSERT, NOT REPLACE. This is now a CLAUDE.md gotcha.
- **Test fixture PRAGMA discipline** — every Phase 9 migration test fixture sets `foreign_keys=ON` to mirror production (Phase 7 hotfix `283d4fa` lesson).
- **Existing swing.config.toml seed:** writing-plans dispatch will draft the seed migration that copies current swing.config.toml values into `risk_policy` row 1.

### §2.5 — TOS reconciliation depth subsumption

Per `docs/phase3e-todo.md` "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" — Phase 9 SUBSUMES this bundle. Three queued gaps map to `reconciliation_discrepancies.discrepancy_type` enum values:

1. **CLOSE-fill price-mismatch detection** (Gap 1) → `discrepancy_type = 'close_price_mismatch'`
2. **Stop-order reconciliation against Account Order History section** (Gap 2) → `discrepancy_type = 'stop_mismatch'`
3. **Position-level holdings reconciliation against Equities section** (Gap 3) → `discrepancy_type = 'position_qty_mismatch'`

Brainstorm enumerates the four queued gaps + maps each to a discrepancy_type enum value + specifies `expected_value_json` / `actual_value_json` shape per type. Existing `swing/journal/tos_import.py:reconcile_tos` refactors to write into Phase 9 tables instead of returning a result dict — writing-plans territory.

### §2.6 — Sector/industry tamper hardening scope decision

Per §1.5. Brainstorm decides:
- (A) Schema-side: add `sector_tamper` discrepancy_type to enum + define `expected_value_json` / `actual_value_json` shape for sector mismatch.
- (B) Route-layer-only: pure code change in writing-plans; no Phase 9 schema impact.
- Recommendation: BOTH — schema supports the discrepancy_type for audit logging, route-layer enforces the rejection at trade entry POST. Brainstorm finalizes.

### §2.7 — Phase 10 hand-off (capture-needs feedback)

Phase 10 writing-plans dispatch follows Phase 9 execution. Enumerate Phase 9 design choices that Phase 10 needs to know about:

- Risk_Policy versioning surface for metric defaults — does the Phase 10 dashboard read live policy values or seed at-trade-time?
- Reconciliation discrepancy surface for metrics-data-quality reporting — Phase 10 may add a "reconciliation status" badge on dashboard / journal review.
- Hypothesis status history — Phase 10 §3.2 surfaces single-most-recent transition only V1; full history requires Phase 9 audit table.

### §2.8 — Open questions for orchestrator triage

Per Phase 8/Phase 10 brainstorm pattern (open questions enumerated; not all blocking on writing-plans).

Likely categories:
- Risk_Policy versioning granularity (per-field-versioned vs per-policy-snapshot).
- Reconciliation discrepancy resolution_action enum scope (auto-resolve vs operator-acknowledge vs reopen-review-only).
- Material-to-review threshold (what qualifies as "material" — any discrepancy? amount-threshold? type-discriminated?).
- account_equity_snapshots cadence (daily mandatory? sparse-allowed? gap policy?).
- Sector/industry tamper hardening — schema vs route-layer-only (per §2.6).
- Schwab API Phase A coordination — is the Phase 9 reconciliation_runs.source enum extension a Phase 9 task OR a Schwab-Phase-A task?

---

## §3 OUT OF SCOPE (do not do)

- **Migration SQL drafting** — that's writing-plans territory. Schema SKETCHES (column lists + CHECK semantics) are in scope; full `CREATE TABLE` SQL is not.
- **Code drafting** — view-models, query implementations, Jinja templates, route handlers, repo functions, CLI command bodies.
- **Phase 9 task-decomposition into dispatches** — writing-plans output.
- **Re-litigating §1 binding constraints** — accepted as given.
- **Re-deriving Phase 8 §11 + Phase 10 §6.2 capture-need lists** — accept as given.
- **Schwab API library evaluation** (schwabdev vs schwab-py vs build-from-scratch) — that's the eventual Schwab Phase A brainstorm scope. Phase 9 designs schema-side support for Schwab as a `source` enum value; library choice is downstream.
- **Schwab API authentication design** — Schwab Phase A territory. Phase 9 schema accepts the eventual auth-flow output (refresh token storage location open Q in Schwab entry; not Phase 9's call).
- **Designing for fractional shares** — gated on Schwab API Phase B (per `docs/phase3e-todo.md` 2026-05-05 entry).
- **Designing for `trade.entry_date` datetime promotion** — gated on future schema-migration entry; not Phase 9.
- **Phase 10 dashboard layer** — Phase 10 brainstorm + spec already shipped; writing-plans for Phase 10 happens AFTER Phase 9 execution.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 6/7/8/Finviz V1 precedent if Codex finds substantive issues.
- **Commit message:** `docs(phase9): Phase 9 risk-policy + reconciliation brainstorm spec`. No Claude co-author footer. No `--no-verify`. No amending.
- **Spec format:** mirror `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md`. Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage.
- **Spec line target:** ~600–900 lines (Phase 9 has the largest design surface in this brainstorm chain). If exceeding 900, re-scope.
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget 5–6 rounds (convergent chain expected per Phase 7/8 lesson family).
- **Schema sketches use simplified syntax** — column-name + type + CHECK descriptor + FK target, NOT full DDL.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Phase 7 state-machine integration completeness.** §2.3: how do reconciliation discrepancies on `reviewed` trades propagate? If Phase 7 state machine extension proposed, enumerate ALL transitions (not just the new one).
2. **Phase 7 lesson application — predicate rewrite per call-site (lesson 2026-05-04).** Any Phase 9 query filtering by `trades.state` or `review_log.review_state` evaluated per-purpose. Audit §2.3 + §2.5 + §2.7.
3. **Phase 8 lesson application — `is_superseded` flag pattern.** Phase 9's risk_policy effective_to UPDATE pattern: if multiple policies can be "current" mid-transition, MUST use the dual-column pattern (`is_active` flag + `superseded_by_policy_id` FK), per Phase 8 R2 lesson. Prevents same-row mid-transaction-conflation bug.
4. **Phase 8 lesson — SQLite REPLACE prohibition.** §2.4 migration discipline + §2.2 capture cadence + §2.5 TOS reconciliation refactor: NO use of `INSERT OR REPLACE` against any FK-referenced or audit-trail table. SELECT-then-UPDATE-or-INSERT only. Cross-check against CLAUDE.md gotcha.
5. **Per-row stamp of policy-versioned values (Phase 8 R1 M5 lesson).** When risk_policy values are CONSUMED in per-trade or per-snapshot capture (e.g., `scratch_epsilon` at review-completion-time, `mfe_mae_default_precision_level` at snapshot-emit-time), enumerate per-row stamping where historical reinterpretation matters.
6. **Phase 10 §6.2 + Phase 8 §11 capture-need completeness.** Cross-check §2.1 schema sketch against §1.2 binding capture list. Every listed field has a target column.
7. **Schwab API Phase A coordination cleanliness.** §2.1 `source` enum on `reconciliation_runs` + `account_equity_snapshots` includes `schwab_api` as a reserved value (not yet wired). Phase 9 ships TOS-CSV V1 only; Schwab is V2 surface. Brainstorm doesn't paint Schwab into a corner with TOS-CSV-specific assumptions.
8. **TOS reconciliation bundle subsumption completeness.** §2.5 enumerates all THREE queued gaps from 2026-04-30 entry mapped to discrepancy_type values. Each gap's `expected_value_json` / `actual_value_json` shape specified.
9. **Sector/industry tamper hardening scope clarity (§1.5 + §2.6).** Decision locked between schema-side / route-layer / both with rationale.
10. **Material-to-review semantics enumerated.** §2.3: which discrepancy_types qualify as material? What does "reopen review" mean operationally (Phase 7 state transition? Phase 6 review_log flag? Both)?
11. **Backup gate condition (Phase 7 Sub-A I1 lesson).** Phase 9 migration backup-gate fires only on `current_version == 16 AND target >= 17`.
12. **Backup-on-every-rebuild discipline.** `risk_policy` is the operator's source-of-truth-for-policy table; if Phase 9 ever needs to rebuild this table (e.g., adding a column to the seed-row policy), the migration runner must back up the existing policy data. Brainstorm flags as writing-plans-phase requirement.
13. **Test fixture PRAGMA state (Phase 7 hotfix `283d4fa` lesson).** §2.4 test discipline calls out `PRAGMA foreign_keys=ON`.
14. **Datetime impedance mismatch (Phase 7 Sub-B R1 M1 lesson) + lexicographic ordering (R3 M1 lesson).** All TEXT datetime columns specify naive-only OR canonicalized-to-UTC + validator policy. Audit `effective_from`/`effective_to` on risk_policy + hypothesis_status_history.
15. **JS-test-harness gap awareness (CLAUDE.md gotcha).** Phase 9 may add reconciliation surfaces to the dashboard — enumerate any HTMX patterns that would surface a JS-test-harness gap.
16. **Operator-actionability test (Phase 10 watch-item 11 inheritance).** Each Phase 9 surface answers: "what action does the operator take?"
17. **Convergent-chain expectation (Phase 7 Sub-B + Phase 8 R2-R5 lesson).** Codex round count likely 4-6; chain shape matters more than count. Implementer's return report should document fix-introduced regression vs adversarial-thrash distinction.
18. **Brief-premise empirical-verification (Phase 10 + 2026-05-04 lesson family).** If the brief asserts shipped-code state (e.g., "Phase 6 ships X" / "Phase 7 ships Y"), the implementer verifies against the actual code/migration files before encoding as binding §1.

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase9-risk-policy-reconciliation-design.md` covering §2.1–§2.8.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors prior brainstorm spec format.
4. Single commit OR landing+fixes split: `docs(phase9): Phase 9 risk-policy + reconciliation brainstorm spec` (and follow-up commit `docs(phase9): Phase 9 risk-policy spec — Codex R1-R<N> fixes` if applicable).
5. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 9 risk-policy + reconciliation brainstorm

### Spec location
`docs/superpowers/specs/<YYYY-MM-DD>-phase9-risk-policy-reconciliation-design.md` ({line count} lines)
Commits on main:
- {sha} `docs(phase9): Phase 9 risk-policy + reconciliation brainstorm spec` (initial)
- (optional) {sha} `docs(phase9): Phase 9 risk-policy spec — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### Risk_Policy versioning model decision (§2.1)
Locked: per-field-versioned / per-policy-snapshot.
Rationale: ...

### Reconciliation lifecycle decision (§2.1 + §2.3)
Locked: discrepancy_type enum scope + material-to-review semantics + state-machine integration approach.
Rationale: ...

### Sector/industry tamper hardening scope (§1.5 + §2.6)
Locked: schema-side / route-layer-only / both.
Rationale: ...

### TOS reconciliation bundle subsumption mapping (§2.5)
Locked: each of the 3 queued gaps mapped to discrepancy_type + expected_value_json / actual_value_json shape.

### Schwab API Phase A coordination (§1.6 + §2.1)
Locked: source enum scope; future-Schwab-pluggability cleanliness.

### Open questions for orchestrator triage
1. ...
2. ...

### Capture-needs feedback FOR PHASE 10 WRITING-PLANS
- ...

### Outstanding capture-needs that DEFER to V2+ (Schwab API gated / Phase 9+ follow-ups)
- ...
```

---

## §8 If you get stuck

- If §1 strategic-context constraints conflict with what v1.2 §7.8/§7.9 or Phase 7/8 specs propose, §1 wins.
- If a Codex round produces a finding you can't disposition without operator input, ACCEPT-with-rationale + flag explicitly in spec's "open questions" section + return report.
- If the spec exceeds ~900 lines, re-scope.
- DO NOT propose migration SQL. DO NOT write code. If you start drafting `CREATE TABLE ...` or `class FooVM`, stop.
- If you encounter a Phase 7 or Phase 8 lesson that conflicts with a Phase 9 design proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a design constraint.
- If Phase 8 §11 + Phase 10 §6.2 + §1.2 binding constraints diverge (shouldn't happen; §1.2 is the union — but if Codex spots a divergence), call it out explicitly.
- If Schwab API Phase A coordination tempts you to design Schwab-specific schema fields beyond the source enum value, STOP — that's Schwab Phase A brainstorm territory.
