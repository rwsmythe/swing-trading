# Phase 12 Sub-bundle C — Auto-Correct Journal-from-Schwab Reconciliation — Design Spec (Brainstorm Output)

**Baseline:** `main` at HEAD post-`b09eb06` (Phase 12 Sub-bundle B SHIPPED 2026-05-15); ~3862 fast tests green; production schema_version = 18 (Schwab integration). Phase 11 CLOSED 2026-05-14 (Schwab API integration arc A+B+C+D); Phase 12 Sub-bundle A SHIPPED 2026-05-15 at `123d27a` (operational-pain mini-bundle); Phase 12 Sub-bundle B SHIPPED 2026-05-15 at `b09eb06` (web-UI-friendliness; credentials-in-file cfg-cascade + web OAuth paste-back form). Sub-bundle C ships the architectural pivot banked at `28a7d01` + `75b876c` from Sub-bundle A's operator-witnessed gate.

**Goal:** Lock the architectural pivot from the Phase 9 + Phase 11 "emit reconciliation discrepancies for operator-triage" loop to a **three-tier resolution model** in which Schwab data IS treated as truth when available, with **tier-1 unambiguous auto-correct** of journal-from-Schwab, **tier-2 ambiguity surfaced for operator decision** with type-specific resolution choices, and **tier-3 rare operator override** of an applied tier-1 correction. Lock the new audit-history table + `ambiguity_kind` column + `resolution_action` CHECK enum widening + classifier architecture + auto-correction service module + reconciliation flow pivot + Tier-2 operator-facing surface + backfill path + lifecycle integration with Phase 6 review_log freezing + Phase 7 fills validators + Phase 8 daily_management snapshots + Phase 9 reconciliation_runs state machine.

**RESEARCH-AND-LOCK posture:** schema sketches + classifier sketches + service-architecture sketches + flow-pivot sketches + open questions, NOT migration SQL, NOT code. Writing-plans (next dispatch) consumes this spec as binding §0 input and translates locked decisions into per-task acceptance criteria.

**Brief:** `docs/phase12-bundle-C-auto-correct-reconciliation-brainstorm-brief.md` (commit on `main` pre-dispatch).

**Scope inputs (binding, not re-derived):**
- §1.1 four operator-locked architectural constraints from brief (`docs/phase3e-todo.md` 2026-05-15 ARCHITECTURAL entry at `28a7d01` + `75b876c`).
- §1.2 three discriminating examples (discrepancies 39 DHC unmatched_open_fill / 40 VSAT unmatched_open_fill / 41 CVGI entry_price_mismatch).
- Shipped schemas: migrations 0014 (Phase 7 fills + trade_events expansion) + 0017 (Phase 9 risk_policy + reconciliation_runs + reconciliation_discrepancies + hypothesis_status_history + account_equity_snapshots + trades/review_log policy stamps) + 0018 (Phase 11 schwab_api_calls + account_equity_snapshots.schwab_account_hash + reconciliation_runs.schwab_api_call_id).
- Service-layer transactional discipline shipped at `swing/trades/reconciliation.py:run_tos_reconciliation` (Phase 9 Sub-bundle B): reject caller-held transactions; own BEGIN IMMEDIATE / COMMIT / ROLLBACK; MATERIAL_BY_TYPE authoritative at INSERT time; defense-in-depth dedup; failure-path UPDATEs state='failed' without rollback-new-row.
- Phase 11 forward-binding lessons + Phase 12 Sub-bundle A+B forward-binding lessons (34 cumulative).
- CLAUDE.md gotchas: `INSERT OR REPLACE` cascade-wipe prohibition; `executescript()` implicit COMMIT; session-anchor read/write mismatch family; SQLite REPLACE prohibition; service-layer transactional discipline three-piece family; Schwab API gotcha set (12 gotchas added at Sub-bundle D T-D.4 + 2 added at Sub-bundle B).

**Spec line target:** ~900–1200 lines per brief §4.

---

## §1 Background, framing, and binding constraints

### §1.1 What this spec produces

A locked schema set (§3): one new table `reconciliation_corrections`; one new column `reconciliation_discrepancies.ambiguity_kind` with CHECK enum; one widening of `reconciliation_discrepancies.resolution` CHECK enum (5 → 9 values); one new column `review_log.superseded_by_correction_id` (Phase 6 freezing audit); one widening of `trade_events.event_type` CHECK enum (+`reconciliation_auto_correct`); one widening of `schwab_api_calls` audit FK shape (+`linked_correction_id`); schema_version bump v18 → v19. A locked classifier shape (§4): pure function input/output contract, per-discrepancy-type sub-classifiers, `ambiguity_kind` enum coverage, determinism principle, validator-respecting downgrade rule. A locked auto-correction service architecture (§5): module name, transactional discipline, idempotency contract, validator chain, audit emission. A locked Tier-2 operator-facing surface (§6): CLI-first V1; per-`ambiguity_kind` resolution choices; web V2 deferred. A locked reconciliation flow pivot (§7): the `classify → dispatch → apply` shape at `run_schwab_reconciliation` + `run_tos_reconciliation` call sites; failure-mode contract. A locked backfill path (§8): operator-initiated CLI; dry-run support; idempotency. A locked lifecycle integration design (§9): Phase 6 review_log freezing RETAIN-and-mark-superseded; Phase 7 `fills.reconciliation_status` enum unchanged V1; Phase 8 `daily_management_records` snapshots RETAIN as historical; Phase 9 `reconciliation_runs` state machine unchanged. Three discriminating-example walkthroughs end-to-end (§10): CVGI 41 + DHC 39 + VSAT 40 through classifier + service + backfill. A locked migration strategy (§11). A sub-sub-bundle decomposition recommendation (§12): 4 sub-sub-bundles C.A / C.B / C.C / C.D with dispatch ordering + cross-bundle dependencies + projected test deltas + projected line counts. A locked OUT-OF-SCOPE statement on fill auto-population at trade-entry time (§13) plus a description of clean layering interfaces Sub-bundle C ships for the future prospective sub-bundle to consume. Enumerated open questions for orchestrator triage (§14). A writing-plans hand-off section (§15).

### §1.2 What this spec does NOT produce (out of scope per brief §3)

Migration SQL drafts; code drafts (service modules, view-models, query implementations, Jinja templates, route handlers, repo functions, CLI command bodies); sub-sub-bundle task-decomposition into per-task acceptance criteria (writing-plans output); re-litigation of brief §1.1 binding constraints; fill auto-population at trade-entry time (per §1.6 explicit operator handoff lock); Phase 11 Schwab API V2 features (token encryption-at-rest; Option B HTTPS callback; per-env namespacing; multi-account picker; `surface='web'` CHECK enum widening; all banked in Sub-bundle A + B V2 lists); Phase 7 state-machine extension beyond enum widening; re-deriving the 34 cumulative Phase 9 + Phase 11 + Phase 12 A + B forward-binding lessons.

### §1.3 Binding constraints (operator-locked; brief §1.1; not re-derived)

Per brief §1.1 ARCHITECTURAL framing at `28a7d01` + `75b876c`, the following are accepted as **binding design constraints**. Operator-locked during 2026-05-15 architectural-pushback conversation. If an adversarial review round produces a finding that contradicts §1.3, the finding is enumerated as an open question for orchestrator triage; §1.3 is not relaxed in the spec.

1. **Schwab data IS truth.** When Schwab API responses are available + the call succeeded, the journal must converge TO Schwab, not the other way around. The current `acknowledged_immaterial` operator-triage loop bypasses validators + treats journal as authoritative — this is the architectural anti-pattern Sub-bundle C closes.
2. **Three-tier resolution model.**
   - **Tier 1 — unambiguous auto-correct (most common):** classifier identifies single journal fill + single Schwab record + single field differs + clear target value. System auto-corrects journal to match Schwab + writes audit row. ZERO operator involvement.
   - **Tier 2 — ambiguity surfaced for operator decision (operationally important):** classifier identifies mismatch but cannot deterministically resolve. Surfaced with **structured `ambiguity_kind` enum** + **type-specific resolution choices** for operator. Operator picks → service auto-applies + audits.
   - **Tier 3 — rare operator override (edge case):** operator has ground-truth knowledge that Schwab itself is wrong (broker error; reporting glitch). Operator marks an applied tier-1 correction as `operator_overridden` + provides ground-truth value + reason. Audit chain preserves all three values: pre-correction journal / Schwab-said / operator-override.
3. **Magnitude is the WRONG axis.** Determinism is the axis. `$0.07` is not "small"; the question is whether the correction is deterministic, not whether the delta is big. NO magnitude-based auto-vs-surface threshold gates anywhere in the design.
4. **`acknowledged_immaterial` back-compat preserved.** Existing 30 resolved discrepancies in production (all `acknowledged_immaterial` per operator's manual resolution sweep during Phase 11 + Phase 12 Sub-bundle A gates) remain valid; they predate Sub-bundle C semantics. New discrepancies use the new `resolution` enum values: `auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`. The `acknowledged_immaterial` enum value stays as back-compat for the SPECIFIC narrow tier-3 case where operator has ground-truth-Schwab-is-wrong knowledge and chooses NOT to override an applied correction. No backfill rewriting of historical `acknowledged_immaterial` resolutions.

### §1.4 Concrete current-state evidence (3 unresolved discrepancies; classifier discriminating examples)

Production state at dispatch time (per `swing schwab status --environment production` 2026-05-15 + brief §1.2):

- **disc 41 CVGI `entry_price_mismatch`:** journal `fills.fill_id=9` price=$5.23 × N shares on entry date D, Schwab=$5.30, delta `+$0.07`. **Tier-1 `auto_correctable` candidate:** single journal fill matches single Schwab transaction by (ticker, date, qty); only `price` field differs; clear target = $5.30. Classifier emits `(tier=1, ambiguity_kind=None, correction_target={'price': 5.30})`. Service applies via `fills.price` UPDATE + writes `reconciliation_corrections` audit row + sets discrepancy `resolution='auto_corrected_from_schwab'`. ZERO operator involvement.

- **disc 39 DHC `unmatched_open_fill`:** journal `fills.fill_id=2` entry @$7.58 × 39 on 2026-04-27; Schwab Trader API returned `actual={"matched": null}` indicating no single Schwab transaction matched. **Tier-2 `ambiguous` candidate, `ambiguity_kind=multi_partial_vs_consolidated`:** Schwab almost certainly has partial fills (e.g., 20 + 19 at slightly different prices); journal has single consolidated row. Classifier emits `(tier=2, ambiguity_kind='multi_partial_vs_consolidated', correction_target=None)`. Service does NOT auto-apply; sets discrepancy `resolution='pending_ambiguity_resolution'` + populates `ambiguity_kind` column; operator resolves via CLI surface (§6) by picking one of: split-into-partials / keep-consolidated-use-Schwab-VWAP / keep-journal-as-is-mark-aggregation-acknowledged / operator-custom.

- **disc 40 VSAT `unmatched_open_fill`:** journal `fills.fill_id=6` entry @$65.69 × 2 on 2026-05-06; `manual_entry_confidence='low'` (operator flagged uncertain at entry); Schwab `actual={"matched": null}`. **Classifier evaluates per-row based on actual Schwab payload at classification time:** if Schwab has single fill at slightly different price/qty → tier-1 `entry_price_mismatch` or `position_qty_mismatch` redirect; if Schwab has multiple partials → tier-2 `multi_partial_vs_consolidated`; if Schwab has no record at all → tier-2 `schwab_returned_no_match`. Discriminator is the Schwab payload, not the journal-side `manual_entry_confidence` flag (which is operator-honesty metadata, not classification input).

All three fills carry `reconciliation_status='unreconciled'` + `tos_match_id=NULL`. These cases drive §4 classifier design + §8 backfill path; §10 works each example through the proposed classifier + service + backfill end-to-end as discriminating walkthroughs.

### §1.5 Binding integrations (shipped surfaces Sub-bundle C consumes)

Sub-bundle C composes over Phase 6 + Phase 7 + Phase 9 + Phase 11 + Phase 12 Sub-bundle A/B surfaces:

- **`reconciliation_runs` (Phase 9 schema v17):** current state machine `('running','completed','failed')`. Sub-bundle C does NOT extend state machine (§9.4 + §12.A LOCK). Classification + tier-1 apply happen INSIDE the `state='running'` window before COMMIT.
- **`reconciliation_discrepancies` (Phase 9 schema v17):** current `resolution` CHECK enum is `('journal_corrected', 'source_treated_canonical', 'manual_override', 'unresolved', 'acknowledged_immaterial')` — five values per actual shipped migration `0017_phase9_risk_policy_and_reconciliation.sql` (brief enumeration `'mistake_corrected'` was incorrect; shipped schema is authoritative). Sub-bundle C widens to 9 values (§3.2). The brief's mentioned `'mistake_corrected'` value does not exist on shipped schema and is NOT added by this spec.
- **`fills.reconciliation_status` (Phase 7 schema v14):** current enum is `('unreconciled','reconciled_match','reconciled_discrepancy','reconciled_discrepancy_resolved','manual_override')` — five values per actual shipped migration `0014_phase7_state_machine_and_fills.sql` (brief enumeration `('unreconciled','reconciled')` was incorrect; shipped schema is authoritative). Sub-bundle C does NOT widen this enum V1 (§9.2). Per-discrepancy `resolution` carries the meaningful state at the discrepancy grain; widening fills.reconciliation_status would duplicate signal at fill grain and reintroduce a write-amplification surface.
- **`schwab_api_calls` (Phase 11 schema v18):** audit table for Schwab API invocations. Sub-bundle C's auto-correction service may emit new audit rows when it fetches Schwab data to verify the tier-1 correction in §10 worked example or to break ambiguity in C.D backfill resolution; source-artifact reference shape locked at `schwab_api:call/{call_id}` per Phase 11 gotcha. Sub-bundle C adds ONE new FK column `schwab_api_calls.linked_correction_id` (NEW; mirrors `linked_snapshot_id` + `linked_reconciliation_run_id` precedent; FK to `reconciliation_corrections(correction_id)` ON DELETE SET NULL).
- **Phase 7 fills validators (`swing/data/repos/fills.py`):** auto-correction MUST preserve invariants — quantity > 0; price > 0; trade_id FK valid; `_recompute_aggregates` invariants `current_size = sum(entry qty) - sum(trim/exit/stop qty)`. Classifier downgrades tier-1 → tier-2 with `ambiguity_kind='validator_rejected'` if dry-run validator chain rejects.
- **Phase 6 review_log freezing (`swing/data/repos/review_log.py`):** auto-correction post-review on a closed-reviewed trade RETAINS frozen aggregates as historical record; new column `review_log.superseded_by_correction_id` marks the review row as "superseded by a later correction" (Phase 8 `is_superseded` precedent). No retroactive rewrite of frozen `realized_R_if_plan_followed` / `actual_realized_R_effective` / `mistake_cost_R` / etc. Phase 10 dashboard can render badges via the FK.
- **Phase 8 `daily_management_records` (`swing/data/repos/daily_management.py`):** historical snapshots are point-in-time observations; RETAIN as historical (no retroactive adjustment under auto-correction). Phase 8 self-stamps `position_capital_denominator_dollars` + `trail_MA_period_days` + `mfe_mae_precision_level` per row (already shipped per Phase 9 §3.1.1 R1 M5); the snapshot grain is decoupled from the corrected fill grain by design.
- **Phase 11 Sub-bundle C marketdata + Sub-bundle B trader endpoints:** Schwab API surfaces the auto-correction service consumes for tier-1 truth-fetching during reconciliation runs. Sandbox short-circuit gating MUST be preserved (CLAUDE.md gotcha: under `environment='sandbox'`, domain rows are NOT written but audit rows are; corrections under sandbox are SHORT-CIRCUITED to no-op + WARNING log, per §9.7).
- **Phase 12 Sub-bundle B cfg-cascade:** credentials resolved via `apply_overrides` at all 5 Schwab entry points. The auto-correction service, when it constructs `schwabdev.Client(...)` directly or composes over `swing/integrations/schwab/trader.py` + `marketdata.py`, becomes a 6th entry point and inherits `apply_overrides` discipline + single-Client-instance discipline.
- **Phase 12 Sub-bundle A `_construct_pipeline_schwab_client(cfg)`:** the pipeline-time client constructor at `swing/integrations/schwab/__init__.py` (or wherever it landed; verified at writing-plans-time). Auto-correction inside `_step_schwab_orders` reuses the same client to avoid double-construction.

### §1.6 Apply existing DROP rules

Inherits from prior phases — no new DROP rules unique to Sub-bundle C. Specifically:

- **No magnitude-based threshold** (operator §1.3 lock #3).
- **No re-litigating Schwab-truth premise** (operator §1.3 lock #1).
- **No Phase 7 state-machine extension beyond enum widening** (Phase 9 lesson; per §1.5 + §9.2). Sub-bundle C widens `trade_events.event_type` CHECK enum by adding `'reconciliation_auto_correct'` (one value). No trade-state machine transitions added.
- **No fill auto-population at trade-entry time** (operator §1.7 lock; separate sub-bundle).

### §1.7 Fill auto-population at trade-entry time — EXPLICITLY OUT OF SCOPE (separate sub-bundle)

Per brief §1.6 + `docs/phase3e-todo.md` 2026-05-15 ARCHITECTURAL entry under §"Fill auto-population at trade-entry time": creating fills directly from Schwab Trader API responses at trade-entry handler time (instead of operator-typing-from-memory) closes the entire discrepancy stream as a CATEGORY (not one-at-a-time). **Operator-locked decision (brief §1.6 + brief operator-handoff Step 8 #6):** this is a SEPARATE sub-bundle. Sub-bundle C is the retroactive-correction surface; auto-population at entry is the prospective analog and lives in a future sub-bundle.

Sub-bundle C ships clean layering interfaces that the future prospective sub-bundle consumes (§13). Sub-bundle C does NOT design schema for fill auto-population; does NOT propose any new tables for it; does NOT propose CHECK enum widenings for it.

### §1.8 Sub-sub-bundle decomposition expectation

Per brief §1.5 + §2.8 Sub-bundle C is expected to decompose into 3-4 sub-sub-bundles for executing-plans. This spec proposes 4 sub-sub-bundles in §12; writing-plans refines + locks at task grain.

---

## §2 Vocabulary anchored against shipped surfaces

| Term | Definition (Phase 12 Sub-bundle C) | Anchor / shipped surface |
|---|---|---|
| **Discrepancy** | Existing Phase 9 vocabulary: a single field-level disagreement detected within a reconciliation run. Carries `discrepancy_type` (10-value enum) + linked entity FKs + JSON shapes + `resolution` enum + `material_to_review` classification flag. Sub-bundle C adds the `ambiguity_kind` column + 4 new `resolution` enum values. | Phase 9 §3.3; migration 0017 |
| **Tier (classification)** | An integer `{1, 2, 3}` produced by the classifier (§4). Tier 1 = unambiguous deterministic auto-correct; Tier 2 = ambiguous, operator picks from type-specific choices; Tier 3 = operator-initiated post-tier-1 override (classifier never emits tier=3 itself — operators reach tier-3 by overriding an applied tier-1 correction via CLI). | §4; §6; §3.2 |
| **Ambiguity kind** | A string enum value naming the structured reason a tier-2 classification was emitted. NULL on tier-1 discrepancies. Drives the per-discrepancy resolution-choice menu in the Tier-2 surface (§6). | §3.2; §4.3 |
| **Correction target** | A dict shape `{field_name: target_value, ...}` produced by the classifier on tier-1 emissions. The auto-correction service consumes this dict to drive the journal UPDATE. NULL on tier-2 emissions. | §4.2; §5.3 |
| **Auto-correction** | The act of applying a tier-1 correction to the journal: UPDATEing the affected journal table (`fills` / `trades` / `cash_movements`) + INSERTing a `reconciliation_corrections` audit row + UPDATEing `reconciliation_discrepancies.resolution='auto_corrected_from_schwab'`, all atomic under the auto-correction service's BEGIN IMMEDIATE / COMMIT / ROLLBACK boundary. | §5 |
| **Reconciliation correction** | One row in the new `reconciliation_corrections` audit table (§3.1). Forensic-trail record preserving pre-correction journal value + Schwab-said value + applied correction + correction lifecycle (auto-applied OR operator-resolved-ambiguity OR operator-overridden) + per-row policy stamp. | §3.1; §5.4 |
| **Operator override** | Tier-3 action: operator marks an applied tier-1 `reconciliation_corrections` row as `operator_overridden`, supplying ground-truth value + reason. Audit chain preserves pre-correction journal value AND Schwab-said value AND operator-supplied truth — three-value chain (§3.1). Reverts the journal-side UPDATE to the operator's truth + writes a second audit row chained to the first. | §3.1; §6.4 |
| **Determinism principle** | When in doubt, classify as tier-2 (NOT tier-1). False-positive tier-1 silently corrupts journal; false-positive tier-2 just defers to operator (no harm). | §4.5 |
| **Validator chain** | The set of Phase 7 fills validators + Phase 6 review_log invariants + Phase 9 risk_policy at-trade-time-locked references the auto-correction service consults before applying a tier-1 correction. If the dry-run rejects the correction, classifier downgrades tier-1 → tier-2 with `ambiguity_kind='validator_rejected'`. | §4.6; §5.5 |
| **Backfill** | Operator-initiated one-time CLI operation that runs the classifier across all existing `reconciliation_discrepancies` rows where `resolution='unresolved'` and applies tier-1 / sets tier-2 ambiguity_kind / leaves tier-3-eligible cases alone. | §8 |
| **Pivot (reconciliation flow)** | The architectural change to `run_schwab_reconciliation` (and optionally `run_tos_reconciliation`) from "emit discrepancies + return" to "emit discrepancies + classify each + dispatch tier-1 to auto-correction + dispatch tier-2 to pending-ambiguity + return summary". | §7 |
| **Resolution action** | Existing Phase 9 vocabulary refined by Sub-bundle C. The `resolution` enum value an operator or the auto-correction service stamps on a discrepancy to record the outcome. V1 = 5 values; Sub-bundle C widens to 9 values. | §3.2 |

---

## §3 Schema sketches (LOCKED)

### §3.1 New table: `reconciliation_corrections`

**Audit-history table for tier-1 auto-applied corrections + tier-2 operator-resolved ambiguities + tier-3 operator overrides.** Preserves the forensic trail: pre-correction journal value + Schwab-said value + applied correction value + operator-override value (if any) + lifecycle metadata + per-row policy stamp.

**Decision rationale (LOCKED; §3.1.0):** dedicated NEW table chosen over `trade_events` extension OR `event_log` extension OR sibling-table-on-`reconciliation_discrepancies`.

- `trade_events` is trade-grain with a tight `event_type` CHECK enum already cycled through Phase 7's expansion gotcha; reconciliation-correction events span trades/fills/cash_movements grain and aren't all attributable to a single trade (e.g., cash_movement-grain corrections). Adding `'reconciliation_auto_correct'` value to the enum IS done by Sub-bundle C (§3.5) for the per-trade audit-cross-reference benefit, but the FORENSIC TRAIL itself lives on `reconciliation_corrections` not `trade_events`.
- `event_log` (Phase 8) is daily_management-grain at session cadence; doesn't fit.
- Sibling-on-discrepancy via column accretion would muddle the row-grain (one discrepancy → potentially N corrections over time: initial tier-1 apply + later operator override + later operator re-override are 3 audit rows from 1 discrepancy).
- Dedicated table mirrors `risk_policy` audit-trail pattern (versioned with explicit FK chain via `superseded_by_policy_id` self-reference). Sub-bundle C uses an analogous `superseded_by_correction_id` self-reference chain (§3.1 column list) for the override-of-override edge case.

**Column sketch** (column-name + type + nullability + CHECK / FK):

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `correction_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `discrepancy_id` | INTEGER | NOT NULL | FK → `reconciliation_discrepancies(discrepancy_id)` ON DELETE CASCADE (correction is meaningless without the discrepancy that spawned it) |
| `correction_action` | TEXT | NOT NULL | CHECK IN (`'auto_applied'`, `'operator_resolved_ambiguity'`, `'operator_overridden'`); identifies which of the three tiers produced this row |
| `correction_choice` | TEXT | nullable | NULL on tier-1 `auto_applied`; for tier-2 `operator_resolved_ambiguity` carries the resolution-choice code the operator picked from the per-`ambiguity_kind` menu (§6.2 enumerates codes per kind); for tier-3 `operator_overridden` carries `'operator_truth'` (single value V1) |
| `affected_table` | TEXT | NOT NULL | CHECK IN (`'fills'`, `'trades'`, `'cash_movements'`, `'account_equity_snapshots'`); names the journal table the correction modified |
| `affected_row_id` | INTEGER | NOT NULL | the PK of the modified row in `affected_table` (e.g., `fills.fill_id`); NOT a FK because the affected table varies by row (per-row polymorphism — schema CHECK enforces the table name; soft FK enforced at app layer in service) |
| `field_name` | TEXT | NOT NULL | the column name within `affected_table` that the correction modified (e.g., `'price'`, `'quantity'`, `'fill_datetime'`); single-column-per-correction-row simplifies forensic trail (multi-column atomic corrections produce N rows under same `discrepancy_id` chained by `applied_in_correction_set_id` — §3.1.1) |
| `pre_correction_value_json` | TEXT | NOT NULL | JSON-stringified pre-correction journal value (the value BEFORE this correction applied; mirrors Phase 9 `expected_value_json` shape) |
| `source_canonical_value_json` | TEXT | nullable | JSON-stringified Schwab-said value (the value the source asserted at classifier time); NULL on tier-3 `operator_overridden` rows that chain off a tier-1 row (the chained-from row carries the Schwab-said value); NOT NULL on tier-1 `auto_applied` rows |
| `applied_value_json` | TEXT | NOT NULL | JSON-stringified post-correction journal value (the value AFTER this correction applied) |
| `operator_truth_value_json` | TEXT | nullable | JSON-stringified operator-truth value supplied during tier-3 override; NULL except on `'operator_overridden'` rows |
| `applied_at` | TEXT | NOT NULL | ISO datetime with millisecond precision (`YYYY-MM-DDTHH:MM:SS.SSS`); naive-UTC per shipped datetime discipline; service stamps at apply time |
| `applied_by` | TEXT | NOT NULL | CHECK IN (`'auto'`, `'operator'`); `'auto'` on tier-1 `auto_applied`; `'operator'` on tier-2 + tier-3 |
| `correction_set_id` | INTEGER | nullable | groups multi-column atomic corrections under one logical correction (§3.1.1); NULL when the correction is single-column (most common) |
| `superseded_by_correction_id` | INTEGER | nullable | FK → `reconciliation_corrections(correction_id)` self-reference; set when a later override-of-override chains; preserves the override chain |
| `risk_policy_id_at_correction` | INTEGER | nullable | FK → `risk_policy(policy_id)` ON DELETE SET NULL; **NULLABLE** to be consistent with `ON DELETE SET NULL` action (Codex R1 Major #3 fix — NOT NULL + SET NULL is internally inconsistent; matches Phase 9 §3.1.1 trades.risk_policy_id_at_lock + review_log.risk_policy_id_at_review_completion precedent which are also nullable + SET NULL). risk_policy is append-only in V1 so DELETE doesn't fire in practice; SET NULL is defensive forward compat. App layer SHOULD populate at write time (Phase 8 R1 M5 lesson — per-row stamp at write time so future policy edits don't reinterpret the validator chain that approved this correction); a defensive backfill of legacy NULL rows is V2 candidate if a Phase 10 metric requires the stamp on every correction row |
| `schwab_api_call_id` | INTEGER | nullable | FK → `schwab_api_calls(call_id)` ON DELETE SET NULL; the Schwab API call whose response surfaced the source-canonical value used for this correction; NULL when the source is TOS-CSV (not Schwab) or when no specific call is attributable (e.g., classifier ran against cached payload) |
| `reconciliation_run_id` | INTEGER | NOT NULL | FK → `reconciliation_runs(run_id)` ON DELETE CASCADE (mirrors discrepancy FK; correction is bound to the run that emitted the discrepancy) |
| `correction_reason` | TEXT | nullable | free-text rationale; auto-filled on `'auto_applied'` rows with classifier-generated description; operator-supplied on `'operator_resolved_ambiguity'` and `'operator_overridden'` rows (REQUIRED on tier-3 per §6.4) |
| `notes` | TEXT | nullable | additional operator notes |

**Column count:** 19 columns.

**Indexes:**

- `CREATE INDEX ix_reconciliation_corrections_discrepancy ON reconciliation_corrections(discrepancy_id, applied_at)` — supports "show me all corrections that hit this discrepancy" lookup (override chain).
- `CREATE INDEX ix_reconciliation_corrections_affected_row ON reconciliation_corrections(affected_table, affected_row_id, applied_at)` — supports "show me all corrections that hit this fill / trade / cash_movement" lookup for trade-detail dashboard surfaces.
- `CREATE INDEX ix_reconciliation_corrections_run ON reconciliation_corrections(reconciliation_run_id)` — supports per-run audit reporting.
- `CREATE INDEX ix_reconciliation_corrections_action ON reconciliation_corrections(correction_action, applied_at)` — supports operator filters ("show me all tier-2 resolved last 30 days").

**Retention policy:** append-only; never deleted. Override chain preserves history. Migration v18 → v19 introduces the table; no seeding (production schema starts empty; backfill (§8) populates retroactively for existing discrepancies 39/40/41 + any future).

#### §3.1.1 Multi-column atomic corrections (`correction_set_id`)

A small number of correction families operate over multiple columns atomically. Example (`unmatched_open_fill` → `multi_partial_vs_consolidated` resolved via "split-into-partials" operator choice): operator picks split; service deletes the consolidated journal fill + inserts N partial fills. That single operator choice produces multiple `reconciliation_corrections` rows (one per affected fill PK and per column conceptually; the simplification we adopt is one row per affected (table, row_id, field_name)). The `correction_set_id` column groups them: all rows in the same set share a common UUID-like INTEGER (autoincrement seed assigned at set-construction time by the service; first row in set is its own set anchor, subsequent rows reference the anchor row's `correction_id` as `correction_set_id`).

Single-column corrections leave `correction_set_id` NULL (most common). Multi-column corrections set `correction_set_id` on all rows in the set; the value is the `correction_id` of the anchor row (the first row INSERTed in the set; subsequent rows reference the anchor row's `correction_id` as `correction_set_id`). The anchor row points back at itself: after the anchor row is INSERTed, it is UPDATEd to set `correction_set_id = correction_id`. Codex R1 Minor #1 fix: this is an **anchor correction id**, not a "UUID-like INTEGER" — the value is the autoincrement-assigned PK of the anchor row, used as a group identifier within the set. Writing-plans clarifies the bind-on-INSERT mechanic (two-step: INSERT anchor row → SELECT its `correction_id` → UPDATE anchor row's `correction_set_id` to itself → INSERT remaining rows in set with `correction_set_id` = anchor's `correction_id`).

#### §3.1.2 Override chain semantics (`superseded_by_correction_id`)

- Tier-1 `auto_applied` row's `superseded_by_correction_id` is NULL until an operator subsequently overrides via tier-3.
- Tier-3 `operator_overridden` row is INSERTed as a new row chained to the tier-1 row: the new row's `superseded_by_correction_id` is NULL (it is the current row); the tier-1 row's `superseded_by_correction_id` is UPDATEd to point to the new row's `correction_id`. Mirrors `risk_policy.is_active` + `superseded_by_policy_id` pattern (Phase 9 §3.1.1 + §4.1 6-step sequence).
- Edge case (override-of-override): operator changes their mind. Tier-3 row #2 is INSERTed; tier-3 row #1's `superseded_by_correction_id` UPDATEd to point to row #2; the chain extends. Currently-effective correction is the row where `superseded_by_correction_id IS NULL` for the chain rooted at a given discrepancy.

#### §3.1.3 The "correction was applied but the discrepancy was wrong about the source" edge

If subsequent Schwab API data reveals that the source-canonical value at classifier time was itself stale (e.g., Schwab corrected its own trade history later), the operator override is the path. Sub-bundle C does NOT design a "re-classify" path; the operator overrides via tier-3 with the new ground-truth. Re-classification across already-applied corrections is V2 territory.

### §3.2 `reconciliation_discrepancies` column additions + CHECK enum widening

**SHIPPED schema (migration 0017, verified at writing-plans-time):**

- `resolution TEXT NOT NULL CHECK (resolution IN ('journal_corrected', 'source_treated_canonical', 'manual_override', 'unresolved', 'acknowledged_immaterial')) DEFAULT 'unresolved'`

**Sub-bundle C changes:**

1. **CHECK enum widening** — widen `resolution` from 5 values to 9 values:
   - **EXISTING preserved:** `'journal_corrected'`, `'source_treated_canonical'`, `'manual_override'`, `'unresolved'`, `'acknowledged_immaterial'`
   - **NEW added:** `'auto_corrected_from_schwab'`, `'pending_ambiguity_resolution'`, `'operator_resolved_ambiguity'`, `'operator_overridden'`

   Mechanic: SQLite CHECK constraint widening on an existing column requires a table-rebuild (CREATE new table → INSERT-SELECT-old-data → DROP old → ALTER RENAME). Writing-plans drafts the rebuild script following Phase 7's trades-table-rebuild precedent (migration 0014 §10) + the `executescript()` implicit-COMMIT discipline (CLAUDE.md gotcha).

   Back-compat: existing 30 resolved discrepancies in production all carry `resolution='acknowledged_immaterial'`. The rebuild copies them as-is; no value rewriting. Sub-bundle C's new resolution values apply only to NEW discrepancies after migration v19 lands.

2. **NEW column** — `ambiguity_kind TEXT NULL CHECK (ambiguity_kind IS NULL OR ambiguity_kind IN ('multi_partial_vs_consolidated', 'multi_match_within_window', 'unknown_schwab_subtype', 'field_shape_incompatible', 'schwab_returned_no_match', 'validator_rejected', 'unsupported'))`.

   Constraint: `ambiguity_kind` IS NOT NULL ONLY when `resolution='pending_ambiguity_resolution'` OR `resolution='operator_resolved_ambiguity'` (i.e., on tier-2 discrepancies). Phase 9 R1 Minor #4 precedent (defense-in-depth schema CHECK) — Sub-bundle C adds:
   `CHECK ((ambiguity_kind IS NULL AND resolution NOT IN ('pending_ambiguity_resolution','operator_resolved_ambiguity')) OR (ambiguity_kind IS NOT NULL AND resolution IN ('pending_ambiguity_resolution','operator_resolved_ambiguity')))`.

   Note: this cross-column CHECK adds defense-in-depth; the binding app-layer enforcement happens in the auto-correction service (§5.2) when it stamps resolution + ambiguity_kind atomically.

3. **NEW index** — `CREATE INDEX ix_reconciliation_discrepancies_pending_ambiguity ON reconciliation_discrepancies(ambiguity_kind, created_at) WHERE resolution = 'pending_ambiguity_resolution'`. Partial-index on the tier-2 backlog surface; supports the Tier-2 surface (§6.2) "show me all pending ambiguities by kind" query.

#### §3.2.1 `ambiguity_kind` enum coverage

| Value | Classifier emits when | Type-specific resolution choices (§6.2 menu) |
|---|---|---|
| `multi_partial_vs_consolidated` | Schwab side has N (N ≥ 2) partial fills for a single journal-side consolidated fill (or vice-versa) matching by `(ticker, date, total_qty)` | (a) Split journal into matching partials; (b) Keep journal consolidated + use Schwab VWAP as `fills.price`; (c) Keep journal as-is + mark `schwab_partial_fill_aggregation_acknowledged`; (d) Operator-custom |
| `multi_match_within_window` | Multiple Schwab transactions could plausibly match one journal fill within the matching window (e.g., 2 Schwab fills at same price + qty within the same day for the same ticker) | (a) Pick Schwab record #N (operator selects from listed candidates); (b) Mark journal unmatched (no Schwab record corresponds — possible manual-entry mistake at trade-entry time); (c) Operator-custom |
| `unknown_schwab_subtype` | Schwab transaction type is unrecognized by the classifier's `schwab_subtype` lookup (e.g., a new Schwab transaction kind classifier has no `discrepancy_type` mapping for) | (a) Acknowledge + log for code update (V2 sub-bundle adds classifier coverage); (b) Operator-custom |
| `field_shape_incompatible` | Schwab payload shape doesn't fit the journal schema's column structure (e.g., a fractional-shares-as-string field where journal expects INTEGER quantity) | (a) Acknowledge + log for code update; (b) Operator-custom transformation |
| `schwab_returned_no_match` | Schwab API queried for the relevant period returned NO matching record for a journal fill (`actual={"matched": null}`); journal fill might be entirely manual-entry-mistake OR a non-Schwab-routed broker fill that operator typed-from-memory after-the-fact | (a) Mark journal unmatched (Schwab has no record — operator decides if mistake or pre-Schwab-arc legacy); (b) Operator-supplied source-of-truth (operator types in the real values); (c) Acknowledge + leave journal as-is + mark as `'acknowledged_immaterial'` (tier-3 path) |
| `validator_rejected` | Tier-1 correction target would violate a Phase 7 fills validator OR Phase 6 review_log invariant OR Phase 9 risk_policy at-trade-time-locked reference; classifier downgrades automatically | (a) Acknowledge (correction would violate journal invariants; system cannot apply); (b) Operator-supplied alternative value (must still pass validator chain at apply time); (c) Operator-supplied policy override (writes a new risk_policy version + retries — V2 path; V1 = NOT supported) |
| `unsupported` | Catch-all for shapes the classifier doesn't know how to disposition; emits a WARNING log line tagged with the discrepancy payload so V2 can extend coverage | (a) Operator-supplied source-of-truth (manual override); (b) Acknowledge + leave as-is |

Coverage check against §1.4 production discrepancies: CVGI 41 hits tier-1 (no kind needed); DHC 39 hits `multi_partial_vs_consolidated`; VSAT 40 is classifier-data-dependent (may hit either tier or any of `multi_partial_vs_consolidated` / `schwab_returned_no_match` per actual Schwab payload). All three covered without `unsupported` fallback.

### §3.3 `review_log` column addition

**SHIPPED schema (migration 0013 + 0017):** `review_log` carries frozen aggregates per Phase 6 + the new policy stamp `risk_policy_id_at_review_completion` (Phase 9 §3.1.1).

**Sub-bundle C change:**

1. **NEW column** — `superseded_by_correction_id INTEGER NULL REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL`.

   Marks a review row as "post-review correction has been applied to one or more of its constituent fills" so Phase 10 dashboards + operator-facing review-detail surfaces can render the badge `"Frozen aggregates were computed before a reconciliation correction applied on YYYY-MM-DD; the frozen R-multiple may not match current fills"`.

   Mechanic: the auto-correction service (§5) at apply-time queries which `review_log` rows are CADENCE-PERIOD-anchored against the affected fill's owning trade's close date — `review_log` itself is cadence-period-grain with NO `trade_id` column (Phase 6 migration 0013), so the JOIN is via the affected trade's close date falling within the review's `[period_start, period_end]`. Per §5.4 step 9 for the binding lookup SQL sketch. UPDATEs `review_log.superseded_by_correction_id` for each matched review row. Operator can opt to re-review (Phase 6 surface; out of Sub-bundle C scope to wire UI for this — surface in V2). Frozen aggregates remain frozen (per §9.1 LOCK).

   ALTER mechanic: `ALTER TABLE review_log ADD COLUMN superseded_by_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` — nullable column add, no rebuild needed.

### §3.4 `schwab_api_calls` column addition

**Sub-bundle C change:**

1. **NEW column** — `linked_correction_id INTEGER NULL REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL`.

   Mirrors `linked_snapshot_id` + `linked_reconciliation_run_id` precedent (Phase 11 §3.x); preserves the bidirectional provenance chase. When the auto-correction service fetches additional Schwab data to confirm a tier-1 target value or to break a tier-2 ambiguity (e.g., re-query the trader API with a wider time window), the new `schwab_api_calls` row gets `linked_correction_id` set + `surface='cli'` (V1 — no new surface enum value).

   ALTER mechanic: `ALTER TABLE schwab_api_calls ADD COLUMN linked_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` — nullable add, no rebuild.

### §3.5 `trade_events` CHECK enum widening

**SHIPPED schema (migration 0014 §11):** `trade_events.event_type CHECK IN ('entry','stop_adjust','note','exit','flag','pre_trade_edit')`.

**Sub-bundle C change:**

1. **CHECK enum widening** — add `'reconciliation_auto_correct'` as a 7th value.

   Rationale: when auto-correction modifies a fill on an active trade, emitting a `trade_events` row at the trade grain gives the trade-detail dashboard surface (Phase 7 — `/trades/{id}`) a single audit log to render alongside entries / stops / exits / pre-trade-edits without requiring the dashboard to JOIN against `reconciliation_corrections` directly. The `trade_events.payload_json` carries `{correction_id, affected_table, affected_row_id, field_name, pre, applied}`. The forensic trail STILL lives on `reconciliation_corrections`; this is a per-trade convenience surface.

   Mechanic: table-rebuild precedent already established in migration 0014 §11. Writing-plans drafts.

   Single-event-per-correction discipline: ONE `trade_events` row per `reconciliation_corrections` row when `affected_table='fills'` AND that fill's `trade_id` is non-NULL. Cash-movement-grain corrections or future account-level corrections do NOT emit `trade_events` rows (no trade attribution).

### §3.6 `fills.reconciliation_status` enum — NO WIDENING V1 (LOCK)

Per §1.5 + §9.2: V1 does NOT widen `fills.reconciliation_status`. The 5 existing values (`'unreconciled','reconciled_match','reconciled_discrepancy','reconciled_discrepancy_resolved','manual_override'`) cover the fill-grain reconciliation state adequately. Per-discrepancy `resolution` carries the meaningful Sub-bundle C state.

When auto-correction applies a tier-1 correction to a fill, the service does flip `fills.reconciliation_status` from whatever it was (likely `'unreconciled'`) to `'reconciled_discrepancy_resolved'`. No new enum values needed.

V2 candidate: if a discriminating need surfaces (e.g., Phase 10 dashboard wants per-fill provenance signaling distinguishable from operator-resolved-ambiguity vs auto-applied), Sub-bundle V2 adds `'auto_corrected_from_schwab'` value to fills.reconciliation_status. Banked.

### §3.7 `reconciliation_runs` state machine — NO EXTENSION (LOCK)

Per §1.5 + §9.4: V1 does NOT extend `reconciliation_runs.state` enum. Stays at `('running','completed','failed')`. Classification + tier-1 apply happen INSIDE the `state='running'` window before COMMIT. The `reconciliation_corrections` audit table carries the per-correction lifecycle; no need to extend run-grain states. `reconciliation_runs.summary_json` is extended with new top-level keys `{"tier1_applied_count": N, "tier2_pending_count": M, "tier3_overridden_count": K}` written at apply-time — a JSON-shape extension, not a schema-CHECK change.

### §3.8 Schema migration shape (v18 → v19)

Single atomic migration `0019_phase12_bundle_C_auto_correct_reconciliation.sql` lands ALL Sub-bundle C schema changes in one pass per Phase 9 §A.0 LOCK precedent (foundation sub-bundle C.A ships first; B/C/D consume code-side only):

1. `CREATE TABLE reconciliation_corrections (...)` + 4 indexes (§3.1).
2. `ALTER TABLE reconciliation_discrepancies ADD COLUMN ambiguity_kind TEXT REFERENCES <none>` — note: SQLite doesn't allow adding NEW CHECK to an existing column via ADD COLUMN; the new column carries its own CHECK at ADD time. The cross-column CHECK on (`ambiguity_kind`, `resolution`) joint requires a table-rebuild.
3. Table-rebuild `reconciliation_discrepancies` to (a) widen `resolution` CHECK enum from 5 to 9 values; (b) add cross-column CHECK between `ambiguity_kind` and `resolution`; (c) preserve all existing rows + columns + indexes. The rebuild mirrors migration 0014's trades-table-rebuild discipline + the `executescript()` implicit-COMMIT wrapper at the runner level (CLAUDE.md gotcha) — writing-plans must use explicit BEGIN / COMMIT in the migration SQL.
4. `ALTER TABLE review_log ADD COLUMN superseded_by_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` (§3.3).
5. `ALTER TABLE schwab_api_calls ADD COLUMN linked_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` (§3.4).
6. Table-rebuild `trade_events` to widen `event_type` CHECK enum (§3.5).
7. New partial index `ix_reconciliation_discrepancies_pending_ambiguity` (§3.2).
8. `UPDATE schema_version SET version = 19` (LAST statement; Phase 9 §A.0 R1 Critical #1 precedent).

Migration backup gate: runner-level `swing-pre-phase12-bundle-c-migration-<ISO>.db` fires when `current_version == 18 AND target >= 19`. Writing-plans wires (Phase 9 precedent).

---

## §4 Ambiguity classifier design

### §4.1 Module placement

New module: `swing/trades/reconciliation_classifier.py` (parallel to `swing/trades/reconciliation_auto_correct.py` per §5; both inside `swing/trades/` because they operate at the service-composition grain and consume Phase 7 fills / Phase 9 discrepancy / Phase 11 Schwab API surfaces).

Pure-function module — NO DB writes, NO Schwab API calls, NO transaction management. Classifier consumes pre-fetched payloads + journal rows + returns a decision struct. The service (§5) is the I/O surface; classifier is the pure logic.

### §4.2 Public interface (LOCKED)

```
def classify_discrepancy(
    discrepancy: ReconciliationDiscrepancy,
    *,
    source_payload: dict | None,
    journal_row: dict | None,
    validator_chain: ValidatorChainCallable | None = None,
) -> ClassificationResult: ...
```

Where:

- `discrepancy: ReconciliationDiscrepancy` — the Phase 9 dataclass row (carries discrepancy_type + field_name + expected/actual JSON + linked FKs).
- `source_payload: dict | None` — the parsed Schwab API response slice (or TOS CSV row slice) that produced the discrepancy. NULL when source-side data is unavailable at classification time (e.g., backfill running without re-fetching).
- `journal_row: dict | None` — the parsed journal-side row (`fills` / `trades` / `cash_movements` / `account_equity_snapshots`) that the discrepancy referenced. NULL when journal-side row has been deleted post-emit (rare; classifier emits `tier=2, ambiguity_kind='unsupported'`).
- `validator_chain: ValidatorChainCallable | None` — dependency-injected dry-run validator callable. If provided + classifier proposes a tier-1 correction, classifier calls validator_chain(correction_target) → bool; on False, downgrades to tier-2 with `ambiguity_kind='validator_rejected'`. If NULL, classifier skips the dry-run + service handles validator chain at apply time (defense-in-depth; service ALWAYS runs validators at apply time per §5.5 regardless of whether classifier did).

`ClassificationResult` shape (NamedTuple or dataclass):

```
tier: int  # 1 or 2
ambiguity_kind: str | None  # NULL on tier=1; one of §3.2.1 enum values on tier=2
correction_target: dict | None  # {field_name: target_value, ...} on tier=1; NULL on tier=2
correction_reason: str  # human-readable classifier rationale; always non-empty
candidate_choices: list[dict] | None  # tier=2 only; list of per-resolution-choice prebuilt option dicts for the Tier-2 surface to render (e.g., for multi_match_within_window: each candidate Schwab transaction as a separate choice dict)
```

Determinism principle: classifier MUST be deterministic on a fixed input. Reproducible classification is a binding contract for testability + audit replay.

### §4.3 Per-discrepancy-type sub-classifiers

The classifier dispatches on `discrepancy.discrepancy_type` (10-value Phase 9 enum) into per-type sub-classifiers. Each sub-classifier owns its narrow domain logic.

#### §4.3.1 `entry_price_mismatch` sub-classifier

- INPUT: discrepancy (carrying `expected_value_json={"entry_price": X}` and `actual_value_json={"entry_price": Y}`), journal_row (the journal `fills` row), source_payload (the Schwab transaction).
- LOGIC:
  - If journal_row's (ticker, date, quantity) match source_payload's (ticker, date, quantity) exactly AND only `price` differs → tier=1, `correction_target={'price': source_payload['price']}`.
  - If source_payload has multiple transactions matching (ticker, date) within some tolerance window → tier=2, `ambiguity_kind='multi_match_within_window'`.
  - If source_payload is None → tier=2, `ambiguity_kind='schwab_returned_no_match'`.
- VALIDATOR-DOWN-CHECK: dry-run validator chain on `{'price': source_payload['price']}`; if validator rejects (e.g., price ≤ 0, or downstream `current_avg_cost` recompute fails), downgrade to tier=2 with `ambiguity_kind='validator_rejected'`.

This is the CVGI 41 path (§10.1).

#### §4.3.2 `unmatched_open_fill` sub-classifier

- INPUT: discrepancy (carrying `actual_value_json={"matched": null}` or similar), journal_row (the journal `fills` row), source_payload (the Schwab transactions list for the period — potentially multiple, potentially zero).
- LOGIC:
  - If source_payload has ZERO matching Schwab transactions → tier=2, `ambiguity_kind='schwab_returned_no_match'`. Choices: operator marks unmatched OR supplies source-of-truth OR acknowledges as tier-3.
  - If source_payload has ONE Schwab transaction matching (ticker, date) but with different price OR quantity → tier=2, `ambiguity_kind='multi_match_within_window'` IF source quantity / price diverges enough to suggest mis-attribution; OR redirects to `entry_price_mismatch` sub-classifier (§4.3.1) IF (ticker, date, qty) all match and only price differs (operator-friendly redirect).
  - If source_payload has TWO OR MORE Schwab transactions whose total quantity matches journal_row.quantity → tier=2, `ambiguity_kind='multi_partial_vs_consolidated'`. Candidate choices include the partial-split path (with each partial as a candidate) and the VWAP-consolidate path.
  - If source_payload has TWO OR MORE Schwab transactions whose totals DON'T match → tier=2, `ambiguity_kind='multi_match_within_window'`. Choices: operator picks one OR marks unmatched.

This is the DHC 39 + VSAT 40 path (§10.2 + §10.3).

#### §4.3.3 `unmatched_close_fill` sub-classifier

- Mirrors `unmatched_open_fill` symmetrically for close-side fills. Same ambiguity_kind values; same candidate choice menus. Writing-plans clarifies any close-side asymmetries (e.g., trim vs final-exit semantics impact the validator chain at apply time).

#### §4.3.4 `stop_mismatch` sub-classifier

- Stop mismatches are produced when journal `trades.current_stop` differs from broker/source-side stop value. Common Phase 9 Sub-bundle B + C cause was the Bundle E parser-gap-now-closed family.
- LOGIC:
  - If source_payload has ONE active stop matching (ticker) → tier=1, `correction_target={'current_stop': source_payload['stop_price']}`.
  - If source_payload has MULTIPLE active stops (rare; usually a Schwab CSV multi-section issue) → tier=2, `ambiguity_kind='multi_match_within_window'`.
  - If source_payload has ZERO active stops AND journal_row has a stop → tier=2, `ambiguity_kind='schwab_returned_no_match'` (operator decides: journal-stop wrong, OR Schwab GTC expired, OR position closed at broker but still open in journal — separate diagnosis paths).
- VALIDATOR-DOWN-CHECK: stop must satisfy `stop > 0` AND (for entered trades) `stop < entry_price` AND must not violate Phase 9 risk_policy stop-tighten advisory rules — but Sub-bundle C is conservative: validator chain at apply time enforces stop > 0 AND FK existence; risk_policy advisory checks are advisories not validators (per §1.6 lock — advisory ≠ blocking). Stops outside advisory thresholds STILL classify as tier-1 + apply; the advisory surfaces at the Phase 10 dashboard, not the validator chain.

#### §4.3.5 `position_qty_mismatch` sub-classifier

- Journal `trades.current_size` (computed via `fills` aggregate) differs from broker position quantity.
- LOGIC:
  - If broker has ONE position record matching ticker AND journal has fill-history that should sum to broker qty AND fills count is small (≤ 3) → tier=2, `ambiguity_kind='multi_match_within_window'` per fill (operator decides which fill is wrong-qty); fully-automated fill-qty correction is risky without per-fill source attribution.
  - If broker has ZERO positions AND journal has open trade → tier=2, `ambiguity_kind='schwab_returned_no_match'` (position closed at broker but still open in journal — likely missing exit fill).
  - Most position_qty_mismatch cases route to tier-2 in V1; tier-1 auto-quantity-correction requires per-fill broker attribution that V1 Schwab API doesn't provide cleanly. V2 candidate for richer auto-correct on this discrepancy type.

#### §4.3.6 `close_price_mismatch` sub-classifier

- Phase 8 daily_management snapshot vs broker close price differs.
- LOGIC: this is a price-mismatch on a HISTORICAL snapshot, not a fill. Sub-bundle C treats this as tier-2 `unknown_schwab_subtype` UNLESS the snapshot is recent AND clearly attributable to a specific Schwab quote response. Historical close-price corrections are V2 candidate (re-imports OHLCV history; out of Sub-bundle C scope).

#### §4.3.7 `cash_movement_mismatch` sub-classifier

- Journal `cash_movements` row differs from source-reported cash movement.
- LOGIC:
  - If source_payload has ONE matching cash movement by (date, amount within tolerance, type) → tier=1, `correction_target={...specific fields differ...}`.
  - Otherwise tier=2 with appropriate ambiguity_kind.
- V1 conservative: cash movement classification is small-N; expect most to route to tier-2 operator review.

#### §4.3.8 `sector_tamper` sub-classifier

- Phase 9 Sub-bundle D sector/industry tamper discrepancies. Operator-action-only; tier-3 path always. Classifier emits `tier=2, ambiguity_kind='unknown_schwab_subtype'` because Schwab doesn't supply sector data — these aren't "Schwab is truth" discrepancies. Operator resolution is the only path.

#### §4.3.9 `snapshot_mismatch` sub-classifier

- Similar to `close_price_mismatch` — historical snapshot data; V2 candidate; V1 routes to tier-2.

#### §4.3.10 `equity_delta` sub-classifier

- Phase 9 Sub-bundle C cross-bundle wiring already emits these. Journal `account_equity_snapshots.equity_dollars` differs from source-reported equity by > $10.
- LOGIC:
  - If the journal snapshot is the most-recent at-date snapshot AND source has a clear post-date Schwab equity reading → tier=2, `ambiguity_kind='field_shape_incompatible'` because cash-basis vs MTM semantics divergence is a known V2 candidate (operator-locked at Phase 9 Sub-bundle C ship-time; banked at `docs/phase3e-todo.md` 2026-05-12). Operator-resolution path; not tier-1.
  - Auto-correcting equity from Schwab API would require Phase 10 cash-basis-vs-MTM formalization first. Out of Sub-bundle C scope; tier-2 only.

### §4.4 Determinism principle (LOCKED per §1.3 lock #2-tier-2-default)

The classifier defaults to tier-2 when in doubt. False-positive tier-1 silently corrupts journal; false-positive tier-2 just defers to operator (no harm).

Concretely:

- Any sub-classifier with multiple plausible target values → tier-2 always.
- Any sub-classifier with payload shape it doesn't recognize → tier-2, `ambiguity_kind='unsupported'`.
- Any sub-classifier whose `correction_target` would change MORE THAN ONE field at once → tier-2 unless explicitly designed as multi-field tier-1 (§3.1.1 `correction_set_id` ALLOWS multi-field tier-1 but per-discrepancy-type sub-classifier must opt in; V1 default opt-in is FALSE for every sub-classifier above except potentially `cash_movement_mismatch` where the structure naturally bundles fields).
- Any sub-classifier with stale source data (source_payload supplied at classifier time differs from current Schwab API response) → tier-2 if the staleness is detected; V1 does not detect staleness, so this is V2 candidate.

### §4.5 Classifier failure-mode contract

If a sub-classifier raises an unexpected exception (malformed payload, FK lookup failure, etc.), the dispatcher catches + logs WARNING + emits `(tier=2, ambiguity_kind='unsupported', correction_target=None, correction_reason=f"classifier exception: {type(e).__name__}: {e}")`. Discrepancy stays unresolved-but-flagged; operator can disposition via tier-2 surface.

Pipeline / CLI never crashes on classifier errors (graceful degradation contract; Phase 11 forward-binding lesson #2).

### §4.6 Validator chain integration

The classifier optionally invokes a dependency-injected validator chain on tier-1 proposals BEFORE returning. Validator chain validates the proposed correction against the journal table's invariants:

For `fills` corrections:
- `quantity > 0`
- `price > 0`
- `trade_id` FK exists + active
- `action` is in CHECK enum
- `_recompute_aggregates` doesn't produce `current_size < 0` after applying

For `trades` corrections:
- `current_stop > 0`
- `current_stop > 0 AND (state != 'reviewed' OR is the legacy-edit path)`

For `cash_movements` corrections:
- `amount` sign is consistent with `movement_type` (debit / credit)
- `date` parses as ISO

If any validator returns False (or raises), classifier downgrades to tier-2 with `ambiguity_kind='validator_rejected'` + the validator's rejection reason in `correction_reason`.

The service (§5) ALWAYS re-runs validators at apply time even when classifier already ran them — defense-in-depth (schema state may have shifted between classifier run + apply call in the same transaction or in a backfill scenario; per Phase 11 lesson family on state-shift races).

---

## §5 Auto-correction service architecture

### §5.1 Module placement

New module: `swing/trades/reconciliation_auto_correct.py` (parallel to `swing/trades/reconciliation.py` for consistency with existing service-layer naming).

### §5.2 Public interface (LOCKED)

```
def apply_tier1_correction(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    classification: ClassificationResult,
    schwab_api_call_id: int | None = None,
    risk_policy_id: int | None = None,
    correction_reason: str | None = None,
) -> CorrectionResult: ...


def apply_tier2_resolution(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_custom_payload: dict | None = None,
    operator_reason: str,
    risk_policy_id: int | None = None,
) -> CorrectionResult: ...


def apply_tier3_override(
    conn: sqlite3.Connection,
    *,
    correction_id: int,  # the prior correction being overridden
    operator_truth_value: dict,
    operator_reason: str,
    risk_policy_id: int | None = None,
) -> CorrectionResult: ...
```

`CorrectionResult` dataclass exposes: `correction_id`, `affected_table`, `affected_row_id`, `field_name`, `applied_value_json`, `correction_action`, `notes`.

### §5.3 Transactional discipline (LOCKED — Phase 8 + Phase 9 lesson family)

All three service entry points OWN their transactions:

- Reject caller-held transaction at entry: `if conn.in_transaction: raise CallerHeldTransactionError(...)` mirroring `swing/trades/reconciliation.py:run_tos_reconciliation`'s shipped pattern.
- `conn.execute("BEGIN IMMEDIATE")` at entry.
- `conn.commit()` at the single happy-path COMMIT.
- `conn.rollback()` on any exception path (defensive; suppressed via `contextlib.suppress(sqlite3.Error)`); re-raise the exception.

Idempotency contract:

- Before applying, SELECT the discrepancy's current `resolution`. If already `auto_corrected_from_schwab` OR `operator_resolved_ambiguity` OR `operator_overridden`, the service returns the existing correction_id (idempotent re-invocation) WITHOUT writing a new audit row.
- The `reconciliation_corrections` table has no UNIQUE constraint on `(discrepancy_id, correction_action)` because the override chain LEGITIMATELY produces multiple rows per discrepancy. Idempotency is enforced at the service layer via the SELECT-first pattern, NOT at schema layer.

### §5.4 Atomic flow for `apply_tier1_correction`

1. REJECT caller-held transaction.
2. BEGIN IMMEDIATE.
3. SELECT discrepancy row by `discrepancy_id`. If NULL → raise. If `resolution != 'unresolved'` → return idempotent existing-correction lookup.
4. Re-run validator chain on `classification.correction_target` (defense-in-depth — schema state may have shifted since classifier ran). If validator REJECTS, ROLLBACK + raise `ValidatorRejectedError` (caller decides; the typical caller — reconciliation flow pivot §7 — falls through to tier-2 path on this exception).
5. UPDATE the affected journal table (`fills` / `trades` / `cash_movements` / `account_equity_snapshots`) via the existing repo helpers (NOT REPLACE — UPDATE only per CLAUDE.md gotcha). For multi-column atomic corrections (rare V1; §3.1.1), execute all UPDATEs serially.
6. For `fills` corrections specifically, call the existing `_recompute_aggregates` (the same path Phase 7 `insert_fill_with_event` uses) so `trades.current_size` / `current_avg_cost` / `last_fill_at` stay consistent.
7. INSERT one `reconciliation_corrections` row per (affected_table, affected_row_id, field_name) tuple. For multi-column atomic corrections (rare V1), bundle via `correction_set_id` (§3.1.1).
8. UPDATE `reconciliation_discrepancies` SET `resolution='auto_corrected_from_schwab'`, `resolution_reason=correction_reason`, `resolved_at=NOW`, `resolved_by='auto'`.
9. UPDATE affected `review_log` rows' `superseded_by_correction_id` to point to the new correction (for closed-reviewed trades' fills). **Codex R1 Major #1 fix (LOCKED):** `review_log` is cadence-period-grain — it has NO `trade_id` column. The shipped schema (migration 0013 lines 44-70) has `(review_type, period_start, period_end, completed_date, ...)`; Phase 6's `complete_review_atomic` helper (`swing/data/repos/review_log.py:213-238`) derives the per-review trade set by joining closed trades whose final exit/close date falls in `[period_start, period_end]`. The Sub-bundle C supersede-lookup mirrors that derivation:
   - For `affected_table='fills'`: compute the `trade_id` of the affected fill → compute that trade's effective close date (`MAX(fill.fill_datetime)` over its `'exit'`/`'stop'` action fills) → match against review_log rows where `state='completed'` (`completed_date IS NOT NULL`) AND `period_start <= <trade_close_date> <= period_end`.
   - For `affected_table='trades'` (rare; e.g., stop_mismatch corrections): same trade-close-date derivation against review_log periods.
   - For `affected_table='cash_movements'` or `'account_equity_snapshots'`: skip — these aren't trade-grain so review_log doesn't reference them.
   - Concrete SQL sketch (writing-plans verifies + tightens):
     ```
     -- For a corrected fill at affected_row_id = <fill_id>:
     SELECT rl.review_id
     FROM review_log rl
     WHERE rl.completed_date IS NOT NULL
       AND rl.period_start <= <trade_close_date_iso>
       AND <trade_close_date_iso> <= rl.period_end;
     ```
   - Per §9.1 LOCK frozen aggregates stay frozen; only the FK pointer is set on each matched review_log row. If the affected fill belongs to a trade whose close date doesn't fall into any review's period (e.g., the trade is still OPEN at correction time — CVGI 41 path, §10.1), zero `review_log` rows are touched.
10. Emit one `trade_events` row with `event_type='reconciliation_auto_correct'` (per §3.5) when `affected_table='fills'` AND the affected fill's trade_id is non-NULL. Payload JSON carries the correction details for trade-detail UI consumption.
11. COMMIT.

Failure-mode contract: any exception between step 4 and step 11 triggers ROLLBACK; the discrepancy stays `unresolved`. Caller (§7 flow pivot) catches `ValidatorRejectedError` specifically and re-routes to tier-2 path with `ambiguity_kind='validator_rejected'`.

### §5.5 Validator chain composition (Codex R1 Major #2 fix — LOCKED)

**Important clarification:** shipped repo modules (`swing/data/repos/fills.py`, `trades.py`, `cash_movements.py`, `account_equity_snapshots.py`) do NOT currently expose dedicated callable validator functions. The invariants today are enforced primarily via (a) SQLite schema `CHECK` constraints + FK constraints at INSERT/UPDATE time, plus (b) `_recompute_aggregates` invariants triggered indirectly by `insert_fill_with_event` / similar service entry points (e.g., `swing/data/repos/fills.py:79-105`). There is no `def validate_fill(...)` callable a third party can import + dry-run.

**Sub-bundle C ships a new shim module** at sub-sub-bundle C.B time: `swing/trades/reconciliation_validators.py`. This shim exposes pure-function dry-run validators that mirror the schema's CHECK + FK constraints WITHOUT performing the actual INSERT/UPDATE:

| Validator | Mirrors | Surfaces |
|---|---|---|
| `validate_fill_correction(conn, fill_id, proposed_updates: dict) -> bool` | migration 0014 `fills` CHECK + FK constraints + Phase 7 `_recompute_aggregates` invariants (post-correction `current_size >= 0`) | for `affected_table='fills'` corrections |
| `validate_trade_correction(conn, trade_id, proposed_updates: dict) -> bool` | migration 0014 `trades` CHECK + state transitions (`current_stop > 0` etc.) | for `affected_table='trades'` corrections |
| `validate_cash_movement_correction(conn, movement_id, proposed_updates: dict) -> bool` | shipped `cash_movements` CHECK + FK | for `affected_table='cash_movements'` corrections |
| `validate_snapshot_correction(conn, snapshot_id, proposed_updates: dict) -> bool` | migration 0017 `account_equity_snapshots.equity_dollars > 0` etc. | for `affected_table='account_equity_snapshots'` corrections |

Each validator: reads the current row from the conn (no UPDATE) → applies the proposed updates to a Python dict copy → checks the resulting dict against the schema-CHECK-mirror predicates → for `fills`, additionally simulates `_recompute_aggregates`'s aggregate formula via a SELECT-based dry-run → returns True/False (plus a rejection reason on False via a paired-out variable or exception).

**Composition path:** the auto-correction service (`apply_tier1_correction` + inner) composes the right validator based on `affected_table` + invokes BEFORE the actual UPDATE in step 4 (per §5.4 atomic flow). On False return, raises `ValidatorRejectedError` with the rejection reason — caller (§7.1 pivot or §6 CLI) catches + downgrades to tier-2 with `ambiguity_kind='validator_rejected'`.

**Phase 6 review_log invariants are NOT validators** (they're frozen aggregates by design; auto-correction RETAINS them per §9.1 — only updates the superseded_by pointer). The validator chain does NOT consult `review_log` at all.

**Phase 9 risk_policy at-trade-time-locked references** are advisories, NOT validators (per §1.6 lock — advisory ≠ blocking). When auto-correction touches `fills.price` on an entry fill whose trade has a non-NULL `risk_policy_id_at_lock`, the resulting `current_avg_cost` is still computed (and may trip the policy's `scratch_epsilon_R` or `max_account_risk_per_trade_pct` advisory thresholds) — but these surface as Phase 10 dashboard tripwires, NOT as validator rejections. The validator chain stops at schema-CHECK-mirror + FK-existence + Phase 7 aggregate invariants.

**V2 candidate:** refactor the shim into the repo modules themselves so the validator functions become first-class on `swing/data/repos/*.py`. Banked. V1 keeps the validators in `swing/trades/reconciliation_validators.py` to scope the change to Sub-bundle C without touching existing repo files.

### §5.6 Atomic flow for `apply_tier2_resolution`

Operator picks a `choice_code` from the per-ambiguity_kind menu (§6.2). The service:

1. REJECT caller-held transaction; BEGIN IMMEDIATE.
2. SELECT discrepancy; verify `resolution='pending_ambiguity_resolution'`.
3. Dispatch on `(ambiguity_kind, choice_code)` to a per-pair handler. Each handler builds an explicit `ClassificationResult`-equivalent struct + invokes the same step 4-11 sequence as `apply_tier1_correction` (with `correction_action='operator_resolved_ambiguity'` + `applied_by='operator'`).
4. For multi-fill split-into-partials (DHC 39 path), the handler:
   - DELETEs the consolidated journal fill (`fills` table; `_recompute_aggregates` runs).
   - INSERTs N partial fills via the existing `insert_fill_with_event` path (each gets its own `fill_id`).
   - Writes N + 1 `reconciliation_corrections` rows bundled under one `correction_set_id` (the deletion as a row with `correction_action='operator_resolved_ambiguity'` + `field_name='__delete__'` sentinel; the inserts as rows with field_name='__insert__' sentinel). Writing-plans clarifies sentinel handling.
   - The `correction_set_id` plus the sentinel approach preserves forensic trail without overloading the per-field row shape.

This sentinel approach is the cleanest path; alternative would be a separate `reconciliation_correction_operations` join table, but that introduces additional schema. V1 sticks with sentinels; V2 may formalize if multi-operation corrections become common.

### §5.7 Atomic flow for `apply_tier3_override`

Tier-3 is operator-initiated AFTER a tier-1 correction has been applied. Operator-supplied truth value supersedes the auto-applied value.

1. REJECT caller-held; BEGIN IMMEDIATE.
2. SELECT the prior `reconciliation_corrections` row by `correction_id`. Verify it's the current row (`superseded_by_correction_id IS NULL`).
3. INSERT NEW `reconciliation_corrections` row with `correction_action='operator_overridden'`, `applied_by='operator'`, `operator_truth_value_json` populated, `pre_correction_value_json` = the prior row's `applied_value_json` (since we're reverting AWAY from that), `applied_value_json` = the operator-truth value.
4. UPDATE prior row's `superseded_by_correction_id` = new row's `correction_id`.
5. UPDATE the affected journal table to the operator-truth value (UPDATE only; no REPLACE).
6. `_recompute_aggregates` if `affected_table='fills'`.
7. UPDATE `reconciliation_discrepancies.resolution='operator_overridden'`.
8. UPDATE `review_log.superseded_by_correction_id` for affected review rows (same logic as §5.4 step 9).
9. Emit `trade_events` row (per §3.5).
10. COMMIT.

### §5.8 Surface awareness

Auto-correction service is consumed by:

- **Pipeline** (`surface='pipeline'` per Phase 11 forward-binding lesson #4) — when `_step_schwab_orders` runs reconciliation that emits classifiable discrepancies; the service applies tier-1 inline within the pipeline transaction window.
- **CLI** (`surface='cli'`) — when operator runs `swing journal reconcile-schwab` OR the Tier-2 resolution CLI OR the backfill CLI.

V1 does NOT add a `surface='web'` value (banked V2 candidate from Sub-bundle B). When the auto-correction service fetches additional Schwab API data (e.g., to break ambiguity in C.D backfill), it inherits the caller's surface attribution + emits a `schwab_api_calls` audit row accordingly.

### §5.9 Sandbox short-circuit

Per Phase 11 sandbox gating gotcha: under `environment='sandbox'`, the auto-correction service writes a WARNING log line + returns a `CorrectionResult` with `correction_id=None` + `notes='sandbox: domain write short-circuited'`. The discrepancy stays `unresolved`. Domain rows are NOT written. Audit rows in `schwab_api_calls` (if classifier fetched Schwab data) ARE written per shipped gating discipline. This prevents synthetic sandbox Schwab data from contaminating production journal.

---

## §6 Tier-2 ambiguity-resolution surface (operator-facing)

### §6.1 Decision: CLI-first V1; web V2 (LOCKED)

**Decision rationale:**
- Sub-bundle C scope is already large (4 sub-sub-bundles; new audit table + classifier + service + flow pivot + 5 schema changes + backfill path).
- Web HTMX form-driven surface has 4 cumulative browser-only failure modes per CLAUDE.md gotchas (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted; mistake_cost_confidence Python `or ""` collision). Adding a web surface to Sub-bundle C compounds the browser-only-gate risk.
- CLI is the canonical operator surface for discrepancy resolution per Phase 9 Sub-bundle B `swing journal discrepancy resolve` precedent (currently shipped). Extending the existing CLI surface group is the lowest-risk path.
- V2 dispatch can layer web `/discrepancies/{id}/resolve` analogous to `/schwab/setup` (Phase 12 Sub-bundle B precedent) once Sub-bundle C ships and operator validates the choice taxonomy in real production use. The CLI's choice-code enumeration becomes the binding contract for the V2 web form's option list.

V2 web surface candidate (NOT designed here; banked): `/discrepancies` route group with index + per-discrepancy resolve route mirroring the `/schwab/setup` HTMX pattern. The web route consumes the same CLI's underlying service layer functions; only the user-facing form layer is new.

### §6.2 CLI surface shape (LOCKED)

Extend existing `swing journal discrepancy` CLI group (Phase 9 Sub-bundle B precedent) with NEW subcommand `resolve-ambiguity`:

```
swing journal discrepancy resolve-ambiguity <discrepancy_id> \
    --choice <choice_code> \
    [--custom-value '<json>'] \
    [--reason <free-text>]
```

Where `<choice_code>` is a per-ambiguity_kind code per §6.2.1 table. `--custom-value` is REQUIRED when `choice_code` ends in `_custom`; supplies the operator's structured payload as JSON. `--reason` is REQUIRED on all resolutions per §5.6.

Plus NEW `list-pending-ambiguities` subcommand for operator discovery:

```
swing journal discrepancy list-pending-ambiguities \
    [--ambiguity-kind <kind>] \
    [--ticker <ticker>]
```

Returns the rows in `reconciliation_discrepancies WHERE resolution='pending_ambiguity_resolution'` joined to discriminating context (ticker, trade_id, fill_id, ambiguity_kind, candidate choices summary). Output is a table per Phase 9 Sub-bundle B's discrepancy listing CLI precedent.

Plus NEW `show-ambiguity` subcommand for per-discrepancy detail:

```
swing journal discrepancy show-ambiguity <discrepancy_id>
```

Renders the full discrepancy detail + the per-ambiguity_kind candidate choice menu with codes the operator can pass to `resolve-ambiguity`. This is the operator's "menu" — viewing it tells them exactly which `--choice` codes are valid.

#### §6.2.1 Per-ambiguity_kind choice codes (LOCKED)

| `ambiguity_kind` | Choice code | Description | Action |
|---|---|---|---|
| `multi_partial_vs_consolidated` | `split_into_partials` | Replace journal consolidated fill with N partial fills from Schwab side | DELETE consolidated fill; INSERT N partial fills; `correction_set_id` group; resolution → `operator_resolved_ambiguity` |
| `multi_partial_vs_consolidated` | `consolidate_using_schwab_vwap` | Keep journal consolidated row; UPDATE journal price to Schwab VWAP | UPDATE `fills.price` to Schwab VWAP; resolution → `operator_resolved_ambiguity` |
| `multi_partial_vs_consolidated` | `keep_journal_as_is` | Acknowledge that Schwab partials aggregate to journal's consolidated row; operator-acknowledged "journal's aggregation is intentional" | NO journal mutation; INSERT audit row with `correction_action='operator_resolved_ambiguity'` + `correction_choice='keep_journal_as_is'` + `applied_value_json` == `pre_correction_value_json`; resolution → `operator_resolved_ambiguity` |
| `multi_partial_vs_consolidated` | `custom` | Operator supplies arbitrary structured payload | `--custom-value` provides the payload; service applies as multi-column correction; resolution → `operator_resolved_ambiguity` |
| `multi_match_within_window` | `pick_schwab_record_<N>` | Pick the Nth Schwab candidate (N is an index into the candidate list from `show-ambiguity`) | UPDATE journal fields to match Nth candidate; resolution → `operator_resolved_ambiguity` |
| `multi_match_within_window` | `mark_unmatched` | Journal entry has no corresponding broker record (operator decision: keep journal-as-recorded; no Schwab attribution) | NO journal mutation; INSERT audit row with `correction_action='operator_resolved_ambiguity'` + `correction_choice='mark_unmatched'`; resolution → `operator_resolved_ambiguity` |
| `multi_match_within_window` | `custom` | Operator supplies arbitrary payload | `--custom-value`; resolution → `operator_resolved_ambiguity` |
| `unknown_schwab_subtype` | `acknowledge` | Acknowledge + log for V2 code update (no mutation; operator opts to defer until classifier widens) | NO journal mutation; INSERT audit row with `correction_action='operator_resolved_ambiguity'` + `correction_choice='acknowledge'` + the unrecognized Schwab subtype string in `correction_reason` so V2 has a discovery surface; resolution → `operator_resolved_ambiguity` |
| `unknown_schwab_subtype` | `custom` | Operator-custom transformation | `--custom-value`; resolution → `operator_resolved_ambiguity` |
| `field_shape_incompatible` | `acknowledge` | Acknowledge + log (no mutation) | NO journal mutation; audit row per above; resolution → `operator_resolved_ambiguity` |
| `field_shape_incompatible` | `custom` | Operator-custom transformation | `--custom-value`; resolution → `operator_resolved_ambiguity` |
| `schwab_returned_no_match` | `mark_unmatched` | Schwab has no record; operator decides journal stays as-is (e.g., pre-Schwab-arc legacy fill OR non-Schwab-routed broker fill that operator typed-from-memory) | NO journal mutation; audit row with `correction_choice='mark_unmatched'` + operator-supplied reason; resolution → `operator_resolved_ambiguity` |
| `schwab_returned_no_match` | `operator_truth` | Operator supplies the real values (e.g., a manually-entered non-Schwab-routed fill that needs price/qty correction from operator's records) | `--custom-value` carries the truth; service applies as multi-column correction; resolution → `operator_resolved_ambiguity` |
| `validator_rejected` | `acknowledge` | Correction would violate invariants; system cannot apply (no mutation; operator opts to leave divergence as-is) | NO journal mutation; audit row records the rejected target value + the validator's rejection reason in `correction_reason`; resolution → `operator_resolved_ambiguity` |
| `validator_rejected` | `operator_alternative` | Operator supplies alternative correction value that passes validators | `--custom-value`; service re-runs validator chain on operator-supplied value; resolution → `operator_resolved_ambiguity` |
| `unsupported` | `operator_truth` | Operator-custom resolution | `--custom-value`; resolution → `operator_resolved_ambiguity` |
| `unsupported` | `acknowledge` | Leave journal as-is (no mutation; classifier didn't know the shape; operator dispositions without applying) | NO journal mutation; audit row with `correction_choice='acknowledge'` + operator-supplied reason explaining; resolution → `operator_resolved_ambiguity` |

Each `<choice_code>` is a binding contract: the service's per-pair handler (per §5.6) is keyed on `(ambiguity_kind, choice_code)`. Writing-plans enumerates the handler-function map; each handler is a small focused function.

**Codex R1 Critical #1 fix (LOCKED):** EVERY tier-2 resolution lands as `resolution='operator_resolved_ambiguity'` + a `reconciliation_corrections` audit row, even when the operator's choice is "no journal mutation" (e.g., `keep_journal_as_is`, `mark_unmatched`, `acknowledge`). The audit row records the operator's explicit no-mutation choice with `applied_value_json` == `pre_correction_value_json` + `correction_action='operator_resolved_ambiguity'` + `correction_choice='<choice_code>'`. This preserves the architectural-pivot intent: every new discrepancy gets an explicit audit-row disposition; `acknowledged_immaterial` is RESERVED for the narrow Tier-3 case where operator declares Schwab itself wrong (§6.4). Earlier brainstorm wording that emitted `acknowledged_immaterial` for "no mutation" tier-2 outcomes would have preserved the operator-triage bypass the bundle closes; the discipline above replaces it.

### §6.3 Operator workflow

Operator daily/weekly cadence (mirrors Phase 9 Sub-bundle B `swing journal discrepancy list --unresolved --material` precedent):

1. After a reconciliation run completes, operator runs `swing journal discrepancy list-pending-ambiguities` to see the tier-2 backlog.
2. For each pending discrepancy, operator runs `swing journal discrepancy show-ambiguity <id>` to see the candidate choices.
3. Operator picks a `<choice_code>` + supplies `--reason` (REQUIRED) + supplies `--custom-value` if the code ends in `_custom`.
4. Service applies the resolution + writes audit + sets `resolution='operator_resolved_ambiguity'`.

Phase 10 dashboard already surfaces an "unresolved material discrepancies (N)" banner on every base-layout VM (per Phase 10 Sub-bundle A T-A.7 + Sub-bundle E T-E.3 retrofit); the count includes both `'unresolved'` AND `'pending_ambiguity_resolution'` rows that are material — so the operator sees the backlog at every page render. Writing-plans verifies the banner predicate covers the new resolution value.

### §6.4 Tier-3 override CLI

NEW subcommand `swing journal discrepancy override-correction`:

```
swing journal discrepancy override-correction <correction_id> \
    --truth-value '<json>' \
    --reason <free-text>
```

REQUIRES `--reason` (mandatory; operator must explain why Schwab is wrong). Service calls `apply_tier3_override`. New correction row is INSERTed; prior row chained via `superseded_by_correction_id`.

---

## §7 Reconciliation flow pivot

### §7.1 Pivot at `run_schwab_reconciliation` call site (LOCKED)

The shipped `run_schwab_reconciliation` (defined in `swing/trades/schwab_reconciliation.py` — distinct from the TOS-side `swing/trades/reconciliation.py:run_tos_reconciliation`) currently emits discrepancies + returns. The pivoted flow:

```
run_schwab_reconciliation(conn, ...) → ReconciliationRun:
  STEP 1 (PHASE 9 PRESERVED): emit discrepancies via existing emitter
  STEP 2 (NEW): for each newly-emitted discrepancy:
    # Per-correction SAVEPOINT (Codex R1 Critical #3 fix):
    sp_name = f"correction_sp_{disc.id}"
    conn.execute(f"SAVEPOINT {sp_name}")
    try:
      classification = classify_discrepancy(discrepancy, ...)
      if classification.tier == 1:
        try:
          _apply_tier1_correction_inner(conn, discrepancy_id=disc.id, classification=...)
          conn.execute(f"RELEASE SAVEPOINT {sp_name}")
          counters.tier1_applied += 1
        except ValidatorRejectedError as e:
          # ROLLBACK TO undoes the partial UPDATEs the inner function made before
          # raising; per SQLite spec, ROLLBACK TO does NOT release the savepoint —
          # subsequent RELEASE is required to remove it from the active stack.
          # Outer transaction continues unaffected (Codex R2 Minor #1 comment fix).
          conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
          conn.execute(f"RELEASE SAVEPOINT {sp_name}")
          # Fall through to tier-2 path with validator_rejected.
          UPDATE discrepancies SET resolution='pending_ambiguity_resolution',
            ambiguity_kind='validator_rejected', resolution_reason=str(e)
          counters.tier2_pending += 1
      else:  # tier == 2
        UPDATE discrepancies SET resolution='pending_ambiguity_resolution',
          ambiguity_kind=classification.ambiguity_kind,
          resolution_reason=classification.correction_reason
        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
        counters.tier2_pending += 1
    except Exception as e:
      # Graceful degradation per Phase 11 lesson #2.
      # ROLLBACK TO undoes any partial state from this iteration (including
      # any partial UPDATE that occurred before the exception); the outer
      # reconciliation transaction is preserved (other discrepancies' applied
      # corrections + emitted discrepancy rows stay committed at outer commit).
      conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
      conn.execute(f"RELEASE SAVEPOINT {sp_name}")
      WARNING log "classifier or apply exception for discrepancy {disc.id}: {e}"
      # Leave discrepancy as `resolution='unresolved'` — operator dispositions later.
      counters.tier_errored += 1
  STEP 3 (NEW): update run summary_json with counters; commit (outer BEGIN IMMEDIATE)
```

**Critical contract (Codex R1 Critical #3 fix — LOCKED):** Per-discrepancy SAVEPOINT discipline. The outer reconciliation transaction (started by `BEGIN IMMEDIATE` at the run's entry) owns the commit boundary. Each per-discrepancy classify+apply iteration is wrapped in `SAVEPOINT correction_sp_<id>` / `RELEASE` on success / `ROLLBACK TO ... + RELEASE` on any exception. Without the SAVEPOINT, an exception AFTER `UPDATE fills` but BEFORE the audit row INSERT + discrepancy resolution UPDATE would leave a silent journal mutation when the outer transaction commits. With the SAVEPOINT, ROLLBACK TO undoes the partial journal mutation atomically before falling through to graceful-degradation pathway.

SAVEPOINT names use the discrepancy_id to guarantee uniqueness within the outer transaction (each iteration's savepoint is independent; nested savepoints not required for V1).

Classification + apply happen INSIDE the run's existing outer transaction; the auto-correction service's standalone outer-transaction discipline is at the SERVICE-COMPOSED-FROM-OUTSIDE level (CLI / backfill / tier-2 resolve invocations), not at this nested level (see §7.3 transaction nesting note for the outer/inner split).

### §7.2 Pivot at `run_tos_reconciliation` call site — OPEN QUESTION

Per §14: should the TOS-CSV reconciliation flow ALSO pivot to classify + apply, or only Schwab? Locked tentative: YES, both pivot. Rationale: tier-1 entry_price_mismatch corrections from TOS CSV (when TOS data is more trustworthy than operator-typed-from-memory journal) are equally meaningful; the "Schwab is truth" framing extends to "the source-of-truth side of the reconciliation IS truth" — TOS CSV is the source-of-truth side when invoked.

Caveat: TOS CSV source IS operator-controlled (operator chose which CSV to upload); the trust premise is weaker than Schwab API which is uncontroversially the broker's actual ledger. Open question for orchestrator: do we keep `run_tos_reconciliation` unchanged (V1 conservative) OR pivot both?

Tentative spec recommendation: PIVOT BOTH. Per §14.OQ-2 banked for triage. Writing-plans triages.

### §7.3 Transaction nesting concern

The auto-correction service (§5) owns its own transaction (rejects caller-held). The reconciliation flow pivot calls into the service from within `run_schwab_reconciliation`'s already-open transaction — direct invocation would raise `CallerHeldTransactionError`.

**Resolution:** the pivoted flow inside `run_schwab_reconciliation` does NOT call the public `apply_tier1_correction` service API. Instead, the pivot refactors the service into a public OUTER function (own-transaction) + a private INNER function (caller-controlled-transaction) following the Phase 8 CLAUDE.md gotcha discipline ("when composing multiple side-effects under one atomic boundary, call the REPO-level functions directly; do NOT route through service-level wrappers that own their own transaction"). The pivot calls the INNER function with the reconciliation run's transaction.

Module shape:

```
swing/trades/reconciliation_auto_correct.py:
  def apply_tier1_correction(conn, ...):  # PUBLIC; owns transaction
      if conn.in_transaction: raise CallerHeldTransactionError
      conn.execute("BEGIN IMMEDIATE")
      try:
          _apply_tier1_correction_inner(conn, ...)
          conn.commit()
      except Exception:
          conn.rollback()
          raise

  def _apply_tier1_correction_inner(conn, ...):  # PRIVATE; caller-controlled
      # All §5.4 logic except BEGIN IMMEDIATE / COMMIT / ROLLBACK.
      ...
```

The pivoted `run_schwab_reconciliation` calls `_apply_tier1_correction_inner`. Standalone backfill CLI + standalone operator CLI calls the public `apply_tier1_correction`. Same for tier-2 + tier-3 (matched inner/outer split).

This is the canonical pattern Phase 8 codified for `record_event_log` (Phase 8 ship). Sub-bundle C inherits.

### §7.4 Failure-mode contract (graceful degradation; Phase 11 lesson #2)

Reconciliation run-pivot NEVER crashes on classification or apply errors. The dispatcher catches broad exceptions per Phase 11 forward-binding lesson #2:

- Classifier exception → defaults to tier-2-unsupported (per §4.5).
- `_apply_tier1_correction_inner` exception → log WARNING + leave discrepancy `unresolved`.
- `ValidatorRejectedError` → re-route to tier-2 with `validator_rejected` (per §7.1 pivot logic).

Pipeline-mode invocation: under `surface='pipeline'`, the pipeline step never raises out; reconciliation_run row commits as `state='completed'` with the failed-correction count surfaced in `summary_json`. Operator's daily cycle catches the failures via dashboard banner / pending-ambiguities listing.

### §7.5 Operator-visible CLI output

`swing schwab fetch --all` output (the operator-facing CLI command that triggers reconciliation) gains new lines reporting tier-1 applied + tier-2 pending counts. Writing-plans formats:

```
Reconciliation: 12 matched, 2 mismatches detected.
  - Tier 1 auto-corrected: 1 (CVGI entry_price_mismatch)
  - Tier 2 pending operator review: 1 (DHC unmatched_open_fill — multi_partial_vs_consolidated)
View pending ambiguities: swing journal discrepancy list-pending-ambiguities
Resolve a specific one: swing journal discrepancy resolve-ambiguity <discrepancy_id> --choice <code> --reason <text>
```

The CLI output ALSO surfaces in `briefing.md` per Phase 11 Sub-bundle D briefing.md banner pattern: a new section "Reconciliation status" enumerates pending tier-2 count + recent tier-1 applied count. Writing-plans wires.

---

## §8 Backfill path

### §8.1 Purpose

One-time operator-initiated CLI sweep that runs the classifier across all existing `reconciliation_discrepancies` rows where `resolution='unresolved'` and applies tier-1 / sets tier-2 ambiguity_kind / leaves tier-3-eligible cases alone.

At dispatch time, production has 3 unresolved-material discrepancies (39 DHC + 40 VSAT + 41 CVGI). The backfill resolves these 3 + any future unresolved-but-pre-pivot discrepancies (none expected since pivot ships at C.C; but defensive).

### §8.2 CLI surface (LOCKED)

NEW subcommand:

```
swing journal reconcile-backfill [--apply] [--dry-run] [--ticker <ticker>] [--limit <N>] [--no-pass-2-on-dry-run] [--retry-pass-2-failures]
```

Default mode: `--dry-run`. Prints a classification matrix showing each unresolved discrepancy + its proposed classification + (if tier-1) the proposed correction target. **Codex R2 Major #1 fix (LOCKED) — dry-run mutation scope:** dry-run does NOT mutate journal tables (`fills`/`trades`/`cash_movements`/`account_equity_snapshots`), does NOT mutate `reconciliation_discrepancies.resolution`/`ambiguity_kind`, does NOT INSERT `reconciliation_corrections`, does NOT INSERT `trade_events`, does NOT UPDATE `review_log.superseded_by_correction_id`. Dry-run DOES write `schwab_api_calls` audit rows when Pass-2 re-fetches occur (§8.4 Pass 2 is a read of source-of-truth; the audit row is the read's audit-trail contract, not a journal mutation). The CLI prints an explicit advisory before any Pass-2 re-fetches: `"dry-run will consume Schwab API quota for N discrepancies and write audit rows; only journal-side mutations are skipped"`. Operator can pass `--no-pass-2-on-dry-run` to skip Pass-2 entirely on dry-run (resulting in tier-2 `unsupported` for Pass-2-required discrepancies in the projected matrix; trade-off: less accurate dry-run projection). V2 candidate: a no-audit preview mode that caches Pass-2 responses in memory without writing audit rows; banked.

`--apply` flag: actually executes the tier-1 corrections + tier-2 stamps. Without `--apply`, only dry-run.

`--ticker` and `--limit`: scope/throttle flags for safety during initial operator dispositioning of the existing 3 cases.

`--retry-pass-2-failures`: opt-in flag that re-attempts Pass 2 on discrepancies whose prior backfill attempt failed Pass-2 fetch (persisted as `resolution='pending_ambiguity_resolution'` + `ambiguity_kind='unsupported'` + `resolution_reason` containing `"Pass 2 re-fetch failed"` — see §8.3 + §8.4 #3). Without this flag, those discrepancies are SKIPPED on rerun per the §8.3 idempotency contract.

### §8.3 Idempotency (Codex R2 Major #2 fix — LOCKED)

Re-running `swing journal reconcile-backfill --apply` is safe: discrepancies whose `resolution != 'unresolved'` are SKIPPED (per the SELECT-first idempotency contract at §5.3 AND consistent with the Pass-2-failure persisted state in §8.4 #3). The CLI prints a summary like `"Skipped 27 already-resolved discrepancies"` AND `"Skipped 3 Pass-2-failed discrepancies (use --retry-pass-2-failures to retry)"` when any Pass-2-failed cases exist.

**Pass-2-failed discrepancies are persisted as `resolution='pending_ambiguity_resolution'`** (see §8.4 #3); they are NOT in `resolution='unresolved'` state, so the §8.3 skip rule covers them. Operator paths to dispose of them: (a) re-run backfill with `--retry-pass-2-failures` (re-attempts Pass 2 only on these rows); (b) resolve manually via `swing journal discrepancy resolve-ambiguity <id> --choice acknowledge --reason ...` (no journal mutation; per §6.2.1 menu).

### §8.4 Classifier source-payload sourcing

The backfill needs source_payload (Schwab API responses) to classify. The shipped `schwab_api_calls` audit table records the CALL metadata (endpoint, status, timing, signature hash) but NOT the FULL RESPONSE BODY. The reconciliation logic at run time consumed the response inline + emitted small slices into the discrepancy's `expected_value_json` + `actual_value_json`. Per Codex R1 verification of shipped emitter at `swing/trades/schwab_reconciliation.py:439-449`: unmatched_open_fill emits `actual_value_json={"matched": null}` and NO partials/candidate enumeration. The persisted JSON is insufficient for any tier-1 classification beyond "Schwab returned no single-fill match"; it cannot distinguish `multi_partial_vs_consolidated` vs `multi_match_within_window` vs genuine `schwab_returned_no_match` cases.

**Decision (LOCKED — Codex R1 Critical #2 fix):** the backfill source-payload sourcing is a **two-pass** contract:

1. **Pass 1 — persisted-JSON-only classification.** Read the discrepancy's `expected_value_json` + `actual_value_json` + the journal row referenced by FK. Run the classifier. For most discrepancy types where the persisted JSON carries enough signal (e.g., `entry_price_mismatch` carries `{"price": X}` on both sides — CVGI 41 path), the classifier emits a definitive tier-1 or tier-2 result here. Pass 1 needs ZERO Schwab API calls.

2. **Pass 2 — re-fetch Schwab when Pass 1 emits `ambiguity_kind='unsupported'` or persisted JSON is provably insufficient.** For `unmatched_open_fill` / `unmatched_close_fill` discrepancies with `actual_value_json={"matched": null}` (the persisted shape on shipped emitter), Pass 1 cannot distinguish partials-vs-no-match-vs-multi-match. **Pass 2 calls `get_account_orders` at `swing/integrations/schwab/trader.py:329` (NOT `get_account_transactions` — Codex R2 Critical #1 verification: `SchwabTransactionResponse` at `swing/integrations/schwab/models.py:207-218` carries only transaction_id+date+type+net_amount+description with NO symbol/quantity/price; only the orders endpoint's `SchwabOrderResponse` at `models.py:133-203` carries `instrument_symbol`+`quantity`+`price`+`instruction` needed for fill-level partial-fill matching).** Each Pass 2 fetch consumes one `schwab_api_calls` audit row with `surface='cli'` (operator-initiated backfill) + `linked_correction_id` set when a correction is ultimately written. Per Phase 11 sandbox gating (§9.7), under `environment='sandbox'` Pass 2 returns no domain data; the classifier emits tier-2 `unsupported` with rationale "sandbox: cannot re-fetch source-canonical payload".

   **V1 mapper limitation — tier-1 redirect FORBIDDEN when source is order-level (Codex R3 Critical #1 + Major #1 fix — LOCKED):** the shipped V1 `SchwabOrderResponse.price` field maps from the order's top-level `price` (limit-price) OR `stopPrice` per the shipped mapper at `swing/integrations/schwab/mappers.py:223-229`, NOT from per-execution fill prices. A limit/stop price can differ from the actual execution price, so auto-correcting `fills.price` to match `SchwabOrderResponse.price` would silently corrupt the journal — a textbook violation of the §4.4 determinism principle. Pass 2 returning `SchwabOrderResponse` data SHALL NOT be used for tier-1 price corrections. The classifier behavior under Pass 2 with order-level source data is **tier-2 always**:

   - 0 orders returned → tier=2, `ambiguity_kind='schwab_returned_no_match'`.
   - 1 order returned (single Schwab order; cannot disambiguate single-execution vs multiple-executions due to V1 mapper limitation) → tier=2, `ambiguity_kind='unknown_schwab_subtype'` with rationale "Schwab returned a single order at order-grain; V1 mapper does not expose per-execution fill detail; cannot determine whether journal price reflects actual execution. Operator dispositions via `--choice acknowledge` (keep journal as-is) or `--choice operator_truth` (operator supplies real fill price from broker statement)".
   - 2+ orders returned summing to journal qty → tier=2, `ambiguity_kind='multi_partial_vs_consolidated'` (operator picks split / VWAP-consolidate / keep-consolidated / custom — but operator's choice does NOT auto-derive from `SchwabOrderResponse.price`; operator must SUPPLY the truth value via `--custom-value` if they want price corrections, OR pick `keep_journal_as_is` if confident the operator-typed price is correct).
   - 2+ orders returned NOT summing to journal qty → tier=2, `ambiguity_kind='multi_match_within_window'`.
   - In every case: Pass 2 with order-level source data MAY confirm PRESENCE of matching Schwab activity but MAY NOT auto-derive fill-level prices.

   V2 candidate: expand the mapper to surface `orderActivityCollection[].executionLegs[]` for per-execution fill detail. Once shipped, sub-bundle V2 of Sub-bundle C can revisit the determinism boundary and consider tier-1 price corrections from execution-leg data. Banked at `docs/phase3e-todo.md` for post-Phase-12 standalone dispatch.

   **Persisted-JSON vs Pass-2-re-fetched data distinction (LOCKED):** the Pass-2-FORBIDDEN rule applies to NEW data the classifier re-fetches mid-backfill, NOT to the persisted `actual_value_json` already emitted by the shipped reconciliation at original-run time. Tier-1 from persisted `entry_price_mismatch` JSON IS allowed (CVGI 41 path). Important caveat for transparency: the shipped reconciliation at `swing/trades/schwab_reconciliation.py:454-479` compares against `SchwabOrderResponse.price` which is order-level (limit/stop price), NOT execution-level — verified at Codex R3 verification of shipped mappers. The operator has locked CVGI 41 as tier-1 despite this order-level-vs-execution distinction; the underlying assumption is that for typical Schwab-routed swing-trade orders, the order/limit price closely matches actual execution price. Sub-bundle C does NOT re-litigate this operator-lock (§1.3 framing); the order-level basis is the SAME limitation already accepted at original-discrepancy-emit time.

   **Net effect:** the discriminating examples in §10.2 + §10.3 (DHC 39 + VSAT 40) resolve to tier-2 ambiguity-resolution regardless of Pass 2 response shape because the persisted JSON for `unmatched_open_fill` is `{"matched": null}` (no price/qty/execution data to redirect from). CVGI 41 (§10.1) resolves to tier-1 from persisted `entry_price_mismatch` JSON. The asymmetric treatment of persisted-JSON-tier-1 vs Pass-2-re-fetched-tier-1 is the cleanest path that respects both the operator-lock on CVGI 41 AND the determinism principle for unmatched-fill backfill resolution.

3. **Pass 2 failure-mode (Codex R2 Major #2 fix — LOCKED persisted state).** If the Schwab re-fetch fails (auth_failed / rate_limited / network error), the classifier emits tier-2 `unsupported` with rationale "Pass 2 re-fetch failed: <reason>". The persisted state under `--apply` is `resolution='pending_ambiguity_resolution'` + `ambiguity_kind='unsupported'` + `resolution_reason` carrying the failure reason. This is the SAME persisted state as any other tier-2 `unsupported` classification; downstream operator surfaces (CLI `list-pending-ambiguities`, Phase 10 dashboard banner) treat them identically.

   **Re-run handling:** the §8.3 idempotency contract SKIPS Pass-2-failed discrepancies on subsequent backfill `--apply` runs by default (they are no longer in `'unresolved'` state). Operator can opt-in to retry via `--retry-pass-2-failures` flag (§8.2) which scopes the iteration to rows where `resolution='pending_ambiguity_resolution' AND ambiguity_kind='unsupported' AND resolution_reason LIKE '%Pass 2 re-fetch failed%'`. Each retry re-fetches Schwab + writes a new `schwab_api_calls` audit row (intentional retry-history trail). Alternative operator path: `swing journal discrepancy resolve-ambiguity <id> --choice acknowledge --reason ...` to disposition without retrying Schwab.

4. **Per-discrepancy-type table — which discrepancies need Pass 2?**

| `discrepancy_type` | Pass-1 sufficient? | Why |
|---|---|---|
| `entry_price_mismatch` | YES — `{"price": X}` shapes on both sides; tier-1 deterministic | shipped emitter at `schwab_reconciliation.py:469-474` |
| `close_price_mismatch` | YES — same shape | shipped emitter at `schwab_reconciliation.py:455-479` |
| `stop_mismatch` | LIKELY (persisted price values + journal `current_stop`) | writing-plans verifies |
| `position_qty_mismatch` | LIKELY (persisted qty values) | writing-plans verifies |
| `unmatched_open_fill` | NO — Pass 2 required | shipped emitter persists `{"matched": null}` only (lines 439-449) |
| `unmatched_close_fill` | NO — same as above | symmetric emitter |
| `cash_movement_mismatch` | LIKELY (persisted amount + date) | writing-plans verifies |
| `equity_delta` | YES — persisted equity values | shipped emitter at `swing/trades/reconciliation.py:373-388` |
| `sector_tamper` | YES — no Schwab data dependency | sector data is journal-side only |
| `snapshot_mismatch` | LIKELY (persisted snapshot fields) | writing-plans verifies |

Of the three production discrepancies (CVGI 41 + DHC 39 + VSAT 40): CVGI 41 is `entry_price_mismatch` → Pass 1 sufficient. DHC 39 + VSAT 40 are `unmatched_open_fill` → Pass 2 required.

5. **Idempotency under Pass 2 (Codex R2 Major #2 fix — LOCKED).** Re-running the backfill against ANY non-`'unresolved'` discrepancy is a no-op (skip per §8.3) by default — this includes Pass-2-failed discrepancies which are persisted as `resolution='pending_ambiguity_resolution'`. Operator opts INTO retrying Pass-2-failed cases via the `--retry-pass-2-failures` flag (§8.2 + §8.4 #3); each opt-in retry re-fetches Schwab + writes a new `schwab_api_calls` audit row (intentional retry-history trail). Operators NOT opting in must disposition Pass-2-failed cases manually via `swing journal discrepancy resolve-ambiguity`.

V2 candidate: a separate API response cache table that preserves full Schwab API response bodies for backfill replay, eliminating Pass 2 re-fetches for already-fetched window. Banked at `docs/phase3e-todo.md` for post-Phase-12 standalone dispatch.

### §8.5 Backfill flow

1. SELECT all discrepancies WHERE `resolution='unresolved'` (optionally filtered by `--ticker` / `--limit`).
2. For each:
   a. Reconstruct `source_payload` from discrepancy `actual_value_json` (and/or re-fetch Schwab if the payload is insufficient).
   b. Fetch `journal_row` via discrepancy FK columns (`fill_id` / `trade_id` / `cash_movement_id`).
   c. Call `classify_discrepancy(discrepancy, source_payload, journal_row)`.
   d. If `--dry-run`: print classification row.
   e. Else (`--apply`): dispatch on tier — tier-1 → `apply_tier1_correction`; tier-2 → set ambiguity_kind + leave for operator.
3. Print final summary: N tier-1 applied / M tier-2 stamped / K errored / L skipped-already-resolved.

### §8.6 Backfill applied to existing 3 discrepancies — see §10 walkthroughs

§10.1 (CVGI 41) shows the tier-1 auto-apply path under backfill.
§10.2 (DHC 39) shows the tier-2 stamp path under backfill.
§10.3 (VSAT 40) shows the classifier-data-dependent path under backfill.

---

## §9 Lifecycle integration

### §9.1 Phase 6 review_log freezing — RETAIN + mark superseded (LOCKED)

When auto-correction modifies a fill on a closed-reviewed trade:

- Frozen aggregates on `review_log` (e.g., `realized_R_if_plan_followed`, `actual_realized_R_effective`, `mistake_cost_R`, process-grade fields, frozen `risk_policy_id_at_review_completion`) stay frozen. They are the historical record at review-completion time.
- The auto-correction service UPDATEs `review_log.superseded_by_correction_id` (NEW FK column per §3.3) to point to the new `reconciliation_corrections.correction_id`.
- Phase 10 dashboard surfaces (`/metrics/*`) consume the FK to render a badge:
   `"Review computed at policy_id=X with fills as of YYYY-MM-DD; superseded by a reconciliation correction on YYYY-MM-DD. Frozen R-multiple ≠ current fills"`.
- Operator can opt to re-review (Phase 6 surface; Sub-bundle C does NOT wire UI for this — surface in V2 if needed). The frozen aggregates do NOT change.

Rationale: Phase 8 `is_superseded` precedent. Preserves audit trail. Phase 6 review IS the at-the-time computation; rewriting frozen aggregates retroactively would corrupt the audit trail and break Phase 10's cohort metrics which depend on review-snapshot semantics.

### §9.2 Phase 7 fills.reconciliation_status — NO V1 ENUM WIDENING (LOCKED)

Per §1.5 + §3.6: the existing 5 values cover Sub-bundle C's needs adequately. Auto-correction sets `fills.reconciliation_status='reconciled_discrepancy_resolved'` on the affected fill, matching the existing enum. Per-discrepancy `resolution` carries the meaningful Sub-bundle C state.

V2 candidate: add `'auto_corrected_from_schwab'` if Phase 10 dashboard needs per-fill provenance distinguishable from operator-resolved-ambiguity. Banked.

### §9.3 Phase 7 trade_events — ENUM WIDENING (+1 value) (LOCKED)

Per §3.5: add `'reconciliation_auto_correct'` value to `trade_events.event_type` CHECK. Each `reconciliation_corrections` row affecting a fill with a non-NULL trade_id emits one `trade_events` row at the trade grain. The forensic trail STILL lives on `reconciliation_corrections`; this is a per-trade convenience surface for trade-detail UI.

Single-event-per-correction discipline: ONE `trade_events` row per `reconciliation_corrections` row when `affected_table='fills'` AND that fill's `trade_id` is non-NULL. Multi-fill corrections (DHC split path) produce one `trade_events` row per resulting fill, all chained via the `correction_set_id`.

### §9.4 Phase 8 daily_management_records — RETAIN as historical (LOCKED)

No retroactive adjustment. Phase 8 snapshots are point-in-time observations. They self-stamp `position_capital_denominator_dollars` + `trail_MA_period_days` + `mfe_mae_precision_level` per row (Phase 9 §3.1.1 R1 M5 family already shipped). Auto-correction post-snapshot doesn't rewrite snapshot rows.

If a snapshot row's underlying fill is corrected post-snapshot-emit, the snapshot's recorded position state may diverge from the corrected current state. This is intentional — snapshots ARE historical observations. Phase 10 dashboard surfaces compute "current state" off live `fills` + `trades` queries, not off snapshot replay; the snapshots are for audit-trail use only.

V2 candidate: a `daily_management_records.superseded_by_correction_id` column mirroring `review_log` could be added if a Phase 10 metric materializes on snapshot replay AND that metric is operationally important. Banked.

### §9.5 Phase 9 reconciliation_runs.state — NO EXTENSION (LOCKED)

Per §1.5 + §3.7: stays at `('running','completed','failed')`. Classification + tier-1 apply happen INSIDE the `state='running'` window. The new tier counters live in `summary_json`.

### §9.6 Phase 9 reconciliation_discrepancies.resolution + ambiguity_kind — WIDENING (LOCKED)

Per §3.2: 5 → 9 resolution values; NEW ambiguity_kind column with 7-value CHECK enum + cross-column CHECK between `(ambiguity_kind, resolution)`. Table-rebuild required (CHECK widening). Migration v18→v19 lands the rebuild atomically.

### §9.7 Phase 11 Schwab API sandbox gating — PRESERVED (LOCKED)

Auto-correction under `environment='sandbox'`:
- Schwab API calls during classification: SHORT-CIRCUITED to no-op (existing Phase 11 gating). Classifier receives None for source_payload + emits tier-2 `unsupported`.
- Auto-correction service apply path: SHORT-CIRCUITED at service-entry (per §5.9). Writes WARNING log + returns no-op CorrectionResult. Discrepancy stays unresolved.

Production-only auto-correction. Sandbox-and-test paths don't write to the journal.

### §9.8 Phase 12 Sub-bundle B credentials cascade — PRESERVED (LOCKED)

Auto-correction service constructs its own Schwab client (when needed) via the existing `swing/integrations/schwab/__init__.py` factory + `apply_overrides(cfg)` discipline (Phase 12 Sub-bundle B forward-binding lesson #6). Single-Client-instance per process discipline preserved. When invoked from the pipeline flow pivot (§7.1), the service reuses the pipeline's existing Schwab client instance instead of constructing a new one (Phase 12 Sub-bundle A forward-binding lesson #12 — T-A.3 gap pre-emption pattern: wire the Schwab client through the callsite, don't hardcode `client=None`).

---

## §10 Discriminating-example walkthroughs (BINDING)

### §10.1 CVGI 41 — tier-1 auto-correct end-to-end

**Setup:**
- `reconciliation_discrepancies.discrepancy_id=41`
- `discrepancy_type='entry_price_mismatch'`
- `field_name='price'`
- `trade_id=<CVGI trade>`
- `fill_id=9`
- `ticker='CVGI'`
- `expected_value_json={"price": 5.23}` (journal value at emit time per shipped emitter `swing/trades/schwab_reconciliation.py:469-474` — Codex R1 Major #4 verification)
- `actual_value_json={"price": 5.30}` (Schwab value at emit time per same shipped emitter)
- `delta_text='+$0.07 (schwab minus journal)'` (matches shipped emitter format at `schwab_reconciliation.py:475-478`)
- `material_to_review=1`
- `resolution='unresolved'`

**Backfill Pass 1 (§8.4) — persisted JSON sufficient:** `entry_price_mismatch` is Pass-1-sufficient per §8.4 table: the persisted `expected_value_json={"price": 5.23}` + `actual_value_json={"price": 5.30}` carry the deterministic information the classifier needs. Pass 2 not required. Zero `schwab_api_calls` audit rows consumed by the classifier.

**Classifier (§4.3.1 entry_price_mismatch sub-classifier):**
- INPUT: discrepancy, source_payload = `actual_value_json={"price": 5.30}` plus the matching Schwab transaction's (ticker, date, qty) implied by the discrepancy's FK to journal `fills.fill_id=9`, journal_row = the `fills.fill_id=9` row.
- LOGIC: (ticker, date, quantity) match exactly between journal and source; only price differs.
- VALIDATOR DRY-RUN: `{'price': 5.30}` against fills validators → price > 0 ✓; `_recompute_aggregates` updates `trades.current_avg_cost` to $5.30 (single entry fill); no negative current_size; no FK breaks. PASSES.
- OUTPUT: `ClassificationResult(tier=1, ambiguity_kind=None, correction_target={'price': 5.30}, correction_reason="entry_price_mismatch on (CVGI, fill_id=9): journal $5.23 vs Schwab $5.30; single-fill match; tier-1 auto-correct", candidate_choices=None)`.

**Service (`apply_tier1_correction`):**
1. REJECT caller-held tx. BEGIN IMMEDIATE.
2. SELECT discrepancy 41; resolution = 'unresolved' → proceed.
3. Re-run validator chain on `{'price': 5.30}` → PASSES.
4. `UPDATE fills SET price = 5.30 WHERE fill_id = 9`.
5. `_recompute_aggregates(conn, trade_id=<CVGI>)` → `trades.current_avg_cost = 5.30`.
6. INSERT `reconciliation_corrections` row:
   - `discrepancy_id=41`
   - `correction_action='auto_applied'`
   - `affected_table='fills'`
   - `affected_row_id=9`
   - `field_name='price'`
   - `pre_correction_value_json={"price": 5.23}`
   - `source_canonical_value_json={"price": 5.30}`
   - `applied_value_json={"price": 5.30}`
   - `operator_truth_value_json=NULL`
   - `applied_at=<now>`, `applied_by='auto'`
   - `correction_set_id=NULL`
   - `superseded_by_correction_id=NULL`
   - `risk_policy_id_at_correction=<active>`
   - `schwab_api_call_id=<call_id from current reconciliation_run>`
   - `reconciliation_run_id=<current run>`
   - `correction_reason="entry_price_mismatch ... tier-1 auto-correct"`
7. UPDATE `reconciliation_discrepancies SET resolution='auto_corrected_from_schwab', resolution_reason=..., resolved_at=<now>, resolved_by='auto' WHERE discrepancy_id=41`.
8. Compute CVGI trade's close date — CVGI is OPEN at this time (no exit/stop fills), so the trade has no close date; the review_log cadence-period lookup (per §5.4 step 9 SQL sketch) returns 0 rows; no `review_log.superseded_by_correction_id` UPDATEs. (Walkthrough applies the §5.4 step 9 mechanic correctly even when the result is empty.)
9. INSERT `trade_events` row: `event_type='reconciliation_auto_correct'`, payload carries correction details.
10. COMMIT.

**Post-state:**
- `fills.fill_id=9.price = 5.30`
- `trades.<CVGI>.current_avg_cost = 5.30`
- `reconciliation_corrections.correction_id=<new>` written
- `reconciliation_discrepancies.discrepancy_id=41.resolution='auto_corrected_from_schwab'`
- `trade_events` row written
- ZERO operator involvement

**Backfill walkthrough (§8):** identical to above, except the trigger is `swing journal reconcile-backfill --apply` instead of a live reconciliation run. Same end state.

### §10.2 DHC 39 — tier-2 pending ambiguity end-to-end

**Setup:**
- `reconciliation_discrepancies.discrepancy_id=39`
- `discrepancy_type='unmatched_open_fill'`
- `trade_id=<DHC trade>`, `fill_id=2`, `ticker='DHC'`
- `expected_value_json={"qty": 39.0, "price": 7.58, "action": "entry"}` (shipped emitter shape at `schwab_reconciliation.py:439-449`)
- `actual_value_json={"matched": null}` (shipped emitter persists null-match only; NO partials info — Codex R1 Critical #2 verification against shipped code)
- `material_to_review=1`, `resolution='unresolved'`

**Backfill Pass 1 (persisted-JSON-only classification — §8.4):**
- Pass 1 inputs: discrepancy + journal_row (the `fills.fill_id=2` row at $7.58 × 39).
- Pass 1 LOGIC: `actual_value_json={"matched": null}` gives the classifier no candidate enumeration; cannot distinguish partial-vs-no-match. Per §8.4 Pass-1 vs Pass-2 contract, the classifier flags this case as requiring Pass 2.
- Pass 1 OUTPUT (interim, NOT the final classification): tier=2, `ambiguity_kind='unsupported'`, with metadata flag `pass_2_required=True`.

**Backfill Pass 2 (re-fetch Schwab — §8.4):**
- Pass 2 fetches Schwab via `swing/integrations/schwab/trader.py:get_account_orders(...)` (per §8.4 Codex R2 C#1 fix — the orders endpoint, NOT the transactions endpoint) for `(ticker='DHC', from_date='2026-04-27', to_date='2026-04-27')`. Writes a `schwab_api_calls` audit row with `surface='cli'` (backfill is operator-invoked CLI), `endpoint='accounts.orders.list'`, plus all the existing audit columns.
- Pass 2 receives a `list[SchwabOrderResponse]` filtered to DHC. Sub-classifier (§4.3.2 unmatched_open_fill) re-evaluates against the response shape — **tier-2 ALWAYS per §8.4 V1-mapper-limitation lock** (Pass-2-tier-1-FORBIDDEN for order-level source data):
  - If Schwab returns 2 SEPARATE orders summing to qty=39 (e.g., 20 + 19) → tier=2, `ambiguity_kind='multi_partial_vs_consolidated'` (operator picks split / VWAP-consolidate / keep-consolidated / custom; operator MUST supply price truth via `--custom-value` if they want price corrections since `SchwabOrderResponse.price` is order-level not execution-level).
  - If Schwab returns 1 order with qty=39 + aggregated price → tier=2, `ambiguity_kind='unknown_schwab_subtype'` with rationale "Schwab returned a single order at order-grain; V1 mapper does not expose per-execution fill detail; operator dispositions via `--choice acknowledge` (keep journal as-is) or `--choice operator_truth` (operator supplies execution price)".
  - If Schwab returns 0 orders → tier=2, `ambiguity_kind='schwab_returned_no_match'`.
- Pass 2 OUTPUT (assume the 2-separate-orders case): `ClassificationResult(tier=2, ambiguity_kind='multi_partial_vs_consolidated', correction_target=None, candidate_choices=[...the 2 SchwabOrderResponse rows enumerated as partial-fill candidates...])`.

**Classifier (§4.3.2 unmatched_open_fill sub-classifier) — final under Pass 2:**
- INPUT: discrepancy, source_payload from Pass 2 re-fetch (2 partial fills summing to qty=39), journal_row = single fill_id=2 with qty=39.
- LOGIC: source_payload has 2 transactions whose total quantity matches journal_row.quantity → tier=2, `ambiguity_kind='multi_partial_vs_consolidated'`.
- OUTPUT: `ClassificationResult(tier=2, ambiguity_kind='multi_partial_vs_consolidated', correction_target=None, correction_reason="unmatched_open_fill on (DHC, fill_id=2): journal consolidated qty=39 @ $7.58; Schwab has 2 partials (20 @ $7.57; 19 @ $7.59); operator must choose split or VWAP-consolidate or acknowledge.", candidate_choices=[{"code": "split_into_partials", "description": "Replace journal fill with 2 partial fills"}, {"code": "consolidate_using_schwab_vwap", "description": "Keep journal consolidated; update price to Schwab VWAP $7.58 (= ((20×7.57)+(19×7.59))/39)"}, {"code": "keep_journal_as_is", "description": "Acknowledge partial-fill aggregation"}, {"code": "custom", "description": "Operator-supplied payload"}])`.

**Service (flow pivot step 2; NOT apply path):**
- UPDATE `reconciliation_discrepancies SET resolution='pending_ambiguity_resolution', ambiguity_kind='multi_partial_vs_consolidated', resolution_reason=<classifier reason>`.
- NO `reconciliation_corrections` row yet (operator hasn't picked).
- Phase 10 dashboard banner increments pending count by 1.

**Operator-side resolution (§6.2 CLI):**
- Operator runs `swing journal discrepancy show-ambiguity 39`. Sees the 4 candidate choices with codes.
- Operator picks (hypothetically) `consolidate_using_schwab_vwap`. Runs: `swing journal discrepancy resolve-ambiguity 39 --choice consolidate_using_schwab_vwap --reason "Schwab partials are same trade; keeping consolidated row"`.
- Service calls `apply_tier2_resolution(discrepancy_id=39, choice_code='consolidate_using_schwab_vwap', operator_reason=...)`.

**`apply_tier2_resolution` flow (§5.6):**
1. REJECT caller-held; BEGIN IMMEDIATE.
2. SELECT discrepancy; verify resolution='pending_ambiguity_resolution'. Verify ambiguity_kind matches choice_code's compatible-kind set. PASSES.
3. Dispatch to handler `(multi_partial_vs_consolidated, consolidate_using_schwab_vwap)`:
   - Compute VWAP from source_payload (cached or re-fetched).
   - Build correction target: `{'price': 7.58}` (the VWAP).
   - Re-run validator chain → PASSES.
4. UPDATE `fills.fill_id=2 SET price = 7.58`.
5. `_recompute_aggregates`.
6. INSERT `reconciliation_corrections`:
   - `correction_action='operator_resolved_ambiguity'`
   - `correction_choice='consolidate_using_schwab_vwap'`
   - `affected_table='fills'`, `affected_row_id=2`, `field_name='price'`
   - `pre_correction_value_json={"price": 7.58}` (current journal value)
   - `source_canonical_value_json={"price": 7.58}` (VWAP)
   - `applied_value_json={"price": 7.58}` (same as source in this case)
   - `applied_by='operator'`
   - `correction_reason=<operator reason>`
   - Other fields per §3.1
7. UPDATE `reconciliation_discrepancies SET resolution='operator_resolved_ambiguity', resolved_at=<now>, resolved_by='operator'`.
8. UPDATE `review_log.superseded_by_correction_id` via the §5.4 step 9 cadence-period-anchored lookup: compute DHC trade's close date (DHC is OPEN at time of dispatch → no close date), match against review_log periods. Zero rows matched → no review_log UPDATEs. (Same pattern as §10.1 step 8.)
9. INSERT `trade_events` row.
10. COMMIT.

**Alternate path: operator picks `split_into_partials` instead.**

The handler:
- DELETEs fill_id=2.
- INSERTs 2 new fills: (qty=20, price=7.57) and (qty=19, price=7.59), both with `action='entry'` per the original fill's action.
- `_recompute_aggregates` after each.
- Writes 3 `reconciliation_corrections` rows (1 deletion sentinel + 2 insertion sentinels) bundled under one `correction_set_id`. Each row's `field_name` is `'__delete__'` / `'__insert__'` sentinel; `applied_value_json` carries the full inserted fill payload for forensic trail. Operator-decision-anchored.

This is the more invasive path; the VWAP path is the operator-friendly default and is the recommended UI hint in `show-ambiguity` output.

**Backfill walkthrough (§8):** dry-run prints the ambiguity-kind line + candidate choices. `--apply` mode does the `pending_ambiguity_resolution` stamp but does NOT auto-pick a choice (tier-2 is operator action by definition). Operator then dispositions via `resolve-ambiguity` CLI.

### §10.3 VSAT 40 — classifier-data-dependent path end-to-end

**Setup:**
- `reconciliation_discrepancies.discrepancy_id=40`
- `discrepancy_type='unmatched_open_fill'`
- `trade_id=<VSAT trade>`, `fill_id=6`, `ticker='VSAT'`
- `expected_value_json={"qty": 2.0, "price": 65.69, "action": "entry"}` (shipped emitter shape at `schwab_reconciliation.py:439-449`)
- `actual_value_json={"matched": null}` (shipped emitter persists null-match only)
- `manual_entry_confidence='low'` on the underlying fill (operator-self-flagged; NOT classifier input — see "manual_entry_confidence note" below)
- `material_to_review=1`, `resolution='unresolved'`

**Backfill Pass 1 (§8.4) — persisted JSON insufficient:** `unmatched_open_fill` with `actual_value_json={"matched": null}` is Pass-1-insufficient per §8.4 table. Pass 1 emits interim tier=2 `unsupported` with `pass_2_required=True`. Backfill proceeds to Pass 2.

**Backfill Pass 2 (§8.4) — re-fetch Schwab transactions for (VSAT, 2026-05-06):** consumes one `schwab_api_calls` audit row with `surface='cli'`. Three downstream classifier paths depending on actual Schwab payload:

**Case A (Schwab returns 1 single matching order, different price OR qty than journal):**
- Per §8.4 Codex R3 C1+M1 LOCK (Pass-2-tier-1-FORBIDDEN for order-level source): tier=2, `ambiguity_kind='unknown_schwab_subtype'`. Classifier does NOT redirect to `entry_price_mismatch` sub-classifier from Pass-2 order-level data because `SchwabOrderResponse.price` is limit/order price, not execution price. Operator dispositions via `--choice operator_truth` (operator supplies real execution price from broker statement) OR `--choice acknowledge` (keep journal as-is) OR `--choice custom`.

**Case B (Schwab returns 2 SEPARATE orders summing to qty=2):**
- Tier=2, `ambiguity_kind='multi_partial_vs_consolidated'` → operator picks per §10.2 (same Pass-2-tier-1-FORBIDDEN rule).

**Case C (Schwab returns 0 orders for the (VSAT, 2026-05-06) window):**
- Tier=2, `ambiguity_kind='schwab_returned_no_match'` → operator decides: mark unmatched OR supply truth OR acknowledge.

(All three cases are tier-2; no tier-1 redirect is permitted because Pass-2 source data is order-level not execution-level.)

**Why VSAT 40 is per-row data-dependent:** Pass 1 (§8.4) cannot break the ambiguity from `{"matched": null}` alone — same persisted-shape gap as DHC 39. Pass 2 re-fetches Schwab API for (VSAT, 2026-05-06) to get the full transaction list (consuming a `schwab_api_calls` audit row attributed with `surface='cli'`; under sandbox this short-circuits per §9.7 and classifier emits tier-2 `unsupported`).

**Backfill behavior under production environment:**
- Dry-run: Pass 1 → interim tier-2 `unsupported`; Pass 2 re-fetches Schwab; classifier emits final classification per the 3-case logic above (Case A → tier-1 redirect to entry_price_mismatch/position_qty_mismatch; Case B → tier-2 multi_partial_vs_consolidated; Case C → tier-2 schwab_returned_no_match); prints projected classification. The Pass-2 re-fetch IS performed under dry-run because the classifier needs actual source-of-truth data to decide; the audit row is written but no journal mutation occurs.
- `--apply`: same Pass-2 re-fetch + actual classification + tier-1 auto-apply (with SAVEPOINT-per-correction per §7.1) OR tier-2 stamp.

**Backfill behavior under sandbox environment:** Pass 2's Schwab re-fetch is short-circuited per §9.7. Classifier emits tier-2 `unsupported` with rationale `"sandbox: cannot re-fetch source-canonical payload"`. Discrepancy stays unresolved-pending-ambiguity. Operator re-runs backfill under production environment OR dispositions manually via `resolve-ambiguity`.

**manual_entry_confidence note:** the `manual_entry_confidence='low'` flag on the underlying fill is operator-honesty metadata captured at trade-entry time — NOT a classifier input. Classifier doesn't read it. Operator confidence affects how the operator dispositions the tier-2 result (operator can be more aggressive about marking as unmatched given their own self-flagged uncertainty), but it doesn't change the auto-classification.

---

## §11 Migration strategy (v18 → v19)

### §11.1 Single atomic migration file

`swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql`. ALL Sub-bundle C schema changes land in one file per Phase 9 §A.0 LOCK precedent. Sub-sub-bundles B / C / D consume code-side only; no further migrations in Sub-bundle C scope.

### §11.2 File contents (LOCKED order)

Per §3.8 enumeration:

1. `BEGIN;` (explicit transaction for `executescript()` partial-failure rollback per CLAUDE.md gotcha — migration 0018 precedent).
2. `CREATE TABLE reconciliation_corrections (...)` + 4 indexes (§3.1).
3. Table-rebuild `reconciliation_discrepancies` (CHECK enum widening 5→9 + new `ambiguity_kind` column with CHECK + cross-column CHECK). The rebuild creates `reconciliation_discrepancies_new` with the wider CHECK, INSERT-SELECTs all existing rows (29 + 3 = 32 rows in production at dispatch time per §1.4 evidence; existing values copied verbatim, `ambiguity_kind=NULL` for all), DROPs the old, ALTER RENAMEs. Preserves all 4 existing indexes; recreates them post-rename. Per Phase 7 trades-table-rebuild migration 0014 §10 precedent.
4. `ALTER TABLE review_log ADD COLUMN superseded_by_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` (§3.3).
5. `ALTER TABLE schwab_api_calls ADD COLUMN linked_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` (§3.4).
6. Table-rebuild `trade_events` to widen `event_type` CHECK enum (per §3.5; migration 0014 §11 precedent already did this rebuild once + can be repeated).
7. New partial index `ix_reconciliation_discrepancies_pending_ambiguity` (§3.2).
8. `UPDATE schema_version SET version = 19`.
9. `COMMIT;`.

### §11.3 Backup gate

Runner-level `swing-pre-phase12-bundle-c-migration-<ISO>.db` fires when `current_version == 18 AND target >= 19`. Writing-plans wires runner-side per Phase 9 backup-gate precedent (`swing/data/db.py` migration runner extension).

### §11.4 FK ordering note (writing-plans verifies)

Migration 0019 creates `reconciliation_corrections` BEFORE the ALTER ADD COLUMN statements that reference it. Order in §11.2 is correct. Writing-plans confirms migration runner doesn't toggle `foreign_keys` mid-script in a way that breaks the ALTER FK reference (Phase 7 hotfix 283d4fa + Phase 9 §A.4 precedent).

---

## §12 Sub-sub-bundle decomposition recommendation

Per §1.8: 4 sub-sub-bundles. Writing-plans refines + locks dispatch order. Projected metrics below are rough; writing-plans tightens.

### §12.A — Sub-sub-bundle C.A — Foundation (schema + dataclass + repo CRUD)

**Scope:**
- Migration 0019 (§11) lands all schema changes.
- New `swing/data/models.py:ReconciliationCorrection` dataclass.
- New `swing/data/repos/reconciliation_corrections.py` repo with pure CRUD (insert / get / list_by_discrepancy / list_by_run / list_by_affected_row / update_superseded_by — pure SQL inside caller's transaction).
- New columns on `swing/data/models.py:ReconciliationDiscrepancy` for `ambiguity_kind` (TEXT NULL).
- New column on `swing/data/models.py:ReviewLog` for `superseded_by_correction_id`.
- New column on `swing/integrations/schwab/models.py:SchwabApiCall` for `linked_correction_id`.
- Backup-gate wiring at the migration runner.
- ZERO behavior change. ZERO new service logic. ZERO operator-visible changes (audit table empty until C.C ships).

**Projected fast-test delta:** +35-55 tests (schema migration applied; CRUD coverage; dataclass round-trips; CHECK violations rejected; cross-column CHECK family on (`ambiguity_kind`, `resolution`)).

**Projected line count:** ~700-1100 lines of plan content.

**Cross-bundle dependency:** C.B / C.C / C.D blocked on C.A's `reconciliation_corrections` repo + dataclass + schema.

### §12.B — Sub-sub-bundle C.B — Classifier

**Scope:**
- New `swing/trades/reconciliation_classifier.py` module with `classify_discrepancy` public function + per-discrepancy-type sub-classifiers.
- `ClassificationResult` NamedTuple/dataclass.
- NEW shim module `swing/trades/reconciliation_validators.py` per §5.5 Codex R1 Major #2 LOCK with 4 pure-function dry-run validators: `validate_fill_correction` + `validate_trade_correction` + `validate_cash_movement_correction` + `validate_snapshot_correction`. Shim mirrors shipped schema CHECK + FK constraints + Phase 7 `_recompute_aggregates` aggregate invariants WITHOUT performing INSERT/UPDATE.
- `ValidatorChainCallable` protocol + a stock implementation `default_validator_chain(conn)` that dispatches on `affected_table` to the right shim validator. (The shipped repo-layer modules do NOT expose dedicated callable validators; the shim is the mandatory composition source per §5.5.)
- Test coverage per §4.3 sub-classifier (10 sub-classifiers × multiple cases each).
- ZERO journal mutations. ZERO Schwab API calls. ZERO service composition.

**Projected fast-test delta:** +60-90 tests (one test per (discrepancy_type, classification outcome) pair; validator-rejected downgrade tests; payload-shape-edge-case tests).

**Projected line count:** ~600-900 lines of plan content.

**Cross-bundle dependency:** C.C blocks on C.B's classifier.

### §12.C — Sub-sub-bundle C.C — Auto-correction service + reconciliation flow pivot

**Scope:**
- New `swing/trades/reconciliation_auto_correct.py` module with:
  - `apply_tier1_correction` (public; owns transaction)
  - `_apply_tier1_correction_inner` (private; caller-controlled)
  - `apply_tier2_resolution` + private inner
  - `apply_tier3_override` + private inner
  - Per-(ambiguity_kind, choice_code) resolution handlers
  - `CallerHeldTransactionError` (mirrors Phase 9 Sub-bundle B pattern)
  - `ValidatorRejectedError`
- Reconciliation flow pivot at `swing/trades/schwab_reconciliation.py:run_schwab_reconciliation` (Schwab-side; Codex R1 Major #6 fix — Schwab module is `schwab_reconciliation.py`, NOT `reconciliation.py`) AND `swing/trades/reconciliation.py:run_tos_reconciliation` (TOS-CSV side per §14.OQ-2 disposition).
- `briefing.md` extension: new "Reconciliation status" section enumerates tier-2 backlog (Phase 11 Sub-bundle D banner precedent).
- Phase 10 dashboard banner predicate update: include `'pending_ambiguity_resolution'` in the unresolved-material count (per §6.3 + Phase 10 T-E.3 retrofit precedent).

**Projected fast-test delta:** +70-110 tests (service tests; transaction-rejection contract; idempotency; multi-fill-split handler; override chain; sandbox short-circuit; flow-pivot graceful degradation; cross-discrepancy-type integration tests; tier-3 override chain tests).

**Projected line count:** ~900-1300 lines of plan content.

**Cross-bundle dependency:** C.D blocks on C.C.

### §12.D — Sub-sub-bundle C.D — Tier-2 CLI surface + backfill + worked examples

**Scope:**
- New `swing journal discrepancy resolve-ambiguity` + `list-pending-ambiguities` + `show-ambiguity` + `override-correction` subcommands (§6.2).
- New `swing journal reconcile-backfill` subcommand (§8.2).
- Backfill applied to existing production discrepancies 39 + 40 + 41 via operator-witnessed gate (S2 in §15 hand-off).
- Phase 10 dashboard tile or row surfacing tier-2 backlog count (optional; if Phase 10 banner already covers this, skip the standalone tile — writing-plans decides).

**Projected fast-test delta:** +50-70 tests (CLI behavior tests; backfill dry-run vs apply; idempotency; the 3 production discrepancies walked through; choice-code rejection on incompatible ambiguity_kind).

**Projected line count:** ~600-900 lines of plan content.

**Cross-bundle dependency:** none beyond C.C.

### §12.5 Aggregate projection

**Total projected fast-test delta:** +215-325 across C.A + C.B + C.C + C.D (Phase 11 + Phase 9 arc precedent: +447 across 4 sub-bundles; Phase 10 +494; Sub-bundle C is mid-range complexity per §1).

**Total projected plan-doc line count:** ~2800-4200 across the 4 sub-sub-bundle plans.

**Dispatch order:** C.A → C.B → C.C → C.D. Strictly sequential per cross-bundle dependencies.

---

## §13 Out-of-scope linkage: fill auto-population at trade-entry time

### §13.1 Scope statement (per §1.7 lock — repeats explicit out-of-scope)

Sub-bundle C does NOT design schema for fill auto-population at trade-entry time. Does NOT propose new tables for it. Does NOT propose CHECK enum widenings for it. Does NOT propose service modules for it. The prospective sub-bundle is separate.

### §13.2 Clean layering interfaces Sub-bundle C ships that the future sub-bundle consumes

The future fill-auto-population-at-entry sub-bundle benefits from:

1. **`classify_discrepancy` is reusable prospectively.** Apply the same classification logic at trade-entry handler time against incoming Schwab transactions vs operator-filled-out form values. Same `ClassificationResult` shape, same tier discrimination, same per-discrepancy-type sub-classifiers. The classifier is a PURE FUNCTION — it has no DB writes or Schwab API I/O coupled to the retroactive context.
2. **`reconciliation_corrections` schema is analogous to a prospective `entry_auto_population_log` table.** A future sub-bundle might create a sibling audit table with the same forensic-trail shape (pre-form-value / Schwab-said / applied-value chain). Sub-bundle C does NOT design that table.
3. **Per-(ambiguity_kind, choice_code) resolution handler shape extends.** The future sub-bundle's prospective resolution surface can re-use the same per-pair handler architecture.
4. **`reconciliation_runs.source` enum already includes `'manual'`.** A trade-entry-time auto-population flow might emit a synthetic reconciliation_run with `source='schwab_api'` per fill at entry time. Sub-bundle C does not foreclose this; the schema already supports it.

### §13.3 Sub-bundle C decisions that would foreclose or complicate the future sub-bundle

NONE identified. The chosen architecture (pure-function classifier + service-layer apply + dedicated audit table) is intentionally retroactive-vs-prospective-symmetric. The retroactive flow Sub-bundle C ships and the prospective flow the future sub-bundle ships can share classifier code.

The ONE caveat: if the future sub-bundle wants to write directly into `reconciliation_corrections`, Sub-bundle C's audit table is too tightly bound to a (`discrepancy_id`, `reconciliation_run_id`) pair (both NOT NULL). A future prospective flow that has neither a discrepancy nor a run would need either (a) a new sibling table OR (b) a Sub-bundle C-time relaxation of these FKs to nullable. The spec recommends keeping them NOT NULL in Sub-bundle C — V2 sub-bundle creates its own sibling table for prospective audit. Banked.

---

## §14 Open questions for orchestrator triage

### §14.OQ-1 — Audit-history table vs `event_log` extension (LOCKED at §3.1.0; banked here as orchestrator-can-revisit)

Spec locked: NEW dedicated `reconciliation_corrections` table. Alternative considered: extending `event_log` (Phase 8 daily_management grain) — REJECTED because event_log is session-cadence-grained and doesn't fit reconciliation correction events.

If orchestrator wants to revisit, the lockable alternative is: extend `trade_events` to carry forensic correction trail (would mean making `payload_json` carry the full forensic trail in JSON). Spec recommends staying with dedicated table.

### §14.OQ-2 — Pivot scope: Schwab only OR both Schwab and TOS-CSV reconciliation? (spec recommends BOTH)

Per §7.2. Spec recommends BOTH pivot. The TOS-CSV reconciliation also produces discrepancies that are classifier-tractable; tier-1 entry_price_mismatch from TOS CSV is no different from Schwab.

Caveat: TOS CSV is operator-uploaded; trust premise differs slightly from Schwab API which is uncontroversially broker-authoritative. Some discrepancy-types may need source-specific tier-determination tweaks (e.g., a sector_tamper discrepancy from TOS CSV vs from Schwab API has different trust shapes). Writing-plans triages.

Default recommendation: pivot BOTH; per-discrepancy-type sub-classifiers handle source-specific nuance internally.

### §14.OQ-3 — Tier-2 surface: CLI-only V1 vs web-from-start (LOCKED at §6.1; banked here as orchestrator-can-revisit)

Spec locked: CLI-only V1, web V2. Operator can revisit if their workflow strongly favors web — but the operator-locked architectural framing supports CLI as the operator's discrepancy-resolution surface (per §6.1 rationale).

### §14.OQ-4 — `multi_partial_vs_consolidated` default choice (recommend `consolidate_using_schwab_vwap`)

When operator runs `show-ambiguity`, which choice is highlighted as the "recommended" default? Spec recommends `consolidate_using_schwab_vwap` because:
- Least invasive (no fill table changes other than a price field).
- Preserves existing trade analytics (single-fill semantics intact).
- Operator can later opt for split if desired (always reversible via tier-3 override).

Writing-plans confirms via operator preference.

### §14.OQ-5 — Backfill on production discrepancies — does operator want it auto-fired at C.D ship, or only on explicit operator invocation?

Spec recommends EXPLICIT operator invocation only. C.D ship-time gate plays the operator-witnessed gate role: walk operator through dry-run + apply against the 3 production cases (§10.1 + §10.2 + §10.3). Beyond that, backfill is operator-on-demand only. Avoids surprising production state mutation post-merge.

### §14.OQ-6 — `correction_set_id` mechanic in `reconciliation_corrections` (anchor-self-references-self vs separate `correction_sets` table)

Spec proposes: anchor row sets `correction_set_id = correction_id` of itself after the INSERT completes, requiring a two-step INSERT-then-UPDATE. Alternative: a separate `correction_sets` table with its own autoincrement PK that all set members reference. Spec recommends the inline two-step because it avoids a new table for a relatively-rare V1 use case. Writing-plans verifies and locks.

### §14.OQ-7 — Phase 10 dashboard banner predicate widening

Sub-bundle C makes `pending_ambiguity_resolution` rows operationally similar to `unresolved` rows from the operator's perspective. Sub-bundle C should update the Phase 10 `discrepancies.py` helper + base-layout VM mixin predicate to include `'pending_ambiguity_resolution'` alongside `'unresolved'` for the unresolved-material count. This is a small change but touches 10 retrofit VMs from Phase 10 Sub-bundle E. Lockable in C.D scope OR in a follow-up dispatch — writing-plans decides.

### §14.OQ-8 — Tier-3 override CLI: confirmation prompt?

`swing journal discrepancy override-correction` is a destructive operation (overrides system's auto-applied correction back to operator's claim). Should it prompt for confirmation by default + accept `--force` for non-interactive? Spec recommends YES + `--force` flag per the cleanup-script `-DeregisterFirst` precedent. Writing-plans clarifies.

### §14.OQ-9 — `__delete__` and `__insert__` sentinels in `reconciliation_corrections.field_name`

Spec proposes sentinels for multi-fill operations. Alternative: a separate `reconciliation_correction_operations` join table. Spec recommends sentinels for V1 simplicity. Operator-facing surfaces interpret sentinels via documented convention; SQL queries can filter via `field_name NOT LIKE '\_\_%' ESCAPE '\'`. Writing-plans verifies and locks.

### §14.OQ-10 — Schwab API call response body caching for backfill replay

Per §8.4: V1 backfill works against discrepancy `actual_value_json` slices + (when insufficient) re-fetches Schwab. V2 candidate: a separate full-API-response-cache table. Out of Sub-bundle C scope. Banked.

### §14.OQ-11 — Brief enumeration mismatches against shipped schema (informational, not blocking)

Per §1.5 verification, the brief's enumerations of (a) `reconciliation_discrepancies.resolution` enum and (b) `fills.reconciliation_status` enum did not match shipped schema. The spec uses the shipped schema (verified against migrations 0014 + 0017) and §1.5 documents the divergence. This is enumerated here so writing-plans dispatch carries it forward as a brief-vs-shipped-schema discrepancy lesson (one of the 18 adversarial-review watch items in brief §5 #15: "Brief-premise empirical-verification" lesson family).

### §14.OQ-12 — Cross-column CHECK between `ambiguity_kind` and `resolution` — schema-defended OR app-layer-only?

Per §3.2: spec proposes schema-defense-in-depth via cross-column CHECK. Phase 9 §3.1 R1 Minor #4 precedent supports schema-defense-in-depth for cross-column CHECKs. Writing-plans verifies SQLite syntax executes correctly under the runner.

### §14.OQ-13 — Sandbox short-circuit semantics (LOCKED at §9.7)

Spec locked: under sandbox, auto-correction is no-op. Banked here for orchestrator-can-revisit if a sandbox-friendly preview mode is desired (V2 candidate).

### §14.OQ-14 — Validator chain composition source (LOCKED at §5.5; banked)

**LOCKED at §5.5 (Codex R2 Major #3 cleanup):** validator chain composed from NEW shim module `swing/trades/reconciliation_validators.py` shipped at sub-sub-bundle C.B time. Earlier brainstorm wording "No new validator module" is SUPERSEDED — the shim is mandatory because shipped repo-layer modules do NOT expose dedicated callable validator functions (only schema CHECK + FK constraints + indirect `_recompute_aggregates` invariants per §5.5 Codex R1 Major #2 verification). The shim mirrors schema invariants as importable Python predicates for dry-run validation. V2 candidate: refactor the shim into the repo modules themselves so validators become first-class on `swing/data/repos/*.py`. Banked.

### §14.OQ-15 — When `apply_tier3_override` is invoked on a correction_id that's already superseded (chain longer than 2)

Spec proposes: REJECT — operator must override the CURRENT row in the chain (where `superseded_by_correction_id IS NULL`). CLI displays the chain head's correction_id when listing. Writing-plans confirms.

---

## §15 Writing-plans hand-off

### §15.1 What writing-plans inherits as BINDING from this spec

1. §1.3 four operator-locked architectural constraints — NOT re-litigated.
2. §3 schema sketches — all column lists, CHECK enums, FK relationships, indexes locked.
3. §3.8 + §11 migration shape — atomic single-file migration 0019; backup gate.
4. §4 classifier architecture — pure function; per-discrepancy-type sub-classifiers; determinism principle; validator-respecting downgrade.
5. §5 auto-correction service architecture — public/private outer/inner split; transactional discipline; idempotency contract.
6. §6 Tier-2 CLI surface — CLI-only V1; per-(ambiguity_kind, choice_code) handler architecture; choice codes.
7. §7 reconciliation flow pivot — both `run_schwab_reconciliation` AND `run_tos_reconciliation` (per §14.OQ-2 default); graceful-degradation contract.
8. §8 backfill path — dry-run default; explicit `--apply` required; idempotency.
9. §9.1 review_log freezing — RETAIN + mark superseded.
10. §9.4 daily_management snapshots — RETAIN as historical.
11. §10 three discriminating-example walkthroughs — operator-witnessed gate at C.D ship validates the post-state for 39 + 40 + 41.
12. §12 sub-sub-bundle decomposition — 4 sub-sub-bundles; dispatch order C.A → C.B → C.C → C.D; cross-bundle dependencies.
13. §13 fill auto-population at entry — OUT OF SCOPE.

### §15.2 What writing-plans triages per §14

15 open questions §14.OQ-1 through §14.OQ-15. Each has a spec recommendation; writing-plans converts the recommendation to a per-task acceptance criterion OR escalates to orchestrator triage.

### §15.3 What writing-plans should pre-verify against shipped code

1. Migration runner's `executescript()` partial-failure wrapper handles the 0019 table-rebuilds correctly (Phase 7 hotfix 283d4fa + Phase 9 §A.4 + Phase 12 Sub-bundle A T-A.7 precedent).
2. `swing/trades/reconciliation.py:run_tos_reconciliation` AND `swing/trades/schwab_reconciliation.py:run_schwab_reconciliation` (per Codex R1 Major #6 verification — Schwab reconciliation is in a SEPARATE module file from TOS reconciliation); writing-plans grep-verifies the signatures + locks the pivot patches to the correct files.
3. `_construct_pipeline_schwab_client(cfg)` exact module location (Phase 12 Sub-bundle A T-A.3 ship; writing-plans verifies).
4. Existing `swing journal discrepancy` CLI command group module/function names (Phase 9 Sub-bundle B precedent; writing-plans verifies).
5. Phase 10 `discrepancies.py` helper module location + base-layout VM mixin signature (Phase 10 Sub-bundle A T-A.18 + Sub-bundle E T-E.3 ship; writing-plans verifies).
6. `swing/data/repos/fills.py` (and trades.py / cash_movements.py / account_equity_snapshots.py) validator coverage — confirmed at Codex R1 + R2 verification that these files do NOT expose dedicated callable validator functions; invariants live in schema CHECK + FK + indirect `_recompute_aggregates`. Sub-bundle C.B MUST ship the new shim module `swing/trades/reconciliation_validators.py` per §5.5 LOCK + §12.B scope. Writing-plans at C.B task time grep-verifies the 4 shim functions are implemented + the validator-chain composition wires through `default_validator_chain(conn)` in §12.B.
7. `briefing.md` generator extension point (Phase 11 Sub-bundle D banner ship); writing-plans confirms hook location.
8. `trades.current_avg_cost` recompute under tier-1 fill-price correction matches expected post-state for CVGI 41 case (writing-plans writes a discriminating integration test).

### §15.4 What writing-plans should explicitly carry forward as forward-binding lessons for executing-plans dispatches

1. Transactional discipline three-piece family (caller-controlled at repo; transaction-owning at service; reject caller-held tx at single-transaction service). Inherited.
2. SQLite `INSERT OR REPLACE` prohibition on FK-referenced + audit-trail tables. Inherited.
3. Form-render hidden anchors + soft-warn confirm `form_values` round-trip (relevant if V2 web surface gets layered).
4. POST-time recompute vs form-render-emitted hidden anchors (relevant if V2 web surface).
5. Service-layer `with conn:` opens its own transaction — don't compose from inside outer single-transaction (per §7.3 outer/inner split discipline).
6. Cross-column CHECK at schema time + app-layer enforcement at service time (per §3.2 + §5.6 dual discipline).
7. Per-row policy stamping (Phase 8 R1 M5 — `risk_policy_id_at_correction` per §3.1).
8. Phase 11 forward-binding lessons #1 through #5 (typed exception audit-row close; pipeline graceful degradation; sandbox short-circuit; surface attribution; `apply_overrides` discipline at Schwab entry points).
9. Phase 12 Sub-bundle A + B forward-binding lessons (env-var + cfg-tier cascade; T-A.3 gap pre-emption pattern; `_MASKED_WRITEABLE_PATHS` discipline; HTMX gotcha trinity).
10. Brief-premise empirical-verification (per §14.OQ-11; spec verified resolution + reconciliation_status enums against shipped migrations 0014 + 0017; writing-plans does the same against any further claimed-shipped surfaces).

### §15.5 Operator-witnessed gate expectations (writing-plans builds gate plan)

Per Phase 11 + Phase 12 precedent: each sub-sub-bundle ships with an operator-witnessed gate. Recommended surfaces:

**C.A gate:**
- S1: inline `pytest -q` PASS at new test count (+35-55 above worktree baseline).
- S2: `swing db-migrate` against fresh DB lands schema_version=19.
- S3: `swing db-migrate` against production-snapshot DB lands schema_version=19 with no data loss (rebuild preserves 30+ existing discrepancies; 3 unresolved-material counted by both `'unresolved'` AND new banner predicate).
- S4: ruff baseline unchanged.

**C.B gate:**
- S1: inline `pytest -q` PASS.
- S2: classifier called against fixtures derived from discrepancies 39 + 40 + 41 emits expected `ClassificationResult` shapes (per §10 walkthroughs).
- S3: ruff baseline unchanged.

**C.C gate:**
- S1: inline `pytest -q` PASS.
- S2: simulated reconciliation run with planted tier-1 + tier-2 discrepancies exercises the flow pivot end-to-end (graceful degradation tested with deliberately-rigged validator failure; counter accuracy verified).
- S3: sandbox short-circuit test — under sandbox env, no journal mutation occurs even when classifier emits tier-1.
- S4: ruff baseline unchanged.

**C.D gate (the big one) — Codex R3 Major #2 fix (LOCKED sequence):**
- S1: inline `pytest -q` PASS.
- S2: `swing journal reconcile-backfill --dry-run` against production DB; outputs the projected classification matrix (CVGI 41 → tier-1; DHC 39 + VSAT 40 → tier-2 with their ambiguity_kinds projected per §10.2 + §10.3); operator reviews. Dry-run consumes Pass-2 Schwab API quota for DHC + VSAT (writes `schwab_api_calls` audit rows; no journal mutations per §8.2 dry-run scope LOCK).
- S3: `swing journal reconcile-backfill --apply --ticker CVGI` against production; verifies disc 41 auto-corrected end-to-end per §10.1 (journal `fills.fill_id=9.price = $5.30`; `reconciliation_corrections` row written; discrepancy `resolution='auto_corrected_from_schwab'`).
- S4: `swing journal reconcile-backfill --apply --ticker DHC` AND `--apply --ticker VSAT` (two separate invocations OR one invocation without --ticker filter; operator preference); verifies DHC 39 + VSAT 40 are stamped tier-2 with `resolution='pending_ambiguity_resolution'` + `ambiguity_kind` populated per their actual Pass-2 outcomes (one of the §10.2/§10.3 Cases A/B/C). This step is REQUIRED before S5 because `show-ambiguity` only renders the candidate menu after the discrepancy is in `pending_ambiguity_resolution` state (per §6.2 CLI semantics + §8 backfill mutation discipline).
- S5: `swing journal discrepancy show-ambiguity 39` displays the candidate choices for DHC 39 per the ambiguity_kind set in S4 (per §10.2).
- S6: operator picks (interactively, no automation) — `swing journal discrepancy resolve-ambiguity 39 --choice <picked> --reason ...` — and the disposition lands per §10.2 post-state (resolution → `operator_resolved_ambiguity`).
- S7: `swing journal discrepancy show-ambiguity 40` then `resolve-ambiguity 40 --choice <picked> --reason ...` for VSAT 40 per §10.3 (tier-2 case A/B/C dispositioned per actual Pass-2 outcome).
- S8: Phase 10 dashboard banner clears to ZERO unresolved-material discrepancies (assuming all 3 dispositioned). NOTE: Phase 10 banner predicate change per §14.OQ-7 (include `'pending_ambiguity_resolution'` alongside `'unresolved'` in unresolved-material count) — verified at S4 that the banner correctly increments when DHC + VSAT land in pending state (after S3+S4 the banner shows count=2; after S6+S7 count=0).
- S9: ruff baseline unchanged.
- S10: cycle-checklist + CLAUDE.md gotcha additions per writing-plans-time spec.

---

## §16 Spec status

LOCKED. Single commit `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation brainstorm spec` lands on `main`. Adversarial Codex review fires next; finalized after `NO_NEW_CRITICAL_MAJOR` verdict from the copowers wrapper.

Sub-bundle C writing-plans dispatch is UNBLOCKED once this spec ships + reaches `NO_NEW_CRITICAL_MAJOR`.
