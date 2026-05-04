# Phase 7 — Trade Lifecycle State Machine + Fills First-Class Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL per sub-dispatch: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the binary `status open|closed` column with a 5-state lifecycle machine; introduce `fills` as the canonical execution log replacing `exits`; lock pre-trade decision fields at first-fill; add 18 thesis fields + 3 named premortem fields + a non-bypassable pre-trade gate; migrate the 3 in-flight production trades (VIR/DHC/CC) without operator data entry.

**Architecture:** Single-transaction migration `0014_phase7_state_machine_and_fills.sql` rebuilds `trades` (drop `status`, add `state` CHECK enum + ~21 new columns) and `trade_events` (expand `event_type` CHECK), creates `fills`, drops `exits` after 1:1 backfill. New service `swing/trades/state.py` is the single state-transition write path; new service `swing/trades/origin.py` derives `trade_origin` at entry; new service `swing/trades/derived_metrics.py` provides pure `realized_pnl` / `r_multiple` formulas. Three executing-plans sub-dispatches (Sub-A schema/repos/state-machine; Sub-B services/CLI; Sub-C web/UX) execute in serial worktrees with marker-file Codex-blocking workflow per binding convention 2026-05-02.

**Tech Stack:** SQLite (CHECK enums + WHERE-partial indexes + CTAS table-rebuild pattern); Python 3.11+ dataclasses; FastAPI + HTMX + Jinja2 templates; click CLI; pytest fast suite (1587-baseline).

**Spec:** [docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md](../specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md) at commit `c926f01` after 3 Codex rounds (NO_NEW_CRITICAL_MAJOR). The spec is the binding source-of-truth; this plan converts spec → tasks. Plan does NOT relitigate spec decisions; conflict-pause protocol per spec §17 applies if a hard conflict surfaces during implementation.

---

## §0 Sub-dispatch ordering, worktree posture, baseline SHAs

### §0.1 Three sub-dispatches — serial with parallelization permitted post-Sub-A

| Sub-dispatch | Scope | Worktree branch | Baseline SHA |
|---|---|---|---|
| **Sub-A** | Schema + repos + state-machine + origin + derived_metrics + fixture refactor + migration safety tests | `phase7-sub-a-schema` | main HEAD at plan-commit time |
| **Sub-B** | Entry / exit / stop_adjust / review service refactors + CLI surface + journal predicate rewrites | `phase7-sub-b-services` | main HEAD after Sub-A merge |
| **Sub-C** | Web routes + view models + templates + state-badge partial + entry-form expansion | `phase7-sub-c-web` | main HEAD after Sub-A merge **OR** after Sub-B merge if serial preferred |

**Sub-B vs Sub-C ordering:** plan declares them parallelizable from Sub-A merge (file-disjoint after Sub-A lands). Default to **serial** Sub-A → Sub-B → Sub-C; orchestrator may parallelize Sub-B + Sub-C from Sub-A merge if scheduling pressure justifies. Parallelization decision is at orchestrator triage time — NOT a binding plan decision.

### §0.2 Worktree + marker-file Codex-blocking workflow per sub-dispatch

Per binding convention dated 2026-05-02 (orchestrator-context.md `worktree-isolated executing-plans + marker-file Codex-blocking workflow`). For each sub-dispatch:

1. Orchestrator creates worktree via `superpowers:using-git-worktrees`.
2. Orchestrator `touch .copowers-subagent-active` at worktree root.
3. Orchestrator invokes `superpowers:subagent-driven-development` directly on the sub-dispatch task list.
4. After all sub-dispatch tasks ship, orchestrator `rm .copowers-subagent-active`.
5. Orchestrator invokes `copowers:adversarial-critic` for executing-plans-side adversarial review on the diff.
6. Operator-witnessed verification gate (browser DevTools for HTMX changes; CLI manual run for CLI changes; pytest pass + ruff clean).
7. Merge to main.

The marker file blocks redundant Codex review during in-flight subagent work; lifting the marker after subagent completion is what triggers the executing-plans Codex review pass.

### §0.3 No-main-commits-during-in-flight discipline

Per orchestrator-context lesson 2026-05-04 (`no-main-commits-during-in-flight-dispatch discipline`): during executing-plans worktree dispatches, no main-side commits land except verified-non-overlapping pure-docs edits. The plan author commits this plan to `main` (it's pure docs); subsequent Sub-A/B/C dispatches must record their `BASELINE_SHA` against main HEAD at dispatch start, and orchestrator merges only after verifying main hasn't moved (or rebases the worktree).

### §0.4 Pre-flight per sub-dispatch (binding before subagent dispatch)

Before each sub-dispatch begins:

- [ ] Record `BASELINE_SHA = git rev-parse HEAD` on main; pin in dispatch brief.
- [ ] Verify operator backed up production DB to `~/swing-data-backups/swing-pre-phase7-<ISO>.db` via SQLite-native backup (NOT shutil.copy2 — see §6.1 migration runner discipline). The migration runner itself also creates a backup as part of the 0014 transaction; the operator-side pre-flight backup is belt-and-suspenders.
- [ ] Verify `python -m pytest -m "not slow" -q` is green at BASELINE_SHA (1587 fast tests pass).
- [ ] For Sub-A specifically: verify production DB still has 3 trades (VIR/DHC/CC) + 1 exit (VIR's stop-hit) per spec §2 #14 / §12.

---

## §1 Vocabulary lists — operator-confirm checkpoint

Three CHECK-enum vocabularies must be locked **before Sub-A executing-plans dispatch begins** (the migration SQL embeds them; changing values mid-implementation requires another migration). Plan recommends final values; operator confirms via single-message reply before Sub-A dispatch is commissioned.

**This checkpoint does NOT gate plan-approval.** The writing-plans skill's plan-review proceeds unblocked. The vocabulary checkpoint runs as a separate operator-confirm step between plan-approval and Sub-A executing-plans dispatch commissioning.

### §1.1 `catalyst` — 9 values (trimmed from v1.2 §4.6's 13)

| Value | Definition | v1.2 source? |
|---|---|---|
| `earnings_driven` | Earnings beat / miss / guidance call drove the move. | yes |
| `guidance_change` | Forward guidance change (separate from earnings event itself). | yes |
| `corporate_action` | M&A, spin-off, buyback, capital raise, dividend change. | yes |
| `sector_rotation` | Industry / sector rotation favors this name. | yes |
| `macro_event` | FOMC / CPI / employment / geopolitical / regime-level event. | yes |
| `sympathy_move` | Peer / sector leader moved; this stock follows. | yes |
| `product_news` | Product launch, FDA approval, design win, contract win. | yes |
| `technical_only` | Pure pattern setup; no specific catalyst identified. | yes |
| `other` | Catch-all; requires `catalyst_other_description` (CHECK enforced via app-layer pattern). | yes |

**Trimmed from v1.2:** `analyst_action` (folded into `guidance_change` for upgrade/downgrade-as-guidance-proxy semantics); `economic_data_release` (folded into `macro_event`); `regulatory_change` (folded into `corporate_action` if specific to issuer; `macro_event` if industry-wide); `competitor_news` (folded into `sympathy_move` for peer-driven moves).

**Operator confirm:** Do these 9 values cover your actual workflow? Any merges to undo / any new categories?

### §1.2 `emotional_state_pre_trade` — 8 values, multi-select (JSON-list)

| Value | Definition |
|---|---|
| `calm` | Clear-headed; routine setup; no urgency. |
| `confident` | High conviction in thesis. |
| `anxious` | Background unease; sleeping poorly; market jitters. |
| `fomo` | Fear of missing the move; rushed entry. |
| `revenge` | Trying to recover from a recent loss. |
| `hopeful` | Wanting it to work for non-thesis reasons. |
| `doubtful` | Unsure of thesis; uncertainty on key invariants. |
| `distracted` | External life pressure; reduced attention budget. |

**Storage:** TEXT with JSON-list canonicalization (sorted unique array). Validation/canonicalization helpers mirror Phase 6 `mistake_tags` pattern. Empty list → form rejects (operator must select at least one); never NULL.

**Operator confirm:** Coverage check. Workflow gaps?

### §1.3 `event_type` — 7 values (conditional; required if `event_risk_present=1`)

| Value | Definition |
|---|---|
| `earnings` | Quarterly / preliminary earnings release. |
| `fed_meeting` | FOMC meeting / minutes / chair speech. |
| `cpi_release` | CPI / PPI / PCE inflation prints. |
| `economic_data` | Other macro data (NFP, retail sales, GDP, ISM, etc.). |
| `product_announcement` | Investor day, product launch, FDA panel, etc. |
| `legal_ruling` | Patent ruling, antitrust verdict, regulatory decision. |
| `other` | Catch-all (no separate description column required for V1). |

**Operator confirm:** Coverage adequate?

### §1.4 Operator-confirm gate mechanism

Plan ships with the recommended values above. Before Sub-A executing-plans dispatch is commissioned, operator replies (single message):

- "Vocabulary confirmed" → migration 0014 embeds these exact values in CHECK enums, Sub-A dispatch proceeds.
- "Vocabulary modified: <changes>" → orchestrator updates this §1 + spec §8.1 + spec §18 in a docs-only commit on main; Sub-A dispatch proceeds with the modified values.
- "Defer" → not applicable; Sub-A blocks until confirmation since CHECK enums must be set before migration SQL is finalized.

### §1.5 Other pre-locked enums (not in this checkpoint — already locked by spec)

These are NOT subject to operator-confirm; they are spec-locked:

- `state` (5 values): `entered`, `managing`, `partial_exited`, `closed`, `reviewed` — spec §3.1.
- `trade_origin` (4 values): `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` — spec §10.4.
- `fills.action` (4 values): `entry`, `trim`, `exit`, `stop` — spec §4.2.
- `fills.reconciliation_status` (5 values): `unreconciled`, `reconciled_match`, `reconciled_discrepancy`, `reconciled_discrepancy_resolved`, `manual_override` — spec §4.2.
- `fills.manual_entry_confidence` (3 values, NULLABLE): `high`, `normal`, `low` — spec §4.2.
- `event_handling` (5 values): `avoid_event`, `hold_through`, `reduce_before`, `exit_before`, `not_applicable` — spec §8.1.
- `gap_risk_handling` (5 values): `accept`, `reduce_size`, `tight_stop`, `exit_before_close`, `not_applicable` — spec §8.1.
- `market_regime` (3 values): `Bullish`, `Caution`, `Bearish` (matches existing `weather_runs.status`) — spec §8.1.
- `trade_events.event_type` adds `pre_trade_edit` to existing 5-value enum — spec §6.4.

---

## §2 `status` → `state` per-call-site predicate rewrite mapping

Per spec §5.2, the rewrite is NOT uniform substitution. Each call site classifies into one of 4 operation-specific predicate categories:

- **Active-trade** (`is this trade currently open?`): `state IN ('entered','managing','partial_exited')`.
- **Closed-but-not-reviewed** (`ready for review?`): `state == 'closed'` (only — must reject already-reviewed).
- **Closed-or-reviewed** (`historical / completed?`): `state IN ('closed','reviewed')`.
- **Write paths** (`UPDATE trades SET status=...`): eliminated; `swing/trades/state.py:state_transition()` is the single write path.
- **Display** (`render the user-visible label`): replace `status` with `state` (or per-state badge label).

### §2.1 Production code call sites (12 files; full rewrite map)

| File | Line(s) | Current expression | Category | Rewrite |
|---|---|---|---|---|
| `swing/data/repos/trades.py` | 60 (INSERT col list), 66, 69 | `INSERT INTO trades(... status, ...) VALUES (..., ?, ...)` with `trade.status` | Write path | Remove `status` from INSERT; INSERT `state` instead with value `'entered'` (Sub-A T6 + Sub-B T1). |
| `swing/data/repos/trades.py` | 98–104 (`get_trade` SELECT) | `SELECT ... status, ...` | Read path; display | Replace `status` with `state` in SELECT col list; `Trade` dataclass loses `status`, gains `state`. |
| `swing/data/repos/trades.py` | 117 | `INSERT INTO exits (...)` inside `insert_exit_with_event` | Function deletion (NOT a status-rewrite site) | The entire `insert_exit_with_event` function is removed in A.6 (Sub-B T4 exit service routes through `swing/data/repos/fills.py`'s `insert_fill_with_event` instead). Spec §5.1's enumeration listed line 117 over-broadly; it does not reference `status`, only the now-dropped `exits` table. No status predicate to rewrite at this line. |
| `swing/data/repos/trades.py` | 144 | `UPDATE trades SET status='closed' WHERE id = ?` | Write path | DELETE this line entirely. State transition via `state_transition(conn, trade_id, 'closed', ...)` from `swing/trades/state.py` (Sub-A T7). The exit service in Sub-B will call the state service. |
| `swing/data/repos/trades.py` | 156 (docstring), 165 | `WHERE id = ? AND status = 'open'` (atomic guard in `update_stop_with_event`) | Active-trade predicate | `WHERE id = ? AND state IN ('entered','managing','partial_exited')`. The stop-adjust service in Sub-B will additionally route through state service for `entered → managing` first-stop trigger. |
| `swing/data/repos/trades.py` | 225, 238, 247, 265, 344, 373, 390 | various SQL queries; classify per spec §5.2 categories | Mixed | Plan task A.6 reads each line, classifies, rewrites. Most are active-trade; some are closed-or-reviewed (journal-style aggregates). |
| `swing/data/db.py` | 20 (migration 0004 docstring) | docstring mentions `status='open'` partial-index | Display (docs) | Update docstring to `state IN ('entered','managing','partial_exited')`. |
| `swing/data/db.py` | 42, 52, 58, 62 | Migration 0004 helper duplicate-`status='open'` check; helper still callable by runtime code in current code-path | Active-trade predicate | **Rewrite per spec §5.3** to use `state IN ('entered','managing','partial_exited')`. Sub-A T1 owns the rewrite (alongside the backup-discipline additions). The 0004 migration SQL itself is historical and unchanged; only the docstring at line 20 + the runtime helper body at lines 42/52/58/62 are rewritten. Runtime call sites in `record_entry`'s duplicate-check route through `list_open_trades(conn)` (Sub-A T6 rewrites that to use `state`). |
| `swing/trades/entry.py` | 197 | `Trade(..., status="open", ...)` dataclass construction | Write path | Remove `status="open"`; the `Trade` dataclass drops the field (Sub-A T2). The state value `'entered'` is set by `record_entry()`'s atomic INSERT (Sub-B T1). |
| `swing/trades/review.py` | 214 | `if trade.status != "closed":` (Phase 6 review precondition) | Closed-but-not-reviewed | `if trade.state != "closed":` — must reject `state='reviewed'` (already reviewed, terminal). The naïve `state not in ('closed','reviewed')` would let already-reviewed trades through review again — DO NOT use that form. (Sub-B T6.) |
| `swing/journal/stats.py` | 47, 96, 179 | Closed-trade aggregation predicates | Closed-or-reviewed | `WHERE state IN ('closed','reviewed')` (or Python equivalent on Trade objects). (Sub-B T9.) |
| `swing/journal/flags.py` | 39, 59, 93 | Closed-trade flags predicates | Closed-or-reviewed | Same as stats.py. (Sub-B T9.) |
| `swing/journal/analyze.py` | 242 | Analyze output passes `trade.status` for display | Display | Pass `trade.state`; downstream display layer formats per-state badge. (Sub-B T9.) |
| `swing/journal/tos_import.py` | 287, 318 | `WHERE t.status='closed'` SQL | Closed-or-reviewed | `WHERE t.state IN ('closed','reviewed')`. (Sub-B T9.) Also: lines 257, 316 read from `exits` table; rewrite to read from `fills` repo helpers (`list_fills_for_trade()` filtering `action IN ('trim','exit','stop')`). |
| `swing/cli.py` | 588 | CLI display `f"{t.status:<8}"` | Display | Replace with `f"{t.state:<14}"` (state strings up to 14 chars: `partial_exited`). (Sub-B T7.) |
| `swing/cli.py` | 1008 | `if trade.status != "closed":` (review-CLI precondition) | Closed-but-not-reviewed | `if trade.state != "closed":` — same semantics as `swing/trades/review.py:214`. MUST reject `state='reviewed'` (already-reviewed trades; terminal per spec §3.2). The naïve `state not in ('closed','reviewed')` would let already-reviewed trades through review again — DO NOT use that form. (Sub-B T7.) |
| `swing/web/routes/trades.py` | 844, 1082, 1198 | Route preconditions | Active-trade | `state IN ('entered','managing','partial_exited')`. (Sub-C T7.) |
| `swing/web/view_models/trades.py` | 331, 385, 432 | VM filter predicates | Active-trade (most) | Verify per-line at task time. (Sub-C T1.) |
| `swing/web/view_models/open_positions_row.py` | 181 | Open-positions row VM filter | Active-trade | (Sub-C T2.) |
| `swing/web/templates/journal.html.j2` | 34 | `{{ t.status }}` | Display | `{{ t.state_badge }}` (per-state badge label) or `{{ t.state }}` if compact display preferred — see Sub-C T6 for badge component. |

### §2.2 Test files — bundle predicate rewrites into the owning sub-dispatch's last task

Test files that set `status="open"` / `status="closed"` directly on Trade fixtures or assert on `trade.status` need rewriting to `state="entered"` (or appropriate state per fixture intent) and `trade.state`. Bundle the rewrites into:

- **Sub-A T0 fixture refactor** updates the canonical trade-fixture builder + every direct `Trade(...)` construction in `tests/data/`, `tests/pipeline/`, `tests/research/`. Identified files (from spec §5.1 + grep at audit time): `tests/data/test_repos_trades.py`, `tests/data/test_db_v3.py`, `tests/data/test_models.py` (line 11–16: dataclass-instantiation smoke; constructs `Trade(..., status="open", ...)` and asserts `t.status == "open"`), `tests/pipeline/test_runner.py`, `tests/pipeline/test_runner_chart_targets.py`, `tests/cli/test_cli_advisory.py`, `tests/cli/test_cli_trade_analyze.py`, `tests/research/parity/test_fetcher.py`, `tests/trades/test_equity.py`. Sub-A T0's empirical-audit refresh (per §2.3) re-runs the grep at dispatch time and bundles any new hits into the same task.
- **Sub-A T9** (migration safety tests) covers VIR/DHC/CC fixture migration to `state` correctly.
- **Sub-B T6** (review service refactor) updates `tests/cli/test_review_complete_cli.py`, `tests/cli/test_trade_review_cli.py`, `tests/web/test_review_route.py`, `tests/web/test_review_template.py`, `tests/web/test_dashboard_needs_review_badge.py` for the `state == 'closed'` predicate.
- **Sub-B T8** (CLI option expansion) updates `tests/cli/test_cli_trade.py`.
- **Sub-B T9** (journal predicate rewrites) updates `tests/journal/test_stats.py`, `tests/journal/test_flags.py`, `tests/journal/test_analyze.py`, `tests/journal/test_tos_import.py`, `tests/journal/test_hypothesis_progress.py`.
- **Sub-C T*** updates web-layer tests as touched.

### §2.3 Empirical-audit refresh at sub-dispatch dispatch time

Before each sub-dispatch begins, the dispatched subagent re-runs the grep enumeration `grep -rn "trades.status\|t\.status\|status='open'\|status='closed'\|status = 'open'\|status = 'closed'" swing/ tests/` against the worktree's BASELINE_SHA, and reconciles the hit list with §2.1 + §2.2 above. Discrepancies (new hits since plan-write; line-number drift) are addressed in the dispatch's first task before substantive work.

The grep-based discovery is mechanical; no judgment call required at sub-dispatch time. Adversarial review of the executing-plans diff verifies completeness.

---

## §3 Carve-out file enumeration (~37 files)

Default posture: read-only on `swing/data/` + `swing/trades/`. Phase 7 carve-out per spec §15:

### §3.1 Schema / data layer

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `swing/data/migrations/0014_phase7_state_machine_and_fills.sql` | NEW | Sub-A T2 | Single transactional migration: rebuild `trades` (drop `status`, add `state` + ~21 cols), create `fills`, drop `exits`, expand `trade_events.event_type` enum. |
| `swing/data/models.py` | MOD | Sub-A T3 | Drop `status` field from `Trade`; add ~21 new fields; add new `Fill` dataclass; remove `Exit` dataclass. |
| `swing/data/db.py` | MOD | Sub-A T1 + T2 | Add `MigrationBackupRequiredException`; add `_create_pre_migration_backup()` runner helper using `Connection.backup()`; add 4 integrity checks; bump `EXPECTED_SCHEMA_VERSION` 13 → 14. Also update migration-0004 docstring (line 20) to reflect partial-index now keyed on `state`. |

### §3.2 Repo layer

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `swing/data/repos/trades.py` | MOD | Sub-A T6 | INSERT col list rewrite (drop `status`, add `state` + new cols); SELECT col list rewrite in `get_trade`/`list_open_trades`/etc.; remove direct `UPDATE trades SET status='closed'` (handled by state service); rewrite all `WHERE status=...` predicates per §2.1 mapping; add new `update_pre_trade_field_with_audit()` helper for §6.4 edit-after-lock path (V1 not invoked from UI; tests + escape-valve callers only). |
| `swing/data/repos/fills.py` | NEW | Sub-A T4 | CRUD: `insert_fill_with_event()`, `get_fill()`, `list_fills_for_trade()`, `get_authoritative_entry_fill()` (per spec §4.3.1 — `ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1`); `_recompute_aggregates()` private helper updating `current_size` / `current_avg_cost` / `last_fill_at` after every fill insert. |

### §3.3 Service layer

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `swing/trades/state.py` | NEW | Sub-A T5 | `state_transition(conn, trade_id, new_state, *, event_ts, rationale)` — single write path for all `state` mutations. Embeds `TRANSITION_MATRIX: dict[(str, str), bool]` (5×5 = 25 cells, 5 allowed). Embeds `OPERATION_REQUIRED_FIELDS` per spec §3.5.1. Provides `validate_for_operation(req, *, op, current_state) -> list[str]`. Defines `MissingPreTradeFieldsException(missing_fields)`. Atomic state-update + `trade_events` row write. |
| `swing/trades/origin.py` | NEW | Sub-A T7 | `EntryPath` enum (4 values); `derive_trade_origin(conn, ticker, entry_path) -> str` per §10.1 mapping; uses `most-recent-completed-pipeline-run` candidate-bucket lookup with yesterday-fallback. |
| `swing/trades/derived_metrics.py` | NEW | Sub-A T8 | Pure functions: `realized_pnl(entry_price, exit_price, quantity) -> float`; `r_multiple(realized_pnl, initial_risk_per_share, quantity) -> float`; `initial_risk_per_share(entry_price, initial_stop) -> float`. Replaces stored `exits.realized_pnl` + `exits.r_multiple` columns. |
| `swing/trades/entry.py` | MOD | Sub-B T1, T2, T3 | `EntryRequest` gains 18 new pre-trade fields + `entry_path: EntryPath`. `record_entry()` validates required fields → derives `trade_origin` → atomic INSERT trades (with `state='entered'`) + first entry-fill (`action='entry'`) + sets `pre_trade_locked_at = req.event_ts`. Removes `status="open"` write (line 197). New `MissingPreTradeFieldsException` rejection path (not force-bypassable). |
| `swing/trades/exit.py` | MOD | Sub-B T4 | `record_exit()` writes a `fills` row with `action='trim'` if `current_size > 0` after fill else `'exit'` (or `'stop'` for stop-hit reason); calls `state_transition()` to move `entered`/`managing` → `partial_exited` or `closed`; recomputes aggregates via `_recompute_aggregates()`. Removes direct `exits` table writes (table no longer exists post-0014). |
| `swing/trades/stop_adjust.py` | MOD | Sub-B T5 | `update_stop_with_event()` precondition rewrite: only fires in `state IN ('entered','managing','partial_exited')`. First stop-adjust on `state='entered'` triggers atomic `entered → managing` transition via `state_transition()`. |
| `swing/trades/review.py` | MOD | Sub-B T6 | Phase 6 review precondition (line 214) `trade.status != "closed"` → `trade.state != "closed"`. Review-completion writes `state='reviewed'` via `state_transition(closed → reviewed)`. |

### §3.4 Web layer

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `swing/web/routes/trades.py` | MOD | Sub-C T3, T7, T8 | Entry form GET/POST adds the 18 new fields; trade-detail route renders Pre-Trade Decision section + audit log. State-aware filtering predicates (lines 844, 1082, 1198). Pre-trade gate failure rendering: `MissingPreTradeFieldsException` → re-render form with `missing_fields` highlights + draft preservation per spec §11.2. |
| `swing/web/view_models/trades.py` | MOD | Sub-C T1 | TradeVM gains `state`, all 18 new pre-trade fields, `state_badge_label`, `has_pre_trade_data`. Status predicates (lines 331, 385, 432) rewritten per §2.1. |
| `swing/web/view_models/open_positions_row.py` | MOD | Sub-C T2 | Row VM filter (line 181) status → state predicate; row VM gains `state_badge_label`. |
| `swing/web/templates/trades/entry_form.html.j2` | MOD | Sub-C T4 | 7 sectioned `<fieldset>` blocks per spec §11.1: §1 Position basics; §2 Setup attribution (+ trade_origin display-only); §3 Pre-trade thesis; §4 Premortem; §5 Risk acknowledgments; §6 Operator state; §7 Notes. |
| `swing/web/templates/trades/detail.html.j2` | MOD | Sub-C T5 | "Pre-Trade Decision" section above position-management; lock indicator + `pre_trade_locked_at` timestamp; `trade_events` audit-log read-display for `event_type='pre_trade_edit'`. Hides section entirely when `vm.has_pre_trade_data` is false (legacy NULL premortem_technical). |
| `swing/web/templates/journal.html.j2` | MOD | Sub-C T6 | Line 34 `{{ t.status }}` → state-badge include or `{{ t.state }}`. |
| `swing/web/templates/partials/state_badge.html.j2` | NEW | Sub-C T6 | Reusable per-state badge partial. Renders `<span class="state-badge state-{{ state }}">{{ state_label }}</span>`. Shared `{% include %}` in dashboard, journal, trade detail to pre-empt OOB-swap drift gotcha. |
| `swing/web/templates/partials/open_positions_table.html.j2` | MOD | Sub-C T6 | Renders state badge per row via the shared `state_badge.html.j2` include (no hand-duplicated markup). |
| `swing/web/static/css/style.css` | MOD | Sub-C T6 | Adds `.state-badge` + `.state-entered` / `.state-managing` / `.state-partial_exited` / `.state-closed` / `.state-reviewed` color rules. |

### §3.5 CLI layer

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `swing/cli.py` | MOD | Sub-B T7, T8 | `swing trade entry` adds 18 new option flags (or interactive prompts on missing). State-aware display + filter sites (lines 588, 1008). `trade_origin` derived from `--entry-path` flag (defaults to `cli_manual`). |

### §3.6 Journal layer (read-side carve-out)

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `swing/journal/stats.py` | MOD | Sub-B T9 | Closed-trade filter predicates (lines 47, 96, 179) status → state per §2.1. |
| `swing/journal/flags.py` | MOD | Sub-B T9 | Closed-trade filter predicates (lines 39, 59, 93). |
| `swing/journal/analyze.py` | MOD | Sub-B T9 | Pass `trade.state` instead of `trade.status` (line 242). |
| `swing/journal/tos_import.py` | MOD | Sub-B T9 | SQL queries (lines 287, 318) `WHERE t.status='closed'` → state predicate; exits-table SELECT (lines 257, 316) → fills-repo helpers. |

### §3.7 Test layer

| File | Add/Mod | Sub-dispatch | Justification |
|---|---|---|---|
| `tests/data/test_migration_0014.py` | NEW | Sub-A T9 + T10 | Migration safety: 4 preservation invariant fixtures + VIR/DHC/CC in-flight migration assertions. |
| `tests/data/test_migration_runner_backup.py` | NEW | Sub-A T1 | Backup-before-migrate runner test gates: backup created; integrity check passes; corrupted backup → `MigrationBackupRequiredException`; missing expected table → exception. |
| `tests/data/test_fills_repo.py` | NEW | Sub-A T4 | `insert_fill_with_event`, `_recompute_aggregates`, `get_authoritative_entry_fill` correctness; aggregate-consistency invariant test. |
| `tests/trades/test_state.py` | NEW | Sub-A T5 | 25-cell transition matrix (5 allowed + 20 rejected); `validate_for_operation` per-operation correctness; per-operation required-field tests. |
| `tests/trades/test_origin.py` | NEW | Sub-A T7 | `derive_trade_origin()` per-cell coverage (5 buckets × 4 entry_paths + ticker-absent + pipeline-not-run-today). |
| `tests/trades/test_derived_metrics.py` | NEW | Sub-A T8 | Pure formula correctness against known fixtures (including VIR's actual numbers). |
| `tests/trades/test_entry.py` | MOD | Sub-B T1, T2, T3 | `MissingPreTradeFieldsException` per missing field; `trade_origin` derivation wired correctly; first entry-fill creation; `pre_trade_locked_at` correctness; force-bypass NOT honored for missing-fields. |
| `tests/trades/test_exit.py` | MOD | Sub-B T4 | Trim vs exit branching; state transition; aggregate recompute. |
| `tests/trades/test_stop_adjust.py` | MOD | Sub-B T5 | State-predicate gating (rejects stop on `closed`/`reviewed`); first-stop `entered → managing` trigger. |
| `tests/web/test_routes/test_trades_route.py` | MOD | Sub-C T3, T7, T8 | Form-validation rejection; pre-trade-detail render; state badge render. |
| `tests/web/test_view_models/test_trades.py` | MOD | Sub-C T1 | State + 18 pre-trade VM fields; state_badge_label correctness; has_pre_trade_data toggle. |
| `tests/cli/test_cli_trade.py` | MOD | Sub-B T8 | New CLI options + interactive prompts. |
| `tests/journal/test_*.py` (5 files per §2.2) | MOD | Sub-B T9 | Replace status predicates with state predicates per spec §5.2 categories. |
| Existing trade-fixture builder tests (8 files per §2.2) | MOD | Sub-A T0 | Update fixtures to use `state="entered"` (or appropriate state) instead of `status="open"`. |

### §3.8 Out-of-carve-out (preserve read-only)

`swing/pipeline/`, `swing/recommendations/`, `swing/evaluation/`, `swing/web/middleware/`, `swing/web/routes/` other than `trades.py`, `swing/web/templates/` other than the 4 listed above + the new `state_badge.html.j2` partial, `swing/data/repos/` other than `trades.py` + new `fills.py`. The 4 carved-out journal files (stats.py, flags.py, analyze.py, tos_import.py) are read-side only — predicate rewrites + repo-helper migration, no schema-shape work in `swing/journal/`.

### §3.9 Total surface

~38 files (37 from spec §15 + new `state_badge.html.j2` partial + new `test_migration_runner_backup.py`). Phase 6 was ~25; Phase 7 is materially larger because of the cross-cutting `status`→`state` rewrite + Fills introduction.

---

## §4 Sub-A — Schema + Repos + State Machine + Fixtures

**Worktree branch:** `phase7-sub-a-schema`
**BASELINE_SHA:** main HEAD at plan-commit time (record at dispatch time).
**Total tasks:** 11 (T0 through T10).
**Expected duration:** 2-3 days of subagent execution + 2-4 Codex rounds on the diff.
**Estimated new tests:** +60-90 (migration safety + state-machine matrix + fills repo + origin + derived_metrics).

### Task A.0: Trade fixture refactor — gates downstream tasks

**Files:**
- Modify: `tests/data/test_repos_trades.py` (Trade(...) constructions)
- Modify: `tests/data/test_db_v3.py`
- Modify: `tests/data/test_models.py` (dataclass-instantiation smoke; lines 11–16)
- Modify: `tests/pipeline/test_runner.py`
- Modify: `tests/pipeline/test_runner_chart_targets.py`
- Modify: `tests/cli/test_cli_advisory.py`
- Modify: `tests/cli/test_cli_trade_analyze.py`
- Modify: `tests/research/parity/test_fetcher.py`
- Modify: `tests/trades/test_equity.py`
- Modify: `tests/conftest.py` (or wherever the canonical `make_trade` builder lives — verify by grep at task time)
- Create: `tests/data/test_fixture_builders.py` — dedicated home for the new fixture-behavior tests (NOT in conftest.py; conftest is support code, not a test module — pytest conventions forbid test functions there)

**Goal:** all existing trade-fixture builders + every direct `Trade(...)` construction in the test corpus shifts to use `state` instead of `status`. This task gates downstream tasks because Sub-A T3 (models.py) drops the `status` field; existing tests would fail at import time without this refactor.

- [ ] **Step 1: Locate the canonical fixture builder.**

```bash
grep -rn "def make_trade\|def seed_trade\|def build_trade\|def _make_trade" tests/ swing/
```

Expected output: locate the canonical builder (likely `tests/conftest.py:make_trade` or per-test-file local builders). If multiple builders exist, this task updates all.

- [ ] **Step 2: Plan the fixture-builder signature change.**

Old:
```python
def make_trade(*, ticker="AAA", status="open", ...) -> Trade:
    return Trade(..., status=status, ...)
```

New (after Sub-A T3 drops `status` from `Trade`):
```python
def make_trade(*, ticker="AAA", state="entered", ...) -> Trade:
    return Trade(..., state=state, ...)
```

State-value mapping per fixture-intent:
- Tests asserting "open" → `state="entered"` (default; safe for tests that don't care about lifecycle stage).
- Tests asserting "closed" → `state="closed"`.
- Tests asserting "reviewed" → `state="reviewed"`.
- Tests covering `partial_exited` semantics → `state="partial_exited"` (rare in current corpus).

- [ ] **Step 3: Write the failing fixture-builder behavior tests in a dedicated test file.**

```python
# tests/data/test_fixture_builders.py — NEW (NOT conftest.py; conftest is support code)
from tests.conftest import make_trade  # adjust import path to the actual canonical builder


def test_make_trade_default_state_entered():
    """Default fixture state is 'entered' — covers the common 'open trade' test case
    that previously used status='open'."""
    t = make_trade(ticker="TEST")
    assert t.state == "entered"
    # NOTE: t.status still exists during A.0 (kept alongside state). The
    # `not hasattr(t, "status")` assertion lives in A.3 once Trade drops
    # the status field.


def test_make_trade_closed_explicit():
    t = make_trade(ticker="TEST", state="closed")
    assert t.state == "closed"


def test_make_trade_status_alongside_state_in_A0_window():
    """During the A.0–A.3 window, Trade has BOTH status and state. A.3 drops
    status; this test will be MODIFIED in A.3 to assert `not hasattr`."""
    t = make_trade(ticker="TEST", state="entered")
    assert hasattr(t, "status")  # still present during A.0
    assert hasattr(t, "state")
```

- [ ] **Step 4: Run the test — should fail.**

```bash
python -m pytest tests/data/test_fixture_builders.py -v
```

Expected: FAIL — `make_trade()` still has only `status=` parameter; passing `state=` raises TypeError.

- [ ] **Step 5: Update fixture builders + every direct `Trade(...)` construction.**

Use ripgrep + structured edit:

```bash
grep -rn 'status="open"\|status="closed"\|status=.open.\|status=.closed.' tests/
```

For each hit: replace `status="open"` with `state="entered"`; `status="closed"` with `state="closed"`. Also remove the `status=...` keyword argument from `Trade(...)` constructions (the field is dropped in T3) — replace with `state=...`.

NOTE: this task lands BEFORE T3 drops the field from the dataclass. To avoid a transient broken state, this task adds `state` as a NEW field on `Trade` with default `"entered"` (alongside the existing `status` field) AND updates fixtures to set `state` explicitly. T3 then drops `status`. This way each task lands an internally-consistent state.

Concrete sequence within Task A.0:
1. Edit `swing/data/models.py` to ADD `state: str = "entered"` to the `Trade` dataclass (KEEP `status` for now; T3 drops it). This is a tiny pre-positioning edit; commit separately at end of A.0.
2. Edit every fixture builder + every direct `Trade(...)` to set both `status` (as it does today) AND `state` explicitly per the mapping in Step 2.
3. Run the new fixture tests; assert they pass.

- [ ] **Step 6: Run the test suite — verify nothing regressed.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1587 + 2 (new fixture tests) = 1589 fast tests pass. No regressions.

- [ ] **Step 7: Commit.**

```bash
git add tests/ swing/data/models.py
git commit -m "$(cat <<'EOF'
test(phase7): A.0 — pre-position state field on Trade + fixture refactor

Adds Trade.state with default 'entered' alongside existing status; updates
all fixture builders + direct Trade(...) constructions to set state
explicitly. T3 will drop status; this task gates that refactor by ensuring
the test corpus already references state.
EOF
)"
```

**Acceptance:** test count = baseline + 2; ruff clean; all fixtures construct Trade with explicit state.

**Expected new tests:** 2.

---

### Task A.1: Migration runner backup discipline (`swing/data/db.py`)

**Files:**
- Modify: `swing/data/db.py` — add `_create_pre_migration_backup()`, `_verify_backup_integrity()`, `MigrationBackupRequiredException`. Wire into `run_migrations()`.
- Test: `tests/data/test_migration_runner_backup.py` (NEW).

**Goal:** before applying migration to schema_version 14, create a backup via `Connection.backup()` (NOT `shutil.copy2`) and run 4 binding integrity checks (PRAGMA integrity_check + expected-table set). Refuse migration if backup fails.

Per spec §12.1: SQLite-native ONLY; size advisory NOT a hard gate.

- [ ] **Step 1: Write the failing tests (4 tests).**

```python
# tests/data/test_migration_runner_backup.py
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    MigrationBackupRequiredException,
    _create_pre_migration_backup,
    _verify_backup_integrity,
    run_migrations,
)


def _seed_v13_db(path: Path) -> None:
    """Build a schema-version-13 DB with the expected table set populated."""
    conn = sqlite3.connect(path)
    # Run migrations 0001..0013 in order. Reuse the existing
    # run_migrations helper but cap target version at 13. For test
    # simplicity, copy the production migrate-up logic.
    from swing.data.db import run_migrations as _run_all
    _run_all(conn, target_version=13)  # helper supports target_version param
    conn.close()


def test_backup_creates_file_via_sqlite_native(tmp_path):
    """The backup helper writes a non-empty file via Connection.backup()."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0


def test_backup_integrity_check_passes_on_healthy_db(tmp_path):
    """PRAGMA integrity_check on the backup returns 'ok' for a healthy DB."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    # Should not raise.
    _verify_backup_integrity(backup_path, expected_tables={"trades", "exits", "trade_events", "schema_version"})


def test_backup_missing_expected_table_raises(tmp_path):
    """If the backup is missing an expected table, integrity check raises."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    # Drop a table from the backup (simulate a torn backup).
    backup_conn = sqlite3.connect(backup_path)
    backup_conn.execute("DROP TABLE IF EXISTS trades")
    backup_conn.commit()
    backup_conn.close()
    with pytest.raises(MigrationBackupRequiredException, match="expected table"):
        _verify_backup_integrity(backup_path, expected_tables={"trades", "exits", "trade_events", "schema_version"})


def test_backup_zero_size_file_raises(tmp_path):
    """Discriminating: explicit check for the 'non-empty' integrity gate.
    A zero-byte backup file (e.g., truncated mid-write) is rejected even if
    the file exists."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = tmp_path / "swing-pre-phase7-migration-empty.db"
    backup_path.write_bytes(b"")  # zero bytes
    with pytest.raises(MigrationBackupRequiredException, match="empty"):
        _verify_backup_integrity(
            backup_path,
            expected_tables={"trades", "exits", "trade_events", "schema_version"},
        )


def test_backup_integrity_check_returns_non_ok_raises(tmp_path):
    """Discriminating: an SQLite file that opens cleanly but reports corruption
    on PRAGMA integrity_check is rejected (page-level corruption / broken
    indices / FK issues — what integrity_check is for). Simulated by writing
    garbage bytes to a SQLite file mid-page; in practice we just write a
    malformed page header to trigger non-ok return."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    # Corrupt page 2 of the backup (page 1 is the SQLite header; page 2 is
    # the schema page — corrupting it makes integrity_check fail without
    # making sqlite3.connect itself raise).
    with open(backup_path, "r+b") as f:
        f.seek(4096)  # default page size
        f.write(b"\xff" * 64)
    with pytest.raises(MigrationBackupRequiredException, match="integrity_check"):
        _verify_backup_integrity(
            backup_path,
            expected_tables={"trades", "exits", "trade_events", "schema_version"},
        )


def test_run_migrations_refuses_when_backup_path_unwritable(tmp_path, monkeypatch):
    """If the backup destination is unwritable, run_migrations refuses to migrate."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    # Point the backup dir at a path that cannot be written to.
    unwritable = tmp_path / "no_such_dir" / "deeper"
    conn = sqlite3.connect(src)
    with pytest.raises(MigrationBackupRequiredException):
        run_migrations(conn, target_version=14, backup_dir=unwritable)
    # Source DB schema_version should still be 13 (unchanged).
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == 13
```

- [ ] **Step 2: Run tests — should fail (helpers don't exist).**

```bash
python -m pytest tests/data/test_migration_runner_backup.py -v
```

Expected: 4 FAILs — `ImportError` on `_create_pre_migration_backup` etc.

- [ ] **Step 3: Implement helpers in `swing/data/db.py`.**

```python
# swing/data/db.py — additions

class MigrationBackupRequiredException(RuntimeError):
    """Raised when pre-migration backup creation or verification fails.
    Migration runner refuses to apply schema changes; source DB unchanged."""


def _create_pre_migration_backup(
    src_path: Path, *, dest_dir: Path | None = None,
) -> Path:
    """Create a SQLite-native consistent-snapshot backup of `src_path`.

    Uses `Connection.backup()` (transactional consistency under live writers).
    `shutil.copy2()` is NOT acceptable per spec §12.1 — filesystem-level copy
    of a live SQLite DB can yield a torn snapshot.
    """
    if dest_dir is None:
        dest_dir = src_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase7-migration-{timestamp}.db"
    src_conn = sqlite3.connect(src_path)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path


def _verify_backup_integrity(
    backup_path: Path, *, expected_tables: set[str],
) -> None:
    """Run 4 binding integrity checks per spec §12.1; raise on any failure.

    Checks (each independent + separately tested):
      1. File exists at backup path.
      2. File is non-empty (size > 0). Size threshold relative to source is
         advisory only — VACUUM INTO can legitimately compact; do NOT use a
         percentage-of-source heuristic as a hard gate (would yield false
         negatives on healthy backups).
      3. PRAGMA integrity_check returns exactly 'ok' (page-level corruption,
         broken indices, FK issues all surface here — authoritative integrity
         check per spec).
      4. sqlite_master contains the expected table set.
    """
    # 1. File exists.
    if not backup_path.exists():
        raise MigrationBackupRequiredException(
            f"backup file missing: {backup_path}"
        )
    # 2. File non-empty.
    if backup_path.stat().st_size == 0:
        raise MigrationBackupRequiredException(
            f"backup file empty: {backup_path}"
        )
    conn = sqlite3.connect(backup_path)
    try:
        # 3. PRAGMA integrity_check.
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise MigrationBackupRequiredException(
                f"PRAGMA integrity_check failed on backup: {result}"
            )
        # 4. Expected-table-set.
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        actual_tables = {r[0] for r in rows}
        missing = expected_tables - actual_tables
        if missing:
            raise MigrationBackupRequiredException(
                f"backup missing expected table(s): {sorted(missing)}"
            )
    finally:
        conn.close()


# Modify run_migrations to accept backup_dir + target_version params and
# invoke backup-then-verify before the version-14 migration:
def run_migrations(
    conn: sqlite3.Connection,
    *,
    target_version: int = EXPECTED_SCHEMA_VERSION,
    backup_dir: Path | None = None,
) -> None:
    current = _read_schema_version(conn)
    if current >= target_version:
        return
    # Phase 7 backup gate — before any migration whose target is >= 14.
    if current < 14 and target_version >= 14:
        src_path = Path(_resolve_db_path(conn))
        if backup_dir is None:
            backup_dir = src_path.parent
        try:
            backup_path = _create_pre_migration_backup(src_path, dest_dir=backup_dir)
            _verify_backup_integrity(backup_path, expected_tables=PHASE7_EXPECTED_TABLES)
        except (OSError, sqlite3.Error) as exc:
            raise MigrationBackupRequiredException(
                f"pre-Phase-7 backup failed: {exc}"
            ) from exc
    # ... existing migration loop (unchanged)


PHASE7_EXPECTED_TABLES = {
    "trades", "exits", "trade_events", "pipeline_runs", "weather_runs",
    "candidates", "evaluation_runs", "daily_recommendations", "watchlist",
    "cash_movements", "review_log", "schema_version",
}
```

- [ ] **Step 4: Run tests — should pass.**

```bash
python -m pytest tests/data/test_migration_runner_backup.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: baseline + 4 = 1593 fast tests pass.

- [ ] **Step 6: Commit.**

```bash
git add swing/data/db.py tests/data/test_migration_runner_backup.py
git commit -m "$(cat <<'EOF'
feat(data): A.1 — migration runner backup discipline (Phase 7)

Adds _create_pre_migration_backup() using Connection.backup() (SQLite-
native; not shutil.copy2) and _verify_backup_integrity() running PRAGMA
integrity_check + expected-table-set check. run_migrations refuses to
apply target_version >= 14 if backup fails, raising
MigrationBackupRequiredException; source DB remains untouched.

Per spec §12.1: shutil.copy2 explicitly forbidden; size threshold is
advisory only (VACUUM INTO can compact).
EOF
)"
```

**Acceptance:** 6 new tests pass; runner refuses on backup failure; source DB untouched; ruff clean. Migration-0004 helper (`swing/data/db.py:42,52,58,62`) rewritten per spec §5.3 to use `state IN ('entered','managing','partial_exited')`.

**Expected new tests:** 6.

---

### Task A.2: Migration 0014 SQL — schema + backfill

**Files:**
- Create: `swing/data/migrations/0014_phase7_state_machine_and_fills.sql`
- Modify: `swing/data/db.py` — bump `EXPECTED_SCHEMA_VERSION` to 14; register migration in the migration loop.

**Goal:** single transactional migration creates `fills`, backfills entry-action + exit-action fills, adds 21 new columns to `trades`, backfills `state`/`pre_trade_locked_at`/`trade_origin`/aggregate denorms, drops `exits`, table-rebuilds `trades` (adds CHECK + NOT NULL on new constrained cols, drops `status`, recreates partial-unique-index against `state`), table-rebuilds `trade_events` (expands `event_type` CHECK to include `pre_trade_edit`).

This task is the centerpiece of Sub-A. It is large but atomic; the migration safety tests in T9–T10 verify the post-migration state.

- [ ] **Step 1: Write a smoke test that asserts the migration applies cleanly to a v13 DB and bumps to v14.**

```python
# tests/data/test_migration_0014.py — smoke test for now; full coverage in T9/T10
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import run_migrations


def _seed_v13_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    run_migrations(conn, target_version=13)
    return conn


def test_migration_0014_smoke(tmp_path):
    """0014 applies cleanly to an empty (no trades) v13 DB; schema_version → 14."""
    db = tmp_path / "test.db"
    conn = _seed_v13_db(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == 14
    # New table exists.
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fills'"
    ).fetchall()
    assert len(rows) == 1
    # Old table is gone.
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='exits'"
    ).fetchall()
    assert len(rows) == 0
    # status column dropped from trades.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
    assert "status" not in cols
    assert "state" in cols
    assert "trade_origin" in cols
    assert "pre_trade_locked_at" in cols
    assert "current_size" in cols
    # New event_type value accepted.
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json)
        SELECT 0, '2026-05-04T12:00:00Z', 'pre_trade_edit', '{}'
        WHERE NOT EXISTS (SELECT 1 FROM trades)
        """
    )  # ON DELETE CASCADE means trade_id=0 fails FK; instead skip if no trades.
    # ... actually FK violation; this test merely confirms the CHECK accepts the value.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
        "VALUES (1, '2026-05-04T12:00:00Z', 'pre_trade_edit', '{}')"
    )
    # No CHECK violation = CHECK was expanded.
```

- [ ] **Step 2: Run the smoke test — should fail (migration doesn't exist).**

```bash
python -m pytest tests/data/test_migration_0014.py::test_migration_0014_smoke -v
```

Expected: FAIL — `run_migrations(target_version=14)` either raises (no migration registered) or returns without changing schema_version.

- [ ] **Step 3: Implement the migration SQL.**

Create `swing/data/migrations/0014_phase7_state_machine_and_fills.sql`:

```sql
-- Phase 7: Trade lifecycle state machine + Fills first-class.
-- Spec: docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md

BEGIN TRANSACTION;

-- 1. Create fills table.
CREATE TABLE fills (
  fill_id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  fill_datetime TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('entry','trim','exit','stop')),
  quantity REAL NOT NULL CHECK (quantity > 0),
  price REAL NOT NULL CHECK (price > 0),
  reason TEXT,
  rule_based INTEGER CHECK (rule_based IS NULL OR rule_based IN (0,1)),
  fees REAL,
  manual_entry_confidence TEXT
      CHECK (manual_entry_confidence IS NULL OR manual_entry_confidence IN ('high','normal','low')),
  reconciliation_status TEXT NOT NULL DEFAULT 'unreconciled'
      CHECK (reconciliation_status IN ('unreconciled','reconciled_match',
        'reconciled_discrepancy','reconciled_discrepancy_resolved','manual_override')),
  tos_match_id TEXT
);

CREATE INDEX ix_fills_trade ON fills(trade_id, fill_datetime);
CREATE INDEX ix_fills_action ON fills(trade_id, action);

-- 2. Backfill entry-action fills from trades (synthetic close-of-session timestamp).
INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, reason, reconciliation_status)
SELECT id, entry_date || 'T16:00:00', 'entry',
       CAST(initial_shares AS REAL), entry_price, NULL, 'unreconciled'
FROM trades;

-- 3. Backfill exit/trim/stop fills from exits with deterministic ordering.
-- Per-trade: ORDER BY exit_date ASC, id ASC. Last row in ordering = 'exit',
-- earlier rows = 'trim'. Notes merged into reason with ' | ' separator.
INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, reason, reconciliation_status)
SELECT
  e.trade_id,
  e.exit_date || 'T16:00:00',
  CASE
    WHEN e.id = (
      SELECT e2.id FROM exits e2
      WHERE e2.trade_id = e.trade_id
      ORDER BY e2.exit_date DESC, e2.id DESC LIMIT 1
    ) THEN 'exit'
    ELSE 'trim'
  END,
  CAST(e.shares AS REAL),
  e.exit_price,
  CASE
    WHEN e.notes IS NULL OR e.notes = '' THEN e.reason
    ELSE e.reason || ' | ' || e.notes
  END,
  'unreconciled'
FROM exits e;

-- 4. Add new columns to trades (initially NULLABLE for backfill;
--    table-rebuild step adds NOT NULL + CHECK on constrained cols).
ALTER TABLE trades ADD COLUMN state TEXT;
ALTER TABLE trades ADD COLUMN trade_origin TEXT;
ALTER TABLE trades ADD COLUMN pre_trade_locked_at TEXT;
ALTER TABLE trades ADD COLUMN current_size REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN current_avg_cost REAL;
ALTER TABLE trades ADD COLUMN last_fill_at TEXT;
ALTER TABLE trades ADD COLUMN thesis TEXT;
ALTER TABLE trades ADD COLUMN why_now TEXT;
ALTER TABLE trades ADD COLUMN invalidation_condition TEXT;
ALTER TABLE trades ADD COLUMN expected_scenario TEXT;
ALTER TABLE trades ADD COLUMN premortem_technical TEXT;
ALTER TABLE trades ADD COLUMN premortem_market_sector TEXT;
ALTER TABLE trades ADD COLUMN premortem_execution TEXT;
ALTER TABLE trades ADD COLUMN premortem_additional TEXT;
ALTER TABLE trades ADD COLUMN event_risk_present INTEGER;
ALTER TABLE trades ADD COLUMN event_handling TEXT;
ALTER TABLE trades ADD COLUMN event_type TEXT;
ALTER TABLE trades ADD COLUMN event_date TEXT;
ALTER TABLE trades ADD COLUMN gap_risk_present INTEGER;
ALTER TABLE trades ADD COLUMN gap_risk_handling TEXT;
ALTER TABLE trades ADD COLUMN emotional_state_pre_trade TEXT;
ALTER TABLE trades ADD COLUMN market_regime TEXT;
ALTER TABLE trades ADD COLUMN catalyst TEXT;
ALTER TABLE trades ADD COLUMN catalyst_other_description TEXT;

-- 5. Backfill state from status + reviewed_at + exits-presence.
UPDATE trades SET state = CASE
  WHEN status = 'closed' AND reviewed_at IS NOT NULL THEN 'reviewed'
  WHEN status = 'closed' AND reviewed_at IS NULL     THEN 'closed'
  WHEN EXISTS (SELECT 1 FROM exits WHERE exits.trade_id = trades.id) THEN 'partial_exited'
  ELSE 'managing'
END;

-- 6. Backfill pre_trade_locked_at = entry_date + 'T16:00:00'.
UPDATE trades SET pre_trade_locked_at = entry_date || 'T16:00:00';

-- 7. Backfill trade_origin (best-guess; per spec §12.3; operator confirmed FIRM).
UPDATE trades SET trade_origin = CASE
  WHEN ticker = 'VIR' THEN 'manual_off_pipeline'
  WHEN ticker IN ('DHC', 'CC') THEN 'pipeline_watch_hyp_recs'
  ELSE 'manual_off_pipeline'
END;

-- 8. Backfill current_size, current_avg_cost, last_fill_at from fills aggregates.
UPDATE trades SET
  current_size = COALESCE((
    SELECT SUM(CASE WHEN action = 'entry' THEN quantity ELSE -quantity END)
    FROM fills WHERE fills.trade_id = trades.id
  ), 0),
  current_avg_cost = (
    SELECT price FROM fills
    WHERE fills.trade_id = trades.id AND action = 'entry'
    ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
  ),
  last_fill_at = (
    SELECT MAX(fill_datetime) FROM fills WHERE fills.trade_id = trades.id
  );

-- 9. Drop exits table (data preserved in fills).
DROP TABLE exits;

-- 10. Table-rebuild trades: drop status, recreate partial-unique-index against state,
--     add NOT NULL + CHECK on new constrained cols.
DROP INDEX IF EXISTS ux_trades_one_open_per_ticker;

CREATE TABLE trades_new (
  id INTEGER PRIMARY KEY,
  ticker TEXT NOT NULL,
  entry_date TEXT NOT NULL,
  entry_price REAL NOT NULL,
  initial_shares INTEGER NOT NULL,
  initial_stop REAL NOT NULL,
  current_stop REAL NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('entered','managing','partial_exited','closed','reviewed')),
  watchlist_entry_target REAL,
  watchlist_initial_stop REAL,
  notes TEXT,
  hypothesis_label TEXT,
  chart_pattern_algo TEXT,
  chart_pattern_algo_confidence REAL,
  chart_pattern_operator TEXT,
  chart_pattern_classification_pipeline_run_id INTEGER,
  sector TEXT NOT NULL DEFAULT '',
  industry TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT,
  mistake_tags TEXT,
  entry_grade TEXT,
  management_grade TEXT,
  exit_grade TEXT,
  process_grade TEXT,
  disqualifying_process_violation INTEGER,
  realized_R_if_plan_followed REAL,
  mistake_cost_confidence TEXT
      CHECK (mistake_cost_confidence IS NULL OR mistake_cost_confidence IN ('high','medium','low')),
  lesson_learned TEXT,
  trade_origin TEXT NOT NULL CHECK (trade_origin IN
      ('pipeline_aplus','pipeline_watch_hyp_recs','pipeline_watch_manual','manual_off_pipeline')),
  pre_trade_locked_at TEXT NOT NULL,
  current_size REAL NOT NULL DEFAULT 0,
  current_avg_cost REAL,
  last_fill_at TEXT,
  thesis TEXT,
  why_now TEXT,
  invalidation_condition TEXT,
  expected_scenario TEXT,
  premortem_technical TEXT,
  premortem_market_sector TEXT,
  premortem_execution TEXT,
  premortem_additional TEXT,
  event_risk_present INTEGER CHECK (event_risk_present IS NULL OR event_risk_present IN (0,1)),
  event_handling TEXT
      CHECK (event_handling IS NULL OR event_handling IN
        ('avoid_event','hold_through','reduce_before','exit_before','not_applicable')),
  event_type TEXT
      CHECK (event_type IS NULL OR event_type IN
        ('earnings','fed_meeting','cpi_release','economic_data','product_announcement','legal_ruling','other')),
  event_date TEXT,
  gap_risk_present INTEGER CHECK (gap_risk_present IS NULL OR gap_risk_present IN (0,1)),
  gap_risk_handling TEXT
      CHECK (gap_risk_handling IS NULL OR gap_risk_handling IN
        ('accept','reduce_size','tight_stop','exit_before_close','not_applicable')),
  emotional_state_pre_trade TEXT,
  market_regime TEXT
      CHECK (market_regime IS NULL OR market_regime IN ('Bullish','Caution','Bearish')),
  catalyst TEXT
      CHECK (catalyst IS NULL OR catalyst IN
        ('earnings_driven','guidance_change','corporate_action','sector_rotation',
         'macro_event','sympathy_move','product_news','technical_only','other')),
  catalyst_other_description TEXT
);

INSERT INTO trades_new
  (id, ticker, entry_date, entry_price, initial_shares, initial_stop, current_stop,
   state, watchlist_entry_target, watchlist_initial_stop, notes, hypothesis_label,
   chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator,
   chart_pattern_classification_pipeline_run_id, sector, industry,
   reviewed_at, mistake_tags, entry_grade, management_grade, exit_grade,
   process_grade, disqualifying_process_violation, realized_R_if_plan_followed,
   mistake_cost_confidence, lesson_learned,
   trade_origin, pre_trade_locked_at, current_size, current_avg_cost, last_fill_at,
   thesis, why_now, invalidation_condition, expected_scenario,
   premortem_technical, premortem_market_sector, premortem_execution, premortem_additional,
   event_risk_present, event_handling, event_type, event_date,
   gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
   market_regime, catalyst, catalyst_other_description)
SELECT
  id, ticker, entry_date, entry_price, initial_shares, initial_stop, current_stop,
  state, watchlist_entry_target, watchlist_initial_stop, notes, hypothesis_label,
  chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator,
  chart_pattern_classification_pipeline_run_id, sector, industry,
  reviewed_at, mistake_tags, entry_grade, management_grade, exit_grade,
  process_grade, disqualifying_process_violation, realized_R_if_plan_followed,
  mistake_cost_confidence, lesson_learned,
  trade_origin, pre_trade_locked_at, current_size, current_avg_cost, last_fill_at,
  thesis, why_now, invalidation_condition, expected_scenario,
  premortem_technical, premortem_market_sector, premortem_execution, premortem_additional,
  event_risk_present, event_handling, event_type, event_date,
  gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
  market_regime, catalyst, catalyst_other_description
FROM trades;

DROP TABLE trades;
ALTER TABLE trades_new RENAME TO trades;

CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
  ON trades(ticker) WHERE state IN ('entered','managing','partial_exited');

-- 11. Table-rebuild trade_events to expand event_type CHECK.
CREATE TABLE trade_events_new (
  id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  ts TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN
      ('entry','stop_adjust','note','exit','flag','pre_trade_edit')),
  payload_json TEXT,
  rationale TEXT,
  notes TEXT
);

INSERT INTO trade_events_new (id, trade_id, ts, event_type, payload_json, rationale, notes)
SELECT id, trade_id, ts, event_type, payload_json, rationale, notes FROM trade_events;

DROP TABLE trade_events;
ALTER TABLE trade_events_new RENAME TO trade_events;

CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- 12. Bump schema_version.
UPDATE schema_version SET version = 14;

COMMIT;
```

Then in `swing/data/db.py`:

```python
EXPECTED_SCHEMA_VERSION = 14  # bumped from 13
# Migration 0014 is registered in the same migration loop as 0001-0013;
# the loop discovers it by filename pattern.
```

- [ ] **Step 4: Run the smoke test — should pass.**

```bash
python -m pytest tests/data/test_migration_0014.py::test_migration_0014_smoke -v
```

Expected: PASS.

- [ ] **Step 5: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: many failures expected at this point — the `Trade` dataclass still has `status` (T0 added `state` alongside; T3 will drop `status`). Ignore those for now; this task's gate is the smoke test + ruff clean on the migration file.

Actually, with status still on `Trade` and the column dropped from the schema, `repos/trades.py:get_trade` will fail at SELECT time. Reorder per dependency:

The dependency requires: T2 (migration drops `status` column) DOES regress runtime code that still SELECTs `status`. The migration must land AFTER models + repos are migrated, OR the migration must keep `status` as a derived view temporarily.

**Resolution:** reorder Sub-A so T3 (models) + T6 (repos) land BEFORE T2 (migration). Updated Sub-A ordering:
- T0: fixture refactor (adds state alongside status)
- T1: backup runner discipline
- T3: models — drop status from Trade dataclass; add state + new fields
- T6: repos — rewrite SELECT/INSERT to drop status, use state
- (now Trade dataclass and repos are state-aware but DB still has status column — runtime will fail until migration lands; tests must use a DB at v14 schema)
- T2: migration 0014 SQL itself

But this creates a window where the runtime code is incompatible with the v13 schema. Tests for T3+T6 must seed a v14 DB (i.e., apply migration 0014). So T2 must land BEFORE T3+T6's tests can pass.

**Actual resolution:** T2 + T3 + T6 land in the SAME COMMIT (or 3 commits within the same task batch with the migration applied to test DBs ahead of repos test runs). The TDD cycle is:
1. T0 lands first (fixture refactor only, no schema change).
2. T1 lands second (backup runner; pure addition).
3. T2/T3/T6 land as a batch — migration SQL + models.py drop-and-add + repos.py rewrites — committed in 3 successive commits but with the test seeding sequence: each test calls `run_migrations(target_version=14)` first.

To preserve TDD discipline within the batch:
- T2 commit: migration SQL only; smoke test (table-shape assertions only; doesn't construct `Trade` at all). Existing tests that import `repos/trades.py` will fail, but we'll fix them in T3+T6.
- T3 commit: models.py drops `status`, adds `state` + 21 fields; updates all `Trade(...)` constructions in `swing/`. Existing repos.py `INSERT INTO trades(... status, ...)` will fail at SQL time on a v14 DB.
- T6 commit: repos.py rewrites to use `state` + new cols. After this commit, the suite is restored.

So the dependency chain is: T0 → T1 → T2 (broken state) → T3 (still broken) → T6 (restored). Within Sub-A, this is acceptable because the executing-plans dispatch's worktree is isolated; intermediate commits don't ship to main until the whole sub-dispatch passes its full-suite-green gate.

UPDATE the Sub-A task ordering accordingly — see §4.0.1 below.

- [ ] **Step 6: Commit (migration SQL + db.py constants).**

```bash
git add swing/data/migrations/0014_phase7_state_machine_and_fills.sql swing/data/db.py tests/data/test_migration_0014.py
git commit -m "$(cat <<'EOF'
feat(data): A.2 — migration 0014 phase7 state machine and fills

Single transactional migration: creates fills with 4-action CHECK enum;
backfills entry-action fills from trades and trim/exit fills from exits
with deterministic ordering; adds 21 new cols to trades; backfills state
from status + reviewed_at + exits-presence; drops exits; rebuilds trades
(drop status, add NOT NULL + CHECK constraints, recreate partial unique
index against state); rebuilds trade_events to expand event_type CHECK
to include pre_trade_edit; bumps schema_version 13 → 14.

Smoke test verifies post-migration table shape. Full migration safety
tests (4-fixture preservation invariant + VIR/DHC/CC backfill) land in
T9/T10. Runtime code (models, repos) requires T3+T6 to compile against
the new schema; TDD discipline within the sub-dispatch.
EOF
)"
```

**Acceptance:** smoke test passes; migration file present; schema_version constant bumped; ruff clean.

**Expected new tests:** 1 (smoke; full suite in T9/T10).

---

### §4.0.1 Sub-A revised task ordering (commit-grain TDD discipline within the broken-state window)

The migration SQL drops `status` from the schema; runtime code that SELECTs `status` fails until repos is rewritten. The Sub-A worktree must absorb a transient broken-state window between T2 and T6. Acceptable because Sub-A is a single executing-plans dispatch; intermediate commits don't reach main until the whole dispatch passes the full-suite-green gate.

Final Sub-A ordering:
- T0: fixture refactor (state added alongside status; full suite green).
- T1: backup runner discipline (pure addition; full suite green).
- T2: migration SQL + db.py constants (full suite RED; only the migration smoke test passes).
- T3: models.py drops status + adds state + 21 fields (full suite STILL RED until T6; type assertions in tests/ may still fail).
- T4: fills repo (NEW; isolated; the new tests pass on a v14 DB).
- T5: state service (NEW; isolated; the new tests pass on a v14 DB).
- T6: repos/trades.py rewrites — SELECT/INSERT drop status, use state. **Full suite GREEN at this point.**
- T7: origin service (NEW; isolated).
- T8: derived_metrics service (NEW; isolated).
- T9: migration safety tests — 4 preservation invariant fixtures.
- T10: in-flight migration tests — VIR/DHC/CC.

The full-suite-green gate at end of T6 is binding for Sub-A merge to main. T7–T10 add coverage on top.

---

### Task A.3: Models — drop `status` from Trade; add `state` + 21 new fields; new `Fill` dataclass; remove `Exit`

**Files:**
- Modify: `swing/data/models.py`

**Goal:** Trade dataclass loses `status`, gains `state` + 21 new pre-trade fields. New Fill dataclass mirrors fills schema. Exit dataclass removed (and any imports of it become dead code; T6 cleans up).

- [ ] **Step 1: Write a failing test asserting the new dataclass shape.**

Per A.0 deferred assertion: this is where `Trade` drops `status` entirely. Update `tests/data/test_fixture_builders.py:test_make_trade_status_alongside_state_in_A0_window` simultaneously to assert `not hasattr(t, "status")` (the assertion deferred from A.0). Rename the test function in the same commit:

```python
# tests/data/test_fixture_builders.py — modify in this task
def test_make_trade_drops_status_attr():
    t = make_trade(ticker="TEST", state="entered")
    assert not hasattr(t, "status")
    assert hasattr(t, "state")
```

```python
# tests/data/test_models_phase7.py — NEW
from dataclasses import fields

from swing.data.models import Fill, Trade


def test_trade_dataclass_drops_status_adds_state():
    field_names = {f.name for f in fields(Trade)}
    assert "status" not in field_names
    assert "state" in field_names
    # Sample of the 21 new fields:
    for new_field in (
        "trade_origin", "pre_trade_locked_at", "current_size", "current_avg_cost",
        "last_fill_at", "thesis", "why_now", "invalidation_condition",
        "expected_scenario", "premortem_technical", "premortem_market_sector",
        "premortem_execution", "premortem_additional",
        "event_risk_present", "event_handling", "event_type", "event_date",
        "gap_risk_present", "gap_risk_handling", "emotional_state_pre_trade",
        "market_regime", "catalyst", "catalyst_other_description",
    ):
        assert new_field in field_names, f"missing field: {new_field}"


def test_fill_dataclass_shape():
    field_names = {f.name for f in fields(Fill)}
    expected = {
        "fill_id", "trade_id", "fill_datetime", "action", "quantity", "price",
        "reason", "rule_based", "fees", "manual_entry_confidence",
        "reconciliation_status", "tos_match_id",
    }
    assert field_names == expected


def test_exit_dataclass_removed():
    """Exit dataclass is removed; imports raise AttributeError."""
    from swing.data import models as mod
    assert not hasattr(mod, "Exit")
```

- [ ] **Step 2: Run tests — should fail.**

```bash
python -m pytest tests/data/test_models_phase7.py -v
```

Expected: 3 FAILs.

- [ ] **Step 3: Update `swing/data/models.py`.**

Replace the existing `Trade` dataclass with a new shape; remove the `Exit` dataclass; add a new `Fill` dataclass.

```python
# swing/data/models.py — Trade dataclass replaced

@dataclass(frozen=True)
class Trade:
    id: int | None
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    state: str  # 'entered'|'managing'|'partial_exited'|'closed'|'reviewed'
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    hypothesis_label: str | None = None
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_operator: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    sector: str = ""
    industry: str = ""
    # Phase 6 review fields (unchanged):
    reviewed_at: str | None = None
    mistake_tags: str | None = None
    entry_grade: str | None = None
    management_grade: str | None = None
    exit_grade: str | None = None
    process_grade: str | None = None
    disqualifying_process_violation: bool | None = None
    realized_R_if_plan_followed: float | None = None  # noqa: N815
    mistake_cost_confidence: str | None = None
    lesson_learned: str | None = None
    # Phase 7 lifecycle fields (atomic with state; NOT NULL in schema):
    trade_origin: str = "manual_off_pipeline"  # default safe for migration backfill
    pre_trade_locked_at: str = ""              # set atomically by entry service
    current_size: float = 0.0
    current_avg_cost: float | None = None
    last_fill_at: str | None = None
    # Phase 7 pre-trade decision fields (NULLABLE; legacy persists NULL):
    thesis: str | None = None
    why_now: str | None = None
    invalidation_condition: str | None = None
    expected_scenario: str | None = None
    premortem_technical: str | None = None
    premortem_market_sector: str | None = None
    premortem_execution: str | None = None
    premortem_additional: str | None = None
    event_risk_present: int | None = None  # 0|1
    event_handling: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    gap_risk_present: int | None = None
    gap_risk_handling: str | None = None
    emotional_state_pre_trade: str | None = None  # JSON-list TEXT
    market_regime: str | None = None
    catalyst: str | None = None
    catalyst_other_description: str | None = None


# REMOVED: Exit dataclass (data migrated to Fill).


@dataclass(frozen=True)
class Fill:
    fill_id: int | None
    trade_id: int
    fill_datetime: str  # ISO-8601
    action: str  # 'entry'|'trim'|'exit'|'stop'
    quantity: float
    price: float
    reason: str | None = None
    rule_based: int | None = None  # 0|1
    fees: float | None = None
    manual_entry_confidence: str | None = None  # 'high'|'normal'|'low'
    reconciliation_status: str = "unreconciled"
    tos_match_id: str | None = None
```

- [ ] **Step 4: Run tests — should pass.**

```bash
python -m pytest tests/data/test_models_phase7.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: The full suite is RED at this commit-point.**

`tests/data/test_repos_trades.py` and many others reference `Trade.status`. T6 will fix them. Acceptable because Sub-A worktree absorbs the broken-state window between T2 and T6.

- [ ] **Step 6: Commit.**

```bash
git add swing/data/models.py tests/data/test_models_phase7.py
git commit -m "$(cat <<'EOF'
feat(data): A.3 — Trade drops status, gains state + 21 Phase 7 fields

Adds Fill dataclass mirroring fills schema. Removes Exit dataclass (data
migrated to Fill in 0014). Suite is transient RED until A.6 lands the
repos rewrite; expected per Sub-A revised ordering §4.0.1.
EOF
)"
```

**Acceptance:** 3 new tests pass; ruff clean on models.py.

**Expected new tests:** 3.

---

### Task A.4: Fills repo + aggregate recompute

**Files:**
- Create: `swing/data/repos/fills.py`
- Test: `tests/data/test_fills_repo.py` (NEW)

**Goal:** CRUD for fills; `_recompute_aggregates()` private helper; `get_authoritative_entry_fill()` per spec §4.3.1; aggregate-consistency invariant.

- [ ] **Step 1: Write failing tests.**

```python
# tests/data/test_fills_repo.py
import sqlite3

import pytest

from swing.data.db import run_migrations
from swing.data.models import Fill, Trade
from swing.data.repos.fills import (
    get_authoritative_entry_fill,
    insert_fill_with_event,
    list_fills_for_trade,
)
from swing.data.repos.trades import get_trade, insert_trade_with_event


def _seed_v14(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _seed_trade(conn, ticker="AAA", state="entered") -> int:
    """Insert a fresh trade with the minimal valid Phase 7 NOT NULL fields."""
    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-05-01",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state=state,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-05-01T16:00:00",
    )
    return insert_trade_with_event(conn, trade, event_ts="2026-05-01T16:00:00")


def test_insert_entry_fill_recomputes_aggregates(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    fill = Fill(
        fill_id=None, trade_id=trade_id,
        fill_datetime="2026-05-01T16:00:00", action="entry",
        quantity=100.0, price=10.0,
    )
    with conn:
        insert_fill_with_event(conn, fill, event_ts="2026-05-01T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.current_size == 100.0
    assert trade.current_avg_cost == 10.0
    assert trade.last_fill_at == "2026-05-01T16:00:00"


def test_insert_trim_fill_decrements_current_size(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=40.0, price=11.0, reason="resistance",
        ), event_ts="2026-05-02T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.current_size == 60.0
    assert trade.last_fill_at == "2026-05-02T16:00:00"


def test_get_authoritative_entry_fill_picks_first_by_datetime(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        # Two entry-action fills (synthetic; V1 service-layer enforces single
        # entry-fill but schema permits multi for future Phase 9).
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="entry",
            quantity=50.0, price=11.0,
        ), event_ts="2026-05-02T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",  # earlier
            quantity=50.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
    auth = get_authoritative_entry_fill(conn, trade_id)
    assert auth.price == 10.0
    assert auth.fill_datetime == "2026-05-01T16:00:00"


def test_list_fills_for_trade_orders_by_datetime(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-03T16:00:00", action="exit",
            quantity=60.0, price=12.0, reason="target",
        ), event_ts="2026-05-03T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=40.0, price=11.0, reason="resistance",
        ), event_ts="2026-05-02T16:00:00")
    fills = list_fills_for_trade(conn, trade_id)
    assert [f.action for f in fills] == ["entry", "trim", "exit"]


def test_aggregate_consistency_invariant(tmp_path):
    """current_size = sum(entry quantities) - sum(trim/exit/stop quantities)."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=30.0, price=11.0, reason="r1",
        ), event_ts="2026-05-02T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-03T16:00:00", action="stop",
            quantity=70.0, price=9.0, reason="stop-hit",
        ), event_ts="2026-05-03T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.current_size == 0.0  # 100 - 30 - 70 = 0


def test_check_constraint_rejects_invalid_action(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    fill = Fill(
        fill_id=None, trade_id=trade_id,
        fill_datetime="2026-05-01T16:00:00", action="bogus",
        quantity=100.0, price=10.0,
    )
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            insert_fill_with_event(conn, fill, event_ts="2026-05-01T16:00:00")
```

- [ ] **Step 2: Run tests — should fail.**

```bash
python -m pytest tests/data/test_fills_repo.py -v
```

Expected: 6 FAILs (ImportError; the repo doesn't exist).

- [ ] **Step 3: Implement `swing/data/repos/fills.py`.**

```python
"""Fills repo — canonical execution log replacing exits.

Phase 7 introduces fills as the single source of truth for trade
execution events. Every insert recomputes the trade's aggregate denorm
columns (current_size, current_avg_cost, last_fill_at) in the same
transaction; the caller wraps with `with conn:`.
"""
from __future__ import annotations

import json
import sqlite3

from swing.data.models import Fill


def insert_fill_with_event(
    conn: sqlite3.Connection, fill: Fill, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert a fill, recompute trade aggregates, write a trade_events row.

    All in caller's transaction. Returns the new fill_id.
    """
    cur = conn.execute(
        """
        INSERT INTO fills
            (trade_id, fill_datetime, action, quantity, price, reason,
             rule_based, fees, manual_entry_confidence,
             reconciliation_status, tos_match_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fill.trade_id, fill.fill_datetime, fill.action, fill.quantity,
            fill.price, fill.reason, fill.rule_based, fill.fees,
            fill.manual_entry_confidence, fill.reconciliation_status,
            fill.tos_match_id,
        ),
    )
    fill_id = int(cur.lastrowid)

    _recompute_aggregates(conn, fill.trade_id)

    payload = {
        "action": fill.action,
        "quantity": fill.quantity,
        "price": fill.price,
        "fill_datetime": fill.fill_datetime,
    }
    # Map fill action to trade_events.event_type ('entry'/'exit' for now;
    # 'trim' and 'stop' co-opt 'exit' on the audit row since the existing
    # trade_events enum doesn't have separate trim/stop values, and we're
    # not expanding it in 0014 beyond pre_trade_edit).
    audit_event_type = "entry" if fill.action == "entry" else "exit"
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            fill.trade_id, event_ts, audit_event_type,
            json.dumps(payload, sort_keys=True), rationale,
        ),
    )
    return fill_id


def _recompute_aggregates(conn: sqlite3.Connection, trade_id: int) -> None:
    """Update trades.current_size + current_avg_cost + last_fill_at from fills.

    Single write path; consistency invariant: current_size = sum(entry qty)
    - sum(trim/exit/stop qty).
    V1: current_avg_cost == entry_price (single entry-fill per trade);
    formula reads the authoritative entry-fill price.
    """
    conn.execute(
        """
        UPDATE trades SET
          current_size = COALESCE((
            SELECT SUM(CASE WHEN action = 'entry' THEN quantity ELSE -quantity END)
            FROM fills WHERE fills.trade_id = ?
          ), 0),
          current_avg_cost = (
            SELECT price FROM fills
            WHERE fills.trade_id = ? AND action = 'entry'
            ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
          ),
          last_fill_at = (
            SELECT MAX(fill_datetime) FROM fills WHERE fills.trade_id = ?
          )
        WHERE id = ?
        """,
        (trade_id, trade_id, trade_id, trade_id),
    )


def get_authoritative_entry_fill(
    conn: sqlite3.Connection, trade_id: int,
) -> Fill | None:
    """Per spec §4.3.1: first entry-fill by (fill_datetime ASC, fill_id ASC)."""
    row = conn.execute(
        """
        SELECT fill_id, trade_id, fill_datetime, action, quantity, price,
               reason, rule_based, fees, manual_entry_confidence,
               reconciliation_status, tos_match_id
        FROM fills
        WHERE trade_id = ? AND action = 'entry'
        ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
        """,
        (trade_id,),
    ).fetchone()
    if row is None:
        return None
    return Fill(*row)


def list_fills_for_trade(
    conn: sqlite3.Connection, trade_id: int,
) -> list[Fill]:
    rows = conn.execute(
        """
        SELECT fill_id, trade_id, fill_datetime, action, quantity, price,
               reason, rule_based, fees, manual_entry_confidence,
               reconciliation_status, tos_match_id
        FROM fills
        WHERE trade_id = ?
        ORDER BY fill_datetime ASC, fill_id ASC
        """,
        (trade_id,),
    ).fetchall()
    return [Fill(*r) for r in rows]
```

- [ ] **Step 4: Run tests — should pass.**

Note: tests depend on T6 having rewritten `insert_trade_with_event` to use the new schema. If T4 is implemented before T6, write a temporary direct-INSERT helper in the test file. Sub-A executing-plans dispatch resolves this by interleaving T4 + T5 + T7 + T8 (NEW files; isolated) AFTER T6 (repos rewrite) lands.

Updated ordering: T0 → T1 → T2 → T3 → **T6** → T4 → T5 → T7 → T8 → T9 → T10. (T6 immediately after T3 to restore suite-green.)

```bash
python -m pytest tests/data/test_fills_repo.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit.**

```bash
git add swing/data/repos/fills.py tests/data/test_fills_repo.py
git commit -m "$(cat <<'EOF'
feat(data): A.4 — fills repo + aggregate recompute

Adds insert_fill_with_event() with single-write-path aggregate
recompute; get_authoritative_entry_fill() per spec §4.3.1
deterministic ordering (fill_datetime ASC, fill_id ASC); list_fills_for_trade.

CHECK constraints on action enum + quantity > 0 + price > 0 enforced
by schema; 6 tests cover happy path + multi-fill aggregates +
authoritative selector + bogus-action rejection.
EOF
)"
```

**Acceptance:** 6 new tests pass; aggregate recompute consistent; ruff clean.

**Expected new tests:** 6.

---

### Task A.5: State service + transition matrix + validate_for_operation

**Files:**
- Create: `swing/trades/state.py`
- Test: `tests/trades/test_state.py` (NEW)

**Goal:** single state-transition write path with 5×5 transition matrix; `validate_for_operation` per spec §3.5.1; `MissingPreTradeFieldsException`.

- [ ] **Step 1: Write the 25-cell transition matrix test (parameterized) + per-operation required-fields tests.**

```python
# tests/trades/test_state.py — NEW
import sqlite3

import pytest

from swing.data.db import run_migrations
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.trades.state import (
    ALLOWED_TRANSITIONS,
    InvalidStateTransition,
    MissingPreTradeFieldsException,
    OPERATION_REQUIRED_FIELDS,
    state_transition,
    validate_for_operation,
)

ALL_STATES = ["entered", "managing", "partial_exited", "closed", "reviewed"]


def _seed_v14(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _seed_trade_in_state(conn, state: str) -> int:
    trade = Trade(
        id=None, ticker="TST", entry_date="2026-05-01",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state=state,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-05-01T16:00:00",
    )
    return insert_trade_with_event(conn, trade, event_ts="2026-05-01T16:00:00")


@pytest.mark.parametrize("from_state,to_state", [
    (f, t) for f in ALL_STATES for t in ALL_STATES
])
def test_transition_matrix_25_cells(tmp_path, from_state, to_state):
    """5×5 transition matrix: 5 allowed, 20 rejected."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade_in_state(conn, from_state)
    is_allowed = (from_state, to_state) in ALLOWED_TRANSITIONS
    if is_allowed:
        with conn:
            state_transition(
                conn, trade_id=trade_id, new_state=to_state,
                event_ts="2026-05-02T16:00:00",
            )
        cur = conn.execute("SELECT state FROM trades WHERE id = ?", (trade_id,))
        assert cur.fetchone()[0] == to_state
    else:
        with pytest.raises(InvalidStateTransition):
            with conn:
                state_transition(
                    conn, trade_id=trade_id, new_state=to_state,
                    event_ts="2026-05-02T16:00:00",
                )


def test_allowed_transitions_count_is_exactly_5():
    """Sanity: no over- or under-counting in the allowed set."""
    assert len(ALLOWED_TRANSITIONS) == 5


def test_validate_for_operation_entry_create_rejects_missing_thesis():
    req = {
        "ticker": "TST", "entry_date": "2026-05-01", "entry_price": 10.0,
        "initial_shares": 100, "initial_stop": 9.0,
        "trade_origin": "manual_off_pipeline",
        "pre_trade_locked_at": "2026-05-01T16:00:00",
        # 'thesis' missing
        "why_now": "x", "invalidation_condition": "y", "expected_scenario": "z",
        "premortem_technical": "a", "premortem_market_sector": "b",
        "premortem_execution": "c",
        "event_risk_present": 0, "gap_risk_present": 0,
        "emotional_state_pre_trade": '["calm"]',
        "market_regime": "Bullish", "catalyst": "technical_only",
        "manual_entry_confidence": "normal",
    }
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    assert "thesis" in missing


def test_validate_for_operation_entry_create_complete_passes():
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["entry_create"]}
    # Numeric overrides:
    req["entry_price"] = 10.0
    req["initial_shares"] = 100
    req["initial_stop"] = 9.0
    req["event_risk_present"] = 0
    req["gap_risk_present"] = 0
    req["emotional_state_pre_trade"] = '["calm"]'
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    assert missing == []


def test_validate_for_operation_transition_managing_no_required_fields():
    """transition_managing has no required fields (trigger event suffices)."""
    missing = validate_for_operation({}, op="transition_managing", current_state="entered")
    assert missing == []


def test_validate_for_operation_transition_reviewed_requires_phase6_fields():
    req = {}
    missing = validate_for_operation(req, op="transition_reviewed", current_state="closed")
    for required in (
        "reviewed_at", "mistake_tags",
        "entry_grade", "management_grade", "exit_grade", "process_grade",
        "disqualifying_process_violation",
        "realized_R_if_plan_followed",
        "mistake_cost_confidence",
        "lesson_learned",
    ):
        assert required in missing


@pytest.mark.parametrize("missing_field", [
    "reviewed_at", "mistake_tags",
    "entry_grade", "management_grade", "exit_grade", "process_grade",
    "disqualifying_process_violation",
    "realized_R_if_plan_followed",
    "mistake_cost_confidence",
    "lesson_learned",
])
def test_transition_reviewed_per_field_discriminator(missing_field):
    """Discriminating per-field test: each Phase 6 review field, removed individually,
    surfaces in the missing list. Catches an OPERATION_REQUIRED_FIELDS tuple that
    silently omits any one of these (regression that would let an incomplete review
    transition through to state='reviewed')."""
    req = {f: "x" for f in OPERATION_REQUIRED_FIELDS["transition_reviewed"]}
    req["disqualifying_process_violation"] = 0
    req["realized_R_if_plan_followed"] = 0.0
    del req[missing_field]
    missing = validate_for_operation(req, op="transition_reviewed", current_state="closed")
    assert missing_field in missing


def test_state_transition_writes_trade_events_audit_row(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade_in_state(conn, "entered")
    with conn:
        state_transition(
            conn, trade_id=trade_id, new_state="managing",
            event_ts="2026-05-02T16:00:00", rationale="first stop adjust",
        )
    rows = conn.execute(
        "SELECT event_type, payload_json FROM trade_events "
        "WHERE trade_id = ? AND event_type IN ('stop_adjust','note') "
        "ORDER BY ts DESC", (trade_id,),
    ).fetchall()
    # state_transition emits a 'note' event with the transition details since
    # event_type='state_transition' isn't in the CHECK enum.
    # Audit confirmation: at least one 'note' row with payload referencing the new state.
    assert any("managing" in (r[1] or "") for r in rows)


def test_missing_pre_trade_fields_exception_carries_field_list():
    exc = MissingPreTradeFieldsException(missing_fields=["thesis", "why_now"])
    assert exc.missing_fields == ["thesis", "why_now"]
    assert "thesis" in str(exc)
```

- [ ] **Step 2: Run tests — should fail.**

```bash
python -m pytest tests/trades/test_state.py -v
```

Expected: many FAILs (ImportError; service doesn't exist).

- [ ] **Step 3: Implement `swing/trades/state.py`.**

```python
"""State-machine service — single write path for trade.state mutations.

Per spec §3 + §3.5.1: 5-state lifecycle; 5 allowed transitions; operation-
contextual validation (NOT retroactive invariants on existing rows).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal, Mapping


# (from_state, to_state) tuples representing every allowed transition.
ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("entered", "managing"),
    ("managing", "partial_exited"),
    ("managing", "closed"),
    ("partial_exited", "closed"),
    ("closed", "reviewed"),
})


# Per spec §3.5.1: the validator selects the exact required-field set per
# operation; no fallback to "validate everything for the target state."
OPERATION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "entry_create": (
        "ticker", "entry_date", "entry_price", "initial_shares", "initial_stop",
        "trade_origin", "pre_trade_locked_at",
        "thesis", "why_now", "invalidation_condition", "expected_scenario",
        "premortem_technical", "premortem_market_sector", "premortem_execution",
        "event_risk_present", "gap_risk_present",
        "emotional_state_pre_trade",
        "market_regime", "catalyst",
        "manual_entry_confidence",
    ),
    "transition_managing": (),
    "transition_partial_exited": (),
    "transition_closed": (),
    "transition_reviewed": (
        "reviewed_at", "mistake_tags",
        "entry_grade", "management_grade", "exit_grade", "process_grade",
        "disqualifying_process_violation",
        "realized_R_if_plan_followed",
        "mistake_cost_confidence",
        "lesson_learned",
    ),
}


_CONDITIONAL_FIELD_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (gating_field, gating_value, required-when-gated fields)
    ("event_risk_present", 1, ("event_handling", "event_type", "event_date")),
    ("gap_risk_present", 1, ("gap_risk_handling",)),
    ("catalyst", "other", ("catalyst_other_description",)),
)


class InvalidStateTransition(ValueError):
    """Raised when state_transition is called with a (from, to) pair not in ALLOWED_TRANSITIONS."""


class MissingPreTradeFieldsException(ValueError):
    """Raised when validate_for_operation returns a non-empty missing list
    AND the caller is in entry-create context. Carries the structured field
    list for surface-specific error rendering (form re-render highlights, CLI
    stderr, hyp-recs panel error)."""

    def __init__(self, *, missing_fields: list[str]):
        self.missing_fields = missing_fields
        super().__init__(
            f"Missing required pre-trade fields: {', '.join(missing_fields)}"
        )


Operation = Literal[
    "entry_create",
    "transition_managing",
    "transition_partial_exited",
    "transition_closed",
    "transition_reviewed",
]


def validate_for_operation(
    req: Mapping[str, Any], *,
    op: Operation,
    current_state: str | None,
) -> list[str]:
    """Returns a sorted list of missing/empty required-field names; empty if valid.

    Operation-contextual: each `op` selects an exact required-field set;
    no inheritance from "the target state's required fields." Legacy rows
    pre-Phase-7 are exempt by NULLABLE schema; transition operations on
    legacy rows only validate their delta fields, not pre-trade fields.

    Conditional fields (event_*, gap_*, catalyst_other_description) are
    appended to the missing list when the gating flag indicates required.
    """
    missing: list[str] = []
    required = OPERATION_REQUIRED_FIELDS.get(op, ())
    for field in required:
        value = req.get(field) if isinstance(req, Mapping) else getattr(req, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    # Conditional rules (only fire on entry_create; transitions don't re-check pre-trade).
    if op == "entry_create":
        for gating_field, gating_value, deps in _CONDITIONAL_FIELD_RULES:
            actual = req.get(gating_field) if isinstance(req, Mapping) else getattr(req, gating_field, None)
            if actual == gating_value:
                for dep in deps:
                    val = req.get(dep) if isinstance(req, Mapping) else getattr(req, dep, None)
                    if val is None or (isinstance(val, str) and not val.strip()):
                        missing.append(dep)
    return sorted(set(missing))


def state_transition(
    conn: sqlite3.Connection, *,
    trade_id: int,
    new_state: str,
    event_ts: str,
    rationale: str | None = None,
) -> None:
    """Single write path for trade.state mutation. Atomic: state UPDATE +
    trade_events audit row in same transaction (caller's `with conn:`).

    Rejects illegal transitions per ALLOWED_TRANSITIONS; rejects unknown
    trade_id; rejects unknown new_state.
    """
    if new_state not in {"entered", "managing", "partial_exited", "closed", "reviewed"}:
        raise InvalidStateTransition(f"unknown state: {new_state!r}")
    row = conn.execute(
        "SELECT state FROM trades WHERE id = ?", (trade_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"trade {trade_id} not found")
    current_state = row[0]
    if (current_state, new_state) not in ALLOWED_TRANSITIONS:
        raise InvalidStateTransition(
            f"transition {current_state!r} → {new_state!r} not allowed"
        )
    conn.execute(
        "UPDATE trades SET state = ? WHERE id = ?", (new_state, trade_id),
    )
    payload = {"from_state": current_state, "to_state": new_state}
    # Use 'note' event_type since 'state_transition' is NOT in the CHECK enum;
    # the audit's payload_json carries the structured transition.
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale, notes)
        VALUES (?, ?, 'note', ?, ?, ?)
        """,
        (
            trade_id, event_ts, json.dumps(payload, sort_keys=True),
            rationale, f"state_transition {current_state}→{new_state}",
        ),
    )
```

- [ ] **Step 4: Run tests — should pass.**

```bash
python -m pytest tests/trades/test_state.py -v
```

Expected: 25 (parameterized matrix) + 7 (validation/audit) = 32 PASS.

- [ ] **Step 5: Commit.**

```bash
git add swing/trades/state.py tests/trades/test_state.py
git commit -m "$(cat <<'EOF'
feat(trades): A.5 — state service with 5×5 transition matrix

Single state-transition write path. ALLOWED_TRANSITIONS enumerates the
5 allowed pairs; remaining 20 cells reject. validate_for_operation per
spec §3.5.1 selects exact required-field set per operation; conditional
rules append event_*/gap_*/catalyst_other_description deps when gated.

state_transition emits 'note'-type trade_events row with structured
payload_json (event_type='state_transition' not in CHECK enum;
intentionally not expanded in 0014 to keep migration scope tight).

32 tests covering 25-cell matrix + per-operation required-fields +
audit-row write.
EOF
)"
```

**Acceptance:** 42 new tests pass; matrix complete; per-operation required-field discriminators in place for `transition_reviewed`'s 10 fields; ruff clean.

**Expected new tests:** 42.

---

### Task A.6: Repos `swing/data/repos/trades.py` rewrite — drop status, use state, route writes through state service

**Files:**
- Modify: `swing/data/repos/trades.py`
- Test: existing `tests/data/test_repos_trades.py` (MOD)

**Goal:** rewrite SELECT/INSERT col lists to drop `status` and add `state` + 21 new cols; remove direct `UPDATE trades SET status='closed'`; rewrite all `WHERE status=...` predicates per §2.1; preserve transaction boundaries; preserve `_validate_chart_pattern_invariant`.

After this task, the full fast suite must be GREEN (Sub-A's binding gate).

- [ ] **Step 1: Read the existing `swing/data/repos/trades.py` end-to-end.**

```bash
wc -l swing/data/repos/trades.py
# expected ~390 lines
```

Inspect every `status` reference; classify each per §2.1.

- [ ] **Step 2: Write a discriminating regression test that would have failed pre-rewrite.**

Add to `tests/data/test_repos_trades.py`:

```python
def test_get_trade_returns_state_not_status(tmp_path):
    """Post-Phase-7: get_trade returns Trade with .state attr; .status is gone."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn, state="entered")  # _seed_trade per A.4 helper
    trade = get_trade(conn, trade_id)
    assert trade.state == "entered"
    assert not hasattr(trade, "status")


def test_list_open_trades_filters_by_state_set(tmp_path):
    """list_open_trades returns trades in {entered, managing, partial_exited}."""
    conn = _seed_v14(tmp_path)
    _seed_trade(conn, ticker="AAA", state="entered")
    _seed_trade(conn, ticker="BBB", state="managing")
    _seed_trade(conn, ticker="CCC", state="partial_exited")
    _seed_trade(conn, ticker="DDD", state="closed")
    _seed_trade(conn, ticker="EEE", state="reviewed")
    open_trades = list_open_trades(conn)
    tickers = {t.ticker for t in open_trades}
    assert tickers == {"AAA", "BBB", "CCC"}


def test_insert_trade_no_longer_writes_status_column(tmp_path):
    """The INSERT col list is rewritten; verify by inspecting the schema."""
    conn = _seed_v14(tmp_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
    assert "status" not in cols
    # Confirm a trade row inserts cleanly.
    trade_id = _seed_trade(conn)
    assert trade_id > 0
```

- [ ] **Step 3: Run tests — should fail.**

```bash
python -m pytest tests/data/test_repos_trades.py -v
```

Expected: many FAILs from existing tests + the 3 new tests fail (existing INSERT references `status`; existing list_open_trades uses `WHERE status='open'`).

- [ ] **Step 4: Rewrite `swing/data/repos/trades.py`.**

Apply per-line per §2.1:

```python
# swing/data/repos/trades.py — full rewrite of the INSERT statement and
# all WHERE/SET clauses that reference status.

def insert_trade_with_event(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    _validate_chart_pattern_invariant(trade)
    cur = conn.execute(
        """
        INSERT INTO trades
            (ticker, entry_date, entry_price, initial_shares, initial_stop,
             current_stop, state, watchlist_entry_target,
             watchlist_initial_stop, notes, hypothesis_label,
             chart_pattern_algo, chart_pattern_algo_confidence,
             chart_pattern_operator,
             chart_pattern_classification_pipeline_run_id,
             sector, industry,
             trade_origin, pre_trade_locked_at, current_size,
             current_avg_cost, last_fill_at,
             thesis, why_now, invalidation_condition, expected_scenario,
             premortem_technical, premortem_market_sector,
             premortem_execution, premortem_additional,
             event_risk_present, event_handling, event_type, event_date,
             gap_risk_present, gap_risk_handling,
             emotional_state_pre_trade, market_regime, catalyst,
             catalyst_other_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade.ticker, trade.entry_date, trade.entry_price,
            trade.initial_shares, trade.initial_stop, trade.current_stop,
            trade.state,
            trade.watchlist_entry_target, trade.watchlist_initial_stop,
            trade.notes, trade.hypothesis_label,
            trade.chart_pattern_algo, trade.chart_pattern_algo_confidence,
            trade.chart_pattern_operator,
            trade.chart_pattern_classification_pipeline_run_id,
            trade.sector, trade.industry,
            trade.trade_origin, trade.pre_trade_locked_at,
            trade.current_size, trade.current_avg_cost, trade.last_fill_at,
            trade.thesis, trade.why_now, trade.invalidation_condition,
            trade.expected_scenario,
            trade.premortem_technical, trade.premortem_market_sector,
            trade.premortem_execution, trade.premortem_additional,
            trade.event_risk_present, trade.event_handling,
            trade.event_type, trade.event_date,
            trade.gap_risk_present, trade.gap_risk_handling,
            trade.emotional_state_pre_trade, trade.market_regime,
            trade.catalyst, trade.catalyst_other_description,
        ),
    )
    trade_id = int(cur.lastrowid)
    # ... existing trade_events 'entry' row INSERT (unchanged signature)
    return trade_id


# REMOVED entirely: insert_exit_with_event (data path moves to fills repo).
# The exit service in Sub-B T4 calls insert_fill_with_event with action='exit'
# (or 'trim' / 'stop'), then state_transition.


def update_stop_with_event(
    conn: sqlite3.Connection, *, trade_id: int, new_stop: float,
    event_ts: str, rationale: str | None = None,
    notes: str | None = None,
) -> None:
    """Phase 7 atomic guard: only fires on active trades."""
    # ... (existing get_trade lookup unchanged)
    cur = conn.execute(
        "UPDATE trades SET current_stop = ? "
        "WHERE id = ? AND state IN ('entered','managing','partial_exited')",
        (new_stop, trade_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"trade {trade_id} is not active or does not exist")
    # ... (existing trade_events 'stop_adjust' row INSERT unchanged)


def get_trade(conn: sqlite3.Connection, trade_id: int) -> Trade | None:
    row = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, state, watchlist_entry_target,
               watchlist_initial_stop, notes, hypothesis_label,
               chart_pattern_algo, chart_pattern_algo_confidence,
               chart_pattern_operator,
               chart_pattern_classification_pipeline_run_id,
               sector, industry,
               reviewed_at, mistake_tags, entry_grade, management_grade,
               exit_grade, process_grade, disqualifying_process_violation,
               realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned,
               trade_origin, pre_trade_locked_at, current_size,
               current_avg_cost, last_fill_at,
               thesis, why_now, invalidation_condition, expected_scenario,
               premortem_technical, premortem_market_sector,
               premortem_execution, premortem_additional,
               event_risk_present, event_handling, event_type, event_date,
               gap_risk_present, gap_risk_handling,
               emotional_state_pre_trade, market_regime, catalyst,
               catalyst_other_description
        FROM trades WHERE id = ?
        """,
        (trade_id,),
    ).fetchone()
    if row is None:
        return None
    return Trade(*row)


def list_open_trades(conn: sqlite3.Connection) -> list[Trade]:
    rows = conn.execute(
        """
        SELECT [same column list as get_trade]
        FROM trades
        WHERE state IN ('entered','managing','partial_exited')
        ORDER BY entry_date DESC, id DESC
        """,
    ).fetchall()
    return [Trade(*r) for r in rows]
```

(Repeat the SELECT col list pattern for every read function in this file. The implementer MUST iterate every function and apply the rewrite consistently. Adversarial review on the diff will catch any function that still references `status`.)

- [ ] **Step 5: Run tests — should pass.**

```bash
python -m pytest -m "not slow" -q
```

Expected: full suite back to GREEN. Test count = baseline + (T0 + T1 + T2 + T3 + T4 + T5 contributions: 2 + 4 + 1 + 3 + 6 + 32 = 48). Target: 1635.

- [ ] **Step 6: Commit.**

```bash
git add swing/data/repos/trades.py tests/data/test_repos_trades.py
git commit -m "$(cat <<'EOF'
refactor(repos): A.6 — trades.py drops status, uses state + 21 new cols

INSERT/SELECT col lists rewritten end-to-end. UPDATE-stop guard
predicate state IN (entered,managing,partial_exited) replaces status='open'.
Direct UPDATE-status-closed removed (state-transition service is sole
write path). insert_exit_with_event removed entirely; exit service in
Sub-B T4 routes through fills repo + state service.

Sub-A full-suite-green gate: passes after this commit.
EOF
)"
```

**Acceptance:** full fast suite GREEN; existing tests pass with state semantics; new tests pass; ruff clean. **Sub-A binding gate.**

**Expected new tests:** 3 (regression coverage from §2.1 §rewrite).

---

### Task A.7: Origin service + EntryPath enum

**Files:**
- Create: `swing/trades/origin.py`
- Test: `tests/trades/test_origin.py` (NEW)

**Goal:** `derive_trade_origin(conn, ticker, entry_path) -> str` per spec §10.1; `EntryPath` enum.

- [ ] **Step 1: Write parameterized derivation tests.**

```python
# tests/trades/test_origin.py — NEW
import sqlite3

import pytest

from swing.data.db import run_migrations
from swing.trades.origin import EntryPath, derive_trade_origin


def _seed_v14(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _insert_candidate(conn, ticker, bucket, run_id):
    """Insert a candidate row with the given bucket for the given run."""
    conn.execute(
        "INSERT INTO candidates (pipeline_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, tight_streak, pullback_pct, "
        "prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, "
        "pattern_tag, notes, sector, industry) "
        "VALUES (?, ?, ?, 10.0, NULL, 9.0, 5.0, 3, 5.0, 30.0, 50, 0.1, "
        "'universe', 'vcp', NULL, '', '')",
        (run_id, ticker, bucket),
    )


def _insert_pipeline_run(conn, run_id, finished=True):
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, state) "
        "VALUES (?, '2026-05-04T08:00:00', ?, ?)",
        (run_id, "2026-05-04T08:30:00" if finished else None,
         "completed" if finished else "running"),
    )


@pytest.mark.parametrize("bucket,entry_path,expected", [
    ("aplus",   EntryPath.APLUS_TODAY_DECISION, "pipeline_aplus"),
    ("aplus",   EntryPath.HYP_RECS_BUTTON,      "pipeline_aplus"),
    ("aplus",   EntryPath.MANUAL_WEB_FORM,      "pipeline_aplus"),
    ("aplus",   EntryPath.CLI_MANUAL,           "pipeline_aplus"),
    ("watch",   EntryPath.HYP_RECS_BUTTON,      "pipeline_watch_hyp_recs"),
    ("watch",   EntryPath.MANUAL_WEB_FORM,      "pipeline_watch_manual"),
    ("watch",   EntryPath.CLI_MANUAL,           "pipeline_watch_manual"),
    ("watch",   EntryPath.APLUS_TODAY_DECISION, "pipeline_watch_manual"),
    ("skip",    EntryPath.HYP_RECS_BUTTON,      "manual_off_pipeline"),
    ("error",   EntryPath.MANUAL_WEB_FORM,      "manual_off_pipeline"),
    ("excluded",EntryPath.CLI_MANUAL,           "manual_off_pipeline"),
])
def test_derive_trade_origin_per_cell(tmp_path, bucket, entry_path, expected):
    conn = _seed_v14(tmp_path)
    _insert_pipeline_run(conn, run_id=1)
    _insert_candidate(conn, "TST", bucket, run_id=1)
    assert derive_trade_origin(conn, "TST", entry_path) == expected


def test_derive_trade_origin_ticker_absent_returns_manual_off_pipeline(tmp_path):
    conn = _seed_v14(tmp_path)
    _insert_pipeline_run(conn, run_id=1)
    # No candidate row for TST.
    assert derive_trade_origin(conn, "TST", EntryPath.MANUAL_WEB_FORM) == "manual_off_pipeline"


def test_derive_trade_origin_no_completed_pipeline_returns_manual(tmp_path):
    conn = _seed_v14(tmp_path)
    # Pipeline run exists but not finished.
    _insert_pipeline_run(conn, run_id=1, finished=False)
    _insert_candidate(conn, "TST", "aplus", run_id=1)
    assert derive_trade_origin(conn, "TST", EntryPath.HYP_RECS_BUTTON) == "manual_off_pipeline"


def test_derive_trade_origin_falls_back_to_yesterday_run(tmp_path):
    conn = _seed_v14(tmp_path)
    # Yesterday's run finished; today's hasn't.
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, state) "
        "VALUES (1, '2026-05-03T08:00:00', '2026-05-03T08:30:00', 'completed')"
    )
    _insert_candidate(conn, "TST", "aplus", run_id=1)
    assert derive_trade_origin(conn, "TST", EntryPath.HYP_RECS_BUTTON) == "pipeline_aplus"
```

- [ ] **Step 2: Run tests — should fail.**

```bash
python -m pytest tests/trades/test_origin.py -v
```

Expected: many FAILs (ImportError).

- [ ] **Step 3: Implement `swing/trades/origin.py`.**

```python
"""Trade-origin derivation service (Phase 7 §10).

Maps (candidates.bucket × entry_path) → 4-value trade_origin enum.
Lookup uses the most-recent-completed pipeline_runs row's candidates;
if none completed, falls back to manual_off_pipeline.
"""
from __future__ import annotations

import sqlite3
from enum import Enum


class EntryPath(str, Enum):
    APLUS_TODAY_DECISION = "aplus_today_decision"
    HYP_RECS_BUTTON      = "hyp_recs_button"
    MANUAL_WEB_FORM      = "manual_web_form"
    CLI_MANUAL           = "cli_manual"


def _latest_completed_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM pipeline_runs "
        "WHERE finished_ts IS NOT NULL AND state = 'completed' "
        "ORDER BY started_ts DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else None


def _bucket_for_ticker(
    conn: sqlite3.Connection, ticker: str, run_id: int,
) -> str | None:
    row = conn.execute(
        "SELECT bucket FROM candidates WHERE pipeline_run_id = ? AND ticker = ?",
        (run_id, ticker),
    ).fetchone()
    return row[0] if row else None


def derive_trade_origin(
    conn: sqlite3.Connection, ticker: str, entry_path: EntryPath,
) -> str:
    run_id = _latest_completed_run_id(conn)
    if run_id is None:
        return "manual_off_pipeline"
    bucket = _bucket_for_ticker(conn, ticker, run_id)
    if bucket is None:
        return "manual_off_pipeline"
    if bucket == "aplus":
        return "pipeline_aplus"
    if bucket == "watch":
        if entry_path == EntryPath.HYP_RECS_BUTTON:
            return "pipeline_watch_hyp_recs"
        return "pipeline_watch_manual"
    # skip / error / excluded → off-pipeline.
    return "manual_off_pipeline"
```

- [ ] **Step 4: Run tests — should pass.**

```bash
python -m pytest tests/trades/test_origin.py -v
```

Expected: 14 PASS.

- [ ] **Step 5: Commit.**

```bash
git add swing/trades/origin.py tests/trades/test_origin.py
git commit -m "$(cat <<'EOF'
feat(trades): A.7 — origin service + EntryPath enum

derive_trade_origin maps (bucket × entry_path) → 4-value trade_origin
per spec §10.1. Most-recent-completed pipeline run lookup; ticker-absent
+ pipeline-not-completed → manual_off_pipeline. 14 tests cover all 11
cell combinations + ticker-absent + pipeline-not-run + yesterday-fallback.
EOF
)"
```

**Expected new tests:** 14.

---

### Task A.8: Derived metrics service

**Files:**
- Create: `swing/trades/derived_metrics.py`
- Test: `tests/trades/test_derived_metrics.py` (NEW)

**Goal:** pure formulas for `realized_pnl` and `r_multiple` previously stored on `exits`.

- [ ] **Step 1: Write tests with VIR's actual numbers as discriminating fixture.**

```python
# tests/trades/test_derived_metrics.py
import math

import pytest

from swing.trades.derived_metrics import (
    initial_risk_per_share, r_multiple, realized_pnl,
)


def test_realized_pnl_long_winner():
    assert realized_pnl(entry_price=10.0, exit_price=12.0, quantity=100.0) == 200.0


def test_realized_pnl_long_loser():
    assert realized_pnl(entry_price=10.0, exit_price=9.0, quantity=100.0) == -100.0


def test_initial_risk_per_share():
    assert initial_risk_per_share(entry_price=10.0, initial_stop=9.0) == 1.0


def test_r_multiple_loser():
    """+1R win → r_multiple = 1.0; -0.5R loss → -0.5; etc."""
    pnl = realized_pnl(entry_price=10.0, exit_price=9.0, quantity=100.0)  # -100
    risk = initial_risk_per_share(entry_price=10.0, initial_stop=9.0)     # 1.0
    r = r_multiple(realized_pnl=pnl, initial_risk_per_share=risk, quantity=100.0)
    assert r == -1.0


def test_r_multiple_vir_actual_numbers():
    """VIR's documented numbers: entry $11.34, stop $10.30 (per exits.exit_price),
    2 shares, exit at $10.30 → r_multiple ≈ -0.329 (production DB exact value)."""
    # From production DB: exits row (1, 1, '2026-04-24', 10.3, 2, 'stop-hit', -2.0, -0.32894...).
    # We don't know VIR's entry_price from the empirical audit (need to read trades row).
    # For this test: use the documented values directly as the discriminating
    # fixture — this is the ACTUAL math from the production DB at HEAD pre-migration.
    entry_price = 11.34  # placeholder; implementer verifies against production trades row at task time
    exit_price = 10.30
    quantity = 2.0
    pnl = realized_pnl(entry_price=entry_price, exit_price=exit_price, quantity=quantity)
    assert math.isclose(pnl, -2.08, abs_tol=0.01)  # discriminating; pre-migration stored value -2.0
    risk = initial_risk_per_share(entry_price=entry_price, initial_stop=10.30)
    if risk > 0:
        r = r_multiple(realized_pnl=pnl, initial_risk_per_share=risk, quantity=quantity)
        assert r < 0  # confirmed loss
```

NOTE: The implementer MUST verify VIR's actual `entry_price` and `initial_stop` from the production DB at task time (`SELECT entry_price, initial_stop FROM trades WHERE ticker='VIR'`) and update the fixture before committing. The placeholder values above will not produce exactly `-2.0` PnL; that's intentional — the test gates on "loss is reproduced," not exact equality, until the implementer plugs in real numbers.

- [ ] **Step 2: Run tests — should fail.**

```bash
python -m pytest tests/trades/test_derived_metrics.py -v
```

Expected: 5 FAILs (ImportError).

- [ ] **Step 3: Implement `swing/trades/derived_metrics.py`.**

```python
"""Pure derived-metric formulas for fills-based PnL accounting.

Replaces stored exits.realized_pnl + exits.r_multiple columns with
on-the-fly computation from fill data. Forces formula change to flow
through one place; eliminates drift between stored aggregates and live
math.
"""
from __future__ import annotations


def initial_risk_per_share(*, entry_price: float, initial_stop: float) -> float:
    """Per-share risk in dollars (long-only assumption: entry > stop)."""
    return entry_price - initial_stop


def realized_pnl(*, entry_price: float, exit_price: float, quantity: float) -> float:
    """Long-only realized PnL on a closed quantity."""
    return (exit_price - entry_price) * quantity


def r_multiple(*, realized_pnl: float, initial_risk_per_share: float, quantity: float) -> float:
    """Realized PnL expressed in initial-risk units.

    r_multiple = realized_pnl / (initial_risk_per_share * quantity).
    """
    risk_dollars = initial_risk_per_share * quantity
    if risk_dollars == 0:
        raise ValueError("initial_risk_per_share * quantity is zero; r_multiple undefined")
    return realized_pnl / risk_dollars
```

- [ ] **Step 4: Run tests — should pass.**

```bash
python -m pytest tests/trades/test_derived_metrics.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit.**

```bash
git add swing/trades/derived_metrics.py tests/trades/test_derived_metrics.py
git commit -m "$(cat <<'EOF'
feat(trades): A.8 — pure derived-metrics formulas

realized_pnl + r_multiple + initial_risk_per_share replace stored
exits.realized_pnl + exits.r_multiple columns. Pure functions; no DB
access. Migration 0014 preservation invariant test (T9) gates these
formulas against the legacy stored values within float tolerance.
EOF
)"
```

**Expected new tests:** 5.

---

### Task A.9: Migration safety — 4-fixture preservation invariant

**Files:**
- Modify: `tests/data/test_migration_0014.py` (existing smoke test from T2; add 4 fixture tests).

**Goal:** spec §4.4.1 binding — 4 explicit fixtures (singleton / multi-date / same-date / notes-merged) covering the migration risk surface.

- [ ] **Step 1: Write the 4 fixture tests.**

```python
# tests/data/test_migration_0014.py — additions
import math
import sqlite3

from swing.data.db import run_migrations
from swing.trades.derived_metrics import (
    initial_risk_per_share, r_multiple, realized_pnl,
)


def _seed_v13_with_trades_and_exits(tmp_path, trade_specs, exit_specs):
    """Build a v13 DB seeded with the given trades + exits (legacy schema)."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=13)
    for spec in trade_specs:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            spec,
        )
    for spec in exit_specs:
        conn.execute(
            "INSERT INTO exits (id, trade_id, exit_date, exit_price, shares, "
            "reason, realized_pnl, r_multiple, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            spec,
        )
    conn.commit()
    return conn, db


def test_preservation_invariant_singleton_exit(tmp_path):
    """One trade with one full exit (mirrors VIR shape)."""
    trades = [
        # (id, ticker, entry_date, entry_price, initial_shares, initial_stop, current_stop, status)
        (1, "AAA", "2026-04-20", 11.34, 2, 10.30, 10.30, "closed"),
    ]
    exits_data = [
        # (id, trade_id, exit_date, exit_price, shares, reason, realized_pnl, r_multiple, notes)
        (1, 1, "2026-04-24", 10.30, 2, "stop-hit", -2.08, -1.0, None),
    ]
    conn, db = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    fills = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills ORDER BY fill_datetime ASC, fill_id ASC"
    ).fetchall()
    assert len(fills) == 2  # 1 entry + 1 exit
    assert fills[0] == ("entry", 2.0, 11.34, None, "2026-04-20T16:00:00")
    assert fills[1] == ("exit", 2.0, 10.30, "stop-hit", "2026-04-24T16:00:00")
    # Re-compute realized_pnl + r_multiple via derived_metrics; assert preserved.
    pnl = realized_pnl(entry_price=11.34, exit_price=10.30, quantity=2.0)
    risk = initial_risk_per_share(entry_price=11.34, initial_stop=10.30)
    r = r_multiple(realized_pnl=pnl, initial_risk_per_share=risk, quantity=2.0)
    assert math.isclose(pnl, -2.08, abs_tol=1e-6)
    assert math.isclose(r, -1.0, abs_tol=1e-6)


def test_preservation_invariant_multi_exit_different_dates(tmp_path):
    """Trade with 3 exits across 3 dates totaling initial_shares.

    Asserts full backfilled fills row contents (action, quantity, price, reason,
    fill_datetime) per spec §4.4.1 binding: each row's structured contents are
    proven, not just the action sequence."""
    trades = [
        (1, "BBB", "2026-04-01", 100.0, 30, 95.0, 95.0, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-05", 105.0, 10, "trim-1",     50.0, 1.0, None),
        (2, 1, "2026-04-10", 110.0, 10, "trim-2",    100.0, 2.0, None),
        (3, 1, "2026-04-15", 115.0, 10, "exit-final",150.0, 3.0, None),
    ]
    conn, db = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    fills = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills WHERE trade_id = 1 AND action != 'entry' "
        "ORDER BY fill_datetime ASC, fill_id ASC"
    ).fetchall()
    assert fills == [
        ("trim", 10.0, 105.0, "trim-1",     "2026-04-05T16:00:00"),
        ("trim", 10.0, 110.0, "trim-2",     "2026-04-10T16:00:00"),
        ("exit", 10.0, 115.0, "exit-final", "2026-04-15T16:00:00"),
    ]
    # Per-row realized_pnl preservation invariant (computed via derived_metrics).
    for stored, fill in zip(exits_data, fills):
        stored_pnl = stored[6]
        computed_pnl = realized_pnl(entry_price=100.0, exit_price=fill[2], quantity=fill[1])
        assert math.isclose(stored_pnl, computed_pnl, abs_tol=1e-6)


def test_preservation_invariant_same_date_multi_exit(tmp_path):
    """Trade with 3 exits on same date totaling initial_shares — deterministic
    ordering by (exit_date ASC, id ASC) drives action assignment.

    Asserts full row contents in id-ASC order: backfill SQL's tie-break on
    `id ASC` for same-date rows is the discriminator."""
    trades = [
        (1, "CCC", "2026-04-01", 50.0, 30, 47.0, 47.0, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-05", 52.0, 10, "trim-A", 20.0, 0.67, None),
        (2, 1, "2026-04-05", 53.0, 10, "trim-B", 30.0, 1.0,  None),
        (3, 1, "2026-04-05", 54.0, 10, "exit-C", 40.0, 1.33, None),
    ]
    conn, db = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    fills = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills WHERE trade_id = 1 AND action != 'entry' "
        "ORDER BY fill_id ASC"
    ).fetchall()
    assert fills == [
        ("trim", 10.0, 52.0, "trim-A", "2026-04-05T16:00:00"),
        ("trim", 10.0, 53.0, "trim-B", "2026-04-05T16:00:00"),
        ("exit", 10.0, 54.0, "exit-C", "2026-04-05T16:00:00"),
    ]


def test_preservation_invariant_notes_merged(tmp_path):
    """Exit row with non-empty notes; post-migration, fill.reason = reason + ' | ' + notes.

    Asserts ALL row fields (action, quantity, price, reason, fill_datetime) — not
    just the merged reason — to prove the migration backfill writes a complete row."""
    trades = [
        (1, "DDD", "2026-04-01", 20.0, 100, 19.0, 19.0, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-05", 22.0, 100, "target hit", 200.0, 2.0, "early bias good"),
    ]
    conn, db = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    row = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills WHERE trade_id = 1 AND action = 'exit'"
    ).fetchone()
    assert row == (
        "exit", 100.0, 22.0,
        "target hit | early bias good",
        "2026-04-05T16:00:00",
    )
```

- [ ] **Step 2: Run tests — assert they pass.**

```bash
python -m pytest tests/data/test_migration_0014.py -v
```

Expected: 5 PASS (smoke + 4 fixture tests).

- [ ] **Step 3: Commit.**

```bash
git add tests/data/test_migration_0014.py
git commit -m "$(cat <<'EOF'
test(data): A.9 — migration 0014 preservation invariant (4 fixtures)

Per spec §4.4.1: singleton-exit (mirrors VIR), multi-exit-different-
dates, same-date-multi-exit, notes-merged. Each fixture asserts post-
migration fills row contents + (where applicable) realized_pnl /
r_multiple match pre-migration stored values within float tolerance.

Discriminating-test discipline: each fixture exercises a distinct
risk-surface dimension; surplus over the singleton case is justified
by the same-date-deterministic-ordering and notes-concat semantics.
EOF
)"
```

**Expected new tests:** 4.

---

### Task A.10: In-flight migration backfill — VIR/DHC/CC

**Files:**
- Modify: `tests/data/test_migration_0014.py` (additions)

**Goal:** spec §12.3 binding test — production-shape fixture migrating to expected (state, fills count, aggregate denorms, trade_origin) per the VIR/DHC/CC table.

- [ ] **Step 1: Write the in-flight migration test.**

```python
def test_in_flight_migration_vir_dhc_cc(tmp_path):
    """Spec §12.3: production-shape fixture migrates VIR + DHC + CC correctly.

    NOTE: this fixture mirrors the production DB shape verified at empirical
    audit time (HEAD `db6727d`, 2026-05-04). Implementer re-verifies
    production state at task time before locking the migration UPDATE
    statements; if production state has drifted, fixture + UPDATEs adjust
    in lockstep before commit.
    """
    trades = [
        # VIR: closed + reviewed (Phase 6 review surface populated reviewed_at).
        (1, "VIR", "2026-04-20", 11.34, 2, 10.30, 10.30, "closed"),
        # DHC: open since 2026-04-27, $7.58 × 39.
        (2, "DHC", "2026-04-27", 7.58, 39, 7.20, 7.20, "open"),
        # CC: open since 2026-04-30, $26.97 × 5.
        (3, "CC", "2026-04-30", 26.97, 5, 25.50, 25.50, "open"),
    ]
    exits_data = [
        # VIR's single full exit at -0.33R (per production DB).
        (1, 1, "2026-04-24", 10.30, 2, "stop-hit", -2.08, -1.0, None),
    ]
    conn, db = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    # Phase 6: VIR was reviewed; mark reviewed_at to drive state='reviewed'.
    conn.execute("UPDATE trades SET reviewed_at = '2026-05-04T10:00:00' WHERE id = 1")
    conn.commit()

    run_migrations(conn, target_version=14, backup_dir=tmp_path)

    # Verify per-trade state assignment.
    rows = conn.execute(
        "SELECT ticker, state, current_size, current_avg_cost, last_fill_at, "
        "trade_origin, pre_trade_locked_at FROM trades ORDER BY id"
    ).fetchall()
    vir, dhc, cc = rows
    assert vir == ("VIR", "reviewed", 0.0, 11.34, "2026-04-24T16:00:00",
                   "manual_off_pipeline", "2026-04-20T16:00:00")
    assert dhc == ("DHC", "managing", 39.0, 7.58, "2026-04-27T16:00:00",
                   "pipeline_watch_hyp_recs", "2026-04-27T16:00:00")
    assert cc  == ("CC",  "managing", 5.0,  26.97, "2026-04-30T16:00:00",
                   "pipeline_watch_hyp_recs", "2026-04-30T16:00:00")

    # Verify fills row count = #trades + #exits = 3 + 1 = 4.
    fill_count = conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
    assert fill_count == 4

    # Verify VIR's pre-trade fields persist NULL.
    row = conn.execute(
        "SELECT thesis, premortem_technical, emotional_state_pre_trade FROM trades WHERE ticker='VIR'"
    ).fetchone()
    assert row == (None, None, None)
```

- [ ] **Step 2: Run — assert it passes.**

```bash
python -m pytest tests/data/test_migration_0014.py::test_in_flight_migration_vir_dhc_cc -v
```

Expected: PASS.

- [ ] **Step 3: Commit.**

```bash
git add tests/data/test_migration_0014.py
git commit -m "$(cat <<'EOF'
test(data): A.10 — in-flight migration test for VIR/DHC/CC

Production-shape fixture verifies spec §12.3 backfill: VIR → reviewed,
DHC → managing, CC → managing; current_size/current_avg_cost/last_fill_at
populated from fills aggregates; trade_origin assigned per operator-
confirmed FIRM values.

Implementer re-verifies production state at task time; fixture +
migration UPDATE statements adjust in lockstep if drift detected.
EOF
)"
```

**Expected new tests:** 1.

---

### Sub-A acceptance summary

- **Total Sub-A tasks:** 11 (T0–T10).
- **Total expected new tests:** 2 + 6 + 1 + 3 + 6 + 42 + 3 + 14 + 5 + 4 + 1 = **87 new fast tests** (Sub-A baseline + 87 = 1674 fast tests).
- **Sub-A binding gate:** full fast suite GREEN at end of T6; T7-T10 add coverage on top.
- **Adversarial Codex review** runs after Sub-A merge; expect 2-4 rounds.
- **Operator-witnessed verification gate** for Sub-A: pytest pass + ruff clean; migration backup file present in `~/swing-data/`; production DB at `schema_version=14` after `run_migrations()` invocation; spot-check `SELECT state, current_size, current_avg_cost, last_fill_at, trade_origin FROM trades` returns the values from spec §12.3 for VIR/DHC/CC. **No CLI entry smoke at Sub-A** — `swing trade entry` doesn't gain Phase 7 fields until Sub-B T8; CLI smoke is Sub-B's verification gate.

---

## §5 Sub-B — Services + CLI

**Worktree branch:** `phase7-sub-b-services`
**BASELINE_SHA:** main HEAD after Sub-A merge.
**Total tasks:** 9 (B.1 – B.9).
**Expected duration:** 2-3 days subagent execution + 2-4 Codex rounds on the diff.
**Estimated new tests:** +50-80 (entry-validator surface + exit/stop/review state-transitions + CLI option expansion + journal predicate rewrite coverage).

### Task B.1: Entry service — required-field validation gate

**Files:**
- Modify: `swing/trades/entry.py` — `EntryRequest` gains 18 new pre-trade fields + `entry_path: EntryPath`. `record_entry()` calls `validate_for_operation(req, op="entry_create", current_state=None)` at the top; raises `MissingPreTradeFieldsException` (NOT force-bypassable).
- Modify: `tests/trades/test_entry.py`

**Goal:** non-bypassable pre-trade gate; all 18 fields populated or rejection.

- [ ] **Step 1: Write failing tests covering missing-field rejection per gate component.**

```python
# tests/trades/test_entry.py — additions
import pytest

from swing.trades.entry import (
    EntryRequest, MissingPreTradeFieldsException, record_entry,
)
from swing.trades.origin import EntryPath


def _full_req(**overrides):
    """Build an EntryRequest with all 18 Phase 7 fields populated."""
    base = dict(
        ticker="TST", entry_date="2026-05-04",
        entry_price=10.0, shares=100, initial_stop=9.0,
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, rationale="vcp-breakout",
        event_ts="2026-05-04T16:00:00",
        entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="bullish on the setup",
        why_now="VCP completed today",
        invalidation_condition="break of 9.0 stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="prior pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small to matter",
        event_risk_present=0,
        event_handling="not_applicable",
        event_type=None, event_date=None,
        gap_risk_present=0,
        gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm","confident"]',
        market_regime="Bullish",
        catalyst="technical_only",
        catalyst_other_description=None,
        manual_entry_confidence="normal",
    )
    base.update(overrides)
    return EntryRequest(**base)


@pytest.mark.parametrize("missing_field", [
    "thesis", "why_now", "invalidation_condition", "expected_scenario",
    "premortem_technical", "premortem_market_sector", "premortem_execution",
    "emotional_state_pre_trade", "market_regime", "catalyst",
    "manual_entry_confidence",
])
def test_record_entry_rejects_missing_required_field(tmp_path, missing_field):
    conn = _seed_v14(tmp_path)
    req = _full_req(**{missing_field: None})
    with pytest.raises(MissingPreTradeFieldsException) as excinfo:
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    assert missing_field in excinfo.value.missing_fields


def test_record_entry_event_risk_conditional_required(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req(
        event_risk_present=1, event_handling=None, event_type=None, event_date=None,
    )
    with pytest.raises(MissingPreTradeFieldsException) as excinfo:
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    for required in ("event_handling", "event_type", "event_date"):
        assert required in excinfo.value.missing_fields


def test_record_entry_catalyst_other_requires_description(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req(catalyst="other", catalyst_other_description=None)
    with pytest.raises(MissingPreTradeFieldsException) as excinfo:
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    assert "catalyst_other_description" in excinfo.value.missing_fields


def test_record_entry_force_does_NOT_bypass_missing_fields(tmp_path):
    """MissingPreTradeFieldsException is not force-bypassable per spec §9.3."""
    conn = _seed_v14(tmp_path)
    req = _full_req(thesis=None)
    with pytest.raises(MissingPreTradeFieldsException):
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)


def test_record_entry_complete_succeeds(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req()
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    assert result.trade_id > 0
```

- [ ] **Step 2: Run — should fail.**

Expected: many failures because `EntryRequest` doesn't have the new fields yet, and `record_entry` doesn't call `validate_for_operation`.

- [ ] **Step 3: Update `swing/trades/entry.py`.**

Expand `EntryRequest`:

```python
@dataclass(frozen=True)
class EntryRequest:
    # ... existing fields ...
    entry_path: EntryPath = EntryPath.MANUAL_WEB_FORM
    # Phase 7 pre-trade decision fields:
    thesis: str | None = None
    why_now: str | None = None
    invalidation_condition: str | None = None
    expected_scenario: str | None = None
    premortem_technical: str | None = None
    premortem_market_sector: str | None = None
    premortem_execution: str | None = None
    premortem_additional: str | None = None
    event_risk_present: int | None = None
    event_handling: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    gap_risk_present: int | None = None
    gap_risk_handling: str | None = None
    emotional_state_pre_trade: str | None = None
    market_regime: str | None = None
    catalyst: str | None = None
    catalyst_other_description: str | None = None
    manual_entry_confidence: str | None = None
```

Add Phase 7 import + validator call:

```python
from swing.trades.state import (
    MissingPreTradeFieldsException, validate_for_operation,
)


def record_entry(
    conn, req, *, soft_warn, hard_cap, force,
):
    # Phase 7 — required-field validation FIRST.
    missing = validate_for_operation(req, op="entry_create", current_state=None)
    if missing:
        raise MissingPreTradeFieldsException(missing_fields=missing)

    # ... existing stop<entry / duplicate / hard cap / soft warn checks unchanged ...
```

Re-export `MissingPreTradeFieldsException` from this module for surface consumption.

- [ ] **Step 4: Run — should pass.**

```bash
python -m pytest tests/trades/test_entry.py -v
```

- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(trades): B.1 — entry service required-field gate"
```

**Expected new tests:** ~14 (parameterized missing-field + 4 special cases).

---

### Task B.2: Entry service — `trade_origin` derivation wired into `record_entry`

**Files:** Modify `swing/trades/entry.py` + `tests/trades/test_entry.py`.

**Goal:** entry service replaces `req.trade_origin` with the derived value before INSERT. Tests parameterize over (bucket, entry_path) → expected origin.

- [ ] **Step 1: Failing test.**

```python
def test_record_entry_derives_trade_origin_from_candidate_bucket(tmp_path):
    conn = _seed_v14(tmp_path)
    # Seed pipeline_run + candidate with bucket='watch'.
    _insert_pipeline_run(conn, run_id=1)
    _insert_candidate(conn, "TST", "watch", run_id=1)
    req = _full_req(entry_path=EntryPath.HYP_RECS_BUTTON)
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    trade = get_trade(conn, result.trade_id)
    assert trade.trade_origin == "pipeline_watch_hyp_recs"
```

- [ ] **Step 2-5: Implement, run, commit.**

```python
# swing/trades/entry.py — within record_entry, after validation, before INSERT:
from swing.trades.origin import derive_trade_origin

derived_origin = derive_trade_origin(conn, req.ticker, req.entry_path)
# Build Trade with derived_origin, ignoring any value the caller passed in.
```

Commit: `feat(trades): B.2 — entry service derives trade_origin via origin service`.

**Expected new tests:** ~4.

---

### Task B.3: Entry service — atomic INSERT trade + first entry-fill + `pre_trade_locked_at`

**Files:** Modify `swing/trades/entry.py` + `tests/trades/test_entry.py`.

**Goal:** within the same transaction, `record_entry` inserts the trades row + the first entry-action fill via `insert_fill_with_event`; `pre_trade_locked_at` is set to `req.event_ts`.

- [ ] **Step 1: Failing test.**

```python
def test_record_entry_writes_first_entry_fill_atomically(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req()
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    fills = list_fills_for_trade(conn, result.trade_id)
    assert len(fills) == 1
    assert fills[0].action == "entry"
    assert fills[0].quantity == 100.0
    assert fills[0].price == 10.0
    assert fills[0].fill_datetime == "2026-05-04T16:00:00"
    assert fills[0].manual_entry_confidence == "normal"
    trade = get_trade(conn, result.trade_id)
    assert trade.pre_trade_locked_at == "2026-05-04T16:00:00"
    assert trade.state == "entered"
    assert trade.current_size == 100.0
```

- [ ] **Step 2-5: Implement, run, commit.**

In `record_entry`:

```python
trade = Trade(
    id=None, ticker=req.ticker, entry_date=req.entry_date,
    entry_price=req.entry_price, initial_shares=req.shares,
    initial_stop=req.initial_stop, current_stop=req.initial_stop,
    state="entered",
    # ... 18 Phase 7 fields propagated from req
    trade_origin=derived_origin,
    pre_trade_locked_at=req.event_ts,
    current_size=0,  # _recompute_aggregates after fill insert sets the real value
    current_avg_cost=None, last_fill_at=None,
    # ... existing fields
)
with conn:
    trade_id = insert_trade_with_event(conn, trade, event_ts=req.event_ts, rationale=req.rationale)
    insert_fill_with_event(conn, Fill(
        fill_id=None, trade_id=trade_id,
        fill_datetime=req.event_ts, action="entry",
        quantity=float(req.shares), price=req.entry_price,
        manual_entry_confidence=req.manual_entry_confidence,
    ), event_ts=req.event_ts)
```

Commit: `feat(trades): B.3 — entry writes first entry-fill atomically + sets pre_trade_locked_at`.

**Expected new tests:** ~3.

---

### Task B.4: Exit service — fill emission + state transition

**Files:** Modify `swing/trades/exit.py` + `tests/trades/test_exit.py`.

**Goal:** `record_exit()` writes a fills row (action `'trim'` if `current_size > 0` after fill, else `'exit'`; `'stop'` if reason matches stop classification); calls `state_transition` for the appropriate state movement; recomputes aggregates via fills repo.

- [ ] **Step 1: Failing tests.**

```python
def test_record_exit_partial_writes_trim_fill_and_transitions_to_partial_exited(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, ticker="TST", state="managing", current_size=100.0)
    record_exit(conn, trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
                shares=40, reason=ExitReason.RESISTANCE, event_ts="2026-05-05T16:00:00")
    fills = list_fills_for_trade(conn, trade_id)
    actions = [f.action for f in fills]
    assert "trim" in actions
    trade = get_trade(conn, trade_id)
    assert trade.state == "partial_exited"
    assert trade.current_size == 60.0


def test_record_exit_full_writes_exit_fill_and_transitions_to_closed(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, ticker="TST", state="managing", current_size=100.0)
    record_exit(conn, trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
                shares=100, reason=ExitReason.TARGET, event_ts="2026-05-05T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.state == "closed"
    assert trade.current_size == 0.0


def test_record_exit_stop_hit_uses_stop_action(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, ticker="TST", state="managing", current_size=100.0)
    record_exit(conn, trade_id=trade_id, exit_date="2026-05-05", exit_price=8.5,
                shares=100, reason=ExitReason.STOP_HIT, event_ts="2026-05-05T16:00:00")
    fills = list_fills_for_trade(conn, trade_id)
    stop_fill = next(f for f in fills if f.action == "stop")
    assert stop_fill.quantity == 100.0


def test_record_exit_same_day_stop_out_double_transitions(tmp_path):
    """entered → managing → closed atomic per spec §3.3."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, ticker="TST", state="entered", current_size=100.0)
    record_exit(conn, trade_id=trade_id, exit_date="2026-05-05", exit_price=8.5,
                shares=100, reason=ExitReason.STOP_HIT, event_ts="2026-05-05T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.state == "closed"  # double-transitioned through 'managing'
```

- [ ] **Step 2-5: Implement, run, commit.**

```python
# swing/trades/exit.py — sketch
from swing.data.repos.fills import insert_fill_with_event, list_fills_for_trade
from swing.trades.state import state_transition

def record_exit(conn, *, trade_id, exit_date, exit_price, shares, reason, event_ts, rationale=None):
    trade = get_trade(conn, trade_id)
    if trade.state not in ("entered", "managing", "partial_exited"):
        raise ValueError(f"trade {trade_id} not active (state={trade.state!r})")
    # Compute action.
    new_size = trade.current_size - shares
    if new_size < 0:
        raise ValueError(f"exit shares {shares} exceeds current size {trade.current_size}")
    if reason == ExitReason.STOP_HIT:
        action = "stop"
    elif new_size > 0:
        action = "trim"
    else:
        action = "exit"
    fill = Fill(
        fill_id=None, trade_id=trade_id,
        fill_datetime=event_ts, action=action,
        quantity=float(shares), price=exit_price, reason=reason.value,
    )
    with conn:
        insert_fill_with_event(conn, fill, event_ts=event_ts, rationale=rationale)
        # Drive state transition.
        if trade.state == "entered" and new_size == 0:
            # Same-day stop-out: entered → managing → closed atomic.
            state_transition(conn, trade_id=trade_id, new_state="managing", event_ts=event_ts)
            state_transition(conn, trade_id=trade_id, new_state="closed", event_ts=event_ts)
        elif trade.state == "entered" and new_size > 0:
            state_transition(conn, trade_id=trade_id, new_state="managing", event_ts=event_ts)
            state_transition(conn, trade_id=trade_id, new_state="partial_exited", event_ts=event_ts)
        elif trade.state == "managing" and new_size == 0:
            state_transition(conn, trade_id=trade_id, new_state="closed", event_ts=event_ts)
        elif trade.state == "managing" and new_size > 0:
            state_transition(conn, trade_id=trade_id, new_state="partial_exited", event_ts=event_ts)
        elif trade.state == "partial_exited" and new_size == 0:
            state_transition(conn, trade_id=trade_id, new_state="closed", event_ts=event_ts)
        # partial_exited + new_size > 0: stays partial_exited (no transition).
```

Commit: `feat(trades): B.4 — exit service writes fill + transitions state`.

**Expected new tests:** ~6.

---

### Task B.5: Stop-adjust — state predicate + first-stop `entered → managing` trigger

**Files:** Modify `swing/trades/stop_adjust.py` + `tests/trades/test_stop_adjust.py`.

**Goal:** stop-adjust only fires on active states; first stop-adjust on `state='entered'` atomically transitions to `managing` per spec §3.3.

- [ ] **Step 1: Failing tests.**

```python
def test_stop_adjust_rejected_on_closed_state(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, state="closed")
    with pytest.raises(ValueError, match="not active"):
        update_stop_with_event(
            conn, trade_id=trade_id, new_stop=9.5,
            event_ts="2026-05-05T16:00:00",
        )


def test_first_stop_adjust_on_entered_transitions_to_managing(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, state="entered")
    update_stop_with_event(
        conn, trade_id=trade_id, new_stop=9.5,
        event_ts="2026-05-05T16:00:00",
    )
    trade = get_trade(conn, trade_id)
    assert trade.state == "managing"
    assert trade.current_stop == 9.5


def test_subsequent_stop_adjust_on_managing_no_state_change(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, state="managing")
    update_stop_with_event(
        conn, trade_id=trade_id, new_stop=9.5,
        event_ts="2026-05-05T16:00:00",
    )
    trade = get_trade(conn, trade_id)
    assert trade.state == "managing"
```

- [ ] **Step 2-5: Implement, run, commit.**

```python
# swing/trades/stop_adjust.py — sketch
from swing.trades.state import state_transition

def update_stop_with_event(conn, *, trade_id, new_stop, event_ts, rationale=None, notes=None):
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.state not in ("entered", "managing", "partial_exited"):
        raise ValueError(f"trade {trade_id} is not active (state={trade.state!r})")
    with conn:
        # Repo-level update (predicate now state-based).
        repo_update_stop_with_event(
            conn, trade_id=trade_id, new_stop=new_stop,
            event_ts=event_ts, rationale=rationale, notes=notes,
        )
        if trade.state == "entered":
            state_transition(conn, trade_id=trade_id, new_state="managing", event_ts=event_ts)
```

Commit: `feat(trades): B.5 — stop-adjust state-aware + entered→managing trigger`.

**Expected new tests:** ~5.

---

### Task B.6: Review service — `state == 'closed'` precondition + state transition on completion

**Files:** Modify `swing/trades/review.py` + relevant tests.

**Goal:** Phase 6 review precondition rewrites `trade.status != "closed"` → `trade.state != "closed"` (NOT `state not in ('closed','reviewed')` per §2.1 — naïve form would let already-reviewed trades through). Review-completion atomically transitions `closed → reviewed` via `state_transition`.

- [ ] **Step 1: Failing tests.**

```python
def test_review_rejects_already_reviewed_trade(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, state="reviewed")
    with pytest.raises(ValueError, match="not in closed state"):
        record_review(conn, trade_id=trade_id, ...)


def test_review_completion_transitions_closed_to_reviewed(tmp_path):
    conn = _seed_v14(tmp_path)
    trade_id = _seed_active_trade(conn, state="closed")
    record_review(conn, trade_id=trade_id, ...complete review fields...)
    trade = get_trade(conn, trade_id)
    assert trade.state == "reviewed"
    assert trade.reviewed_at is not None
```

- [ ] **Step 2-5: Implement, run, commit.**

In `swing/trades/review.py`:

```python
# Line 214 rewrite:
if trade.state != "closed":
    raise ValueError(f"trade {trade_id} is not in closed state (state={trade.state!r})")

# Review completion (in mark_reviewed or equivalent):
with conn:
    # ... write review_log row + update trade review fields (existing Phase 6 code)
    state_transition(conn, trade_id=trade_id, new_state="reviewed", event_ts=event_ts)
```

Update tests: `tests/cli/test_review_complete_cli.py`, `tests/cli/test_trade_review_cli.py`, `tests/web/test_review_route.py`, `tests/web/test_review_template.py`, `tests/web/test_dashboard_needs_review_badge.py` — replace any `status="closed"` fixture with `state="closed"`; verify `state == "reviewed"` post-review.

Commit: `feat(trades): B.6 — review state-aware precondition + transitions to reviewed`.

**Expected new tests:** ~4 + ~10 mod-test fixture rewrites (no new tests; existing tests retain their assertions).

---

### Task B.7: CLI status→state predicate rewrites + display

**Files:** Modify `swing/cli.py` (lines 588, 1008) + `tests/cli/test_cli_advisory.py`, `tests/cli/test_cli_trade_analyze.py`, `tests/cli/test_cli_trade.py`.

**Goal:** display column widens to accommodate `partial_exited`; review-CLI predicate uses `state == 'closed'`.

- [ ] **Step 1: Failing test.**

```python
def test_cli_trade_list_shows_state_column(tmp_path, runner):
    conn = _seed_v14(tmp_path)
    _seed_active_trade(conn, ticker="AAA", state="managing")
    result = runner.invoke(cli, ["trade", "list"])
    assert "managing" in result.output
    assert "open" not in result.output  # status column gone
```

- [ ] **Step 2-5: Implement, run, commit.**

```python
# swing/cli.py:588
click.echo(
    f"${t.entry_price:>6.2f} ${t.current_stop:>6.2f} {remaining:>4} {t.state:<14}"
)
```

For line 1008: read context at task time, classify per §2.1, rewrite.

Commit: `refactor(cli): B.7 — status→state predicate + display rewrites`.

**Expected new tests:** ~2.

---

### Task B.8: CLI new entry options

**Files:** Modify `swing/cli.py` + `tests/cli/test_cli_trade.py`.

**Goal:** `swing trade entry` accepts the 18 new pre-trade fields as click options OR interactive prompts (operator preference: prompts for free-text fields, options for enums; choose at task time).

- [ ] **Step 1: Failing test.**

```python
def test_cli_trade_entry_rejects_missing_thesis(tmp_path, runner):
    """CLI entry without --thesis raises SystemExit with non-zero code."""
    runner.invoke(cli, ["trade", "entry", "--ticker", "TST", "--entry-price", "10.0",
                        "--shares", "100", "--initial-stop", "9.0",
                        # no --thesis flag
                        ])
    # Assert non-zero exit + stderr message references missing thesis.
```

- [ ] **Step 2-5: Implement, run, commit.**

Add click options for each Phase 7 field:

```python
@trade_group.command("entry")
@click.option("--ticker", required=True)
# ... existing options ...
@click.option("--entry-path", type=click.Choice(["aplus_today_decision","hyp_recs_button","manual_web_form","cli_manual"]),
              default="cli_manual")
@click.option("--thesis", required=False)
@click.option("--why-now", required=False)
@click.option("--invalidation", required=False)
@click.option("--expected-scenario", required=False)
@click.option("--premortem-technical", required=False)
@click.option("--premortem-market-sector", required=False)
@click.option("--premortem-execution", required=False)
@click.option("--premortem-additional", required=False)
@click.option("--event-risk", type=click.Choice(["yes","no"]), default="no")
@click.option("--event-handling",
              type=click.Choice(["avoid_event","hold_through","reduce_before","exit_before","not_applicable"]),
              required=False)
@click.option("--event-type",
              type=click.Choice(["earnings","fed_meeting","cpi_release","economic_data",
                                 "product_announcement","legal_ruling","other"]),
              required=False)
@click.option("--event-date", required=False)
@click.option("--gap-risk", type=click.Choice(["yes","no"]), default="no")
@click.option("--gap-risk-handling",
              type=click.Choice(["accept","reduce_size","tight_stop","exit_before_close","not_applicable"]),
              required=False)
@click.option("--emotional-state", multiple=True,
              type=click.Choice(["calm","confident","anxious","fomo","revenge","hopeful","doubtful","distracted"]))
@click.option("--manual-entry-confidence", type=click.Choice(["high","normal","low"]))
@click.option("--market-regime", type=click.Choice(["Bullish","Caution","Bearish"]))
@click.option("--catalyst", type=click.Choice([
    "earnings_driven","guidance_change","corporate_action","sector_rotation",
    "macro_event","sympathy_move","product_news","technical_only","other",
]))
@click.option("--catalyst-other-description", required=False)
def cmd_trade_entry(...):
    # Build EntryRequest; on MissingPreTradeFieldsException, click.echo(stderr) the
    # missing list and exit code 1.
```

Commit: `feat(cli): B.8 — trade entry adds 18 Phase 7 option flags`.

**Expected new tests:** ~6.

---

### Task B.9: Journal status→state predicate rewrites (read-side)

**Files:** Modify `swing/journal/{stats,flags,analyze,tos_import}.py` + 5 test files per §2.2.

**Goal:** all closed-or-reviewed predicates rewrite to `state IN ('closed','reviewed')`. `tos_import.py` exits-table reads migrate to fills repo helpers.

- [ ] **Step 1: Failing tests on the journal modules.**

```python
# tests/journal/test_stats.py — example regression
def test_stats_includes_reviewed_trades(tmp_path):
    conn = _seed_v14(tmp_path)
    _seed_active_trade(conn, ticker="AAA", state="closed")
    _seed_active_trade(conn, ticker="BBB", state="reviewed")
    stats = compute_stats(conn)
    assert stats.total_closed_trades == 2  # both 'closed' and 'reviewed' count
```

- [ ] **Step 2-5: Implement, run, commit.**

Per §2.1 mapping, rewrite each line. For `tos_import.py:257,316` (exits-table SELECT), use `list_fills_for_trade(conn, trade_id)` filtering `f.action != 'entry'` to enumerate closing fills.

Commit: `refactor(journal): B.9 — status→state + exits→fills reads`.

**Expected new tests:** ~6 (mostly mod-existing).

---

### Sub-B acceptance summary

- **Total Sub-B tasks:** 9.
- **Total expected new tests:** ~50 (heavy on parameterization in B.1).
- **Sub-B binding gate:** full fast suite GREEN; 4 entry surfaces (CLI + 3 web) all pass complete-fields test; all journal predicates rewritten.
- **Adversarial Codex review:** 2-4 rounds expected.
- **Operator-witnessed verification:** manual `swing trade entry` with all 18 fields → trade record reflects all 18 + state='entered' + first entry-fill present + pre_trade_locked_at set.

---

## §6 Sub-C — Web + UX

**Worktree branch:** `phase7-sub-c-web`
**BASELINE_SHA:** main HEAD after Sub-A merge (parallel with Sub-B permitted) OR after Sub-B merge (default serial).
**Total tasks:** 8 (C.1 – C.8).
**Estimated new tests:** +50-90 (template render + VM coverage + form validation + state badge + audit-log render).

### Task C.1: TradeVM — state field + 18 pre-trade fields + state_badge_label + has_pre_trade_data

**Files:** Modify `swing/web/view_models/trades.py` + `tests/web/test_view_models/test_trades.py`.

**Goal:** TradeVM gains `state`, all 18 new pre-trade fields, computed `state_badge_label`, computed `has_pre_trade_data` (per spec §11.4 — true iff `premortem_technical IS NOT NULL`). All status predicates (lines 331, 385, 432) rewrite per §2.1.

- [ ] **Step 1: Failing tests.**

```python
def test_trade_vm_state_field_and_badge_label():
    trade = make_trade(state="partial_exited")
    vm = build_trade_vm(trade)
    assert vm.state == "partial_exited"
    assert vm.state_badge_label == "Partial"


def test_trade_vm_has_pre_trade_data_legacy_null():
    trade = make_trade(state="reviewed", premortem_technical=None)
    vm = build_trade_vm(trade)
    assert vm.has_pre_trade_data is False


def test_trade_vm_has_pre_trade_data_phase7_populated():
    trade = make_trade(state="entered", premortem_technical="risk-A")
    vm = build_trade_vm(trade)
    assert vm.has_pre_trade_data is True
```

- [ ] **Step 2-5: Implement, run, commit.**

Add fields to TradeVM dataclass; expose `STATE_BADGE_LABELS = {"entered": "Entered", "managing": "Managing", "partial_exited": "Partial", "closed": "Closed", "reviewed": "Reviewed"}`.

```python
@property
def has_pre_trade_data(self) -> bool:
    return self.premortem_technical is not None
```

Predicate rewrites at lines 331/385/432: classify each per §2.1 and replace.

Commit: `feat(web): C.1 — TradeVM state + 18 pre-trade fields + badge`.

**Expected new tests:** ~6.

---

### Task C.2: Open positions row VM — state predicate + state_badge_label

**Files:** Modify `swing/web/view_models/open_positions_row.py` + `tests/web/test_view_models/test_open_positions_row.py`.

**Goal:** Row VM filter (line 181) status='open' → `state IN ('entered','managing','partial_exited')`; row VM gains `state_badge_label`.

- [ ] **Step 1: Failing test.**

```python
def test_open_positions_row_includes_partial_exited():
    trades = [
        make_trade(ticker="A", state="entered"),
        make_trade(ticker="B", state="partial_exited"),
        make_trade(ticker="C", state="closed"),
    ]
    rows = build_open_positions_rows(trades)
    tickers = {r.ticker for r in rows}
    assert tickers == {"A", "B"}
```

- [ ] **Step 2-5: Implement, run, commit.**

Commit: `refactor(web): C.2 — open positions row VM uses state predicate`.

**Expected new tests:** ~3.

---

### Task C.3: Routes — entry form GET/POST + new fields + gate failure rendering

**Files:** Modify `swing/web/routes/trades.py` + `tests/web/test_routes/test_trades_route.py`.

**Goal:** entry form GET renders the 7 sectioned fieldset blocks; entry POST builds an `EntryRequest` with all 18 fields; on `MissingPreTradeFieldsException`, re-render form with field-level error highlights + draft preservation.

CLAUDE.md gotcha: `value = form.get('catalyst') or None` (NOT `or ""`) for nullable+CHECK columns. Verify per-column.

- [ ] **Step 1: Failing tests.**

```python
def test_entry_form_post_missing_thesis_rerenders_with_error(client):
    """POST with missing thesis → 200 with re-rendered form + error class on thesis input."""
    response = client.post("/trades/entry/form", data={
        "ticker": "TST", "entry_price": 10.0, "shares": 100, "initial_stop": 9.0,
        # ... all other fields populated ...
        # 'thesis' missing
    })
    assert response.status_code == 200  # re-render, not 4xx
    assert "missing-thesis" in response.text  # field-level error class
    assert "TST" in response.text  # draft preserved


def test_entry_form_post_complete_creates_trade_with_state_entered(client):
    response = client.post("/trades/entry/form", data={
        # all 18 fields populated
    })
    assert response.status_code == 303 or response.headers.get("HX-Redirect")
    # Verify trade row exists with state='entered' + first entry-fill.


def test_entry_form_catalyst_empty_persists_null_not_empty_string(client):
    """CLAUDE.md gotcha: nullable CHECK enum with form fallback uses or None."""
    # POST with catalyst='' (not selected)
    response = client.post("/trades/entry/form", data={
        # ... all required fields except catalyst ='' ...
    })
    # If catalyst was required → expect rejection.
    # The discriminating test: a NULLABLE column would persist NULL (CHECK passes);
    # the wrong code path with `or ""` would fail CHECK and 500.
    # In Phase 7, catalyst IS required for entry-create; this test is illustrative
    # for any other nullable+CHECK column (e.g., catalyst_other_description when
    # catalyst != 'other' — should persist NULL, not empty string).
```

- [ ] **Step 2-5: Implement, run, commit.**

```python
# swing/web/routes/trades.py — entry POST handler sketch
@router.post("/trades/entry/form")
async def post_entry_form(request, ...):
    form = await request.form()
    try:
        req = EntryRequest(
            ticker=form["ticker"],
            # ... existing fields ...
            entry_path=EntryPath.MANUAL_WEB_FORM,
            thesis=form.get("thesis") or None,
            why_now=form.get("why_now") or None,
            # ... etc — every field uses `or None` per CLAUDE.md gotcha ...
            event_risk_present=int(form.get("event_risk_present", "0")),
            emotional_state_pre_trade=_canonicalize_emotional_states(form.getlist("emotional_state_pre_trade")),
        )
        result = record_entry(conn, req, soft_warn=..., hard_cap=..., force=False)
        # Success: HX-Redirect to /trades/{id} (canonical trade-detail GET).
        # If the route doesn't exist on entry to this task, T3 ALSO registers
        # `GET /trades/{trade_id}` rendering trades/detail.html.j2 (covered in
        # the Sub-C T5 detail-template task — wire the route in T3, populate
        # the template body in T5).
        target_url = f"/trades/{result.trade_id}"
        return Response(status_code=204, headers={"HX-Redirect": target_url})
    except MissingPreTradeFieldsException as exc:
        # Re-render form with draft + field-level error markers.
        return TemplateResponse(request, "trades/entry_form.html.j2", {
            "vm": EntryFormVM.from_form_with_errors(form, missing_fields=exc.missing_fields),
        })
```

**Canonical HX-Redirect target: `GET /trades/{trade_id}`** (renders trade detail page). MUST be registered in `swing/web/routes/trades.py` AS PART OF THIS TASK if not already present. Per CLAUDE.md gotcha 2026-05-04 (Phase 6 I3 HX-Redirect-target-unrouted): do NOT emit a redirect to a path that doesn't resolve.

Tests gate this with TWO discriminating assertions:

```python
def test_hx_redirect_target_route_registered(client):
    """Phase 6 gotcha: HX-Redirect target must be in app.routes.
    Discriminating: a regression that emits /trades/{id}/detail (or any other
    path) without registering it would silently 404 the operator's browser
    while TestClient assertions on the entry-POST status pass.
    """
    target_paths = {getattr(r, "path", None) for r in client.app.routes}
    # Starlette path templates use `{trade_id}`; assert the templated form
    # is registered, not an arbitrary substring match.
    assert "/trades/{trade_id}" in target_paths


def test_entry_post_hx_redirect_target_resolves(client):
    """Follow the HX-Redirect target with a second TestClient call and
    assert the GET returns 200 — proves the entire round-trip resolves,
    not just header format. Per CLAUDE.md gotcha (Phase 6 I3): TestClient
    does not auto-follow HX-Redirect; explicit follow needed."""
    response = client.post("/trades/entry/form", data={...all 18 fields...})
    assert response.status_code == 204
    target = response.headers["HX-Redirect"]
    # Exact format check: `/trades/<integer>` (no `/detail` suffix; canonical).
    import re
    assert re.fullmatch(r"^/trades/\d+$", target)
    # Follow and verify resolution.
    follow = client.get(target)
    assert follow.status_code == 200
```

Commit: `feat(web): C.3 — entry form route handles 18 Phase 7 fields + gate rejection`.

**Expected new tests:** ~10.

---

### Task C.4: Templates — entry form 7 sectioned fieldset blocks

**Files:** Modify `swing/web/templates/trades/entry_form.html.j2` + `tests/web/test_routes/test_trades_route.py` (template-render tests).

**Goal:** form gains 7 sectioned `<fieldset>` blocks per spec §11.1; field-level error markers honor `vm.missing_fields` set; preserved draft values prefill inputs.

CLAUDE.md gotchas to pre-empt:
- HX-Request header propagation on embedded forms.
- HX-Redirect target route registration (verified C.3).
- OOB-swap drift — no hand-duplicated markup.

- [ ] **Step 1: Failing test.**

```python
def test_entry_form_renders_7_fieldset_sections(client):
    response = client.get("/trades/entry/form?ticker=TST")
    text = response.text
    for legend in (
        "Position basics", "Setup attribution", "Pre-trade thesis",
        "Premortem", "Risk acknowledgments", "Operator state", "Notes",
    ):
        assert legend in text
```

- [ ] **Step 2-5: Implement, run, commit.**

Template sketch:

```jinja
<form method="post" action="/trades/entry/form" hx-post="/trades/entry/form" hx-target="this" hx-headers='{"HX-Request": "true"}'>
  <fieldset>
    <legend>1. Position basics</legend>
    <!-- ticker, entry_price, shares, initial_stop -->
  </fieldset>
  <fieldset>
    <legend>2. Setup attribution</legend>
    <!-- rationale, hypothesis_label, chart_pattern_*, sector/industry, trade_origin display-only -->
  </fieldset>
  <fieldset>
    <legend>3. Pre-trade thesis</legend>
    <textarea name="thesis" {% if 'thesis' in vm.missing_fields %}class="error"{% endif %}>{{ vm.draft_thesis or '' }}</textarea>
    <!-- why_now, invalidation_condition, expected_scenario -->
  </fieldset>
  <fieldset>
    <legend>4. Premortem</legend>
    <!-- premortem_technical, premortem_market_sector, premortem_execution, premortem_additional -->
  </fieldset>
  <fieldset>
    <legend>5. Risk acknowledgments</legend>
    <!-- event_risk_present + event_handling/event_type/event_date; gap_risk_present + gap_risk_handling -->
  </fieldset>
  <fieldset>
    <legend>6. Operator state</legend>
    <!-- emotional_state_pre_trade multi-select checkboxes; manual_entry_confidence radio;
         market_regime radio; catalyst select; catalyst_other_description -->
  </fieldset>
  <fieldset>
    <legend>7. Notes</legend>
    <textarea name="notes">{{ vm.draft_notes or '' }}</textarea>
  </fieldset>
  <button type="submit">Submit</button>
</form>
```

The form root MUST include `hx-headers='{"HX-Request": "true"}'` per CLAUDE.md gotcha (2026-05-02 Phase 5 lesson).

Commit: `feat(web): C.4 — entry form 7 sectioned fieldset blocks`.

**Expected new tests:** ~12 (per-section render + per-field error marker + draft preservation).

---

### Task C.5: Templates — trade detail Pre-Trade Decision section + audit log

**Files:** Modify `swing/web/templates/trades/detail.html.j2` + `tests/web/test_routes/test_trades_route.py`.

**Goal:** "Pre-Trade Decision" section rendered above position-management when `vm.has_pre_trade_data`; lock indicator + `pre_trade_locked_at` timestamp; audit-log read-display from `trade_events` rows where `event_type='pre_trade_edit'`.

- [ ] **Step 1: Failing tests.**

```python
def test_trade_detail_shows_pre_trade_section_for_phase7_trade(client):
    # Seed a trade with phase 7 fields populated.
    response = client.get(f"/trades/{trade_id}/detail")
    text = response.text
    assert "Pre-Trade Decision" in text
    assert "🔒" in text or "locked-at" in text
    assert "thesis" in text.lower()


def test_trade_detail_hides_pre_trade_section_for_legacy_null(client):
    """Legacy trades (premortem_technical IS NULL) hide the section per spec §11.4."""
    legacy_trade_id = _seed_legacy_trade(state="reviewed", premortem_technical=None)
    response = client.get(f"/trades/{legacy_trade_id}/detail")
    text = response.text
    assert "Pre-Trade Decision" not in text


def test_trade_detail_renders_audit_log(client):
    # Seed a trade with a pre_trade_edit trade_events row.
    response = client.get(f"/trades/{trade_id}/detail")
    text = response.text
    assert "Audit Log" in text or "edit history" in text.lower()
```

- [ ] **Step 2-5: Implement, run, commit.**

```jinja
{% if vm.has_pre_trade_data %}
  <section class="pre-trade-decision">
    <h2>Pre-Trade Decision <span class="lock-icon" title="Locked at {{ vm.pre_trade_locked_at }}">🔒</span></h2>
    <dl>
      <dt>Thesis</dt><dd>{{ vm.thesis }}</dd>
      <dt>Why now</dt><dd>{{ vm.why_now }}</dd>
      <dt>Invalidation</dt><dd>{{ vm.invalidation_condition }}</dd>
      <!-- ... all 18 fields in dt/dd pairs -->
    </dl>
    <h3>Audit log (pre-trade edits)</h3>
    {% if vm.audit_entries %}
      <ul>
        {% for entry in vm.audit_entries %}
          <li>{{ entry.ts }}: <strong>{{ entry.field }}</strong> changed from "{{ entry.old_value }}" to "{{ entry.new_value }}" — reason: {{ entry.reason }}</li>
        {% endfor %}
      </ul>
    {% else %}
      <p><em>No edits since lock.</em></p>
    {% endif %}
  </section>
{% endif %}
```

Commit: `feat(web): C.5 — trade detail Pre-Trade Decision section + audit log`.

**Expected new tests:** ~8.

---

### Task C.6: state_badge.html.j2 partial + journal.html.j2 + open positions partial state badge

**Files:**
- Create: `swing/web/templates/partials/state_badge.html.j2`
- Modify: `swing/web/templates/journal.html.j2` (line 34)
- Modify: `swing/web/templates/partials/open_positions_table.html.j2`
- Modify: `swing/web/static/css/style.css` (state-badge CSS rules)
- Test: `tests/web/test_view_models/test_*.py` and `tests/web/test_dashboard_integration.py`

**Goal:** shared state-badge partial used everywhere a state is rendered; CSS rules for the 5 state colors. Pre-empts OOB-swap drift gotcha (CLAUDE.md).

- [ ] **Step 1: Failing test.**

```python
def test_journal_template_renders_state_badge(client):
    response = client.get("/journal")
    assert 'class="state-badge state-closed"' in response.text


def test_open_positions_partial_renders_state_badge(client):
    response = client.get("/")
    assert 'class="state-badge state-managing"' in response.text or \
           'class="state-badge state-entered"' in response.text


def test_state_badge_partial_used_via_shared_include():
    """OOB-swap drift gotcha: verify the partial is included, not duplicated."""
    journal = Path("swing/web/templates/journal.html.j2").read_text()
    open_pos = Path("swing/web/templates/partials/open_positions_table.html.j2").read_text()
    for tmpl in (journal, open_pos):
        assert "state_badge.html.j2" in tmpl  # via {% include %}
```

- [ ] **Step 2-5: Implement, run, commit.**

```jinja
{# swing/web/templates/partials/state_badge.html.j2 #}
<span class="state-badge state-{{ state }}">{{ STATE_LABELS[state] }}</span>
```

```jinja
{# swing/web/templates/journal.html.j2 line 34 (was {{ t.status }}) #}
{% include "partials/state_badge.html.j2" with context %}
```

CSS:

```css
.state-badge { padding: 2px 6px; border-radius: 3px; font-size: 0.85em; font-weight: 500; }
.state-entered { background: #cfe2ff; color: #0a3469; }
.state-managing { background: #d1e7dd; color: #0f5132; }
.state-partial_exited { background: #fff3cd; color: #664d03; }
.state-closed { background: #e2e3e5; color: #41464b; }
.state-reviewed { background: #cff4fc; color: #055160; }
```

Commit: `feat(web): C.6 — state_badge partial + journal + open positions wiring`.

**Expected new tests:** ~5.

---

### Task C.7: Routes — state-aware filtering predicates + base-layout VM check

**Files:** Modify `swing/web/routes/trades.py` (lines 844, 1082, 1198) + relevant tests.

**Goal:** all status predicates rewritten per §2.1; verify NO new field is dereferenced by base layout (per CLAUDE.md gotcha — Phase 7 spec §11.5 confirms no new base-layout field, but plan re-verifies at task time).

- [ ] **Step 1: Failing tests** — covered by existing tests with state fixtures.

- [ ] **Step 2: Read each line + classify per §2.1.**

```bash
sed -n '844p;1082p;1198p' swing/web/routes/trades.py
```

For each line: classify (active-trade / closed-but-not-reviewed / closed-or-reviewed) and rewrite.

- [ ] **Step 3: Verify no new base-layout VM field.**

```bash
grep -n "vm\\.\\(state\\|has_pre_trade_data\\|trade_origin\\|thesis\\)" swing/web/templates/base.html.j2
```

Expected: zero matches. Phase 7 does NOT add base-layout-dereferenced fields (per spec §11.5). If grep returns hits, halt and surface to operator (sub-dispatch escape valve).

- [ ] **Step 4-5: Implement, run, commit.**

Commit: `refactor(web): C.7 — routes state predicates + base-layout VM no-regression`.

**Expected new tests:** ~3.

---

### Task C.8: Pre-trade gate failure rendering — 3 entry surfaces consistency

**Files:** Modify `swing/web/routes/trades.py` (hyp-recs Take-this-trade route + manual entry form route) + `tests/web/test_routes/test_*.py`.

**Goal:** all 3 surfaces (CLI per B.8; web entry form per C.3; hyp-recs panel) render `MissingPreTradeFieldsException` consistently. Hyp-recs panel error message is panel-level (not full-page); the underlying form is the same shared template.

- [ ] **Step 1: Failing tests.**

```python
def test_hyp_recs_take_this_trade_missing_thesis_renders_panel_error(client):
    response = client.post("/recommendations/hypothesis/take-trade", data={
        "ticker": "TST",
        # entry-path defaults to hyp_recs_button on this route
        # ... other fields populated, thesis missing
    })
    assert response.status_code == 200
    assert "missing-thesis" in response.text  # field error class
    # Panel-level error message above the form:
    assert "Pre-trade required fields" in response.text


def test_all_3_entry_surfaces_use_shared_error_template(client):
    """Sanity: web form + hyp-recs route render the SAME entry_form.html.j2."""
    # Both routes' templates ref entry_form.html.j2; OOB-swap drift gotcha pre-empted.
    response_web = client.post("/trades/entry/form", data={"ticker": "TST"})
    response_hyp = client.post("/recommendations/hypothesis/take-trade", data={"ticker": "TST"})
    # Both responses include the section legends from spec §11.1.
    for r in (response_web, response_hyp):
        assert "Pre-trade thesis" in r.text or "Premortem" in r.text
```

- [ ] **Step 2-5: Implement, run, commit.**

Hyp-recs route (existing route handler in `swing/web/routes/recommendations.py` — adjust path; this Phase 7 task expands the existing handler). Wire to the same `record_entry()` path with `entry_path=EntryPath.HYP_RECS_BUTTON`; on `MissingPreTradeFieldsException`, render the same form template with panel-level error chrome.

Commit: `feat(web): C.8 — pre-trade gate consistent rendering at 3 entry surfaces`.

**Expected new tests:** ~6.

---

### Sub-C acceptance summary

- **Total Sub-C tasks:** 8.
- **Total expected new tests:** ~50-60.
- **Sub-C binding gate:** full fast suite GREEN; operator-witnessed browser verification of (a) entry form renders 7 fieldsets; (b) submitting incomplete form re-renders with field-level highlights; (c) successful submit creates trade with state='entered' and HX-Redirects to detail; (d) trade detail shows Pre-Trade Decision section with lock indicator + audit log placeholder; (e) journal + dashboard show state badges per row; (f) hyp-recs Take-this-trade flow round-trips through gate consistently.
- **Adversarial Codex review:** 2-4 rounds expected.

---

## §7 Test strategy summary + count band

### §7.1 Total expected new tests

| Sub-dispatch | New tests | Cumulative |
|---|---|---|
| Sub-A | 87 | baseline + 87 = 1674 |
| Sub-B | ~50 | ~1724 |
| Sub-C | ~50-60 | ~1774-1784 |

**Plan estimate band:** **+150–250 new fast tests** (matches spec §14.8). Wide band acknowledged per Phase 6 lesson `test-count-projections-bias-high`. Surplus over plan estimate is acceptable IF discriminating-test discipline holds; NOT acceptable if vacuous parameterization inflates count.

### §7.2 Discriminating-test discipline

For every test, the implementer MUST answer "would this test fail if the implementation never actually called the new code?" If the answer is "yes, even without the fix, the test passes" — the test is vacuous; redesign it.

Specific discriminators called out:
- **Migration safety (T9):** 4-fixture preservation invariant — each fixture exercises a distinct migration risk dimension (singleton, multi-date, same-date deterministic ordering, notes-merged).
- **Migration in-flight (T10):** VIR/DHC/CC backfill values are EXACT (not "is closed" — but `state == 'reviewed'` for VIR specifically; not "has fills" — but `current_size == 0.0` for VIR exactly).
- **State machine (A.5):** parameterized 25-cell matrix; each cell asserts ALLOW or REJECT exactly once (not parameterized over an over-broad "every transition is enforced" predicate).
- **Validate-for-operation (A.5):** parameterized over per-operation required-field tuple; each field's missing-rejection tests that the validator returns the SPECIFIC field name in the missing list (not just "raises").
- **Origin (A.7):** parameterized 11 (bucket × entry_path) cells + ticker-absent + pipeline-not-completed + yesterday-fallback edge cases.
- **Entry gate (B.1):** parameterized over per-required-field; force=True does NOT bypass (binding regression assertion per spec §9.3).
- **Exit (B.4):** trim/exit/stop branching; same-day stop-out double-transition.
- **Stop-adjust (B.5):** state predicate gating; first-stop transition trigger.
- **CLI (B.7-8):** entry rejects missing required-field with non-zero exit + stderr message.
- **HX-Redirect target route registered (C.3):** discriminating test from CLAUDE.md gotcha 2026-05-04.
- **`or None` for nullable+CHECK columns (C.3):** discriminating test would have caught Phase 6 deviation #3.
- **State badge shared partial (C.6):** discriminating test asserts `{% include "state_badge.html.j2" %}` is used, not hand-duplicated markup.

### §7.3 Test fixture refactor scope

Sub-A T0 covers 8 fixture-using files identified at empirical-audit time. Sub-B T6 covers 5 review-related test files. Additional drift discovered at sub-dispatch dispatch time is bundled into the sub-dispatch's first or last task (typically the predicate-rewrite task that owns the file).

---

## §8 Done criteria + return report format

### §8.1 Plan-side done criteria (this dispatch)

- [x] Plan saved at `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`.
- [ ] Plan committed to `main` via conventional commit `docs(plans): phase 7 trade lifecycle state machine plan`.
- [ ] Plan respects all locked spec decisions in spec §2.
- [ ] Plan resolves all open questions in writing-plans-brief §3:
  - Vocabulary lists with operator-confirm checkpoint mechanism (§1).
  - status→state per-call-site predicate rewrite mapping (§2).
  - Migration sequencing (single 0014 — inherited from spec §13.1).
  - Sub-dispatch decomposition (§0; 3 sub-dispatches A/B/C; serial default with parallelization permitted post-Sub-A).
  - Test count band (§7.1; +150-250).
  - Test fixture refactor scope (Sub-A T0 + Sub-B T6 + Sub-C as-touched).
  - DHC + CC trade_origin verification (Sub-A T2 migration UPDATE uses operator-confirmed FIRM `pipeline_watch_hyp_recs`).
- [ ] Plan organizes tasks into 3 sub-dispatch groups with clean boundaries (§4–§6).
- [ ] Plan enumerates the carve-out file list (§3; ~38 files).
- [ ] Plan includes the per-call-site `status`→state predicate rewrite mapping (§2.1).
- [ ] Plan includes the 4-fixture preservation invariant test gate (Sub-A T9).
- [ ] Plan includes the state-machine all-transition-paths matrix (Sub-A T5; 25 cells).
- [ ] Plan includes the migration runner discipline section (Sub-A T1; SQLite-native backup + 4 binding integrity checks).
- [ ] Plan includes the in-flight migration backfill specification (Sub-A T10 with VIR/DHC/CC).
- [ ] Plan includes the vocabulary operator-confirm checkpoint mechanism (§1.4).
- [ ] Plan total expected new fast tests stated (§7.1; +150-250 wide band).
- [ ] Plan specifies worktree isolation + marker-file Codex-blocking workflow per sub-dispatch (§0.2).
- [ ] Adversarial Codex review on the plan reaches `NO_NEW_CRITICAL_MAJOR` verdict.
- [ ] Operator approves the plan via the writing-plans skill's review gate.

### §8.2 Sub-dispatch-side done criteria (deferred to executing-plans dispatches)

Each Sub-A / Sub-B / Sub-C executing-plans dispatch ships when:

- All sub-dispatch tasks complete with TDD discipline (RED → minimal impl → GREEN → commit per task).
- Full fast suite GREEN at sub-dispatch worktree HEAD.
- Adversarial Codex review on the diff reaches `NO_NEW_CRITICAL_MAJOR`.
- Operator-witnessed verification gate passes (browser DevTools for Sub-C HTMX changes; CLI manual run for Sub-B; pytest + ruff for Sub-A).
- Sub-A specifically: backup file present in `~/swing-data/`; production DB at schema_version 14; all 3 trades migrated to expected state.
- Worktree merges to main; orchestrator records the merge SHA in next sub-dispatch's BASELINE_SHA.

### §8.3 Operator pre-conditions before each sub-dispatch

- **Before Sub-A:** vocabulary confirmation per §1.4; production DB backup verified to a known-good off-Drive path; main is at the BASELINE_SHA recorded in the dispatch brief.
- **Before Sub-B:** Sub-A merged to main + verified-green; full fast suite still GREEN at main; production DB at schema_version 14 with VIR/DHC/CC migrated as expected.
- **Before Sub-C:** Sub-A (and optionally Sub-B) merged + verified-green; full fast suite still GREEN at main.

### §8.4 Return report format (writing-plans dispatch — used by orchestrator triage)

The writing-plans dispatch's final report to the orchestrator follows the brief's §7 format. Key fields:

- `PLAN: docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`
- `COMMITS: <initial> → <final>`
- `ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR`
- Key plan decisions resolutions (vocabulary, predicate rewrite, sub-dispatch decomposition, test count band, fixture refactor scope, DHC+CC origin)
- Carve-out summary (~38 files)
- Per-call-site predicate rewrite summary (12 prod files + 13 test-corpus categories)
- Adversarial findings with disposition (per round)
- Lessons worth capturing (process insights from plan-authoring)
- Open questions for orchestrator (vocabulary awaiting operator confirmation)
- Next-step handoff notes (Sub-A BASELINE_SHA = main HEAD at plan-commit time; Sub-B/C ordering = serial default with parallelization permitted post-Sub-A)

---

*End of plan.*
