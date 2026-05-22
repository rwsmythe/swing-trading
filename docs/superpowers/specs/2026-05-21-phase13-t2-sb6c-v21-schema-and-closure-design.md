# Phase 13 T2.SB6c — v21 schema + SB6 closure design (brainstorming)

**Status:** DRAFT for orchestrator-paired triage + Codex MCP adversarial review. Drafted 2026-05-21 PM #5 against dispatch brief `docs/phase13-t2-sb6c-v21-closure-brainstorm-dispatch-brief.md` + Phase 13 spec `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` + Phase 13 plan `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` + T2.SB6b return report `docs/phase13-t2-sb6b-return-report.md` + worktree HEAD `5ca64c3` (post-T2.SB6b housekeeping + this brief commit).

**Critical brief-vs-actual finding (Expansion #2):** dispatch brief §2.3 proposes `watchlist_close_track_flags` + `watchlist_close_track_flag_events` as a v21 schema delta. **Both tables ALREADY EXIST in v20** — landed at T-A.1.1 atomic migration per `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:263-307` and locked by Phase 13 spec §7.2 line 986 ("Q4 schema FOLDS INTO v20"). The brief's §2.3 proposal is therefore **OBSOLETE**. v21 schema scope reduces from 3 deltas to **2 deltas** (only the 2 trades backlinks). The Q4 surface wiring is owned by T4.SB per Phase 13 plan §G.10 — this brainstorming spec respects that scope boundary.

---

## §1 Status + scope summary

### §1.1 v21 schema delta scope (REVISED — 2 deltas, not 3)

- **Delta A**: `trades.candidate_id INTEGER NULL` + FK + index. Required by spec §5.10 lines 785-790 (label_source split closes T2.SB6b R1 MAJOR #3 V1 simplification).
- **Delta B**: `trades.pattern_evaluation_id INTEGER NULL` + FK + index. Forward-binding for direct trade → detector evaluation linkage; enables single-JOIN cohort analysis per pattern_class.
- **Delta C (brief §2.3) — OBSOLETE**: `watchlist_close_track_flags` already exists in v20. No v21 schema work for Q4. T4.SB inherits the existing schema.

v20 LOCKED streak ends with v21 landing. v20 carried 10 sub-bundles since T-A.1.1 (T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 + T2.SB5 + T3.SB3 + T2.SB6a + T2.SB6b).

### §1.2 SB6 closure wiring scope

10 closure items from T2.SB6b return report §6 (V1 simplifications + V2 dependencies). Grouped by schema dependency:

**Gap A — chart-surface wiring (NO schema dependency; 4 items):**
- A.1 Hyp-rec detail VM 800x500 SVG (consume `chart_renders` cache via existing substrate `get_cached_chart_svg`).
- A.2 Position detail VM 800x500 SVG with fill markers (consume cache; `pipeline_run_id=None` per §3.2 cache key shape).
- A.3 WatchlistVM template renders thumbnail (extend `partials/watchlist_row.html.j2` to consume existing `watchlist_chart_svg_bytes` field already populated on WatchlistVM at T2.SB6b R1 MAJOR #5 partial fix at `94e4418`).
- A.4 Exemplar cache-miss live-render write-through (extend `swing/web/view_models/patterns/exemplars.py` cache-miss path to call `refresh_chart_render` after live render).

**Gap B — review-form / queue / metric-tile data-completeness:**

| Item | Schema dep | Spec source |
|---|---|---|
| B.1 Trend-template state live (currently `"n/a"`) | NO | spec §5.10 line 771 |
| B.2 Volume profile live (currently `"(not available)"`) | NO | spec §5.10 line 773 |
| B.3 POST `/patterns/{candidate_id}/review` label_source split (closed_loop_review vs organic_trade_history) | YES — Delta A | spec §5.10 lines 785-790 |
| B.4 Review form outcome distribution bucketing (reached_1r_pct + hit_stop_pct) | YES — Delta A | spec §5.10 line 775 |
| B.5 Metric tile reached_1r + hit_stop | YES — Delta A | spec §5.10 line 775 + plan §G.9 T-A.6.5 |
| B.6 Queue criterion 3 weather-state-aware underrepresented_regime | NO (consumes existing `weather_runs` read) | spec §5.10 line 799 |

### §1.3 Non-scope (explicit)

- **Q4 close-tracking flag surfaces** (web `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag` + CLI `swing watchlist flag` + `swing watchlist unflag` + watchlist UI badge + auto-clear-on-position-open). Plan §G.10 owns these at T4.SB. The schema substrate is already in v20; T4.SB consumes it. SB6c does NOT take them per OQ-2 recommendation.
- **Phase 13.5 drift surfaces** (≥1 month operating data required; per spec §5.11).
- **ZERO new Schwab API calls** — L2 LOCK preserved.
- **Interactive client-side JS chart library** (V2; spec §4.7).
- **Operator-supplied T4.SB usability triage items** — separate operator action; `project_phase13_t4_sb_pause_for_list_additions` BINDING memory.

---

## §2 v21 schema delta detailed design

### §2.1 Delta A — `trades.candidate_id` backlink

**Column shape**:

```sql
ALTER TABLE trades ADD COLUMN candidate_id INTEGER
    REFERENCES candidates(id) ON DELETE SET NULL;
```

- **Type**: `INTEGER` (matches `candidates.id PRIMARY KEY AUTOINCREMENT` per migration 0001 line 24-25).
- **NULL/NOT-NULL**: **NULLable**. Two reasons: (a) pre-v21 existing `trades` rows have no candidate row guaranteed in the same pipeline run (manual entries; legacy pipeline entries pre-Phase-13); (b) `trade_origin='manual_off_pipeline'` is a first-class V1 origin (per Phase 7 `trade_origin` enum at migration 0014 line 161-162) that legitimately has no candidate_id.
- **DEFAULT**: none (NULL is the default for new ALTER TABLE ADD COLUMN nullable columns per SQLite semantics).
- **CHECK**: none at column level. Cross-row semantic linkage (when populated, must match a real candidates.id) enforced by FK.
- **FK**: `REFERENCES candidates(id) ON DELETE SET NULL`. Rationale: `candidates` rows rotate per pipeline run lifecycle; FK is advisory rather than load-bearing. ON DELETE SET NULL preserves the trade row when its candidate row decays (cascade weekly cleanup precedent). FK constraint is honored when `PRAGMA foreign_keys = ON`.
- **Index**: `CREATE INDEX idx_trades_candidate_id ON trades(candidate_id);` — supports the LEFT JOIN from `pattern_evaluations` (via `candidates.id`) into trades for outcome bucketing (spec §5.10 line 775).

**Backfill semantics**: NULL for all pre-v21 existing rows. **No heuristic ticker+date match** (OQ-1 disposition recommendation = NULL only). Reasons:
- Pre-Phase-13 candidates may not exist for the same pipeline_run_id (entries from before chart_pattern_classification_pipeline_run_id column landed at migration 0010).
- A heuristic match (e.g., "find candidate with same ticker within +/- 3 days of entry_date") risks attributing a trade to the wrong candidate when multiple candidates rotate through the watchlist over time.
- The cumulative gotcha "Schwab API source-artifact reference shape locked" precedent — opaque references can stay NULL pending future enrichment; populate-with-best-guess introduces silent corruption.

**Lifecycle population (NEW OQ-11; brainstorm recommendation)**: at trade-entry-form lock time inside the `with conn:` block where `trades` INSERT happens, populate `candidate_id` IF:
1. `trade_origin IN ('pipeline_aplus', 'pipeline_watch_hyp_recs', 'pipeline_watch_manual')` — entries from the pipeline have a known candidate row.
2. **CRITICAL CORRECTION per Codex R1**: `candidates` table is keyed on `evaluation_run_id` (per migration 0001 line 26 + `swing/trades/origin.py:10-11` BINDING text "candidates.evaluation_run_id (NOT pipeline_run_id) is the join key"), NOT `pipeline_run_id`. The trade's pipeline-run context resolves to candidates via two-table join: `SELECT c.id FROM candidates c INNER JOIN pipeline_runs pr ON c.evaluation_run_id = pr.evaluation_run_id WHERE pr.id = ? AND c.ticker = ? ORDER BY c.id DESC LIMIT 1`. The `pipeline_runs.evaluation_run_id` column was added at migration 0006 specifically to support this resolver pattern.

If `trade_origin = 'manual_off_pipeline'` OR the candidate lookup returns no row, leave `candidate_id = NULL`. NEW trades from pipeline origins SHOULD populate going forward; existing trades remain NULL (no retroactive lookup).

**Paired Python constant**: none — `candidate_id` is a plain nullable INTEGER FK; no enum or Literal.

**Paired dataclass validator (§A.14 paired discipline)**: extend `swing/data/models.py:Trade` dataclass with:

```python
candidate_id: int | None = None
```

No `__post_init__` check needed (plain Optional[int] is sufficient; FK enforces existence at write time).

**Paired read-path mapper extension (T3.SB3 R1 M#1 lesson)**: extend `swing/data/repos/trades.py:_row_to_trade`:

```python
# Index map comment block extended:
#   52:candidate_id (Phase 13 / migration 0021)
candidate_id=row[52],
```

`_TRADE_SELECT_COLS` at `swing/data/repos/trades.py:47` MUST be extended to include `candidate_id` in the SELECT list at column position 52 (after `planned_target_R` at position 51).

**Paired write-path INSERT extension (REVISED per Codex R1 MAJOR #2)**: the existing `INSERT INTO trades` at `swing/data/repos/trades.py:120` MUST be extended with `candidate_id` in the column list + `?` placeholder. **Schema-version-aware INSERT pattern (T3.SB1 `swing/data/repos/fills.py:51-53` precedent) ADOPTED for robustness** even though the column is NULLable. Rationale per Codex finding: NULLable column DEFAULTS do not help when SQL references columns that do not exist on a v20 fixture (i.e., a test that plants a `trades` row via `insert_trade_with_event` against a connection migrated only to v20). Runtime branch via `PRAGMA table_info('trades')` returns the column list; if `candidate_id` present, use extended INSERT; if absent, use legacy column list. Decision rule: implementer at T-A.6c.1 surveys all `insert_trade_with_event` callsites in test fixtures + IF any fixture plants trades against a v20-only connection (i.e., bypasses v21 migration), the runtime branch is REQUIRED; if all test connections run the full migration sweep through v21, the runtime branch is defensive but not load-bearing. Default to ADOPT the runtime branch to mirror T3.SB1 precedent + provide forward-binding safety for future v22+ migrations.

Discriminating test: `test_insert_trade_with_event_runtime_branches_on_table_info_candidate_id_column_presence` — plants a v20-only connection (migrate to v20, NOT v21); inserts via `insert_trade_with_event` (no `candidate_id` kwarg); asserts INSERT succeeds + reads back via `_row_to_trade` (post-v21-migrate that same connection); asserts `Trade.candidate_id is None`.

**Paired discriminating tests** (land in SAME task as schema migration per §A.14):

1. `test_v21_migration_adds_candidate_id_column_at_position_52` — runs migration; asserts `PRAGMA table_info('trades')` returns `candidate_id` at column 52 with type `INTEGER` and nullable.
2. `test_v21_migration_adds_fk_to_candidates_id_on_delete_set_null` — asserts FK exists via `PRAGMA foreign_key_list('trades')`.
3. `test_v21_migration_creates_idx_trades_candidate_id` — asserts `idx_trades_candidate_id` exists via `sqlite_master`.
4. `test_v21_migration_backfills_existing_trades_with_null_candidate_id` — plants 3 pre-v21 trade rows; runs migration; asserts all 3 rows have `candidate_id IS NULL` post-migration.
5. `test_row_to_trade_populates_candidate_id_from_row_52` — plants a v21 trade row with `candidate_id=42`; reads via `_row_to_trade`; asserts `Trade.candidate_id == 42`.
6. `test_row_to_trade_populates_candidate_id_None_when_null_column` — plants a v21 trade row with `candidate_id=NULL`; asserts `Trade.candidate_id is None`.
7. `test_insert_trade_with_candidate_id_persists_via_schema_aware_path` — INSERTs a trade with `candidate_id=42`; reads back via `_row_to_trade`; asserts roundtrip equality (NULL + non-NULL).
8. `test_fk_cascade_on_candidates_delete_sets_trade_candidate_id_null` — INSERTs a candidate + a trade pointing at it; DELETEs the candidate; asserts trade's `candidate_id` is now NULL.

### §2.2 Delta B — `trades.pattern_evaluation_id` backlink

**Column shape**:

```sql
ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER
    REFERENCES pattern_evaluations(id) ON DELETE SET NULL;
```

- **Type**: `INTEGER` (matches `pattern_evaluations.id PRIMARY KEY AUTOINCREMENT` per v20 migration line 231).
- **NULL/NOT-NULL**: **NULLable**. Pre-v21 existing rows have no `pattern_evaluations` row possible (pattern_evaluations is a Phase 13 table; manual_off_pipeline trades will never have one).
- **DEFAULT**: none.
- **CHECK**: none.
- **FK**: `REFERENCES pattern_evaluations(id) ON DELETE SET NULL` — pattern_evaluations rotates per pipeline run via FK to `pipeline_runs.id CASCADE` (v20 line 233); the trade backlink must survive the cascade.
- **Index**: `CREATE INDEX idx_trades_pattern_evaluation_id ON trades(pattern_evaluation_id);` — supports per-pattern_class cohort joins (spec §5.10 line 775 outcome bucketing per pattern class).

**Backfill semantics**: NULL for all pre-v21 existing rows. Same reasoning as §2.1.

**Lifecycle population (NEW OQ-12; brainstorm recommendation, REVISED per Codex R1 MAJOR #1)**: at trade-entry-form lock time, populate `pattern_evaluation_id` IF:
1. The trade has a populated `candidate_id` (from §2.1 logic).
2. AND a `pattern_evaluations` row exists for `(pipeline_run_id, ticker)` at lock time.
3. **REVISED**: pick the HIGHEST-`composite_score` evaluation across all pattern classes for the `(pipeline_run_id, ticker)` tuple — DO NOT key the lookup on `Trade.chart_pattern_algo` / `chart_pattern_operator`. The Phase 6 `chart_pattern_algo` enum is `'none'|'flag'` per migration 0010 lines 11-36 — NOT a Phase 13 detector class. The Phase 13 `pattern_evaluations.pattern_class` enum is one of 5 detector classes (`vcp`, `flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`) per v20 migration 0020 lines 235-238 — disjoint from Phase 6 enum. Lookup query: `SELECT id FROM pattern_evaluations WHERE pipeline_run_id = ? AND ticker = ? ORDER BY composite_score DESC LIMIT 1`.

If `candidate_id IS NULL` OR no pattern_evaluations row exists, leave `pattern_evaluation_id = NULL`.

**Forward-binding**: the `chart_pattern_algo` Phase 6 enum is independent from the Phase 13 detector enum; a V2 enhancement could unify them via a separate spec dispatch (banked).

**Paired dataclass validator**: extend `Trade` dataclass with:

```python
pattern_evaluation_id: int | None = None
```

**Paired read-path mapper extension**:

```python
# Index map comment block extended:
#   53:pattern_evaluation_id (Phase 13 / migration 0021)
pattern_evaluation_id=row[53],
```

`_TRADE_SELECT_COLS` extended with `pattern_evaluation_id` at column position 53.

**Paired write-path INSERT extension**: same shape as §2.1 (nullable extension; no schema-version-aware INSERT needed for NULLable columns).

**Paired discriminating tests** (mirror §2.1 shape; land in SAME task):

1. `test_v21_migration_adds_pattern_evaluation_id_column_at_position_53` — asserts column 53.
2. `test_v21_migration_adds_fk_to_pattern_evaluations_id_on_delete_set_null` — asserts FK.
3. `test_v21_migration_creates_idx_trades_pattern_evaluation_id` — asserts index.
4. `test_v21_migration_backfills_existing_trades_with_null_pattern_evaluation_id` — asserts NULL backfill.
5. `test_row_to_trade_populates_pattern_evaluation_id_from_row_53` — plants v21 row; asserts mapper extraction.
6. `test_row_to_trade_populates_pattern_evaluation_id_None_when_null_column` — asserts NULL handling.
7. `test_insert_trade_with_pattern_evaluation_id_persists` — round-trip equality.
8. `test_fk_cascade_on_pattern_evaluations_delete_sets_trade_pattern_evaluation_id_null` — FK cascade verification.
9. `test_pattern_evaluations_direct_delete_sets_trade_pattern_evaluation_id_null` (REVISED per Codex R1 MAJOR #4) — test DIRECT `pattern_evaluations` row deletion → assert `trades.pattern_evaluation_id` becomes NULL on the dependent trade. **Chained cascade through `pipeline_runs` deletion is NOT tested** because the existing `trades.chart_pattern_classification_pipeline_run_id REFERENCES pipeline_runs(id)` FK (migration 0010 lines 23-36) has default `NO ACTION` semantics — deleting a `pipeline_runs` row with a referencing trade row would FAIL the FK constraint before reaching the v21 `pattern_evaluation_id` cascade. The trade-to-pipeline_runs FK pre-exists; SB6c's v21 cascades are additive but the chained-cascade scenario is blocked by the pre-existing FK. Direct `pattern_evaluations` row deletion is the canonical cascade test path.

### §2.3 Delta C — OBSOLETE (already in v20)

Brief §2.3 proposed `watchlist_close_track_flags` as a v21 delta. **The table already exists in v20** per `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:263-307`. The v20 column shape, partial UNIQUE index, audit table, and CHECK constraints match the spec §7.2 D-Q4.1 + D-Q4.7 locks verbatim. **No v21 schema work for Q4.**

Brief OQs OQ-4 (cleared_by_reason enum scope) and OQ-5 (partial UNIQUE index semantics) are therefore moot at this dispatch — both already locked in v20 via Codex R1 M#9 closure:
- v20 `cleared_reason` enum: `('operator_cleared', 'auto_cleared_on_position_open')` (note: brief OQ-4 wording `'operator_explicit'`/`'position_opened'` is incorrect; the v20 ship uses `'operator_cleared'`/`'auto_cleared_on_position_open'`).
- v20 partial UNIQUE: `WHERE cleared_at IS NULL` (active-only; re-flagging cleared ticker inserts new row).

### §2.4 Migration file shape

**New migration**: `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`

**Atomic landing per CLAUDE.md gotcha "executescript() implicit COMMIT"**: explicit `BEGIN;` ... `COMMIT;` wrap with all 6 DDL statements + 1 schema_version update.

**Backup-gate per CLAUDE.md gotcha "Migration runner backup-gate equality form" + Codex R1 MAJOR #3 (REVISED with full implementation scope)**: the backup gate is wired in `swing/data/db.py:run_migrations`, NOT in `_apply_migration` per se. T-A.6c.1 atomic landing MUST:

1. **Bump `EXPECTED_SCHEMA_VERSION = 21`** in `swing/data/db.py:39` (currently 20).
2. **Add `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES`** constant: `PHASE13_PRE_MIGRATION_EXPECTED_TABLES | {"pattern_exemplars", "chart_renders", "pattern_evaluations", "watchlist_close_track_flags", "watchlist_close_track_flag_events"}` (the 5 v20-shipped tables; per `swing/data/db.py:108-111` PHASE13 set derivation pattern). Derived deterministically from PHASE13 set per the existing precedent.
3. **Add `_phase13_sb6c_backup_gate(...)` function** mirroring `_phase13_backup_gate` (existing) with strict equality: `if pre_version == 20 AND EXPECTED_SCHEMA_VERSION >= 21`.
4. **Add `_create_pre_phase13_sb6c_migration_backup(...)` function** mirroring existing pattern with filename `swing-pre-phase13-sb6c-migration-<ISO>.db` (OQ-8 disposition).
5. **Wire into `run_migrations`** call chain BEFORE the v21 migration applies, per the existing chain pattern at `_phase7_backup_gate` / `_phase8_backup_gate` / etc.

**Backup file name** (OQ-8 disposition): `swing-pre-phase13-sb6c-migration-<ISO>.db` (NOT `swing-pre-v21-migration-...`) per Phase 13 precedent. The phase-prefix convention aligns with `swing-pre-phase13-migration-<ISO>.db` (T-A.1.1 v20 backup file).

**Migration runner discipline** (per `swing/data/db.py:_apply_migration` canonical implementation): explicit `BEGIN` / `executescript` / `COMMIT` with try/except `rollback()` + re-raise. The pre-Phase-13 `executescript()` implicit-COMMIT footgun is closed by the canonical runner; v21 inherits.

**Backup-gate discriminating tests** (added to T-A.6c.1 acceptance):
- `test_run_migrations_v20_to_v21_creates_backup_with_correct_filename` — assert backup file with `swing-pre-phase13-sb6c-migration-` prefix is written + integrity-verified before v21 applies.
- `test_run_migrations_v20_to_v21_strict_equality_pre_version_predicate` — assert gate fires when `pre_version == 20`; does NOT fire when `pre_version == 19` (i.e., multi-version jump from v19 to v21 directly would FAIL because of strict-equality discipline; multi-version jump must run v19→v20 separately first).
- `test_expected_schema_version_constant_is_21_post_sb6c` — asserts constant bump.

**Migration body (skeleton)**:

```sql
-- 0021_phase13_t2_sb6c_trades_backlinks.sql
-- Phase 13 T2.SB6c — v21 migration: trades backlinks to candidates +
-- pattern_evaluations (closes T2.SB6b V1 simplifications #4 + #5 +
-- enables outcome bucketing per spec §5.10 lines 785-790 + line 775).
--
-- Atomic via explicit BEGIN ... COMMIT per CLAUDE.md gotcha
-- "executescript() implicit COMMIT" + migration 0020 precedent.
--
-- Schema deltas (declared order):
--   1. ALTER TABLE trades ADD COLUMN candidate_id INTEGER
--      REFERENCES candidates(id) ON DELETE SET NULL.
--   2. ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER
--      REFERENCES pattern_evaluations(id) ON DELETE SET NULL.
--   3. CREATE INDEX idx_trades_candidate_id ON trades(candidate_id).
--   4. CREATE INDEX idx_trades_pattern_evaluation_id
--      ON trades(pattern_evaluation_id).
--   5. UPDATE schema_version SET version = 21.
--
-- Bumps schema_version 20 -> 21.

BEGIN;

ALTER TABLE trades ADD COLUMN candidate_id INTEGER
    REFERENCES candidates(id) ON DELETE SET NULL;

ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER
    REFERENCES pattern_evaluations(id) ON DELETE SET NULL;

CREATE INDEX idx_trades_candidate_id ON trades(candidate_id);

CREATE INDEX idx_trades_pattern_evaluation_id
    ON trades(pattern_evaluation_id);

UPDATE schema_version SET version = 21;

COMMIT;
```

**SQLite ALTER TABLE ADD COLUMN constraint** (binding watch item): SQLite `ALTER TABLE ADD COLUMN` permits `REFERENCES` clause for newly-added columns (per SQLite docs §"Adding A New Column"). The FK is parsed but is NOT enforced retroactively against existing rows (NULL backfill satisfies any FK trivially). Discriminating test #2 above asserts FK parsing succeeds via `PRAGMA foreign_key_list('trades')`.

---

## §3 SB6 closure consumer mapping

Per-item disposition with LIVE / RESOLVED-via-Delta / V2-NEW. V2-NEW should be the exception, not the rule, per dispatch brief §1 closure intent.

| Item | Spec source | Schema dep | Wiring | Disposition |
|---|---|---|---|---|
| **Gap A.1** Hyp-rec detail VM 800x500 SVG | §4.2 / §C.1 line 396 (spec map: §4.2 chart surface inventory row 2) | NO | `swing/web/view_models/recommendations.py:RecommendationsVM` extend with `hyprec_detail_chart_svg_bytes: bytes | None`; route handler at `swing/web/routes/recommendations.py` populates via `get_cached_chart_svg(conn, ticker, surface='hyprec_detail', pipeline_run_id=<run_id>)`; template at `swing/web/templates/recommendations/detail.html.j2` renders inline `<svg>`. | LIVE (no schema dep) |
| **Gap A.2** Position detail VM 800x500 SVG with fill markers | §4.2 chart surface inventory row 3 | NO | `swing/web/view_models/trades.py:TradeDetailVM` extend with `position_chart_svg_bytes: bytes | None`; route handler populates via `get_cached_chart_svg(conn, ticker, surface='position_detail', pipeline_run_id=None)` per v20 §3.2 cache key shape (position_detail is run-agnostic); template renders inline. | LIVE (no schema dep) |
| **Gap A.3** WatchlistVM template thumbnail | §4.2 row 1 | NO | `swing/web/templates/partials/watchlist_row.html.j2` extend to render `vm.watchlist_chart_svg_bytes` (already populated on WatchlistVM at T2.SB6b R1 MAJOR #5 partial fix `94e4418`). | LIVE (no schema dep) |
| **Gap A.4** Exemplar cache-miss write-through | spec §4.4 cache architecture + plan T-A.6.6b §G.9 line 2240 | NO | `swing/web/view_models/patterns/exemplars.py` cache-miss path: after `render_theme2_annotated_svg` returns bytes, call `refresh_chart_render(conn, ChartRender(...))` per v20 §3.2 substrate write-through. | LIVE (no schema dep) |
| **Gap B.1** Trend-template state live | §5.10 line 771 | NO | `swing/web/view_models/patterns/review_form.py:PatternReviewFormVM` extend with `trend_template_state: str` field. Read via `current_stage()` (Phase 8 weather module) using `swing.data.repos.weather.get_latest(conn, ticker)` to honor backward-looking session anchor (CLAUDE.md gotcha "Session-anchor read/write mismatch"). | LIVE (no schema dep) |
| **Gap B.2** Volume profile live | §5.10 line 773 | NO | `PatternReviewFormVM` extend with `volume_profile: VolumeProfileRow` (NEW frozen dataclass: `recent_30session_volume_sum: int`, `prior_50day_avg_volume: float`, `ratio_pct: float`). Read OHLCV via `swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)` (50 + 30 buffer). Template renders inline sparkline (ASCII bars per CLAUDE.md gotcha "ASCII-only on runtime CLI paths"; SVG sparkline acceptable since SVG bytes don't flow through stdout). | LIVE (no schema dep) |
| **Gap B.3** POST `/patterns/{candidate_id}/review` label_source split (URL parameter named `candidate_id` per shipped code; value is a `pattern_evaluations.id`) | §5.10 lines 785-790 | YES — Delta A | POST handler at `swing/web/routes/patterns.py:patterns_review_post` (T2.SB6b T-A.6.3) extends: after constructing the `PatternExemplar(label_source=..., ...)` row, resolve the canonical `candidates.id` via `SELECT c.id FROM candidates c INNER JOIN pipeline_runs pr ON c.evaluation_run_id = pr.evaluation_run_id WHERE pr.id = ? AND c.ticker = ?` (where `?` is the `pattern_evaluations.pipeline_run_id` from the URL-path-resolved evaluation row; per Codex R1 CRITICAL #1 — `candidates` keyed on `evaluation_run_id` NOT `pipeline_run_id`). Then look up trade via `SELECT 1 FROM trades WHERE candidate_id = ? AND state IN ('entered','managing','partial_exited','closed','reviewed') LIMIT 1`. If row exists AND operator decision is `confirm`, emit `label_source='organic_trade_history'`; else emit `label_source='closed_loop_review'` (T2.SB6b V1 simplification #5 closes; T2.SB6b R1 MAJOR #3 LOCK preserved against ticker-proxy regression). | RESOLVED via Delta A |
| **Gap B.4** Review form outcome distribution bucketing | §5.10 line 775 (item 8: "of last N similar-score candidates, X% triggered, Y% reached 1R, Z% hit stop") | YES — Delta A | `PatternReviewFormVM` extend `OutcomeDistributionRow` with `reached_1r_pct: float | None` + `hit_stop_pct: float | None` (None when n<5 per honesty.suppress_for_n inherited from Phase 10). Compute via: similar candidates by `composite_score +/- 0.1` per pattern_class JOIN'd to `trades` via `candidate_id` → bucket per `reached_1r` (max(daily highs since entry_date) >= entry_price + (entry_price - initial_stop)) + `hit_stop` (any fill at <= initial_stop OR `trades.state = 'closed' AND realized_R_if_plan_followed < 0`). See OQ-6 disposition for bucketing thresholds. | RESOLVED via Delta A |
| **Gap B.5** Metric tile reached_1r + hit_stop | plan §G.9 T-A.6.5 + spec §5.10 line 775 | YES — Delta A | `swing/metrics/pattern_outcomes.py:build_pattern_outcome_rows` extend `PatternOutcomeRow` with `reached_1r_count + reached_1r_pct + hit_stop_count + hit_stop_pct` fields (currently None per T2.SB6b V1 simplification #4). LEFT JOIN `pattern_evaluations` to `trades` via `candidate_id` (denominator = confirmed-by-operator pattern_evaluations; numerator = trades hitting 1R / hitting stop). Wilson-CI per Phase 10 honesty.wilson_ci; suppression at n<5 per honesty.suppress_for_n. | RESOLVED via Delta A |
| **Gap B.6** Queue criterion 3 weather-state-aware | §5.10 line 799 | NO (existing `weather_runs` read) | `swing/patterns/active_learning.py:prioritize_candidates` extend criterion 3 (`underrepresented_regime`) to consume current `weather_runs.weather_runs_id` via `get_latest(conn, ticker='^GSPC')` (the dashboard market-weather ticker); compare per-pattern_class exemplar count against the SAME-weather-state historical baseline (rather than total exemplar count per V1 proxy). Spec §5.10 line 799 LOCK: "low historical exemplar count for current weather state". | LIVE (no schema dep) |

### §3.2 Cross-row lookup discipline (NEW Expansion #7 BINDING)

For each POST handler in Gap B.3 / Gap B.4 / Gap B.5 that consumes operator input AND looks up cross-row state, enumerate the SCOPE of the lookup explicitly per spec wording:

**Gap B.3 lookup scope** (label_source split): The spec §5.10 line 788 binding text says "the candidate-to-trade backlink at `trades.candidate_id` resolves to this row". The lookup scope is **per-candidate, NOT per-ticker** — only a trade opened on the SPECIFIC candidate qualifies as `organic_trade_history`. Pre-empt T2.SB6b R1 MAJOR #3 ticker-proxy regression via discriminating test: plant 2 trades on same ticker (one from candidate A, one from candidate B); review candidate A's pattern; assert ONLY candidate A's trade qualifies the candidate as `organic_trade_history` (not candidate B). **Candidate_id lookup path (REVISED per Codex R1 CRITICAL #1)**: the URL path parameter is named `candidate_id` per shipped T2.SB6b code at `swing/web/routes/patterns.py:372` + 399, but the VALUE is actually a `pattern_evaluations.id` (the handler at line 434 calls `get_evaluation_by_id(conn, candidate_id)`). Naming quirk preserved from T2.SB6b ship; SB6c does NOT rename the URL parameter. The resolution chain: URL path int → `pattern_evaluations.id` → SELECT `pattern_evaluations.pipeline_run_id, pattern_evaluations.ticker` → JOIN to candidates via `pipeline_runs.evaluation_run_id = candidates.evaluation_run_id AND pipeline_runs.id = pattern_evaluations.pipeline_run_id AND candidates.ticker = pattern_evaluations.ticker` → use that `candidates.id` as the lookup target for `trades.candidate_id`. SQL skeleton: `SELECT c.id FROM candidates c INNER JOIN pipeline_runs pr ON c.evaluation_run_id = pr.evaluation_run_id WHERE pr.id = ? AND c.ticker = ?` (where `?` is `pattern_evaluations.pipeline_run_id`). (Alternative: thread `candidate_id` directly into `pattern_evaluations` table at v21 via Delta D — REJECTED as out-of-scope; the join is sufficient given `pipeline_runs.evaluation_run_id` was added at migration 0006 specifically to support this resolver pattern.)

**Gap B.4 lookup scope** (outcome distribution): per-candidate cohort; "last N similar-score candidates" means candidates with composite_score in `[evaluation.composite_score - 0.1, evaluation.composite_score + 0.1]` for the SAME pattern_class. Trade lookup is per-candidate via `trades.candidate_id`.

**Gap B.5 lookup scope** (metric tile): per-pattern_class cohort; LEFT JOIN denominator = all `pattern_evaluations` rows for the pattern_class WHERE `EXISTS (pattern_exemplars row with final_decision='confirmed' for same (ticker, window))`. Numerator = subset that has `trades.candidate_id` populated AND hit 1R / stop per OQ-6 thresholds.

### §3.3 Content-completeness audit (NEW Expansion #6 BINDING)

For each spec §5.10 8-item checklist item (lines 766-775), enumerate the per-field disposition at SB6c ship:

| Spec §5.10 item | Pre-SB6c state | SB6c disposition |
|---|---|---|
| 1. Proposed pattern class | LIVE at T2.SB6b | LIVE (unchanged) |
| 2. Geometric score breakdown | LIVE at T2.SB6b | LIVE (unchanged) |
| 3. Top-3 nearest historical bases | LIVE at T2.SB6b | LIVE (unchanged) |
| 4. Trend-template state | V1 STUB `"n/a"` per T2.SB6b §6 | **LIVE via Gap B.1** |
| 5. RS rank | LIVE at T2.SB6b | LIVE (unchanged) |
| 6. Recent volume profile | V1 STUB `"(not available)"` per T2.SB6b §6 | **LIVE via Gap B.2** |
| 7. Uncertainty reason per criterion | LIVE at T2.SB6b | LIVE (unchanged) |
| 8. Outcome distribution (triggered/reached_1r/hit_stop) | V1 PARTIAL (triggered_pct only) per T2.SB6b §6 | **LIVE via Gap B.4** |

Post-SB6c: ZERO V1 STUBs / V1 PARTIALs remain on the §5.10 8-item checklist. Forward-binding: any future closed-loop review form addition must NOT regress this audit.

---

## §4 Atomic-landing strategy per §A.14

Per cumulative discipline "Schema-CHECK + Python-constant + dataclass-validator MUST land in the same task" + "Read-path mapping must keep pace with write-path" + "Schema-CHECK widening MUST audit ALL Python-side surface guards" + the new "Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts" (T2.SB6a R1 CRITICAL #1):

### §4.1 Atomic landing scope for Delta A (candidate_id)

ONE task / ONE commit lands ALL of:

1. **Schema migration file** `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` with `ALTER TABLE` + `CREATE INDEX` + `UPDATE schema_version`.
2. **Python constant**: none required (no enum/Literal for INTEGER FK).
3. **Dataclass extension**: `Trade.candidate_id: int | None = None` in `swing/data/models.py`.
4. **Read-path mapper**: `_row_to_trade` extended; `_TRADE_SELECT_COLS` extended; index map comment block updated.
5. **Write-path INSERT extension**: `INSERT INTO trades` at `swing/data/repos/trades.py:120` extended with `candidate_id` column + placeholder; function signature accepting `candidate_id: int | None = None` kwarg.
6. **N-mirror auditing (T3.SB2 hotfix `cf3c489` discipline)**: grep `swing/` for ALL other hardcoded SELECT-trade-column-lists. If found, extend at the same commit. Expected callsites: trade journal export (`swing/journal/`); trade CSV export; any audit shape. Brainstorming MUST list each callsite + verify each is in the atomic commit's diff. (At brainstorming time, candidate callsites: `swing/journal/*` if any direct trade SELECTs; otherwise `_row_to_trade` is the canonical reader.)
7. **All 8 discriminating tests** from §2.1 listed above, including the FK cascade test + read-path roundtrip test.

**Pre-Codex review scope expansion #4 BINDING (T2.SB6a R1 MAJOR #2 specific-scenario trace)**: walk a SPECIFIC failure scenario through the atomic commit. Scenario: an operator's existing pre-v21 trade row has 52 columns. Post-v21 migration runs; ALTER TABLE appends 2 nullable columns at positions 52 + 53; `_row_to_trade` reads `row[52]` + `row[53]`. If the atomic commit landed the migration WITHOUT extending `_TRADE_SELECT_COLS`, the SELECT would return only 52 columns + `row[52]` would IndexError. Pre-empt: discriminating test #5 above asserts the read-path returns `candidate_id` correctly; the test runs migration first, then plants a pre-v21-shape row via direct INSERT, then asserts SELECT-via-public-reader produces a Trade with `candidate_id=None`.

### §4.2 Atomic landing scope for Delta B (pattern_evaluation_id)

Mirror §4.1; lands in SAME commit as Delta A (single migration file; single atomic transaction). All extensions are co-located:

1. Same migration file.
2. Same dataclass `Trade` extension (both columns added in one Edit).
3. Same `_row_to_trade` extension (both extracts in one Edit).
4. Same `_TRADE_SELECT_COLS` extension.
5. Same `INSERT INTO trades` extension.
6. All 9 §2.2 discriminating tests + all 8 §2.1 discriminating tests in the same commit.

### §4.3 Atomic landing scope for SB6 closure items (no schema dep)

Per Phase 13 plan §G.9 cumulative precedent, closure items can land across multiple tasks within T2.SB6c. Atomic-landing discipline applies INSIDE each task (e.g., Gap B.1 trend-template state lands VM extension + template extension + 2 discriminating tests in same task; Gap B.2 volume profile lands its full surface + tests in one task).

---

## §5 Test scope projection

### §5.1 Fast-test delta forecast

| Bundle | Test count | Source |
|---|---|---|
| Delta A migration + paired surface | 8 | §2.1 |
| Delta B migration + paired surface | 9 | §2.2 |
| Gap A.1 hyp-rec detail chart | 3 | template + VM + route |
| Gap A.2 position detail chart | 3 | template + VM + route |
| Gap A.3 WatchlistVM template | 2 | template render + responsive zero-rows |
| Gap A.4 exemplar cache-miss write-through | 3 | cache-miss render + write-through + roundtrip |
| Gap B.1 trend-template state live | 4 | VM extension + Phase 8 weather lookup + session-anchor backward-looking round-trip test + template render |
| Gap B.2 volume profile live | 5 | VM + VolumeProfileRow dataclass validator + 30-session sum + 50d avg ratio + template render |
| Gap B.3 label_source split | 5 | candidate-lookup positive (organic_trade_history) + candidate-lookup negative (closed_loop_review) + ticker-proxy-regression discriminating test (T2.SB6b R1 MAJOR #3 LOCK) + confirm-decision-required + non-confirm-decision (no trade qualifies) |
| Gap B.4 outcome distribution bucketing | 5 | reached_1r computation + hit_stop computation + suppression at n<5 + Wilson CI emission + VM template render |
| Gap B.5 metric tile reached_1r + hit_stop | 5 | LEFT JOIN denominator/numerator + per-pattern_class + suppression + Wilson CI + VM banner pin |
| Gap B.6 queue criterion 3 weather-state-aware | 4 | weather-state lookup + per-pattern_class baseline + weather-state-missing fallback + spec line 799 wording verbatim |
| Closer E2E + ruff sweep | 1 fast E2E + ruff | §5.4 |
| **Total estimated** | **~57 + 1 E2E** | Within brief's "~+80-150 fast tests" range (lower bound; closure-focused tests rather than expansive coverage) |

### §5.2 Slow-test delta

ZERO new slow tests. v21 migration is in-process (no Schwab API call, no yfinance fetch); all closure items are pure-VM extensions or in-process queries.

### §5.3 Cross-bundle pin schedule

Per Phase 13 plan §H.3 pin schedule: row 12 is the v21-migration pin (un-skip at SB6c land). Plan plans for additional pins as Phase 13 sub-bundles ship. Current pin status:

- **Row 11** `test_repo_caller_tx_contract_invariant` — PLANTED + GREEN at T2.SB6b (4 parametrized passes; one per Phase 13 NEW repo module).
- **Row 12** (NEW at SB6c) — proposed pin: `test_phase13_t2_sb6c_v21_trade_backlinks_schema_atomic` parametrized over (candidate_id, pattern_evaluation_id). Plants a trade row + asserts schema + FK + index + mapper + INSERT roundtrip on each column.

### §5.4 Operator-witnessed gates

- **S1 (inline)**: fast pytest + ruff + schema = v21.
- **S2 (browser)**: `/patterns/{candidate_id}/review` — confirm all 8 §5.10 checklist items render LIVE data (no `"n/a"` or `"(not available)"` stubs). Acceptance gate Item 4 + Item 6 + Item 8 closes out.
- **S3 (browser)**: hyp-rec detail page — confirm 800x500 SVG with pattern boundaries renders (Gap A.1).
- **S4 (browser)**: position detail page — confirm 800x500 SVG with fill markers renders (Gap A.2).
- **S5 (browser)**: `/watchlist` — confirm thumbnail charts render inline per row (Gap A.3).
- **S6 (browser)**: `/patterns/exemplars` — under cache-miss path, confirm live render fires + cache row is written through (Gap A.4); verify via DB query post-page-load that `chart_renders` has the new exemplar row.
- **S7 (browser)**: `/metrics/pattern-outcomes` — confirm `reached_1r_pct` + `hit_stop_pct` columns render LIVE for cohorts with n>=5 (Gap B.5).
- **S8 (browser)**: `/patterns/queue` — confirm criterion 3 ranking matches current weather state (Gap B.6).
- **S9 (browser; data-shaped)**: open a fresh trade from `/recommendations/` form for a current pipeline candidate; confirm new trade row gets `candidate_id` + `pattern_evaluation_id` populated (NEW lifecycle logic per §2.1 OQ-11 + §2.2 OQ-12).
- **S10 (browser; closed-loop)**: review the candidate at `/patterns/{candidate_id}/review` with `confirm` decision; confirm `pattern_exemplars` row is written with `label_source='organic_trade_history'` (NOT `closed_loop_review` — closes T2.SB6b V1 simplification #5).

---

## §6 Sub-bundle decomposition (proposed T-A.6c.1..T-A.6c.5)

### §6.1 T-A.6c.1 — v21 migration atomic landing

**Scope**: schema migration + Trade dataclass extension + read-path mapper + write-path INSERT extension + all 17 (8+9) schema-paired discriminating tests + Phase 13 plan §H.3 cross-bundle pin row 12 PLANTED.

**Files in scope**:
- Create: `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`.
- Modify: `swing/data/models.py:Trade` (extend with 2 nullable INT fields).
- Modify: `swing/data/repos/trades.py` (`_TRADE_SELECT_COLS` + `_row_to_trade` + `INSERT INTO trades` callsite + insert signature).
- Modify: `swing/data/db.py` per §2.4 backup-gate REVISED implementation (Codex R1 MAJOR #3): (a) bump `EXPECTED_SCHEMA_VERSION` to 21; (b) add `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` constant derived from `PHASE13_PRE_MIGRATION_EXPECTED_TABLES`; (c) add `_phase13_sb6c_backup_gate` function with strict `pre_version == 20` predicate; (d) add `_create_pre_phase13_sb6c_migration_backup` function with filename `swing-pre-phase13-sb6c-migration-<ISO>.db`; (e) wire into `run_migrations` call chain BEFORE the v21 migration applies.
- Create: `tests/data/test_v21_migration_trade_backlinks.py` (17 tests).
- Create: `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` (parametrized pin).

**Acceptance criteria**:
- Migration runs cleanly against v20-shape DB; `SELECT version FROM schema_version` returns 21 (REVISED per Codex R1 Minor #1; the project tracks schema in the `schema_version` table, NOT via SQLite's `PRAGMA user_version`).
- All 17 schema-paired tests PASS + the 3 backup-gate tests PASS.
- Existing 5559 fast tests still PASS (no regression).
- Backup file `swing-pre-phase13-sb6c-migration-<ISO>.db` written before migration runs.

**LOCK**: schema CHECK + Python constant (none here) + dataclass validator + read-path mapper + write-path INSERT extension + all tests land in ONE commit per §A.14.

### §6.2 T-A.6c.2 — SB6 closure Gap A chart-surface wiring

**Scope**: 4 items (A.1-A.4); ~11 fast tests.

**Files in scope**:
- Modify: `swing/web/view_models/recommendations.py` (hyp-rec detail VM extension).
- Modify: `swing/web/view_models/trades.py` (position detail VM extension).
- Modify: `swing/web/templates/recommendations/detail.html.j2` (inline SVG render).
- Modify: `swing/web/templates/trades/detail.html.j2` (inline SVG render).
- Modify: `swing/web/templates/partials/watchlist_row.html.j2` (thumbnail render).
- Modify: `swing/web/view_models/patterns/exemplars.py` (cache-miss write-through).
- Create: `tests/web/test_routes/test_recommendations_detail_chart.py`.
- Create: `tests/web/test_routes/test_trades_detail_chart.py`.
- Modify: `tests/web/test_routes/test_watchlist_template_thumbnail.py` (if exists; else create).
- Modify: `tests/web/test_routes/test_patterns_exemplars_enhanced.py` (extend with write-through test).

**Acceptance criteria**:
- 11 new tests PASS.
- S3 + S4 + S5 + S6 operator-witnessed gates PASS.

### §6.3 T-A.6c.3 — SB6 closure Gap B no-schema review form data-completeness

**Scope**: 3 items (B.1 trend-template + B.2 volume profile + B.6 queue criterion 3); ~13 fast tests.

**Files in scope**:
- Modify: `swing/web/view_models/patterns/review_form.py` (extend with trend_template_state + volume_profile fields + VolumeProfileRow dataclass).
- Modify: `swing/web/templates/patterns/review.html.j2` (render new fields).
- Modify: `swing/patterns/active_learning.py:prioritize_candidates` (criterion 3 weather-state-aware variant).
- Modify: `swing/web/routes/patterns.py` (route handler populates VM extensions).
- Create: `tests/web/test_routes/test_patterns_review_data_completeness.py`.
- Modify: `tests/web/test_routes/test_patterns_queue.py` (extend with weather-state-aware criterion 3 tests).

**Acceptance criteria**:
- 13 new tests PASS.
- S2 + S8 operator-witnessed gates PASS.

### §6.4 T-A.6c.4 — SB6 closure Gap B v21-dependent (label_source + outcomes)

**Scope**: 3 items (B.3 label_source split + B.4 outcome distribution + B.5 metric tile); ~15 fast tests.

**Files in scope**:
- Modify: `swing/web/routes/patterns.py:patterns_review_post` (label_source split via candidate-scope lookup).
- Modify: `swing/web/view_models/patterns/review_form.py:OutcomeDistributionRow` (extend with reached_1r_pct + hit_stop_pct).
- Modify: `swing/metrics/pattern_outcomes.py:build_pattern_outcome_rows` (LEFT JOIN trades; extend `PatternOutcomeRow` with reached_1r + hit_stop fields).
- Modify: `swing/trades/entry.py` (canonical trade entry service; calls `insert_trade_with_event` at `swing/data/repos/trades.py:102`) to populate `candidate_id` + `pattern_evaluation_id` per §2.1 OQ-11 + §2.2 OQ-12 lifecycle logic. **Lookup queries (REVISED per Codex R1)**: (a) candidates resolved via `SELECT c.id FROM candidates c INNER JOIN pipeline_runs pr ON c.evaluation_run_id = pr.evaluation_run_id WHERE pr.id = ? AND c.ticker = ? ORDER BY c.id DESC LIMIT 1` (where `?` is the pipeline_run_id context of the entry — typically resolved via `_latest_complete_evaluation_run_id` per `swing/trades/origin.py:27-37` precedent OR from the operator-form's hidden anchor); (b) pattern_evaluations by `(pipeline_run_id, ticker)` ordered by `composite_score DESC LIMIT 1` (NO `pattern_class` filter — pick highest-scoring across all 5 detector classes for the (run, ticker) tuple). Both queries execute before the `insert_trade_with_event` call within the entry service's own transactional block (which owns its `BEGIN IMMEDIATE` per existing entry service contract).
- Modify: `tests/web/test_routes/test_patterns_review.py` (extend with B.3 + B.4 tests).
- Modify: `tests/web/test_routes/test_metrics_pattern_outcomes.py` (extend with B.5 tests).
- Create: `tests/trades/test_entry_populates_candidate_backlinks.py` (NEW lifecycle test).

**Acceptance criteria**:
- 15 new tests PASS.
- S2 (Item 8) + S7 + S9 + S10 operator-witnessed gates PASS.

**Cross-row semantic discipline**: pre-Codex review MUST verify Gap B.3 lookup scope is per-candidate (NOT ticker-proxy regression). Test `test_patterns_review_label_source_split_ticker_proxy_regression_guard` is BINDING (plants 2 trades on same ticker, different candidates; asserts only the SAME-candidate trade qualifies for `organic_trade_history`).

### §6.5 T-A.6c.5 — Closer (E2E + ruff sweep + cross-bundle pin row 12 promote)

**Scope**: 1 fast E2E + ruff sweep + un-skip cross-bundle pin row 12 (if planted as skip in T-A.6c.1).

**Files in scope**:
- Create: `tests/integration/test_phase13_t2_sb6c_v21_closure_e2e.py` (1 fast E2E walking the full happy path: migrate → enter trade from candidate → confirm pattern → review form renders LIVE data → POST persists `organic_trade_history` → metric tile shows non-None reached_1r_pct).
- ruff sweep across `swing/`.

**Acceptance criteria**:
- E2E PASSES.
- 0 ruff E501 / E violations.
- All previous-task tests PASS in cumulative run.

### §6.6 Cross-task dependency map

```
T-A.6c.1 (v21 migration; foundation)
    |
    +---> T-A.6c.2 (Gap A wiring; no schema dep — could run in parallel)
    |
    +---> T-A.6c.3 (Gap B.1/B.2/B.6 no-schema data-completeness)
    |
    +---> T-A.6c.4 (Gap B.3/B.4/B.5 v21-dependent; consumes Delta A + B)
              |
              +---> T-A.6c.5 (closer E2E + ruff)
```

**Per-task gating**: T-A.6c.4 MUST follow T-A.6c.1 (schema dependency). T-A.6c.2 + T-A.6c.3 can run in parallel with T-A.6c.1 if subagent-driven-development dispatches concurrently (per superpowers:dispatching-parallel-agents); writing-plans phase decides between parallel + sequential dispatch.

**Concurrent dispatch (recommended)**: T-A.6c.1 + T-A.6c.2 + T-A.6c.3 in parallel; T-A.6c.4 sequential after T-A.6c.1; T-A.6c.5 sequential after all. Expected wall-clock savings ~30-40%.

---

## §7 OQ disposition table

14 OQs (10 from brief + 4 NEW surfaced during brainstorming). Operator-paired triage required before writing-plans dispatch.

| OQ | Source | Brainstorm recommendation | Operator decision (pending triage) |
|---|---|---|---|
| **OQ-1** Backfill semantics for `trades.candidate_id` for existing trades | brief §5 | **NULL only** (no heuristic match) — reasons enumerated at §2.1 backfill section | _pending_ |
| **OQ-2** SB6c scope boundary (include Q4 surfaces?) | brief §5 | **NO** — Q4 surfaces locked to T4.SB per plan §G.10; schema already in v20; SB6c respects scope boundary | _pending_ |
| **OQ-3** v21 migration backup-gate predicate | brief §5 | **`pre_version == 20 AND target >= 21` strict equality** per CLAUDE.md gotcha "Migration runner backup-gate equality form" | _pending_ |
| **OQ-4** Cleared_by_reason enum scope | brief §5 | **N/A — already locked in v20** as `('operator_cleared', 'auto_cleared_on_position_open')`. Brief OQ-4 wording was incorrect (`operator_explicit`/`position_opened`); v20 ship is authoritative. | _pending_ |
| **OQ-5** Watchlist-flag partial UNIQUE index semantics | brief §5 | **N/A — already locked in v20** as `WHERE cleared_at IS NULL` (active-only) per spec §7.2 Codex R1 M#9 closure | _pending_ |
| **OQ-6** Outcome distribution bucketing thresholds | brief §5 | **`reached_1r`**: max(daily high since entry_date) >= `entry_price + (entry_price - initial_stop)` (i.e., 1R = the original risk amount, expressed as price delta). **`hit_stop`**: ANY fill at <= initial_stop OR `trade.state IN ('closed', 'reviewed') AND realized_R_if_plan_followed < 0`. Computed from `fills` table + OHLCV cache. Suppression at n<5 per Phase 10 honesty.suppress_for_n. | _pending operator_ |
| **OQ-7** Phase 13 brainstorm D-Q4.2 web+CLI confirmation | brief §5 | **N/A for SB6c** — Q4 surfaces deferred to T4.SB; operator triage at T4.SB dispatch | _pending T4.SB_ |
| **OQ-8** Migration backup file naming | brief §5 | **`swing-pre-phase13-sb6c-migration-<ISO>.db`** per Phase 13 precedent (T-A.1.1 v20 used `swing-pre-phase13-migration-<ISO>.db`) | _pending_ |
| **OQ-9** Read-path mapper column position assignment | brief §5 | **row[52] = candidate_id; row[53] = pattern_evaluation_id** (after `planned_target_R` at row[51] from migration 0016) | _pending_ |
| **OQ-10** Sub-bundle decomposition | brief §5 | **5 tasks**: T-A.6c.1 (schema atomic) + T-A.6c.2 (Gap A wiring) + T-A.6c.3 (Gap B no-schema) + T-A.6c.4 (Gap B v21-dep) + T-A.6c.5 (closer). Concurrent dispatch T-A.6c.1+2+3 recommended. | _pending_ |
| **OQ-11** *(NEW)* trades.candidate_id lifecycle population point | §2.1 lifecycle disposition | **At trade-entry-form lock time inside `with conn:` block IF trade_origin IN pipeline-origins AND candidates lookup returns row; ELSE NULL** | _pending_ |
| **OQ-12** *(NEW)* trades.pattern_evaluation_id lifecycle population point | §2.2 lifecycle disposition | **At trade-entry-form lock time IF candidate_id is populated AND pattern_evaluations row exists for (pipeline_run_id, ticker, [chart_pattern_algo / chart_pattern_operator / highest-composite]); ELSE NULL** | _pending_ |
| **OQ-13** *(NEW)* Metric tile cohort denominator shape | §3.2 cross-row lookup discipline | **LEFT JOIN denominator = pattern_evaluations rows with matching pattern_class AND operator-confirmed (via pattern_exemplars.final_decision='confirmed')**. Numerator = subset with `trades.candidate_id` AND outcome bucket met. Suppression at denominator<5. | _pending operator_ |
| **OQ-14** *(NEW)* Volume profile data path | Gap B.2 wiring | **`swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)`** returning the OhlcvBar window for VM to compute 30-session sum + 50d avg ratio. Aligns with existing OhlcvCache substrate; ACCEPTS fetch-on-cache-miss behavior per existing `get_or_fetch` semantics (Codex R1 Minor #2 — the method can fetch on miss; this is the desired behavior for a review surface that may be loaded against tickers not in the current pipeline-run watchlist). For pure read-only scenarios where fetch-on-miss is undesirable, V2 could introduce a `get_cached_only` variant returning None on miss. | _pending_ |

---

## §8 LOCKs + watch items

### §8.1 Cumulative-discipline LOCKs inherited

- **L1 (spec source-of-truth)**: spec §5.10 lines 766-775 (8-item checklist) + lines 785-790 (label_source split) + line 775 (outcome distribution) + line 799 (queue criterion 3) BINDING text. Constants + comments cite line numbers per Phase 13 §A.14 precedent.
- **L2 (ZERO new Schwab API calls)**: closure dispatch consumes only `pattern_evaluations` + `chart_renders` + `weather_runs` + `trades` + `candidates` + OHLCV cache + `pattern_exemplars`. NO new schwab integration touch.
- **L3 (v21 = single migration)**: 1 migration file at `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`; no other schema files touched.
- **L4 (cross-bundle pin row 12)**: PLANT at T-A.6c.1; un-skip at T-A.6c.5 closer per Phase 10 T-A.7 + T-E.3 + Phase 12 C.A T-A.7 + Phase 13 T2.SB6b row 11 precedent.
- **L5 (branch base)**: branches from main HEAD `2dd90fe` (post-T2.SB6b housekeeping) at executing-plans worktree creation time.
- **L6 (frozen dataclasses with `__post_init__` frozenset validation)**: VolumeProfileRow (NEW; if any Literal field; expected 0) + any new dataclass introduced by closure surface. Pattern: explicit frozenset validator per CLAUDE.md gotcha "`Literal[...]` not runtime-enforced".
- **L7 (T2.SB6a substrate API surface FROZEN)**: `swing/web/charts.py` + `swing/data/repos/chart_renders.py` + `swing/data/models.py:ChartRender` UNTOUCHED. Gap A.4 cache-miss write-through invokes existing `refresh_chart_render` substrate function; no substrate-API additions.
- **L8 (`_CHART_SURFACE_VALUES` semantic LOCK)**: imported from `swing/data/models.py`; no re-definition. Per T2.SB6a R1 CRITICAL #1 + §A.14 paired discipline.
- **L9 (server-recompute at POST)**: POST `/patterns/{candidate_id}/review` continues to server-recompute `proposed_pattern_class` from canonical `pattern_evaluations.pattern_class` (T2.SB6b L9 LOCK preserved). The label_source split (Gap B.3) extends this with candidate-scope lookup; the recompute does NOT trust operator-submitted label_source.
- **L10 (9th metric tile ADDITIVE composition)**: `pattern_outcomes.py` extension at Gap B.5 inherits Phase 10 honesty.wilson_ci + suppress_for_n + RiskPolicy composition. ADDITIVE on existing 9 tiles; no replacement.
- **L11 (BaseLayoutVM banner field propagation)**: all VMs touched at T-A.6c.2 + T-A.6c.3 + T-A.6c.4 already extend BaseLayoutVM per T2.SB6b L11 LOCK; banner fields preserved.
- **L12 (HTMX 3-surface discipline)**: any new POST route gets `hx-headers='{"HX-Request": "true"}'` + 204 + `HX-Redirect: <url>` + target registered. SB6c does NOT introduce new POST routes for Q4 (deferred to T4.SB); existing T2.SB6b POSTs unchanged.
- **L13 (dashboard market weather chart at TOP)**: T2.SB6b L13 preserved; SB6c does not touch dashboard template.
- **L14 (BaseLayoutVM shared-field propagation)**: any new field added to BaseLayoutVM (NONE planned for SB6c) must propagate to all 5+ base-layout VMs per CLAUDE.md gotcha "`base.html.j2` is shared".
- **L15 (Literal validation)**: any new Literal[...] field on a new dataclass MUST have `__post_init__` frozenset validator. (None planned for SB6c at brainstorm time; surface during writing-plans.)
- **L16 (ASCII-only narrative + template literals)**: Phase 13 T2.SB6b R1 MAJOR #7 em-dash LOCK preserved. Template + VM + runtime CLI all ASCII-only.
- **L17 (substrate reuse)**: Gap A.1 + Gap A.2 + Gap A.4 reuse `render_theme2_annotated_svg` + `get_cached_chart_svg` + `refresh_chart_render` substrate verbatim. No duplicate renderer code.
- **L18 (chart_renders cache write-through atomic via substrate)**: Gap A.4 invokes existing `refresh_chart_render` (substrate-owned DELETE-then-INSERT transaction); no caller-side INSERT OR REPLACE.

### §8.2 Phase 13 T2.SB6c-specific watch items

- **W1 (Schema-CHECK + Python-constant + dataclass-validator paired discipline §A.14)**: §4.1 atomic landing scope BINDING. All extensions in ONE commit.
- **W2 (Read-path mapping keeps pace with write-path)**: T3.SB3 R1 M#1 LOCK preserved. `_row_to_trade` extended in SAME task as ALTER TABLE.
- **W3 (Schema-CHECK widening N-mirror auditing)**: T3.SB2 hotfix `cf3c489` discipline. Grep `swing/` for hardcoded SELECT-trade-column-lists pre-Codex review.
- **W4 (Migration runner backup-gate strict equality)**: OQ-3 disposition LOCK; `pre_version == 20 AND target >= 21` per Phase 12 C.A §0.5 precedent.
- **W5 (executescript() implicit-COMMIT)**: migration file uses explicit `BEGIN`+`COMMIT` per `swing/data/db.py:_apply_migration` canonical implementation.
- **W6 (INSERT OR REPLACE cascade-wipe BANNED)**: NEW v21 INSERT paths use ordinary INSERT (FK ON DELETE SET NULL handles cascade); no upsert intent.
- **W7 (Cross-row semantic audit on operator-input flows — Expansion #7 BINDING)**: Gap B.3 candidate-scope lookup MUST be per-candidate (NOT ticker-proxy). Discriminating regression test planted.
- **W8 (Content-completeness audit — Expansion #6 BINDING)**: §3.3 audit table BINDING; ZERO V1 STUBs post-SB6c on the §5.10 8-item checklist.
- **W9 (Session-anchor read/write mismatch family)**: Gap B.1 trend-template state lookup uses `get_latest(conn, ticker='^GSPC')` (backward-looking) per the existing weather-lookup gotcha precedent. Discriminating round-trip test asserts visibility.
- **W10 (Synthetic-fixture-vs-production-emitter shape drift)**: tests for Gap B.4 + Gap B.5 use production-shape fixtures (real `pattern_evaluations.composite_score` values; real `pattern_exemplars.final_decision='confirmed'` rows; real `fills` cross-join). NO synthetic shortcut shapes.
- **W11 (Pre-Codex 5+2 expansion discipline)**: writing-plans phase verifies each expansion against the spec's per-section content. T2.SB6c is the **FIRST RUN BINDING** for Expansions #6 + #7 at brainstorming phase.
- **W12 (V1 simplification banking)**: every V1 STUB / V1 PLACEHOLDER / V1 PARTIAL in T2.SB6c return report MUST be enumerated with V2 dependency cited. Closure dispatch — V1 STUBs are EXPLICITLY in scope to fix, NOT bank again. If a stub from T2.SB6b §6 can't land in SB6c, brainstorming surfaces the BLOCKING dependency + re-banks.
- **W13 (NEW Schwab API calls = 0)**: L2 LOCK preserved. closure-only.
- **W14 (Hidden anchor 4-tier rejection ladder)**: T3.SB1 LOCK. If any NEW SB6c form has hidden audit anchors driving POST validation, apply 4-tier rejection. T2.SB6c does NOT plan new POST routes (per OQ-2 deferral); existing T2.SB6b POSTs unchanged.
- **W15 (`Co-Authored-By` footer ZERO trailer drift)**: cumulative ~360+ commit streak preserved through this brief commit at `5ca64c3`. SB6c MUST NOT regress.

### §8.3 Pre-Codex review expansions verdict per dispatch (FIRST RUN BINDING for #6 + #7)

| Expansion | Source | T2.SB6c brainstorm verdict (pre-Codex) |
|---|---|---|
| #1 hardcoded-duplicate audit | T3.SB2 hotfix `cf3c489` | **CLEAN** — no new CHECK enums; only new INTEGER FK columns; grep `swing/` for hardcoded SELECT-trade-column-lists is a writing-plans-phase action item, not a brainstorm-phase test |
| #2 brief-vs-spec source-of-truth | T2.SB4 R1 M1 | **CATCHES BRIEF §2.3 OBSOLETE** — `watchlist_close_track_flags` already in v20; brief proposal contradicts v20 ship reality; spec §7.2 line 986 LOCK is authoritative |
| #3 schema-CHECK-vs-semantic-contract gap audit | T2.SB6a R1 CRITICAL #1 | **CLEAN at brainstorm** — no new schema CHECK constraints introduced; FK semantics are simple; semantic contracts (column position 52 + 53; lifecycle population logic; cross-row label_source scope) enumerated explicitly at §2.1 + §2.2 + §3.2 |
| #4 CLAUDE.md gotcha specific-scenario trace | T2.SB6a R1 MAJOR #2 | **CLEAN at brainstorm** — schema-version-aware INSERT pattern verified NOT NEEDED (nullable columns); ALTER TABLE FK behavior verified per SQLite docs; row[52]/[53] read-path scenario traced at §4.1 |
| #5 cross-section spec inventory grep | T2.SB6a R1 MAJOR #3 | **CLEAN at brainstorm** — spec §5.10 (lines 766-775 + 785-790 + 799) inventoried + per-item disposition documented at §3.3; spec §4.2 + §3.2 chart cache architecture cited at Gap A items; plan §G.9 + §G.10 cited at sub-bundle decomposition |
| #6 *(FIRST RUN BINDING)* content-completeness audit | T2.SB6b lesson banked | **VERIFIED at brainstorm** — §3.3 audit table enumerates every §5.10 checklist item with per-field disposition (LIVE / V1 PARTIAL / V1 STUB); post-SB6c ZERO V1 STUBs remain |
| #7 *(FIRST RUN BINDING)* cross-row semantic audit on operator-input flows | T2.SB6b lesson banked | **VERIFIED at brainstorm** — §3.2 enumerates SCOPE of each cross-row lookup explicitly (per-candidate for Gap B.3; per-candidate cohort for Gap B.4; per-pattern_class cohort for Gap B.5); discriminating ticker-proxy-regression test planted at Gap B.3 |

---

## §9 Forward-binding lessons + V2 candidates

### §9.1 Forward-binding lessons banked for future arcs

1. **Brief-vs-spec source-of-truth Expansion #2 catches schema-vs-shipped-reality**: T2.SB6c brainstorm caught brief §2.3 OBSOLETE because v20 ship reality is the truth; spec line 986 LOCK supersedes brief draft text written under uncertainty. Future dispatches: when a brief proposes "NEW table X", verify against v_current migration before consuming brief verbatim. (Pre-empt: dispatch-brief authoring at orchestrator side should run `ls swing/data/migrations/` + grep for proposed table names before publishing.)

2. **Schema-CHECK + Python-constant + dataclass-validator §A.14 paired discipline EXTENDS to nullable FK columns**: even without enum CHECK, the discipline applies — read-path mapper extension + write-path INSERT extension + dataclass field addition + paired tests ALL land in same task per T3.SB3 R1 M#1 lesson family. Not just CHECK widenings; ANY column addition.

3. **Lifecycle population logic for nullable FK columns surfaced as NEW OQs**: brainstorming-phase recognized that "where does the FK get populated" is a critical lifecycle question separate from "what's the column shape". OQ-11 + OQ-12 represent this. Future schema dispatches: when adding nullable FK backlinks, enumerate per-`trade_origin` (or per-state-machine-state) population logic as binding spec content.

4. **Cross-row semantic audit (Expansion #7) catches per-ticker vs per-candidate distinction**: Gap B.3 label_source split was the canonical case at T2.SB6b R1 MAJOR #3; SB6c preserves the LOCK via discriminating regression test. Future operator-input + cross-row-lookup POST handlers: enumerate the SCOPE explicitly + plant ticker-proxy-regression discriminating test.

5. **Content-completeness audit (Expansion #6) walks every spec checklist item**: §3.3 audit table is the canonical template. Future closure dispatches: enumerate every spec-bound surface; per-field disposition (LIVE / V1 STUB / V1 PARTIAL); ZERO V1 STUBs post-closure.

### §9.2 V2 candidates banked

| V2 candidate | Rationale | Banked for |
|---|---|---|
| Backfill historical trades with heuristic ticker+date match against `candidates` | OQ-1 disposition rejected; some operator value possible IF the heuristic is constrained (same-pipeline-run only) | V2 if operator surfaces value |
| Add `pattern_evaluations.candidate_id` direct column | Closes the JOIN via `(ticker, pipeline_run_id)` indirection at Gap B.3 lookup; cleaner but adds another schema-paired discipline burden | V2 schema dispatch |
| Auto-fill `candidate_id` retroactively from `chart_pattern_classification_pipeline_run_id` (existing trades column at migration 0010) | Phase 6 column may be sufficient to backfill some pre-v21 trades; needs operator-paired investigation of data quality | V2 enrichment |
| Multi-pattern_class trade backlink (one trade could match multiple pattern_evaluations) | Current §2.2 OQ-12 picks highest-composite-score; alternative is many-to-many table | V2 if operator surfaces value |
| `trades.candidate_id` + `pattern_evaluation_id` cascade behavior alternatives (RESTRICT vs CASCADE) | ON DELETE SET NULL preserves trade row but loses backlink; an audit table could capture the deleted FK target's metadata | V2 audit-trail enrichment |
| `chart_renders` cache key extension for exemplar pages (pipeline_run_id-agnostic exemplar key shape) | Gap A.4 cache-miss write-through is V1 simplification; the cache key for exemplars currently inherits from theme2_annotated; V2 could introduce a fifth `surface='exemplar_thumbnail'` value | V2 cache architecture |
| Theme 2 narrative auto-generation from `structural_evidence_json` (Gap B.7-like new item) | V1 SB6c uses pre-existing narrative text; V2 could generate the narrative from evidence at render time | V2 detector enrichment |

---

## §10 References

- **Phase 13 spec** at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` — §3.2 (chart_renders cache schema + 3-partial-UNIQUE-index discipline); §4.2 (chart surface inventory + per-surface cache architecture); §4.5 (market weather TOP placement); §4.6 (Theme 2 annotated chart deliverable); §5.10 (closed-loop surface; 8-item checklist + 6-decision enum + label_source split + active learning prioritization); §7.2 (Q4 close-tracking flag with D-Q4.1 through D-Q4.7 sub-decisions; line 986 "Q4 schema FOLDS INTO v20" LOCK).
- **Phase 13 plan** at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` — §G.9 T-A.6.1 through T-A.6.7 (T2.SB6 8 tasks; closed at T2.SB6b ship); §G.10 T-D.1 through T-D.7 (T4.SB 8 tasks including Q4 surface wiring; PAUSED for operator list additions); §H.3 cross-bundle pin schedule (row 11 PLANTED at T2.SB6b; row 12 NEW at SB6c).
- **Brief** at `docs/phase13-t2-sb6c-v21-closure-brainstorm-dispatch-brief.md` — §2.3 OBSOLETE per Expansion #2 catch; remainder of brief consumed.
- **T2.SB6b return report** at `docs/phase13-t2-sb6b-return-report.md` — §6 V1 simplifications table (9 V1 simplifications; closure intent of SB6c); §7 operator-paired gates (S6 + S7 V2-deferred → CLOSED at SB6c S3 + S4 gates).
- **T2.SB6a return report** at `docs/phase13-t2-sb6a-return-report.md` — substrate API surface FROZEN inheritance + 3 NEW expansion proposals banked at 23rd cumulative validation.
- **Schema** at `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` — v20 atomic landing; canonical for Q4 schema-already-exists finding.
- **Trades repo** at `swing/data/repos/trades.py` — `_TRADE_SELECT_COLS` (line 47); `_row_to_trade` (line 345); `INSERT INTO trades` callsite (line 120).
- **Trades dataclass** at `swing/data/models.py:Trade` (line 153) — 52 current fields; v21 adds 2 nullable INTEGER backlinks.
- **CLAUDE.md gotchas inherited** (top 14 binding):
  - "Schema-CHECK widening MUST audit ALL Python-side surface guards" (T3.SB2 hotfix `cf3c489`)
  - "Schema-CHECK + Python-constant + dataclass-validator MUST land in same task" (Phase 12 C.A T-A.2)
  - "Schema-coverage Python constant is NOT necessarily the manual-input allowlist" (Phase 12 C.C R1 M#4) — moot for INT FK
  - "Read-path mapping must keep pace with write-path" (T3.SB3 R1 M#1)
  - "Migration runner backup-gate strict equality" (Phase 12 C.A §0.5)
  - "executescript() implicit-COMMIT" (Phase 7 Sub-A R1 M3)
  - "INSERT OR REPLACE cascade-wipe" (Phase 8 daily-management spec §4.2)
  - "Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts" (T2.SB6a R1 CRITICAL #1) — applied at §3.2 cross-row lookup discipline
  - "F6 transient-empty at construction barrier when helper accepts dataclass parameter" (T2.SB6a R1 MAJOR #2) — N/A here (no new write-through-cache helpers)
  - "Pre-Codex 5-expansion discipline does NOT catch CONTENT-completeness vs spec text" (T2.SB6b R1 lessons) — FIRST RUN of Expansion #6 BINDING here
  - "V1 simplification banking discipline" (T2.SB6b lessons) — closure-dispatch intent
  - "Session-anchor read/write mismatch silently invisibles UI display" (Phase 8 + Phase 13 T1.SB0) — applied at Gap B.1
  - "Synthetic-fixture-vs-production-emitter shape drift" (Phase 12 C.D + Phase 13 T2.SB1 + Phase 13 T2.SB1 cassette + production-data-flow-derivation) — applied at W10
  - "`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM" — no new BaseLayoutVM fields planned

---

*End of T2.SB6c brainstorming-phase spec. v21 schema scope = 2 deltas (trades.candidate_id + trades.pattern_evaluation_id; brief §2.3 OBSOLETE per Expansion #2 catch — Q4 schema already in v20). SB6 closure scope = 4 Gap A + 6 Gap B items (3 require v21; 6 LIVE no-schema; 1 weather-state-aware queue criterion). 5 task sub-bundle decomposition with concurrent dispatch recommended. 14 OQs surfaced (10 brief + 4 NEW); operator-paired triage required before writing-plans dispatch. Pre-Codex Expansion #6 + #7 FIRST RUN BINDING at brainstorming phase; verified clean at brainstorm pre-Codex. ~360+ cumulative ZERO Co-Authored-By footer streak preserved through this commit. PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding (separate from this dispatch).*
