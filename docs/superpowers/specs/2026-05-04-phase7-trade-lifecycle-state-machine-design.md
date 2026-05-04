# Phase 7 — Trade Lifecycle State Machine + Fills First-Class: Design Spec

**Status:** Brainstorm complete; awaiting adversarial Codex review.
**Authored:** 2026-05-04
**Source brief:** `docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md` (commit `db6727d`).
**Successor to:** Phase 6 post-trade review surface (shipped 2026-05-04 at `51c79ed`).
**Predecessor to:** Phase 8 (Daily_Management + MFE/MAE), Phase 9 (Risk_Policy + reconciliation depth) — both gated on Phase 7 shipping.
**Estimated implementation dispatches downstream:** 4–6 (writing-plans + executing-plans rounds).

---

## §1 Overview

Phase 7 is the structural backbone of the journal-v1.2 incorporation sub-bundle. It formalizes the trade lifecycle as an explicit 5-state machine, makes Fills the canonical execution log, locks pre-trade decision fields at first-fill, and adds a structured premortem + thesis surface to the entry path.

The phase is materially larger than Phase 5 or 6 — it touches every trade-write path (CLI entry / web entry / hyp-recs entry / exit / stop_adjust) and replaces two long-standing schema patterns (`status open|closed`, `exits` table) with the new state column and Fills table respectively. Schema migration is a single transactional rebuild against the live in-flight production data.

The design respects the v1.2 source spec's structural choices where they fit our pipeline-driven framework-research-loop workflow, and applies the locked v1.2 modification table from `docs/phase3e-todo.md` where the source-spec assumptions don't fit (notably: 4-value pipeline-aware `trade_origin` enum, no self-rated quality scores, no Setup_Playbook DB entity, no pyramiding R-views).

---

## §2 Locked constraints recap

These were settled before this brainstorm; they are not relitigated in this spec. If implementation reveals a hard conflict between any of these and what Phase 7 actually needs, the conflict-pause protocol in §17 applies.

**Sequencing:** Phase 7 = state machine + Fills + `pre_trade_locked_at` + premortem/thesis + pre-trade gate trim. NOT Daily_Management (Phase 8). NOT MFE/MAE precision (Phase 8). NOT Risk_Policy DB entity (Phase 9). NOT Reconciliation_Run / Reconciliation_Discrepancy (Phase 9). Schema must accommodate these futures without painted corners.

**v1.2 modifications adopted in full:**

- `trade_origin` is a **4-value pipeline-aware enum**: `pipeline_aplus | pipeline_watch_hyp_recs | pipeline_watch_manual | manual_off_pipeline`. NOT v1.2's 7-value discretionary enum.
- DROP self-rated `pre_trade_quality_score` (pipeline already grades).
- DROP `Setup_Playbook` as DB entity (encoded in `swing/evaluation/`).
- DROP pyramiding R-views (operator at $7,500 / ~5 positions doesn't pyramid).
- DROP `Screen_Definitions` versioning.
- Drawdown circuit breaker stays opt-in disabled (Phase 9 territory; Phase 7 schema accommodates the toggle without enforcing).

**Project conventions:**

- Phase isolation default = read-only on `swing/data/` + `swing/trades/` with explicit Phase 7 carve-outs (see §15).
- DB at `%USERPROFILE%/swing-data/swing.db`, outside Drive sync. Hard invariant.
- Conventional commits, no Claude co-author footer, no `--no-verify`, no amending.
- Test baseline = 1587 fast tests at HEAD `51c79ed`.

**In-flight production data (binding constraint on migration):**

Three trades exist at HEAD:

- **VIR** — closed + reviewed via Phase 6 surface 2026-05-04. `hypothesis_label = "inaugural trade test"`. Single full exit at -0.33R.
- **DHC** — open since 2026-04-27 ($7.58 × 39 shares). `hypothesis_label = "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)"`.
- **CC** — open since 2026-04-30 ($26.97 × 5 shares). `hypothesis_label = "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"`.

Migration must derive (state, required-fields) for all three **without operator data entry** for legacy pre-trade fields. Backup-then-migrate (`swing-pre-phase7-migration-<ISO>.db`) is binding.

**No data loss:** every existing `exits` row round-trips into `fills` via the migration.

---

## §3 State machine

### §3.1 State enum (5-state minimal)

```
entered → managing → partial_exited → closed → reviewed
```

Five states; no `planned`, no `triggered`, no `canceled`. The watchlist + watchlist_archive layer already serves the "plan and abandon" surface for candidates; trade rows only exist once a fill occurs.

**State semantics:**

| State | Meaning |
|---|---|
| `entered` | First entry-action fill recorded; no post-entry management activity yet. |
| `managing` | At least one management activity (stop_adjust, partial fill, daily review) has occurred. |
| `partial_exited` | At least one trim or partial exit fill recorded; net position still open. |
| `closed` | Net position flat (all shares exited); not yet reviewed. |
| `reviewed` | Phase 6 review completed (`reviewed_at IS NOT NULL`). |

### §3.2 Transition matrix (binding enumeration)

5 × 5 = 25 cells. **5 allowed, 20 rejected.**

| from \ to | entered | managing | partial_exited | closed | reviewed |
|---|---|---|---|---|---|
| **entered** | reject | **allow** | reject | reject | reject |
| **managing** | reject | reject | **allow** | **allow** | reject |
| **partial_exited** | reject | reject | reject | **allow** | reject |
| **closed** | reject | reject | reject | reject | **allow** |
| **reviewed** | reject | reject | reject | reject | reject |

**`reviewed` is terminal in Phase 7's transition map.** Phase 9 reconciliation may reopen reviewed trades on material discrepancy; Phase 9 will add a transition (e.g., `reviewed → closed` or to a new `reopened` state) by extending the transition map. No painted corner.

### §3.3 Transition triggers (which event fires which transition)

| Transition | Trigger |
|---|---|
| `entered → managing` | First management activity: first `stop_adjust` event OR first `trim` / `exit` / `stop`-action fill OR (Phase 8 future) first `daily_management` record. |
| `managing → partial_exited` | First `trim`-action fill where `current_size > 0` after the fill. |
| `managing → closed` | `exit`-action fill that brings `current_size` to 0 (no prior trims). |
| `partial_exited → closed` | Final `exit` fill that brings `current_size` to 0. |
| `closed → reviewed` | Phase 6 `mark_reviewed` flow completes (sets `reviewed_at`). |

**Same-day stop-out path:** `entered → managing → closed` (atomic double-transition in the exit operation). The exit service handles both transitions in one transaction.

### §3.4 Transition enforcement (hybrid)

- **DB CHECK:** `state` column constrained to the 5 valid string values: `CHECK (state IN ('entered','managing','partial_exited','closed','reviewed'))`. Rejects garbage values (`state='lol'`).
- **App-layer:** `state_transition(conn, trade_id, new_state, ...)` service in `swing/trades/state.py` is the SINGLE write path for state changes. Rejects illegal transitions per the matrix above. Emits a `trade_events` row for every transition (audit).

### §3.5 Required-fields-by-state map (data-driven)

A Python dict in `swing/trades/state.py` maps each state to its required-field tuple. Validation runs at write-time (pre-INSERT or pre-state-transition); missing fields → reject with structured exception listing the missing fields.

```python
REQUIRED_FIELDS_BY_STATE: dict[str, tuple[str, ...]] = {
    "entered": (
        "ticker", "entry_date", "entry_price", "initial_shares", "initial_stop",
        "trade_origin", "pre_trade_locked_at",
        # Pre-trade decision (cluster F):
        "thesis", "why_now", "invalidation_condition", "expected_scenario",
        "premortem_technical", "premortem_market_sector", "premortem_execution",
        "event_risk_present", "gap_risk_present",
        "emotional_state_pre_trade", "manual_entry_confidence",
        "market_regime", "catalyst",
        # Conditionally required (validator inspects flag fields):
        # event_handling required if event_risk_present=1
        # event_type, event_date required if event_risk_present=1
        # gap_risk_handling required if gap_risk_present=1
        # catalyst_other_description required if catalyst='other'
    ),
    "managing": ("...inherits from entered...", "current_stop", "current_size", "current_avg_cost"),
    "partial_exited": ("...inherits from managing...", "<at least 1 trim/exit fill exists>"),
    "closed": ("...inherits from managing...", "<current_size = 0>"),
    "reviewed": ("...inherits from closed...", "reviewed_at", "mistake_tags",
                 "entry_grade", "management_grade", "exit_grade", "process_grade",
                 "disqualifying_process_violation", "lesson_learned"),
}
```

**Design property — additive expansion to additional states is non-breaking:** adding a future `planned` state (option B in cluster A) requires only adding a new key to this dict + adding the value to the DB CHECK enum (table-rebuild migration); no existing state semantics change. This is binding for the implementation — the validator must not hardcode `if state == 'entered'` checks.

---

## §4 Fills schema + exits-table disposition

### §4.1 Fills replaces exits (canonical execution log)

The existing `exits` table is **dropped** in migration 0014. Every existing exits row round-trips into `fills` via 1:1 backfill (action mapping per §4.4 below). All readers migrate from `exits` repo → `fills` repo. No coexistence period; one-pass refactor matching the project pattern (Phase 4 watchlist consolidation; Phase 6 `review_log` authoritative entity).

### §4.2 Fills table schema

```sql
CREATE TABLE fills (
  fill_id INTEGER PRIMARY KEY,
  trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  fill_datetime TEXT NOT NULL,                              -- ISO-8601
  action TEXT NOT NULL CHECK (action IN ('entry','trim','exit','stop')),
  quantity REAL NOT NULL CHECK (quantity > 0),
  price REAL NOT NULL CHECK (price > 0),
  reason TEXT,                                              -- nullable; required at app layer for non-entry actions
  rule_based INTEGER CHECK (rule_based IS NULL OR rule_based IN (0,1)),
  fees REAL,                                                -- nullable; populated post-reconciliation
  manual_entry_confidence TEXT
      CHECK (manual_entry_confidence IS NULL OR manual_entry_confidence IN ('high','normal','low')),
  reconciliation_status TEXT NOT NULL DEFAULT 'unreconciled'
      CHECK (reconciliation_status IN ('unreconciled','reconciled_match','reconciled_discrepancy',
                                        'reconciled_discrepancy_resolved','manual_override')),
  tos_match_id TEXT                                         -- external string ID; nullable until reconciled
);
CREATE INDEX ix_fills_trade ON fills(trade_id, fill_datetime);
CREATE INDEX ix_fills_action ON fills(trade_id, action);
```

**Type rationale:**

- `fill_id` INTEGER PRIMARY KEY (project convention; v1.2's "string" is generic; `tos_match_id` carries external string IDs).
- `quantity` REAL with CHECK > 0 (v1.2 numeric; future fractional-share friendly; existing INTEGER values upcast losslessly for whole shares).
- `fill_datetime` TEXT NOT NULL ISO-8601 datetime (project convention; legacy `exits` rows backfilled as `exit_date + 'T16:00:00'` close-of-session approximation flagged via `reconciliation_status='unreconciled'`).
- `action` 4-value enum (`entry | trim | exit | stop`). Drops v1.2's `add` (pyramiding DROPped per locked constraint) and `cover` (long-only V1). YAGNI: CHECK migration is cheap if pyramiding or shorting ever returns.
- `reconciliation_status` defaults `unreconciled`; vocabulary pulled verbatim from v1.2 §4.8 (Phase 9 will own the transitions; Phase 7 just accommodates the column).

### §4.3 Action-enum semantics

| Action | Meaning |
|---|---|
| `entry` | Position-opening fill. Exactly one per trade (the first fill). Sets `pre_trade_locked_at`. |
| `trim` | Partial exit fill; net position remains > 0 after fill. |
| `exit` | Full or final-partial exit fill; net position reaches 0 after fill. |
| `stop` | Stop-loss-triggered exit fill. Subtype of `exit` semantically; preserved as a separate action so reconciliation + analytics can distinguish stop-hits from discretionary exits. |

**Boundary between `trim` and `exit`:** if the fill brings `current_size` to 0, action is `exit` (or `stop`); otherwise `trim`. The fills-write service computes this from per-trade fill aggregation; operator declares intent at submit time and the service can verify.

### §4.4 exits → fills field mapping (migration backfill)

| `exits` column | `fills` column | Notes |
|---|---|---|
| `id` | (none — new INT autogen) | |
| `trade_id` | `trade_id` | 1:1 |
| `exit_date` | `fill_datetime` | Backfilled as `exit_date \|\| 'T16:00:00'`; `reconciliation_status='unreconciled'` flags the synthetic timestamp. |
| `exit_price` | `price` | 1:1 |
| `shares` | `quantity` | INTEGER → REAL upcast (lossless for whole shares). |
| `reason` | `reason` | 1:1 |
| `realized_pnl` | (NOT STORED) | Computed-on-read: `(exit_price - entry_price) * quantity`. Existing readers compute or use a helper. |
| `r_multiple` | (NOT STORED) | Computed-on-read: `realized_pnl / (initial_risk_per_share * quantity)`. |
| `notes` | `reason` (concatenated) | If `notes` non-empty, append to `reason` with separator `' | '`. |

**Action derivation for migration:** for each existing exits row, compute `cumulative_exited_after_this_row` per trade. If `cumulative_exited == initial_shares` AND no later exits exist for this trade → `action='exit'`. Else → `action='trim'`. `action='stop'` not auto-derived (no signal in legacy `exits.reason` reliable enough); legacy stop-out rows persist as `exit` with the original reason text preserved.

**Realized PnL / R-multiple computation helpers:** new module `swing/trades/derived_metrics.py` (or extend existing analytic helper) provides pure functions consuming Trade + per-fill data; existing `exits.realized_pnl` consumers migrate to call these helpers. Spec lists callers in §15.

### §4.5 trades.entry_* — frozen-at-first-fill cache

`trades.entry_date`, `trades.entry_price`, `trades.initial_shares`, `trades.initial_stop` remain on the trades row as a **frozen cache of the first entry-action fill**. Written atomically by the entry service at fill insertion; immutable thereafter (mutation only via pre-trade-edit-audit path per §6).

Rationale: preserves test-fixture compat (no mass refactor); preserves dashboard / journal query simplicity (no first-fill subquery on every read); no analytical fidelity loss (these IS the first-fill data).

### §4.6 Aggregate denorm columns on `trades`

Three new columns updated by the fills-write service after every fill insert:

| Column | Type | Computation |
|---|---|---|
| `current_size` | REAL NOT NULL DEFAULT 0 | `sum(entry quantities) - sum(trim/exit/stop quantities)` |
| `current_avg_cost` | REAL | weighted-avg of entry+add fills (in V1 with no `add`, equals entry_price) |
| `last_fill_at` | TEXT | `max(fills.fill_datetime)` for this trade |

**Update path:** `swing/data/repos/fills.py` `_recompute_aggregates(conn, trade_id)` is called after every fill INSERT. Single write path = consistency invariant.

**Consistency invariant (test assertion):** `current_size = sum(entry quantities) - sum(trim/exit/stop quantities)` must hold after every fill insert. Tested against fixture trades; tested against the migration-time backfill.

---

## §5 `trades.status` integration — DROP entirely

The existing 2-value `status open|closed` column is **dropped** in migration 0014. Every reader rewrites:

- `status='open'` → `state IN ('entered', 'managing', 'partial_exited')`
- `status='closed'` → `state IN ('closed', 'reviewed')`

### §5.1 Empirical enumeration of `trades.status` call sites (spec-write-time grep)

Verified at spec-write 2026-05-04 against HEAD `db6727d`. Plan-time refresh required (writing-plans dispatch re-runs grep before implementation). Excludes false-positives (hypothesis_registry.status, pipeline_runs.state, weather_runs.status, etc.).

**Production code (12 files):**

| File | Sites | Type |
|---|---|---|
| `swing/data/repos/trades.py` | lines 69, 98–104, 117, 144, 165, 225, 238, 247, 265, 344, 373, 390 | INSERT/UPDATE writes + multiple SQL read queries |
| `swing/data/db.py` | lines 20, 42, 52, 58, 62 | Migration 0004 helper docstring + duplicate-`status='open'` check helper |
| `swing/trades/entry.py` | line 197 | `Trade(...)` dataclass construction with `status="open"` |
| `swing/trades/review.py` | line 214 | Phase 6 review precondition (`trade.status != "closed"`) |
| `swing/journal/stats.py` | lines 47, 96, 179 | Closed-trade filter predicates |
| `swing/journal/flags.py` | lines 39, 59, 93 | Closed-trade filter predicates |
| `swing/journal/analyze.py` | line 242 | Analyze output passes `trade.status` |
| `swing/journal/tos_import.py` | lines 287, 318 | SQL queries `WHERE t.status='closed'` |
| `swing/cli.py` | lines 588, 1008 | CLI display + closed-status check |
| `swing/web/routes/trades.py` | lines 844, 1082, 1198 | Route preconditions |
| `swing/web/view_models/trades.py` | lines 331, 385, 432 | VM filter predicates |
| `swing/web/view_models/open_positions_row.py` | line 181 | VM filter predicate |
| `swing/web/templates/journal.html.j2` | line 34 | Template renders `{{ t.status }}` (display) |

**Tests (43 files identified by grep)** — full enumeration deferred to writing-plans dispatch (operator approves at plan-review). Categories:

- Direct `trade.status` assertions in `tests/data/test_repos_trades.py`, `tests/web/test_view_models/test_trades.py`, etc.
- Test fixture builders setting `status="open"` / `"closed"` directly.
- Phase 6 review tests checking pre-state of closed trades (preserve semantics via `state IN ('closed','reviewed')`).

### §5.2 Rewrite pattern per call site

- **Read predicates (Python):** `trade.status == "open"` → `trade.state in ("entered","managing","partial_exited")`. `trade.status != "closed"` → `trade.state not in ("closed","reviewed")`.
- **Read predicates (SQL):** `WHERE status='open'` → `WHERE state IN ('entered','managing','partial_exited')`. `WHERE status='closed'` → `WHERE state IN ('closed','reviewed')`.
- **Write paths:** `UPDATE trades SET status='closed'` → state-transition service emits `state='closed'` (via `swing/trades/state.py` single write path).
- **Display:** `{{ t.status }}` in templates → `{{ t.state }}` (or per-state badge per §11.3).

### §5.3 Migration 0004 helper compatibility

`swing/data/db.py:20-62` contains the duplicate-`status='open'` migration-0004 helper. After `status` is dropped, the helper is rewritten to check the new state predicate (`state IN ('entered','managing','partial_exited')` — same semantics on the new schema). Migration 0014 itself preserves the unique-index invariant (one open trade per ticker) by rebuilding it against `state IN (open-states)` partial index. Plan-time enumeration of partial-index recreation included.

### §5.4 Migration 0004 partial unique index — recreated against new state column

Existing index in migration 0004:

```sql
CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
    ON trades(ticker) WHERE status = 'open';
```

Migration 0014 rebuild (within trades table-rebuild step):

```sql
CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
    ON trades(ticker) WHERE state IN ('entered','managing','partial_exited');
```

Same semantics; preserves the at-most-one-open-trade-per-ticker invariant under the new state model.

---

## §6 `pre_trade_locked_at` semantics + edit-after-lock

### §6.1 Trigger

`pre_trade_locked_at = <fill_datetime of first action='entry' fill>`. Set atomically by the entry / state-transition service when the first entry-action fill is inserted. Once set, never updated via normal write paths.

### §6.2 Locked field set

All pre-trade decision fields are frozen at `pre_trade_locked_at`. The locked set:

- **NEW Phase 7 fields:** `thesis`, `why_now`, `expected_scenario`, `invalidation_condition`, `premortem_technical`, `premortem_market_sector`, `premortem_execution`, `premortem_additional`, `event_risk_present`, `event_handling`, `event_type`, `event_date`, `gap_risk_present`, `gap_risk_handling`, `emotional_state_pre_trade`, `manual_entry_confidence`, `market_regime`, `catalyst`, `catalyst_other_description`, `trade_origin`.
- **Cached first-fill snapshot:** `entry_date`, `entry_price`, `initial_shares`, `initial_stop`.
- **Existing already-frozen fields (precedent):** `hypothesis_label`, `chart_pattern_algo`, `chart_pattern_algo_confidence`, `chart_pattern_operator`, `chart_pattern_classification_pipeline_run_id`, `sector`, `industry`. Phase 7 formalizes the lock semantics these already followed by precedent.

### §6.3 Lock enforcement (app-layer)

No DB triggers. Repo functions for locked fields do not expose UPDATE paths. The pre-trade-edit-audit path (§6.4) is the only mutation entry. Direct SQL UPDATEs to locked columns are forbidden by convention; lint / test discipline polices this rather than DB-level rejection. Consistent with §3.4's hybrid pattern (DB CHECK floor, app-layer single write path).

### §6.4 Edit-after-lock mechanism — `trade_events` reuse

The existing `trade_events` table audits all trade mutations. Phase 7 extends the `event_type` CHECK enum to include `'pre_trade_edit'`:

```sql
-- Migration 0014 expands the CHECK enum:
event_type IN ('entry','stop_adjust','note','exit','flag','pre_trade_edit')
```

**`payload_json` schema for pre_trade_edit events:**

```json
{
  "field": "<column_name>",
  "old_value": <prior value, type-preserved>,
  "new_value": <new value, type-preserved>,
  "reason": "<required operator-supplied text justification>"
}
```

Each edit creates one `trade_events` row per field changed. The `rationale` column on `trade_events` carries the operator-supplied edit reason (also in `payload_json.reason` for structured queries).

### §6.5 V1 UX scope: read-only display + audit-trail visible

Per §11.4 (UX), Phase 7 V1 ships the lock + audit infrastructure but does NOT ship the edit-after-lock UI. Operator-visible trade-detail view renders pre-trade fields read-only with a lock indicator + `pre_trade_locked_at` timestamp + audit-log read-display. Edit form ships in a future phase (deferred to Phase 7 follow-up or later).

If operator needs to correct legacy data in V1, the escape valve is direct DB edit + manual `trade_events` row insertion (operator-only; rare).

### §6.6 Migration handling for VIR / DHC / CC

Per §12 in-flight migration plan: each legacy trade's `pre_trade_locked_at` is set to `entry_date + 'T16:00:00'` (close-of-session approximation). All new pre-trade fields persist as NULL.

---

## §7 Premortem schema

### §7.1 Distribution rule

**Minimum 1 reason per category** across the three categories (technical, market_sector, execution). Operator can add additional reasons via the optional `premortem_additional` field. Forces consideration of each broad failure dimension (counters single-mode-of-failure overconfidence).

### §7.2 Schema shape — 3 named columns + 1 optional additional

| Column | Type | Required (app-layer) |
|---|---|---|
| `premortem_technical` | TEXT (nullable; default NULL) | yes — non-empty/non-whitespace |
| `premortem_market_sector` | TEXT (nullable; default NULL) | yes — non-empty/non-whitespace |
| `premortem_execution` | TEXT (nullable; default NULL) | yes — non-empty/non-whitespace |
| `premortem_additional` | TEXT (nullable) | optional; free-text |

Schema-level nullability + app-layer non-empty validation matches Phase 6 review-field pattern. Legacy migration → NULL on all 4 columns; display layer interprets NULL as "(legacy — no premortem)" for trades where `premortem_technical IS NULL`.

### §7.3 Validation

App-layer in `swing/trades/entry.py`:

```python
def _validate_premortem(req: EntryRequest) -> list[str]:
    """Returns list of missing-field names; empty if valid."""
    missing = []
    for field in ("premortem_technical", "premortem_market_sector", "premortem_execution"):
        value = getattr(req, field, None)
        if value is None or not value.strip():
            missing.append(field)
    return missing
```

`MissingPreTradeFieldsException(missing_fields=...)` includes premortem field names in the missing list.

---

## §8 Thesis + decision fields

### §8.1 KEPT fields (added to `trades` schema)

All NULLABLE in schema (legacy migration → NULL); app-layer entry service enforces non-empty/non-null on Submit.

| Field | Type | Required (app-layer) | Notes |
|---|---|---|---|
| `thesis` | TEXT | yes | Why trade should work. |
| `why_now` | TEXT | yes | Why entry is timely. |
| `invalidation_condition` | TEXT | yes | What proves thesis wrong. |
| `expected_scenario` | TEXT | yes | What should happen if right. |
| `premortem_technical` | TEXT | yes | Per §7. |
| `premortem_market_sector` | TEXT | yes | Per §7. |
| `premortem_execution` | TEXT | yes | Per §7. |
| `premortem_additional` | TEXT | optional | |
| `event_risk_present` | INTEGER (0/1) | yes | |
| `event_handling` | TEXT (CHECK enum) | yes | Values: `avoid_event`, `hold_through`, `reduce_before`, `exit_before`, `not_applicable`. |
| `event_type` | TEXT (CHECK enum) | conditional (if `event_risk_present=1`) | Values: `earnings`, `fed_meeting`, `cpi_release`, `economic_data`, `product_announcement`, `legal_ruling`, `other`. (Spec-review confirms vocabulary.) |
| `event_date` | TEXT (ISO date) | conditional (if `event_risk_present=1`) | |
| `gap_risk_present` | INTEGER (0/1) | yes | |
| `gap_risk_handling` | TEXT (CHECK enum) | yes | Values: `accept`, `reduce_size`, `tight_stop`, `exit_before_close`, `not_applicable`. |
| `emotional_state_pre_trade` | TEXT (JSON-list) | yes | Vocabulary: `calm`, `confident`, `anxious`, `fomo`, `revenge`, `hopeful`, `doubtful`, `distracted`. (Spec-review confirms vocabulary.) Validation + canonicalization helpers mirror Phase 6 mistake_tags pattern. |
| `manual_entry_confidence` | TEXT (CHECK enum) | yes | Values: `high`, `normal`, `low`. |
| `market_regime` | TEXT (CHECK enum) | yes | Values: `Bullish`, `Caution`, `Bearish` (matches existing `weather_runs.status`). Captures operator's planning-time self-assessed regime; may differ from system-computed weather. |
| `catalyst` | TEXT (CHECK enum) | yes | Values: `earnings_driven`, `guidance_change`, `corporate_action`, `sector_rotation`, `macro_event`, `sympathy_move`, `product_news`, `technical_only`, `other`. (Trimmed from v1.2 §4.6's 13 values; spec-review confirms vocabulary.) |
| `catalyst_other_description` | TEXT | conditional (if `catalyst='other'`) | |
| `trade_origin` | TEXT (CHECK 4-value enum) | yes | Per §10. |
| `pre_trade_locked_at` | TEXT (ISO datetime) | yes | Per §6. |

**`... or None` discipline:** every nullable text + CHECK enum column above (event_handling, event_type, gap_risk_handling, manual_entry_confidence, market_regime, catalyst, trade_origin) MUST use `value = form_value or None` (NOT `or ""`) in form-input fallback paths. Empty string fails the CHECK constraint; NULL is accepted. Per CLAUDE.md gotcha (2026-05-04 Phase 6 deviation #3 mistake_cost_confidence collision).

### §8.2 DROPPED fields (with rationale)

| v1.2 field | Rationale for drop |
|---|---|
| `final_pre_trade_decision` (take/pass/wait/reduce_size) | Always 'take' in our 5-state model (no `planned` state to express the others). |
| `pre_trade_quality_score` (0-10 self-rating) | Locked constraint §2.4 — pipeline already grades. |
| `confidence_score` (1-5 self-rating) | Same self-rating-duplication family; redundant with `manual_entry_confidence`. |
| `sector_theme` | Already covered by existing `sector` + `industry` (frozen-at-entry, migration 0012). |
| `sector_condition` (leading/improving/neutral/weakening/lagging) | Self-rated quality field; same family. |
| `planned_holding_period_days` | Limited analytical leverage; YAGNI. |
| `target_1`, `target_2` | No partial-exit-at-target workflow today; YAGNI. |
| `planned_reward_risk_ratio` | Depends on dropped targets. |
| `correlated_exposure` | Already in `sector` + `industry`. |
| `account_equity_pre_trade` | Computed-on-read sufficient; YAGNI. |
| `position_size_override_reason` | Fold into existing `notes`. |
| `planned_risk_dollars` | Computed-on-read from `(entry_price - initial_stop) * initial_shares`; pre-trade gate consumes the computed value. |

### §8.3 Field-purpose taxonomy (documented for clarity across phases)

| Field | Lifecycle moment | Frozen vs mutable |
|---|---|---|
| `notes` (existing) | any point | mutable |
| `thesis`, `why_now`, `invalidation_condition`, `expected_scenario` | pre-trade | frozen-at-lock |
| `premortem_*` | pre-trade | frozen-at-lock |
| `event_*`, `gap_*`, `emotional_state_pre_trade`, `manual_entry_confidence`, `market_regime`, `catalyst` | pre-trade | frozen-at-lock |
| `trade_origin`, `pre_trade_locked_at`, cached `entry_date`/`entry_price`/`initial_shares`/`initial_stop` | pre-trade snapshot | frozen-at-lock |
| `hypothesis_label`, `chart_pattern_*`, `sector`, `industry` | pre-trade (existing) | frozen-at-entry (precedent; joins lock) |
| `current_stop` | management | mutable via `stop_adjust` only |
| `current_size`, `current_avg_cost`, `last_fill_at` | computed-state | recomputed on every fill insert |
| `state` | lifecycle | mutable via `state_transition()` only |
| `lesson_learned` (Phase 6) | review-time | mutable until review marked complete |
| `reviewed_at`, `mistake_tags`, grades (Phase 6) | review-time | frozen at review completion |

Every new field declares disposition; no field ships without one.

---

## §9 Pre-trade gate composition + firing

### §9.1 Gate check composition

**Existing checks preserved (already in `record_entry()`):**

- `HardCapException` (open_count ≥ hard_cap_open) — never bypassable.
- `SoftWarnException` (open_count ≥ soft_warn_open) — bypassable with `force=True`.
- `DuplicateOpenPositionException` (already-open ticker).
- Stop < entry validation.
- Risk-pct enforcement via existing `compute_shares` / `SizingResult` upstream.

**NEW Phase 7 check:**

- `MissingPreTradeFieldsException(missing_fields: list[str])` — validates all required new pre-trade fields are present + non-empty. Field set defined by `REQUIRED_FIELDS_BY_STATE['entered']` in `swing/trades/state.py`. Conditional fields (event_*, gap_*, catalyst_other_description) validated via inspect-flag-then-require pattern.

**DEFERRED to Phase 9 (schema accommodates; not implemented):**

- `portfolio_heat_pct_after_trade > max_portfolio_heat_pct`.
- `consecutive_loss_pause_active`.
- `drawdown_circuit_breaker` (locked opt-in disabled per constraint §2.8).

### §9.2 Gate factoring (single source of truth)

Three entry surfaces (CLI `swing trade entry`, web POST `/trades/entry/form`, hyp-recs Take-this-trade route) all call `record_entry()` in `swing/trades/entry.py`. Phase 7 expands `record_entry()` to validate the new fields at the top of the function (before existing open-count checks).

```python
def record_entry(conn, req: EntryRequest, *, soft_warn, hard_cap, force) -> EntryResult:
    # NEW: Phase 7 — required-field validation (data-driven from state.py).
    missing = validate_required_fields_for_state(req, target_state="entered")
    if missing:
        raise MissingPreTradeFieldsException(missing_fields=missing)

    # NEW: Phase 7 — derive trade_origin from candidate row + entry_path.
    req = replace(req, trade_origin=derive_trade_origin(conn, req.ticker, req.entry_path))

    # Existing: stop-below-entry, duplicate-ticker, hard-cap, soft-warn.
    # ... existing record_entry body, expanded to write Fill on entry.

    # NEW: Phase 7 — atomic INSERT trades + INSERT first entry-fill + SET pre_trade_locked_at.
```

Each surface translates raised exceptions into surface-specific error display:

- **CLI:** stderr message + non-zero exit code.
- **Web:** form re-render with field-level errors (server-side rerender pattern; values prefilled per §11.2).
- **Hyp-recs panel:** panel-level error message; the entry form is the same shared template.

### §9.3 Failure mode — hard reject (no force-bypass for new checks)

`MissingPreTradeFieldsException` is **NOT** force-bypassable. The discipline of "thesis articulated before fill" is meaningless if force-bypassable; soft-warn defeats anti-rationalization.

Existing check semantics preserved unchanged: `HardCap` not bypassable; `SoftWarn` bypassable with `force=True`; `Duplicate` not bypassable; stop < entry not bypassable.

### §9.4 Output enum — NOT adopting v1.2's 6-value APPROVE/REJECT/etc.

Gate is binary (pass / structured-exception-fail). REDUCE_SIZE / WAIT outputs from v1.2 don't apply in our 5-state model (no `planned` state to express deferred-entry).

### §9.5 No new Phase 7 soft-warns

Existing open-count soft-warn carries forward unchanged. No new soft-warn categories.

---

## §10 `trade_origin` derivation

### §10.1 Derivation table

| `candidates.bucket` (most-recent-completed-pipeline-run) | Entry path | `trade_origin` |
|---|---|---|
| `aplus` | any (today_decision button / hyp-recs button / manual web form / CLI) | `pipeline_aplus` |
| `watch` | hyp-recs Take-this-trade button | `pipeline_watch_hyp_recs` |
| `watch` | manual web form / CLI manual / today_decision button (rare for `watch`) | `pipeline_watch_manual` |
| `skip` / `error` / `excluded` | any | `manual_off_pipeline` |
| (ticker absent from candidates) | any | `manual_off_pipeline` |

**Rationale for skip/error/excluded → `manual_off_pipeline`:** pipeline didn't endorse the trade; operator is acting on discretion. The 4-value enum maps cleanly without a 5th value.

### §10.2 Bucket-lookup fallback

Lookup uses **most-recent-completed-pipeline-run's** `candidates` table. If today's pipeline hasn't run yet, use yesterday's run. No day-walking beyond that — operator entering a ticker absent from yesterday's screen counts as off-pipeline.

### §10.3 EntryPath enum

```python
class EntryPath(str, Enum):
    APLUS_TODAY_DECISION = "aplus_today_decision"   # web aplus card / CLI selecting today_decisions
    HYP_RECS_BUTTON       = "hyp_recs_button"        # web hyp-recs "Take this trade" button
    MANUAL_WEB_FORM       = "manual_web_form"        # web form, operator-typed ticker
    CLI_MANUAL            = "cli_manual"             # `swing trade entry` CLI typed ticker
```

Each surface populates `EntryRequest.entry_path` when constructing the request. `derive_trade_origin(conn, ticker, entry_path) -> str` lives in `swing/trades/origin.py` and is called by `record_entry()` at INSERT time.

### §10.4 Persistence

```sql
trade_origin TEXT NOT NULL CHECK (trade_origin IN
    ('pipeline_aplus','pipeline_watch_hyp_recs','pipeline_watch_manual','manual_off_pipeline'))
```

Frozen-at-entry per `hypothesis_label` precedent. No UPDATE path.

---

## §11 UX surface impact

### §11.1 Entry form expansion — single-page sectioned `<fieldset>` blocks

Form gains ~16 new fields. UX pattern: 7 sectioned `<fieldset>` blocks (no JS / no accordion); operator scrolls; section headers visually distinct. Sections:

1. **§1 Position basics** (existing): ticker, entry_price, shares, initial_stop.
2. **§2 Setup attribution** (existing + new): rationale, hypothesis_label, chart_pattern_*, sector/industry. NEW: `trade_origin` display-only (auto-derived, shown to operator for verification).
3. **§3 Pre-trade thesis** (NEW): thesis, why_now, expected_scenario, invalidation_condition. All `<textarea>`.
4. **§4 Premortem** (NEW): premortem_technical, premortem_market_sector, premortem_execution, premortem_additional. All `<textarea>`.
5. **§5 Risk acknowledgments** (NEW): event_risk_present checkbox + event_handling/event_type/event_date (always-visible, app-layer if-then validation in V1; HTMX progressive disclosure deferred to V2). gap_risk_present checkbox + gap_risk_handling.
6. **§6 Operator state** (NEW): emotional_state_pre_trade multi-select checkboxes; manual_entry_confidence radio (high/normal/low); market_regime radio (Bullish/Caution/Bearish); catalyst select; catalyst_other_description always-visible.
7. **§7 Notes** (existing): notes textarea.

### §11.2 Draft preservation on validation rejection

Server-side re-render with operator's typed values prefilled + field-level error highlights (standard HTMX pattern; matches Phase 6 review form). No localStorage; no temp-DB draft rows. Browser-close mid-form loses draft (acceptable trade-off).

### §11.3 Dashboard "Open Positions" card

Predicate changes: `status='open'` → `state IN ('entered', 'managing', 'partial_exited')`. Single card preserved; per-row state badge added (small muted label `[entered]` / `[managing]` / `[partial]` next to ticker). No structural UX change.

### §11.4 Trade-detail view — V1 read-only pre-trade section

Trade-detail page gains a "Pre-Trade Decision" section above the existing position-management section:

- All new pre-trade fields rendered read-only with a lock icon + `pre_trade_locked_at` timestamp.
- Audit-log read-display: `trade_events` rows with `event_type='pre_trade_edit'` rendered chronologically.
- Legacy NULL handling: trades where `premortem_technical IS NULL` show "(legacy — no pre-trade data)" placeholder OR hide the section entirely; spec-review chooses (operator preference). Recommendation: hide the section entirely for legacy.

**V1 explicitly does NOT ship the edit-after-lock UI.** Schema fully supports edit-after-lock (per §6.4); UI ships in a future phase. Operator-only escape valve in V1: direct DB edit + manual `trade_events` row insertion.

### §11.5 CLAUDE.md gotcha pre-emption (binding for plan-time test design)

| Gotcha | Phase 7 surface | Mitigation |
|---|---|---|
| `... or None` vs `... or ""` for nullable text + CHECK enum | event_handling, event_type, gap_risk_handling, manual_entry_confidence, market_regime, catalyst, trade_origin | Form-input fallback uses `or None`; one discriminating test per column submits empty form input + asserts NULL persisted (not CHECK violation). |
| HX-Redirect target route registration | Phase 7 introduces no NEW HTMX POST routes that emit HX-Redirect (entry/exit/stop_adjust forms reuse existing patterns). If implementation discovers one is needed → plan adds target-route-registration assertion in tests. | Verified at spec time; re-verified at plan time. |
| OOB-swap partial drift | New / modified template partials must use shared `{% include %}` not hand-duplicated markup. | Plan enumerates every modified partial + verifies include-source. |
| Base-layout VM rule | Phase 7 introduces no new field that the base layout dereferences (no new banners, no shared session-context fields). | Verified at spec time; re-verified at plan time. |

---

## §12 In-flight migration plan (VIR / DHC / CC)

### §12.1 Pre-migration safety

Backup: `swing-pre-phase7-migration-<ISO-timestamp>.db` snapshot before migration runs. Project precedent.

### §12.2 State derivation rule (general; covers legacy + future imports)

```sql
state = CASE
  WHEN status='closed' AND reviewed_at IS NOT NULL THEN 'reviewed'
  WHEN status='closed' AND reviewed_at IS NULL     THEN 'closed'
  WHEN EXISTS(SELECT 1 FROM exits WHERE exits.trade_id = trades.id) THEN 'partial_exited'
  ELSE 'managing'
END
```

Rationale for `managing` not `entered`: the entered → managing transition signal isn't reliably preserved in legacy data; conservative default.

### §12.3 Per-trade migration outcomes

| Trade | state | pre_trade_locked_at | trade_origin (best-guess) | new pre-trade fields | Fills backfill |
|---|---|---|---|---|---|
| **VIR** (closed + reviewed mid-Apr 2026) | `reviewed` | `entry_date \|\| 'T16:00:00'` | `manual_off_pipeline` | NULL | 1 entry-fill (synth from trades.entry_*) + 1 exit-fill (synth from VIR's single exits row; action=`exit`) |
| **DHC** (open 2026-04-27, $7.58 × 39) | `managing` | `'2026-04-27T16:00:00'` | `pipeline_watch_hyp_recs` (verify at impl time via trade_events) | NULL | 1 entry-fill |
| **CC** (open 2026-04-30, $26.97 × 5) | `managing` | `'2026-04-30T16:00:00'` | `pipeline_watch_hyp_recs` (verify at impl time via trade_events) | NULL | 1 entry-fill |

**Aggregate denorm post-migration:**

- VIR: `current_size=0`, `current_avg_cost=<entry_price>`, `last_fill_at=<exit fill datetime>`.
- DHC: `current_size=39`, `current_avg_cost=7.58`, `last_fill_at='2026-04-27T16:00:00'`.
- CC: `current_size=5`, `current_avg_cost=26.97`, `last_fill_at='2026-04-30T16:00:00'`.

### §12.4 trade_origin verification at implementation time

Migration UPDATE statements use the best-guess values above. Implementation plan adds an empirical-verification step:

1. Read `trade_events` rows for DHC/CC where `event_type='entry'`.
2. Inspect `payload_json.rationale` and any other surface-routing signal.
3. If empirical evidence contradicts the best-guess, plan adjusts the migration UPDATE statements before commit.

Spec records best-guess values; plan can refine.

### §12.5 Display semantics for legacy NULL pre-trade fields

Trade-detail view: NULL pre-trade fields → "(legacy — no pre-trade data)" placeholder OR section hidden entirely (operator preference at spec-review). Phase 6 review surface continues to function (review path operates on outcome + mistake_tags; VIR's existing review precedent confirms).

---

## §13 Migration sequencing

### §13.1 Single migration 0014 in one transaction

Filename: `swing/data/migrations/0014_phase7_state_machine_and_fills.sql`. Atomicity is critical because Fills backfill depends on existing trades + exits data; multi-step would risk partial-migration state if interrupted, and the in-flight Fills derivations must observe pre-migration schema.

### §13.2 Operation order within 0014

1. `CREATE TABLE fills` (full schema with CHECK enums + NOT NULLs).
2. `INSERT INTO fills` entry-action rows (synthesized from existing `trades.entry_date / entry_price / initial_shares`; `fill_datetime = entry_date || 'T16:00:00'`; `reconciliation_status='unreconciled'`).
3. `INSERT INTO fills` exit/trim/stop-action rows (1:1 from existing `exits` rows per §4.4 mapping).
4. `ALTER TABLE trades ADD COLUMN` for each new column (~21 columns). Initially NULLABLE for backfill.
5. `UPDATE trades SET state = <derived per §12.2>`.
6. `UPDATE trades SET pre_trade_locked_at = entry_date || 'T16:00:00'` for legacy.
7. `UPDATE trades SET trade_origin = <best-guess per §12.3>` for legacy.
8. `UPDATE trades SET current_size = ..., current_avg_cost = ..., last_fill_at = ...` from backfilled fills.
9. `DROP TABLE exits`.
10. **Table-rebuild trades** (CREATE NEW → INSERT FROM OLD → DROP OLD → RENAME): drops `status` column, adds NOT NULL on `state` + `pre_trade_locked_at` + `trade_origin`, adds CHECK enums on new constrained columns.
11. **Table-rebuild trade_events**: expand `event_type` CHECK enum to include `'pre_trade_edit'`.
12. `UPDATE schema_version SET version = 14`.

All within `BEGIN TRANSACTION; ... COMMIT;`.

### §13.3 Rollback strategy

Pre-migration backup + single-transaction atomicity IS the rollback. Project precedent.

- Migration fails mid-execution → ROLLBACK; DB unchanged.
- Migration succeeds + post-deploy bug → restore from `swing-pre-phase7-migration-<ISO>.db`; lose any post-migration writes.
- No down-migration SQL script.

### §13.4 Post-migration schema_version bump

`swing/data/db.py` updates `EXPECTED_SCHEMA_VERSION` constant from 13 to 14. Migration runner verifies version match on every connection open.

---

## §14 Test strategy scope

### §14.1 State-transition matrix (binding enumeration)

25 cells parameterized: 5 allowed-transition acceptance tests + 20 rejected-transition rejection tests. Per orchestrator-context lesson 2026-05-04 (state-bearing-entity all-transition-paths enumeration): all 25 tested explicitly, not implicitly.

### §14.2 Per-state required-fields validation

For each of the 5 states:

- `test_<state>_required_fields_complete_succeeds` — all fields present, transition accepted.
- `test_<state>_missing_<field>_rejects` — parameterized over the per-state required-field tuple; each cell asserts `MissingPreTradeFieldsException` raised with the specific field name in the missing list.

Estimated cells: ~5 complete-set + ~50 missing-field parameterized = ~55 field-validation tests.

### §14.3 Migration safety tests (per §12.4 + §13 invariants)

Pre-migration fixture: 3 trades mirroring VIR/DHC/CC in original Phase 6 schema. Run migration 0014. Assert:

- VIR: `state='reviewed'`, `current_size=0`, 2 fills (entry + exit), `pre_trade_locked_at` set, premortem NULL.
- DHC: `state='managing'`, `current_size=39`, 1 fill (entry-action), `pre_trade_locked_at='2026-04-27T16:00:00'`.
- CC: `state='managing'`, `current_size=5`, 1 fill (entry-action), `pre_trade_locked_at='2026-04-30T16:00:00'`.
- Schema invariants: `exits` table dropped; `status` column dropped; `event_type` CHECK includes `'pre_trade_edit'`; `schema_version=14`.
- Row-count: `COUNT(fills) = COUNT(trades_pre) + COUNT(exits_pre) = 4`.
- Aggregate consistency: per-trade `sum(entry/add quantities) - sum(trim/exit/stop quantities) = current_size`.

### §14.4 Discriminating-test discipline

Per CLAUDE.md feedback memory: every test's post-Phase-7 outcome must differ from pre-Phase-7 outcome. Schema tests trivially satisfy (pre-fix has no `state` column; tests fail by absence). Logic tests inherently satisfy (validators don't exist pre-fix; tests fail by absence-of-implementation).

**Vacuous-test risk:** spec calls out "no `assert True`, no `assert isinstance(state, str)`-class assertions" as plan acceptance criterion. Codex-review flags any vacuous-test category.

### §14.5 Pre-trade gate tests (per §9)

Each gate component blocks separately (one test per failure mode):

- Missing thesis / why_now / invalidation_condition / expected_scenario.
- Missing premortem_technical / premortem_market_sector / premortem_execution.
- Missing emotional_state_pre_trade / manual_entry_confidence / market_regime / catalyst.
- `event_risk_present=1` + missing event_handling → conditional rejection.
- `event_risk_present=1` + missing event_type / event_date → conditional rejection.
- `gap_risk_present=1` + missing gap_risk_handling → conditional rejection.
- `catalyst='other'` + missing catalyst_other_description → conditional rejection.
- Existing checks preserved: stop ≥ entry → ValueError; hard cap → HardCapException; duplicate ticker → DuplicateOpenPositionException; soft-warn forceable.

**Complete-pass tests at all 3 surfaces:**

- CLI `swing trade entry` with all fields → success; trade INSERTed at `entered`; first entry-fill exists.
- Web POST `/trades/entry/form` with all fields → success; same.
- Hyp-recs Take-this-trade button with all fields → success; same.

### §14.6 trade_origin derivation tests (per §10.1 mapping)

Parameterized by `(bucket, entry_path)` → expected `trade_origin`. Cover all 5 bucket × 4 entry_path combinations + ticker-absent + pipeline-not-run-today edge cases. ~15 tests.

### §14.7 Existing test-fixture refactor

Trade fixture builders across `tests/` currently construct Trade dataclasses with the legacy field set. Phase 7 fixture-design choice:

**Recommendation:** update the canonical trade fixture to populate Phase 7 required fields with sensible test defaults (canonical thesis text like `"test thesis"`, canonical premortem reasons, etc.). Existing tests that don't care about Phase 7 fields continue to work. Tests that specifically exercise Phase 7 field validation override defaults.

Refactor scope: ~10 test files containing trade fixture builders + any test that constructs a Trade directly. Plan-time enumeration at writing-plans dispatch.

### §14.8 Test-count discipline (per 2026-05-04 lesson "test-count-projections-bias-high")

**Rough estimate band:** ~150–250 new fast tests post-Phase-7. Wide band because parameterization decisions significantly affect raw count.

**Discipline:**

- Each test must be discriminating.
- Parameterize where the failure mode is uniform across cells.
- Spec doesn't size; plan refines after empirical scope check.
- Surplus over plan estimate is acceptable IF discriminating-test discipline holds; NOT acceptable if vacuous parameterization inflates count.

---

## §15 Phase carve-out file list

Default posture is read-only on `swing/data/` + `swing/trades/`. Phase 7 carve-out per file:

### Schema / data layer

| File | Add/Mod/Del | Justification |
|---|---|---|
| `swing/data/migrations/0014_phase7_state_machine_and_fills.sql` | NEW | Migration itself (§13). |
| `swing/data/models.py` | MOD | Add ~21 fields to `Trade`; add new `Fill` dataclass; remove `Exit` dataclass. |
| `swing/data/db.py` | MOD | Bump `EXPECTED_SCHEMA_VERSION` 13 → 14. |

### Repo layer

| File | Add/Mod/Del | Justification |
|---|---|---|
| `swing/data/repos/trades.py` | MOD | State-aware queries (`status` predicates → `state IN (...)`); exits-table reads (lines 108, 117, 248, 276, 292) migrate to fills-repo helpers; new column read/write paths. |
| `swing/data/repos/fills.py` | NEW | CRUD for `fills`; aggregate-recompute helper. |

**Note:** `swing/data/repos/exits.py` does NOT exist (verified at spec-write 2026-05-04). All exits-table SQL access lives inline in `repos/trades.py` and `journal/tos_import.py`; those are MOD targets per the carve-out. No file deletion.

### Service layer

| File | Add/Mod/Del | Justification |
|---|---|---|
| `swing/trades/state.py` | NEW | State-machine service (transition map, required-fields-by-state map, single write path, write-time validator). |
| `swing/trades/entry.py` | MOD | EntryRequest gains new pre-trade fields; `record_entry()` validates, derives `trade_origin`, inserts trade + first entry-fill atomically, sets `pre_trade_locked_at`. New `MissingPreTradeFieldsException`. Removes `status="open"` write (line 197) — entry service writes `state="entered"`. |
| `swing/trades/exit.py` | MOD | `record_exit()` emits trim/exit-action fill; transitions state via `state.py`; recomputes aggregates. |
| `swing/trades/stop_adjust.py` | MOD | State predicate (fires only in `entered`/`managing`/`partial_exited`); first stop_adjust on `entered` triggers `entered → managing`. |
| `swing/trades/review.py` | MOD | Phase 6 review precondition (line 214 `trade.status != "closed"`) → `trade.state not in ("closed","reviewed")`. Review marks state transition `closed → reviewed` via `state.py`. |
| `swing/trades/origin.py` | NEW | `derive_trade_origin()` + `EntryPath` enum (§10). |
| `swing/trades/derived_metrics.py` | NEW | Pure functions for `realized_pnl` + `r_multiple` previously stored on `exits`; consumers migrate from exits-row-fields to these helpers. |

### Web layer

| File | Add/Mod/Del | Justification |
|---|---|---|
| `swing/web/routes/trades.py` | MOD | Entry form route adds new fields; trade-detail route renders pre-trade section + audit log; state-aware filtering predicates (lines 844, 1082, 1198 status checks). |
| `swing/web/view_models/trades.py` | MOD | TradeVM gains state + new pre-trade fields; Open-Positions card VM gains state badge; status predicates (lines 331, 385, 432) become state predicates. |
| `swing/web/view_models/open_positions_row.py` | MOD | Open-positions row VM filter (line 181) status → state predicate; row gains state badge field. |
| `swing/web/templates/trades/entry_form.html.j2` | MOD | 7 sectioned `<fieldset>` blocks (§11.1). |
| `swing/web/templates/trades/detail.html.j2` | MOD | "Pre-Trade Decision" section + lock indicator + audit-log read-display (V1 read-only per §11.4). |
| `swing/web/templates/journal.html.j2` | MOD | Template renders `{{ t.status }}` (line 34) → `{{ t.state }}` or per-state badge. |
| `swing/web/templates/partials/<open_positions partial>` | MOD | State badge per row. |

### CLI layer

| File | Add/Mod/Del | Justification |
|---|---|---|
| `swing/cli.py` | MOD | `swing trade entry` gains all new pre-trade options (or interactive prompt); `swing trade exit` + `stop-adjust` route through state-aware service; CLI display + filter sites (lines 588, 1008) status → state predicates. |

### Journal layer (carve-out additions; default is read-only on `swing/journal/`)

| File | Add/Mod/Del | Justification |
|---|---|---|
| `swing/journal/stats.py` | MOD | Closed-trade filter predicates (lines 47, 96, 179) status → state predicates. |
| `swing/journal/flags.py` | MOD | Closed-trade filter predicates (lines 39, 59, 93) status → state predicates. |
| `swing/journal/analyze.py` | MOD | Analyze output (line 242) passes state instead of status. |
| `swing/journal/tos_import.py` | MOD | SQL queries (lines 287, 318) `WHERE t.status='closed'` → state predicate; exits-table SELECT (lines 257, 316) migrates to fills-repo helpers. |

### Test layer

| File | Add/Mod/Del | Justification |
|---|---|---|
| `tests/data/test_migration_0014.py` | NEW | Migration 0014 forward test (§14.3). |
| `tests/data/test_fills_repo.py` | NEW | CRUD + aggregate recompute. |
| `tests/trades/test_state.py` | NEW | State-machine: 25-cell transition matrix + per-state required-fields validation (§14.1, §14.2). |
| `tests/trades/test_entry.py` | MOD | New required-field validation; `trade_origin` derivation; first-entry-fill creation; `pre_trade_locked_at` correctness. |
| `tests/trades/test_exit.py` | MOD | Fill emission; partial vs full exit state branching. |
| `tests/trades/test_stop_adjust.py` | MOD | State predicate; `entered → managing` trigger. |
| `tests/trades/test_origin.py` | NEW | `derive_trade_origin()` per-cell (§14.6). |
| `tests/web/test_routes_trades.py` | MOD | Form-validation rejection; pre-trade-detail render; state badge render. |
| `tests/web/test_view_models_trades.py` | MOD | State + pre-trade VM fields. |
| `tests/cli/test_trade_cli.py` | MOD | New CLI options + interactive prompts. |
| `tests/journal/test_*.py` | MOD | Replace `status='closed'` predicates with `state IN ('closed','reviewed')`. **Plan enumerates every status-using test at writing-plans dispatch.** |

### Documentation

| File | Add/Mod/Del | Justification |
|---|---|---|
| `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md` | NEW | This spec. |

`CLAUDE.md` and `docs/phase3e-todo.md` updates are out of scope for this brainstorm dispatch (those happen at Phase 7 ship-time, not during design).

**Total surface:** ~37 files (Phase 6 was ~25; Phase 7 is materially larger because of the cross-cutting status→state rewrite + Fills introduction).

**Out of carve-out (preserve read-only):** `swing/pipeline/`, `swing/recommendations/`, `swing/evaluation/`, `swing/web/middleware/`, `swing/web/routes/` other than `trades.py`, `swing/web/templates/` other than the 3 listed, `swing/data/repos/` other than `trades.py` + new `fills.py`. **The 4 carved-out journal files (stats.py, flags.py, analyze.py, tos_import.py) are read-side modifications only — predicate rewrites + repo-helper migration, no schema-shape work in `swing/journal/`.**

---

## §16 Out of scope (explicit)

- **Daily_Management snapshot/event_log generation** — Phase 8.
- **MFE/MAE precision computation** — Phase 8.
- **Risk_Policy DB entity** — Phase 9.
- **Reconciliation_Run / Reconciliation_Discrepancy entities** — Phase 9.
- **Drawdown circuit breaker enforcement** — Phase 9 (schema accommodates per `reconciliation_status` field on fills).
- **Edit-after-lock UI** — V2 Phase 7 follow-up (schema fully supports; UI deferred per §6.5 / §11.4).
- **Production scoring / bucketing changes** — V2.1 §VII.F territory; out of Phase 7.
- **New advisory rules** — separate Tier-3 #6 backlog item.
- **Schwab API / Finviz Elite API integrations** — separate 2026-05-04 backlog entries.
- **HTMX progressive disclosure for conditional fields** (event_*, catalyst_other_description) — V2.

---

## §17 Anti-stuck handling: conflict-pause protocol

If implementation reveals a hard conflict between any locked constraint (§2) and what Phase 7 actually needs:

1. **STOP.** Do not relitigate the locked constraint within the implementation dispatch.
2. Author an interim outbrief describing:
   - The specific locked constraint in conflict.
   - The Phase 7 design surface that conflicts with it.
   - 2–3 design alternatives that resolve the conflict.
   - The cost of each alternative.
3. Surface to operator for orchestrator escalation.
4. Stand by for path-forward brief.
5. Resume implementation only after the orchestrator-level decision lands.

This protocol is binding. Operator established it during cluster A of the Phase 7 brainstorm (2026-05-04).

Documented as a discipline pattern; future phases may adopt the same protocol explicitly.

---

## §18 Open / deferred decisions (operator-confirm at spec-review)

These items have a recommended value but require operator final confirmation:

- **Catalyst enum vocabulary (§8.1):** 9-value trim from v1.2 §4.6's 13 values. Confirm the 9 values cover operator's actual workflow.
- **Emotional state vocabulary (§8.1):** 8-value sketch (calm, confident, anxious, fomo, revenge, hopeful, doubtful, distracted). Confirm coverage.
- **Event type vocabulary (§8.1):** 7-value sketch (earnings, fed_meeting, cpi_release, economic_data, product_announcement, legal_ruling, other). Confirm coverage.
- **Legacy trade-detail display:** show "(legacy — no pre-trade data)" placeholder, OR hide the section entirely. Recommendation: hide entirely.
- **DHC + CC trade_origin verification (§12.4):** best-guess `pipeline_watch_hyp_recs`. Empirical verification at writing-plans dispatch may adjust.

If any of these lands a decision that materially affects schema or service-layer scope, the change re-enters the spec before the writing-plans dispatch.

---

## §19 Estimated implementation dispatches

**4–6 dispatches** downstream of this spec:

1. **Writing-plans dispatch:** authors implementation plan with adversarial Codex review to NO_NEW_CRITICAL_MAJOR. Resolves §18 deferred items. Enumerates every status-using call site + every exits-repo caller. Plan-time empirical verification of DHC/CC trade_origin.
2. **Executing-plans dispatch (likely 2–3 sub-dispatches):**
   - Sub-dispatch A: Migration 0014 + Fills repo + state-machine service. Self-contained schema + foundational service layer.
   - Sub-dispatch B: Entry / exit / stop_adjust service refactor + CLI surface. Wires state machine into write paths.
   - Sub-dispatch C: Web routes + view models + templates. Operator-facing UX.
3. **Verification-before-completion dispatch:** end-to-end walkthrough on the 3 in-flight trades + new fresh trades; operator-witnessed browser verification per HTMX gotcha discipline.

Worktree isolation per writing-plans + executing-plans dispatches (per 2026-05-04 lesson `no-main-commits-during-in-flight-dispatch discipline`). Spec authoring happens on `main` because brainstorm is design-only.

---

*End of spec.*
