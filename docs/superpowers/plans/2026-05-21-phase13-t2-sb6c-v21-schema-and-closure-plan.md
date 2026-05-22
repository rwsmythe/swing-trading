# Phase 13 T2.SB6c — v21 schema + SB6 closure implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land v21 schema (2 NULLable trades backlinks via `trades.candidate_id` + `trades.pattern_evaluation_id`) atomically per §A.14 paired discipline AND resolve the 10 SB6 closure items (4 Gap A chart-surface wirings + 6 Gap B review-form / queue / metric-tile data-completeness items) AND close the §1.5 amendment scope additions (pipeline-side `_step_charts` chart_renders cache write-through + one-shot `labeler_evidence_json` backfill script) — closure-dispatch intent: ZERO new V1 STUBs.

**Architecture:** Five-task decomposition (T-A.6c.1..T-A.6c.5) with concurrent dispatch recommended for the first three (no inter-task schema dependency between T-A.6c.1's migration landing AND T-A.6c.2's chart-surface wiring AND T-A.6c.3's no-schema review-form completeness + labeler backfill). T-A.6c.4 consumes Delta A + Delta B + threads the new `pattern_evaluation_id` hidden form anchor through `POST /trades/entry` with a 5-tier rejection ladder + claim-consistency gate. T-A.6c.5 is the closer (1 fast E2E + ruff sweep + cross-bundle pin row 12 promote).

**Tech Stack:** Python 3.14, SQLite (schema_version table), FastAPI + HTMX + Starlette + Jinja2, matplotlib (SVG inline renderers via existing T-A.6.1 substrate), pytest. Forward-binding to V2: many-to-many `trade_pattern_evaluations` link table; labeler subagent contract extension (Path A); `pattern_evaluations.candidate_id` direct column; `--enforce-stepwise` migration flag; Phase 6 `chart_pattern_algo` enum unification with Phase 13 detector enum.

---

## §A Status + scope

### §A.1 Brainstorming-phase substrate

This plan consumes the brainstorming-phase spec at [`docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`](../specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md) (660 lines; 8 Codex rounds; ZERO ACCEPT-WITH-RATIONALE; converged at R8 NO_NEW_CRITICAL_MAJOR with 1 CRITICAL + 22 MAJOR + 11 MINOR cumulative findings, ALL RESOLVED in-place) AND the dispatch brief at [`docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md`](../../phase13-t2-sb6c-writing-plans-dispatch-brief.md) (AMENDED 2026-05-21 PM #5 at commit `c9bd715` post-operator-witnessed S2-S8 gate verification per §1.5).

All 14 OQs from the brainstorm spec are OPERATOR-AFFIRMED VERBATIM per orchestrator-paired chat triage 2026-05-21 PM #5; dispositions encoded BINDING in this plan; no operator-paired re-triage required at writing-plans phase.

### §A.2 v21 schema delta scope (2 deltas; Delta C OBSOLETE per brainstorm spec Expansion #2 catch)

- **Delta A**: `trades.candidate_id INTEGER NULL` + FK to `candidates(id) ON DELETE SET NULL` + `idx_trades_candidate_id`.
- **Delta B**: `trades.pattern_evaluation_id INTEGER NULL` + FK to `pattern_evaluations(id) ON DELETE SET NULL` + `idx_trades_pattern_evaluation_id`.
- **Delta C** OBSOLETE: `watchlist_close_track_flags` already lives in v20 per [`swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:262-307`](../../../swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql). T4.SB consumes the existing schema; SB6c does NOT take Q4 surfaces (OQ-2 LOCK).

v20 LOCKED streak (10 sub-bundles since T-A.1.1: T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 + T2.SB5 + T3.SB3 + T2.SB6a + T2.SB6b) ENDS at T-A.6c.1 executing-plans landing.

### §A.3 SB6 closure scope (10 items + 2 §1.5 amendments)

Inherited from brainstorm spec §1.2:

- **Gap A** (4 chart-surface wirings; no schema dep): A.1 hyp-rec detail VM 800x500 SVG; A.2 position detail VM 800x500 SVG with fill markers; A.3 WatchlistVM template thumbnail; A.4 exemplar cache-miss live-render write-through.
- **Gap B** (6 review-form / queue / metric-tile items): B.1 trend-template state live (no schema); B.2 volume profile live (no schema); B.3 POST `/patterns/{candidate_id}/review` label_source split (Delta A dep); B.4 review-form outcome distribution bucketing (Delta A dep); B.5 metric tile reached_1r + hit_stop (Delta A dep); B.6 queue criterion 3 weather-state-aware variant (no schema).
- **§1.5.1 amendment** (NEW at T-A.6c.2 scope): pipeline-side `swing/pipeline/runner.py:_step_charts` `chart_renders` cache write-through for 4 surfaces (watchlist_row + hyprec_detail + position_detail + market_weather). `theme2_annotated` remains exemplar-keyed handled at `/patterns/exemplars` cache-miss read path per existing T2.SB6b shipped behavior.
- **§1.5.2 amendment** (NEW at T-A.6c.3 scope): one-shot `labeler_evidence_json` backfill script (Path C; operator-invoked via `swing/cli.py:patterns_exemplars_backfill_labeler_evidence`; idempotent; ASCII-only; synthesizes `rule_criteria` from `geometric_score_json` + copies `geometric_evidence_narrative` to `narrative` key; fail-soft per row).

Path A (labeler subagent emit contract widening) is V2-BANKED per §I.4 for fresh exemplars labeled post-T2.SB6c executing-plans.

### §A.4 Non-scope (explicit; LOCK preserved)

- Q4 close-tracking flag surfaces (web POST flag/unflag + CLI subcommands + UI badge + auto-clear-on-position-open) — T4.SB owns; PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding per memory.
- Phase 13.5 drift surfaces (>=1 month operating data required).
- ZERO new Schwab API calls (L2 LOCK preserved).
- Interactive client-side JS chart library (V2).
- Many-to-many `trade_pattern_evaluations` link table (V2 schema dispatch).
- `--enforce-stepwise` migration runner flag (V2).
- Phase 6 `chart_pattern_algo` enum unification with Phase 13 detector enum (V2 schema dispatch).

### §A.5 OQ disposition table (operator-affirmed VERBATIM)

| OQ | Disposition (BINDING) |
|---|---|
| **OQ-1** Backfill semantics for `trades.candidate_id` for existing trades | NULL only (no heuristic ticker+date match) |
| **OQ-2** SB6c includes Q4 surfaces? | NO — Q4 surfaces locked to T4.SB; schema already in v20 |
| **OQ-3** v21 backup-gate predicate | strict `pre_version == 20 AND target >= 21` |
| **OQ-4** Cleared_by_reason enum scope | N/A — already in v20 (`operator_cleared` / `auto_cleared_on_position_open`) |
| **OQ-5** Watchlist-flag partial UNIQUE | N/A — already in v20 (`WHERE cleared_at IS NULL`) |
| **OQ-6** Outcome bucketing thresholds | `reached_1r` = max(daily_high since entry_date) >= entry_price + (entry_price - initial_stop); `hit_stop` = ANY fill at <= initial_stop OR (`trade.state IN ('closed', 'reviewed') AND realized_R_if_plan_followed < 0`); suppression at n<5 per Phase 10 honesty.suppress_for_n |
| **OQ-7** Phase 13 brainstorm D-Q4.2 web+CLI confirmation | N/A for SB6c |
| **OQ-8** Migration backup file naming | `swing-pre-phase13-sb6c-migration-<ISO>.db` |
| **OQ-9** Read-path mapper column position | row[52] = candidate_id; row[53] = pattern_evaluation_id |
| **OQ-10** Sub-bundle decomposition | 5 tasks T-A.6c.1..T-A.6c.5; concurrent dispatch T-A.6c.1 + T-A.6c.2 + T-A.6c.3 recommended |
| **OQ-11** trades.candidate_id lifecycle population | At trade-entry-form lock time inside `with conn:` block IF `trade_origin IN ('pipeline_aplus', 'pipeline_watch_hyp_recs', 'pipeline_watch_manual')` AND candidates lookup returns row; ELSE NULL |
| **OQ-12** trades.pattern_evaluation_id lifecycle population | CLOSURE-COMMITTED at T-A.6c.4: thread anchor via hidden form input + 5-tier rejection + claim consistency-check gate; manual-off-pipeline persists NULL |
| **OQ-13** Metric tile cohort denominator | LEFT JOIN denominator = pattern_evaluations rows with matching pattern_class AND operator-confirmed (`pattern_exemplars.final_decision='confirmed'`); numerator = subset with `trades.candidate_id` AND outcome bucket met; suppression at denominator<5 |
| **OQ-14** Volume profile data path | `swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)`; fetch-on-cache-miss ACCEPTED |

---

## §B Schema deltas (Delta A + Delta B; verbatim from brainstorm spec §2)

### §B.1 Delta A — `trades.candidate_id` backlink

**Column shape:**

```sql
ALTER TABLE trades ADD COLUMN candidate_id INTEGER
    REFERENCES candidates(id) ON DELETE SET NULL;
```

- **Type:** `INTEGER` (matches `candidates.id PRIMARY KEY AUTOINCREMENT` per migration 0001 line 24-25).
- **NULL/NOT-NULL:** NULLable (pre-v21 existing rows lack guaranteed candidates; `manual_off_pipeline` trade_origin legitimately has no candidate_id).
- **DEFAULT:** none.
- **CHECK:** none at column level; FK enforces existence at write time when populated.
- **FK:** `REFERENCES candidates(id) ON DELETE SET NULL`. Rationale: candidates rotate per pipeline run lifecycle; FK is advisory rather than load-bearing; ON DELETE SET NULL preserves trade row when candidate decays.
- **Index:** `CREATE INDEX idx_trades_candidate_id ON trades(candidate_id);` — supports LEFT JOIN from `pattern_evaluations` (via `candidates.id`) into trades for outcome bucketing (spec §5.10 line 775).

**Backfill semantics:** NULL for all pre-v21 existing rows (OQ-1 LOCK; no heuristic match).

**Lifecycle population (OQ-11):** at trade-entry-form lock time inside the `with conn:` block where the `trades` INSERT happens, populate `candidate_id` IF (1) `trade_origin IN ('pipeline_aplus', 'pipeline_watch_hyp_recs', 'pipeline_watch_manual')` AND (2) the candidates lookup returns a row. CRITICAL: `candidates` is keyed on `evaluation_run_id` (per [`swing/data/migrations/0001_phase1_initial.sql:24-26`](../../../swing/data/migrations/0001_phase1_initial.sql) + [`swing/trades/origin.py:10-11`](../../../swing/trades/origin.py) BINDING text "candidates.evaluation_run_id (NOT pipeline_run_id) is the join key"). Two valid lookup paths:

- Path 1 (if entry context carries `evaluation_run_id` via `_latest_complete_evaluation_run_id` at [`swing/trades/origin.py:27-37`](../../../swing/trades/origin.py)): `SELECT id FROM candidates WHERE evaluation_run_id = ? AND ticker = ? ORDER BY id DESC LIMIT 1`.
- Path 2 (if entry context carries `pipeline_run_id`): `SELECT c.id FROM candidates c INNER JOIN pipeline_runs pr ON c.evaluation_run_id = pr.evaluation_run_id WHERE pr.id = ? AND c.ticker = ? ORDER BY c.id DESC LIMIT 1`. The `pipeline_runs.evaluation_run_id` column was added by migration [`0006_pipeline_chart_linkage.sql:18`](../../../swing/data/migrations/0006_pipeline_chart_linkage.sql) specifically to support this resolver pattern.

DO NOT MIX the two — passing an `evaluation_run_id` into a `pipeline_runs.id` filter would silently miss/wrong-match.

If `trade_origin = 'manual_off_pipeline'` OR the candidate lookup returns no row, leave `candidate_id = NULL`.

### §B.2 Delta B — `trades.pattern_evaluation_id` backlink

**Column shape:**

```sql
ALTER TABLE trades ADD COLUMN pattern_evaluation_id INTEGER
    REFERENCES pattern_evaluations(id) ON DELETE SET NULL;
```

- **Type:** `INTEGER` (matches `pattern_evaluations.id PRIMARY KEY AUTOINCREMENT` per v20 migration 0020 line 231).
- **NULL/NOT-NULL:** NULLable. pattern_evaluations is a Phase 13 table; `manual_off_pipeline` trades never have one.
- **DEFAULT:** none.
- **CHECK:** none.
- **FK:** `REFERENCES pattern_evaluations(id) ON DELETE SET NULL`. pattern_evaluations rotates per pipeline run via FK to `pipeline_runs.id CASCADE` (v20 migration 0020 line 232-233); the trade backlink must survive the cascade.
- **Index:** `CREATE INDEX idx_trades_pattern_evaluation_id ON trades(pattern_evaluation_id);` — supports per-pattern_class cohort joins (spec §5.10 line 775 outcome bucketing per pattern class).

**Backfill semantics:** NULL for all pre-v21 existing rows.

**Lifecycle population (OQ-12 CLOSURE-COMMITTED):** at trade-entry-form lock time, populate `pattern_evaluation_id` IF AND ONLY IF the entry form carries an explicit `pattern_evaluation_id` hidden anchor that the operator's flow has caused to be threaded through. T-A.6c.4 COMMITS to threading the anchor (V1 STUB explicitly in scope to fix; closure-dispatch intent). See §C.5 anchor-threading scope.

### §B.3 SVAI (schema-version-aware INSERT) pattern — REVISED per Codex R2 MAJOR #1 + brainstorm spec §2.1

Even though both new columns are NULLable, the `INSERT INTO trades` at [`swing/data/repos/trades.py:120`](../../../swing/data/repos/trades.py) MUST adopt the schema-version-aware runtime-branch pattern (precedent: T3.SB1 `fills.py:51-53` SVAI). Rationale: SQL referencing columns absent on a v20 fixture connection raises `OperationalError: no such column`; NULLable defaults do NOT cover that case.

Runtime branch via `PRAGMA table_info('trades')` returns the column list; if BOTH `candidate_id` AND `pattern_evaluation_id` are present in the schema, use the extended INSERT (with the 2 new column placeholders); else fall back to the legacy column list (omit the 2 new columns; let `INSERT` use schema defaults — which means the row gets NULL via SQLite default-NULL semantics on the missing columns). This is the same `if "fill_origin" in cols:` shape used at fills.py:53 — only one new conditional, with the legacy + extended INSERT both fully spelled out in code.

### §B.4 Migration file shape

**New migration:** `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`.

Atomic landing per CLAUDE.md gotcha "`executescript()` implicit COMMIT": explicit `BEGIN;` ... `COMMIT;` wrap with 4 DDL statements (2 ALTER + 2 CREATE INDEX) + 1 schema_version update (5 statements + 1 row UPDATE = 6 statements total inside the BEGIN/COMMIT block).

Migration body (skeleton; lands at T-A.6c.1 Step 6):

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

**SQLite ALTER TABLE ADD COLUMN constraint** (binding watch item): SQLite `ALTER TABLE ADD COLUMN` permits `REFERENCES` clause for newly-added columns (per SQLite docs §"Adding A New Column"). The FK is parsed + honored on subsequent writes/deletes but is NOT enforced retroactively against existing rows (NULL backfill satisfies any FK trivially). Discriminating test §G.1 Step 1 asserts FK parsing succeeds via `PRAGMA foreign_key_list('trades')`.

### §B.5 Backup-gate wiring per Codex R1 MAJOR #3 (REVISED full implementation scope)

The backup gate is wired in [`swing/data/db.py:run_migrations`](../../../swing/data/db.py), NOT in `_apply_migration` per se. T-A.6c.1 atomic landing MUST:

1. **Bump `EXPECTED_SCHEMA_VERSION = 21`** in `swing/data/db.py:39` (currently 20).
2. **Add `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES`** constant after `PHASE13_PRE_MIGRATION_EXPECTED_TABLES` (currently at `swing/data/db.py:108-111`): `PHASE13_PRE_MIGRATION_EXPECTED_TABLES | {"pattern_exemplars", "chart_renders", "pattern_evaluations", "watchlist_close_track_flags", "watchlist_close_track_flag_events"}` (the 5 v20-shipped tables; derived deterministically from PHASE13 set per the existing precedent).
3. **Add `_phase13_sb6c_backup_gate(...)` function** mirroring `_phase13_backup_gate` at `swing/data/db.py:634-677` with strict equality: `if target_version < 21 or current_version != 20: return`.
4. **Add `_create_pre_phase13_sb6c_migration_backup(...)` function** mirroring `_create_pre_phase13_migration_backup` at `swing/data/db.py:446` with filename `swing-pre-phase13-sb6c-migration-<ISO>.db` (OQ-8 LOCK).
5. **Wire into `run_migrations`** call chain BEFORE the v21 migration applies, after the existing `_phase13_backup_gate(...)` call at `swing/data/db.py:728`.

Backup-gate strict equality (OQ-3 LOCK) is the canonical pattern: copy the Phase 13 (v20) backup-gate clause VERBATIM; do NOT paraphrase to `<=`. Multi-version jumps from pre-v20 baselines bypass this gate by design — the v20 boundary's own `_phase13_backup_gate` fires at `pre_version == 19`, and the operator who jumps v19→v21 directly accepts that no SB6c-specific backup separates the two boundaries.

---

## §C Atomic-landing strategy (§A.14 paired discipline) + §1.5 amendments

Per cumulative discipline (CLAUDE.md gotchas T3.SB2 hotfix `cf3c489` + Phase 12 C.A T-A.2 + T3.SB3 R1 M#1 + T2.SB6a R1 CRITICAL #1) + the brainstorm spec §4 atomic-landing scope:

### §C.1 Atomic landing scope for Delta A + Delta B (lands in ONE commit at T-A.6c.1)

ONE task / ONE commit lands ALL of:

1. **Schema migration file** `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` per §B.4.
2. **Migration runner extension** in `swing/data/db.py` per §B.5: EXPECTED_SCHEMA_VERSION bump + PHASE13_SB6C constant + `_phase13_sb6c_backup_gate` + `_create_pre_phase13_sb6c_migration_backup` + `run_migrations` wire-in.
3. **Python constant**: NONE required (no enum/Literal for INTEGER FK — plain `int | None`).
4. **Dataclass extension**: `Trade.candidate_id: int | None = None` + `Trade.pattern_evaluation_id: int | None = None` in `swing/data/models.py`.
5. **Read-path mapper**: `_row_to_trade` extended with `candidate_id=row[52]` + `pattern_evaluation_id=row[53]`; `_TRADE_SELECT_COLS` extended with both column names at positions 52 + 53; index map comment block updated (lines 348-365 currently 0..51; extends to 0..53).
6. **Write-path INSERT extension (SVAI per §B.3)**: `INSERT INTO trades` at `swing/data/repos/trades.py:120` extended with BOTH columns via runtime branch. `insert_trade_with_event(...)` signature accepting `candidate_id: int | None = None` AND `pattern_evaluation_id: int | None = None` kwargs (added on `Trade` dataclass; INSERT pulls from `trade.candidate_id` + `trade.pattern_evaluation_id` per fills.py:69-71 precedent).
7. **N-mirror auditing (T3.SB2 hotfix `cf3c489` discipline)**: grep `swing/` for ALL other hardcoded SELECT-trade-column-lists. Acceptance: implementer at T-A.6c.1 Step 2 runs `Grep "SELECT .* FROM trades" swing/` + enumerates findings; any direct-SQL trade column readers found extend in the SAME commit. Expected to be ZERO additional callsites — `_row_to_trade` is the canonical reader; `_TRADE_SELECT_COLS` is the canonical column list — but the audit MUST run + be enumerated in the commit message body.
8. **All 17 paired discriminating tests** (8 for Delta A per brainstorm spec §2.1 + 9 for Delta B per §2.2) + 4 backup-gate tests per §B.5 — see §G.1 for the full test enumeration.

LOCK per §A.14: schema CHECK + Python constant (none here) + dataclass validator + read-path mapper + write-path INSERT extension + ALL discriminating tests land in ONE commit. NO migration-then-Python-then-validator split.

### §C.2 Atomic landing scope for SB6 closure items (lands across T-A.6c.2 + T-A.6c.3 + T-A.6c.4)

Per Phase 13 plan §G.9 cumulative precedent, closure items can land across multiple tasks within T2.SB6c. Atomic-landing discipline applies INSIDE each task:

- T-A.6c.2 (Gap A): VM extensions + template extensions + `_step_charts` write-through + ALL discriminating tests for the 4 surfaces land in ONE commit.
- T-A.6c.3 (Gap B.1 + B.2 + B.6 + labeler backfill): VM extensions + template extensions + active_learning extension + CLI subcommand + ALL discriminating tests land in ONE commit.
- T-A.6c.4 (Gap B.3 + B.4 + B.5 + entry-form anchor threading + entry-path mapping fix): VM + builder + template + POST handler + service-layer + read-path consumer + ALL discriminating tests land in ONE commit.

### §C.3 §1.5.1 amendment scope (pipeline-side `_step_charts` chart_renders cache write-through; T-A.6c.2)

Per dispatch brief §1.5.1: `chart_renders` table is EMPTY across ALL surfaces post-T2.SB6b merge (confirmed via direct DB query against operator's production DB; root cause: `swing/pipeline/runner.py:_step_charts` does NOT call `refresh_chart_render` for any surface; production callers exist only at `swing/web/routes/dashboard.py:107` operator-triggered button + `swing/web/view_models/patterns/exemplars.py:258` import-but-never-invoke).

T-A.6c.2 closes the loop. Watch items per dispatch brief §3.5b:

- `_step_charts` MUST call `refresh_chart_render(conn, ChartRender(...))` for each of 4 surfaces during pipeline run: `watchlist_row` + `hyprec_detail` + `position_detail` + `market_weather`. `theme2_annotated` remains exemplar-keyed handled separately at `/patterns/exemplars` cache-miss read path per T2.SB6b shipped behavior (not changed by this amendment).
- Cache key shape per the T2.SB6a substrate `ChartRender.__post_init__` semantic validator (per T2.SB6a R1 CRITICAL #1 LOCK): run-bound surfaces (`watchlist_row` + `hyprec_detail` + `market_weather`) require non-NULL `pipeline_run_id`; `position_detail` requires NULL `pipeline_run_id`; `theme2_annotated` requires both `pattern_class` + `pipeline_run_id` non-NULL.
- **F6 transient-empty defense at construction barrier** (T2.SB6a R1 MAJOR #2 LOCK): `ChartRender(chart_svg_bytes=b"")` raises `ValueError` per the substrate validator. If a renderer emits empty bytes in `_step_charts`, the pipeline step MUST catch `ValueError` + WARN-log + continue (NOT blank the existing cache row per F6 cumulative gotcha).
- DELETE-then-INSERT atomic per §A.15 + BEGIN IMMEDIATE / COMMIT per §A.12 substrate contract — caller-tx semantics; `_step_charts` opens its own fenced_write transaction (existing pipeline step pattern) before invoking `refresh_chart_render` which is a caller-tx-required substrate function.
- Discriminating test per surface: assert post-`_step_charts` the `chart_renders` table has 1 row per active `(ticker, surface, pipeline_run_id)` tuple for run-bound surfaces + 1 row per ticker (NULL pipeline_run_id) for `position_detail`. Assert F6 transient-empty defense: monkeypatch renderer to return `b""` for one ticker → assert WARN logged + existing cache row preserved verbatim (per T2.SB6a Codex R1 MAJOR #2 discriminating test pattern).

### §C.4 §1.5.2 amendment scope (labeler_evidence_json one-shot backfill script; T-A.6c.3)

Per dispatch brief §1.5.2: all 34 existing pattern_exemplars rows carry `labeler_evidence_json` with keys `['confidence', 'evaluation', 'geometric_evidence_narrative']` — MISSING the `rule_criteria` + `narrative` keys that T-A.6.6b's enhanced `/patterns/exemplars` rendering consumes. Page renders graceful "(no rule_criteria payload available)" / "(no narrative payload available)" placeholders per design.

T-A.6c.3 ships Path C (pragmatic backfill). Watch items per dispatch brief §3.5c (REVISED per Codex R1 MAJOR #2 closure — source is dedicated COLUMN, NOT a key inside the labeler_evidence_json payload):

- Synthesis rule for `rule_criteria` array: enumerate per-criterion entries derived from the dedicated `pattern_exemplars.geometric_score_json` COLUMN (verified at migration 0020 line 94) — 5-detector rule pass/fail + threshold + tolerance per spec §5.2-§5.6 patterns. NOT from `payload.get("geometric_score_json")` because existing 34 exemplars' `labeler_evidence_json` payload carries only `['confidence', 'evaluation', 'geometric_evidence_narrative']` keys. Preserve existing structural_evidence_json keys verbatim.
- Synthesis rule for `narrative`: copy `geometric_evidence_narrative` (the existing payload key) verbatim into a NEW `narrative` key (preserve original `geometric_evidence_narrative` key for audit-trail; do NOT delete).
- Invariant #5 (migration 0020 lines 149-160) LOCK respected: skip rows where `labeler_evidence_json IS NULL` (label_source IN ('closed_loop_review', 'organic_trade_history', 'synthetic', 'perturbation') class; nothing to augment).
- Idempotency: second run is no-op on already-augmented payloads (detect via `rule_criteria` AND `narrative` keys already present); preserves first-run output exactly.
- Fail-soft per row: exception in single-row synthesis WARN-logs + skips that row; continues remaining rows; final summary reports `(augmented: N; skipped: M)`.
- Operator-invoked subcommand at `swing/cli.py:patterns_exemplars_backfill_labeler_evidence`; ASCII-only output per Windows cp1252 stdout safety.
- NEW repo helper `update_exemplar_labeler_evidence_json(conn, exemplar_id, new_json)` lands in T-A.6c.3 scope at `swing/data/repos/pattern_exemplars.py` (existing repo has `insert_exemplar` + `get_exemplar_by_id` + `list_exemplars`; no update helper exists pre-T-A.6c.3 per Codex R1 MINOR #1 audit).
- Path A (labeler subagent emit contract widening) banked V2 per §I.4 — fresh exemplars labeled post-T2.SB6c executing-plans will need the V2 contract extension.

### §C.5 Anchor-threading scope at T-A.6c.4 (OQ-12 CLOSURE-COMMITTED; per brainstorm spec §2.2)

V1 STUB explicitly in scope to fix. The plan threads the anchor through 4 layers atomically:

**Layer 1 — VM/builder extensions (per Codex R7 MAJOR #1):**

- Extend `EntryFormVM` (or canonical entry-form VM dataclass; verify exact name at executing-plans phase via `Grep "class EntryFormVM\\|class.*EntryForm" swing/web/view_models/trades.py`) with 3 new fields: `pattern_evaluation_id: int | None`, `claimed_pattern_evaluation_anchor: bool`, `pipeline_run_id_at_form_render: int | None`.
- Extend `build_entry_form_vm(...)` builder to populate the 3 fields when the entry context provides a `pattern_evaluations` row (looked up via `(pipeline_run_id, ticker)` for the hyp-rec / pipeline-watch origins).
- Extend `HypRecsExpandedVM` (existing dataclass at `swing/web/view_models/dashboard.py:567-603`) with `pattern_evaluation_id: int | None` field per hyp-rec row + `pipeline_run_id: int | None` field. Extend `build_hyp_recs_expanded(...)` builder to JOIN/query `pattern_evaluations` for each hyp-rec ticker against the current pipeline_run_id.

**Layer 2 — Template emission (per Codex R5 MAJOR #2):**

- Extend `swing/web/templates/partials/trade_entry_form.html.j2` (canonical entry-form template) — emit hidden inputs `pattern_evaluation_id`, `claimed_pattern_evaluation_anchor`, `pipeline_run_id_at_form_render` when VM fields populated.
- Extend `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` at line 41-45 (existing hyp-rec → entry-form transition; currently passes only `ticker` + `origin=hyp-recs`) — extend with `pattern_evaluation_id` query param when a `pattern_evaluations` row exists for the (run, ticker) tuple. Also extend any other entry-form-link emitters (watchlist row entry-link if applicable; verify at executing-plans phase via `Grep -r "trade_entry_form\\|/trades/entry" swing/web/templates/`).

**Layer 3 — POST handler 5-tier rejection ladder (per Codex R5 MAJOR #1 + R6 MAJOR #1/#2/#3 + R7 Minor #1):**

POST `/trades/entry` at `swing/web/routes/trades.py:413` MUST use the same `_reject_anchor` helper pattern at `swing/web/routes/trades.py:896-911` (T3.SB1 precedent for Schwab `schwab_source_value_json` anchor; mirror EXACTLY) with 5 tiers:

- **Tier (a) malformed integer on `pattern_evaluation_id`** → 400 + clear anchor on recovery form.
- **Tier (b) `pattern_evaluations` row not found by id** → 400 + clear.
- **Tier (c) row found but `ticker` differs from operator-submitted ticker** → 400 + clear.
- **Tier (d) `pipeline_run_id_at_form_render` form field differs from the row's `pipeline_run_id`** OR form field is MISSING while `pattern_evaluation_id` is PRESENT (missing-anchor symmetry per Codex R6 MAJOR #3) → 400 + clear.
- **Tier (e) anchor present BUT server-derived `trade_origin` is `manual_off_pipeline`** (per Codex R6 MAJOR #1 — `swing/trades/origin.py:derive_trade_origin` at line 52 is the canonical resolver; consumes `(conn, ticker, entry_path: EntryPath)` per line 52-54): after the entry-path mapping fix below, if `derive_trade_origin(conn, ticker, mapped_entry_path) == 'manual_off_pipeline'` AND `pattern_evaluation_id` anchor is present → 400 + clear.

**`claimed_pattern_evaluation_anchor` consistency-check gate** (per Codex R4 MAJOR #3 + R5 MAJOR #3; mirrors `claimed_auto_fill` at `swing/web/routes/trades.py:876-878` for Schwab anchor):

- Missing form field coerces to `"false"` (default-safe per R5 MAJOR #3 missing-value semantics).
- After coercion: (i) `claimed == "true"` AND anchor MISSING → 400 + clear (claim without anchor); (ii) `claimed == "false"` (incl. omitted) AND anchor PRESENT → 400 + clear (anchor without claim); (iii) server-derived `trade_origin == 'manual_off_pipeline'` AND `claimed == "true"` → 400 + clear (manual origin contradicts claim; per Codex R7 Minor #1 wording fix — value-domain is SERVER-DERIVED, NOT form UI origin).

**Layer 4 — Entry-path mapping fix at `swing/web/routes/trades.py:1095`** (per Codex R6 MAJOR #2):

The existing POST handler at `swing/web/routes/trades.py:1095` hardcodes `entry_path=EntryPath.MANUAL_WEB_FORM` for ALL web entries. T-A.6c.4 MUST extend that line so UI `origin='hyp-recs'` → `EntryPath.HYP_RECS_BUTTON`; UI `origin='watchlist'` OR manual → `EntryPath.MANUAL_WEB_FORM`. Without this fix, `derive_trade_origin` cannot distinguish `pipeline_watch_hyp_recs` from `pipeline_watch_manual`; tier (e) coverage would be weak.

**Recovery form anchor-clear discipline** (T3.SB1 R3 M#2 LOCK preserved): on 400 rejection, the recovery form re-render MUST clear the bad anchor (pass `submitted_pattern_evaluation_id=None` + `submitted_claimed_pattern_evaluation_anchor=False` + `submitted_pipeline_run_id_at_form_render=None` to the re-render helper, NOT raw rejected values) — otherwise operator trapped in repeated 400s on resubmit replays.

**Server-recompute discipline** (T3.SB3 R1 M#2 LOCK): the POST handler MUST re-derive `pattern_evaluation_id` from canonical state at POST time (via `(pipeline_run_id_at_form_render, ticker)` lookup against `pattern_evaluations`), NOT consume operator-submitted hidden input verbatim. The 5-tier rejection ladder rejects tampered anchors; only the re-derived authoritative value goes into `insert_trade_with_event(..., pattern_evaluation_id=...)`.

---

## §D Closure consumer mapping (per brainstorm spec §3)

### §D.1 Gap A — chart-surface wiring (4 items + §1.5.1 amendment)

| Item | Spec source | Wiring | Disposition |
|---|---|---|---|
| **A.1** Hyp-rec detail VM 800x500 SVG | §4.2 chart surface inventory row 2 | `swing/web/view_models/recommendations.py:RecommendationsVM` extend with `hyprec_detail_chart_svg_bytes: bytes | None`; route handler at `swing/web/routes/recommendations.py` populates via `get_cached_chart_svg(conn, ticker, surface='hyprec_detail', pipeline_run_id=<run_id>)`; template at `swing/web/templates/recommendations/detail.html.j2` renders inline `<svg>`. | LIVE (no schema dep) |
| **A.2** Position detail VM 800x500 SVG with fill markers | §4.2 row 3 | `swing/web/view_models/trades.py:TradeDetailVM` extend with `position_chart_svg_bytes: bytes | None`; route handler populates via `get_cached_chart_svg(conn, ticker, surface='position_detail', pipeline_run_id=None)` per v20 §3.2 cache key shape (position_detail is run-agnostic); template renders inline. | LIVE (no schema dep) |
| **A.3** WatchlistVM template thumbnail | §4.2 row 1 | `swing/web/templates/partials/watchlist_row.html.j2` extend to render `vm.watchlist_chart_svg_bytes` (already populated on WatchlistVM at T2.SB6b R1 MAJOR #5 partial fix `94e4418`). | LIVE (no schema dep) |
| **A.4** Exemplar cache-miss write-through | spec §4.4 + plan T-A.6.6b §G.9 line 2240 | `swing/web/view_models/patterns/exemplars.py` cache-miss path: after `render_theme2_annotated_svg` returns bytes, call `refresh_chart_render(conn, ChartRender(...))` per v20 §3.2 substrate write-through. | LIVE (no schema dep) |
| **§1.5.1 amendment** Pipeline-side `_step_charts` write-through | dispatch brief §1.5.1 | `swing/pipeline/runner.py:_step_charts` extended to call `refresh_chart_render(conn, ChartRender(...))` for `watchlist_row` + `hyprec_detail` + `position_detail` + `market_weather` during pipeline run. Cache key shape per §C.3 (run-bound surfaces non-NULL pipeline_run_id; position_detail NULL pipeline_run_id). F6 transient-empty defense at ChartRender construction barrier. | LIVE (closure-committed; substrate reuse) |

### §D.2 Gap B — review-form / queue / metric-tile data-completeness (6 items + §1.5.2 amendment)

| Item | Spec source | Schema dep | Wiring | Disposition |
|---|---|---|---|---|
| **B.1** Trend-template state live | §5.10 line 771 | NO | `swing/web/view_models/patterns/review_form.py:PatternReviewFormVM` extend with `trend_template_state: str` field. Read via `swing.patterns.foundation.current_stage(conn, ticker, asof_date)` (Phase 13 trend-template wrapper at `swing/patterns/foundation.py:745`; V1 returns `'stage_2'` when all 8 TT1-TT8 criteria pass on most-recent `action_session_date <= asof_date` candidate; else `'undefined'`). `asof_date` is the pattern_evaluation's `window_end_date` (the trend-template snapshot at the evaluated window's right edge); fully-deterministic + no session-anchor gotcha because the value is window-bound, not session-anchor-bound. | LIVE (no schema dep) |
| **B.2** Volume profile live | §5.10 line 773 | NO | `PatternReviewFormVM` extend with `volume_profile: VolumeProfileRow` (NEW frozen dataclass: `recent_30session_volume_sum: int`, `prior_50day_avg_volume: float`, `ratio_pct: float`). Read OHLCV via `swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)` (50 + 30 buffer; OQ-14 LOCK). Template renders inline SVG sparkline (SVG bytes don't flow through stdout — escape from cp1252 risk). | LIVE (no schema dep) |
| **B.3** POST `/patterns/{candidate_id}/review` label_source split (URL parameter named `candidate_id` per shipped T2.SB6b code; value is a `pattern_evaluations.id`) | §5.10 lines 785-790 | YES — Delta A | POST handler at `swing/web/routes/patterns.py:patterns_review_post` (T2.SB6b T-A.6.3) extends per §D.3 cross-row lookup discipline. If row exists (per the SQL in §D.3) AND operator decision is `confirm`, emit `label_source='organic_trade_history'`; else emit `label_source='closed_loop_review'`. | RESOLVED via Delta A |
| **B.4** Review form outcome distribution bucketing | §5.10 line 775 | YES — Delta A | `PatternReviewFormVM` extend `OutcomeDistributionRow` with `reached_1r_pct: float | None` + `hit_stop_pct: float | None` (None when n<5 per honesty.suppress_for_n). Compute per OQ-6 thresholds. See §D.3 cohort scope. | RESOLVED via Delta A |
| **B.5** Metric tile reached_1r + hit_stop | plan §G.9 T-A.6.5 + spec §5.10 line 775 | YES — Delta A | `swing/metrics/pattern_outcomes.py:build_pattern_outcome_rows` extend `PatternOutcomeRow` with `reached_1r_count + reached_1r_pct + hit_stop_count + hit_stop_pct` fields. LEFT JOIN `pattern_evaluations` to `trades` via `candidate_id`. Wilson-CI per Phase 10 honesty.wilson_ci; suppression at n<5 per honesty.suppress_for_n. | RESOLVED via Delta A |
| **B.6** Queue criterion 3 weather-state-aware | §5.10 line 799 | NO | `swing/patterns/active_learning.py:prioritize_candidates` extend criterion 3 (`underrepresented_regime`) to consume current `weather_runs.status` value (column-verified against `swing/data/migrations/0003_phase2_pipeline_trades.sql:4-15`; values 'Bullish'/'Caution'/'Bearish'; ticker per `cfg.rs.benchmark_ticker` default 'QQQ'). Per-pattern_class exemplar count against the SAME-`status` historical baseline derived via JOIN to `weather_runs` at-or-before `pattern_exemplars.created_at` (no new column; read-side computation per `pattern_exemplars` schema audit — no `weather_state_at_labeling` column exists). | LIVE (no schema dep) |
| **§1.5.2 amendment** labeler_evidence_json one-shot backfill | dispatch brief §1.5.2 | NO | NEW `swing/cli.py:patterns_exemplars_backfill_labeler_evidence` operator-invoked subcommand per §C.4. | LIVE (Path C; Path A V2-banked) |

### §D.3 Cross-row lookup discipline (Expansion #7 BINDING per dispatch brief §3.1.7)

For each POST handler in Gap B.3 / Gap B.4 / Gap B.5 that consumes operator input AND looks up cross-row state, enumerate the SCOPE of the lookup explicitly per spec wording:

**Gap B.3 lookup scope** (label_source split): per-candidate, NOT per-ticker. The URL path parameter is named `candidate_id` per shipped T2.SB6b code at `swing/web/routes/patterns.py:372 + 399`, but the VALUE is actually a `pattern_evaluations.id` (the handler at line 434 calls `get_evaluation_by_id(conn, candidate_id)`). Naming quirk preserved; SB6c does NOT rename. Resolution chain:

```
URL path int -> pattern_evaluations.id
            -> SELECT pattern_evaluations.pipeline_run_id, pattern_evaluations.ticker
            -> JOIN to candidates via:
               pipeline_runs.evaluation_run_id = candidates.evaluation_run_id
                 AND pipeline_runs.id = pattern_evaluations.pipeline_run_id
                 AND candidates.ticker = pattern_evaluations.ticker
            -> use that candidates.id as lookup target for trades.candidate_id
```

SQL skeleton (column-verified against `swing/data/migrations/0001_phase1_initial.sql:24-26` + `0003_phase2_pipeline_trades.sql:120-129` + `0006_pipeline_chart_linkage.sql:18` + `0020_phase13_charts_patterns_autofill_usability.sql:230-254` per Expansion #4 NEW refinement):

```sql
SELECT c.id
FROM candidates c
INNER JOIN pipeline_runs pr
    ON c.evaluation_run_id = pr.evaluation_run_id
WHERE pr.id = ? AND c.ticker = ?
ORDER BY c.id DESC LIMIT 1;
```

(Where `?` is `pattern_evaluations.pipeline_run_id` extracted from the URL-path-resolved evaluation row; ticker is `pattern_evaluations.ticker`.)

Then look up trade via:

```sql
SELECT 1 FROM trades
WHERE candidate_id = ?
  AND state IN ('entered', 'managing', 'partial_exited', 'closed', 'reviewed')
LIMIT 1;
```

If row exists AND operator decision is `confirm`, emit `label_source='organic_trade_history'`; else `label_source='closed_loop_review'`. **Pre-empt T2.SB6b R1 MAJOR #3 ticker-proxy regression via discriminating test**: plant 2 trades on same ticker (one from candidate A, one from candidate B); review candidate A's pattern; assert ONLY candidate A's trade qualifies as `organic_trade_history`.

**Gap B.4 lookup scope** (outcome distribution): per-candidate cohort; "last N similar-score candidates" means candidates with composite_score in `[evaluation.composite_score - 0.1, evaluation.composite_score + 0.1]` for the SAME pattern_class. Trade lookup is per-candidate via `trades.candidate_id`. SQL skeleton (column-verified against `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:230-250` — `pattern_evaluations.id` is the PK column name, NOT `evaluation_id` per Codex R1 CRITICAL #1 catch):

```sql
SELECT t.id, t.realized_R_if_plan_followed, t.state, t.entry_price, t.initial_stop, t.entry_date
FROM pattern_evaluations pe
INNER JOIN candidates c
    ON pe.ticker = c.ticker
   AND pe.pipeline_run_id IN (
       SELECT id FROM pipeline_runs WHERE evaluation_run_id = c.evaluation_run_id)
INNER JOIN trades t ON t.candidate_id = c.id
WHERE pe.pattern_class = ?
  AND pe.composite_score BETWEEN ? AND ?
  AND pe.id != ?
ORDER BY pe.id DESC
LIMIT ?;
```

(Where parameters are `pattern_class`, `composite_score - 0.1`, `composite_score + 0.1`, current `pattern_evaluations.id` (excluded), N similar candidates limit. The implementer at executing-plans phase MAY simplify if a join hint surfaces cleaner SQL — but the per-candidate join via `trades.candidate_id` is BINDING.)

**Gap B.5 lookup scope** (metric tile): per-pattern_class cohort; LEFT JOIN denominator = all `pattern_evaluations` rows for the pattern_class WHERE a confirmed `pattern_exemplars` row exists for the SAME `(ticker, pattern_class, window)` tuple (OQ-13 LOCK + Codex R1 MAJOR #4 closure — denominator MUST match on pattern_class + window, NOT just ticker, to avoid contaminating with unrelated historical exemplars). Numerator = subset that has `trades.candidate_id` populated AND outcome bucket met per OQ-6 thresholds.

Confirmed-pattern_class semantic: `pattern_exemplars.final_decision='confirmed'` AND `pattern_exemplars.proposed_pattern_class = pattern_evaluations.pattern_class`; per migration 0020 Invariant #1 `final_pattern_class IS NULL` when `final_decision != 'relabeled'`, so for `confirmed` exemplars the operator's confirmed class equals `proposed_pattern_class`. For `relabeled` exemplars (a different decision than `confirmed`; not part of the denominator since OQ-13 LOCK requires `final_decision='confirmed'`), the operator's confirmed class would be `final_pattern_class`.

Window-match semantic: `pattern_evaluations.window_start_date <= pattern_exemplars.end_date AND pattern_evaluations.window_end_date >= pattern_exemplars.start_date` (interval overlap; column-verified against migration 0020 `pattern_evaluations` lines 247-248 `window_start_date / window_end_date` + `pattern_exemplars` lines 68-69 `start_date / end_date`). SQL skeleton:

```sql
SELECT pe.pattern_class,
       COUNT(DISTINCT pe.id) AS denominator,
       COUNT(DISTINCT CASE WHEN t.id IS NOT NULL THEN pe.id END) AS evaluations_with_trades,
       COUNT(DISTINCT CASE WHEN t.id IS NOT NULL AND <reached_1r predicate> THEN pe.id END) AS reached_1r_count,
       COUNT(DISTINCT CASE WHEN t.id IS NOT NULL AND <hit_stop predicate>   THEN pe.id END) AS hit_stop_count
FROM pattern_evaluations pe
INNER JOIN candidates c
    ON pe.ticker = c.ticker
   AND pe.pipeline_run_id IN (
       SELECT id FROM pipeline_runs WHERE evaluation_run_id = c.evaluation_run_id)
INNER JOIN pattern_exemplars px
    ON px.ticker = pe.ticker
   AND px.proposed_pattern_class = pe.pattern_class
   AND px.final_decision = 'confirmed'
   AND pe.window_start_date <= px.end_date
   AND pe.window_end_date >= px.start_date
LEFT JOIN trades t ON t.candidate_id = c.id
WHERE pe.pattern_class = ?
GROUP BY pe.pattern_class
HAVING denominator >= 5;
```

(Per Codex R3 MAJOR #1 closure: all numerator counts MUST be unit-aware in terms of `pe.id` (evaluations), NOT `t.id` (trades), because OQ-13 specifies denominator = `pattern_evaluations` rows + numerator = "subset of evaluations with trade/outcome". A pre-R3 `COUNT(DISTINCT t.id)` for trades_opened could produce ratios > 100% when one evaluation's candidate has 2+ trades both reaching 1R. Fix: numerator counts `COUNT(DISTINCT CASE WHEN <predicate> THEN pe.id END)` — counts EVALUATIONS satisfying the predicate, NOT individual trades. With 1 evaluation + 2 trades both hitting 1R, `evaluations_with_trades == 1` AND `reached_1r_count == 1` (both bounded by denominator). `<reached_1r predicate>` and `<hit_stop predicate>` are OQ-6 bucketing predicates; computed via correlated subqueries against `fills` and OHLCV cache at executing-plans phase. Denominator suppression at n<5 LOCK preserved. Per pattern_exemplars Invariant #2 the source-vs-decision matrix admits `confirmed` for label_source IN `('curated_gold', 'claude_silver', 'codex_silver', 'closed_loop_review', 'organic_trade_history')` — all valid denominator participants. Discriminating regression test: plant 1 pattern_evaluation + 2 confirmed pattern_exemplars overlapping the same window + 2 trades on that candidate; assert denominator == 1, evaluations_with_trades == 1 (NOT 2; per-evaluation unit; ratio bounded by denominator). Second discriminating test: plant 5 evaluations, 2 of which have trades hitting 1R; assert denominator == 5, reached_1r_count == 2, ratio = 0.4 (40%).)

### §D.4 Content-completeness audit (Expansion #6 BINDING per dispatch brief §3.1.6)

For each spec §5.10 8-item checklist item, per-field disposition at SB6c ship:

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

Post-SB6c: ZERO V1 STUBs / V1 PARTIALs remain on the §5.10 8-item checklist. Plus the labeler_evidence_json rendering shape gap on existing 34 exemplars closes via the §1.5.2 amendment Path C backfill. Plus the chart_renders cache empty state closes via the §1.5.1 amendment pipeline-side write-through. **Forward-binding: any future closed-loop review form addition MUST NOT regress this audit.**

---

## §E Cross-bundle pin updates (Phase 13 plan §H.3)

Row 12 NEW at SB6c. Planted at T-A.6c.1; un-skipped (promoted to GREEN) at T-A.6c.5 closer.

| Pin name | Planted at | Un-skipped at | Verifies |
|---|---|---|---|
| `test_phase13_t2_sb6c_v21_trade_backlinks_schema_atomic` (parametrized over candidate_id + pattern_evaluation_id) | T-A.6c.1 | T-A.6c.5 | v21 schema + FK + index + mapper + INSERT roundtrip for each Delta |

Pin shape (parametrized over the 2 deltas; planted in `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py`):

```python
import pytest

@pytest.mark.parametrize("delta_label,column_name,fk_table,fk_col,index_name", [
    ("candidate_id", "candidate_id", "candidates", "id", "idx_trades_candidate_id"),
    ("pattern_evaluation_id", "pattern_evaluation_id", "pattern_evaluations", "id",
     "idx_trades_pattern_evaluation_id"),
])
def test_phase13_t2_sb6c_v21_trade_backlinks_schema_atomic(
    v21_db, delta_label, column_name, fk_table, fk_col, index_name,
):
    """Cross-bundle pin row 12: every Delta lands the full §A.14 paired set."""
    # Schema: column exists in trades.
    cols = {r[1] for r in v21_db.execute("PRAGMA table_info(trades)").fetchall()}
    assert column_name in cols, f"{column_name} not in trades cols (delta={delta_label})"

    # FK: ON DELETE SET NULL on referenced table.
    fks = v21_db.execute("PRAGMA foreign_key_list(trades)").fetchall()
    matching = [fk for fk in fks if fk[2] == fk_table and fk[3] == column_name and fk[4] == fk_col]
    assert matching, f"FK not found for {column_name} -> {fk_table}({fk_col})"
    assert matching[0][6] == "SET NULL"  # PRAGMA foreign_key_list col 6 = on_delete

    # Index: exists in sqlite_master.
    idx = v21_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,),
    ).fetchone()
    assert idx is not None, f"index {index_name} not found"

    # Mapper roundtrip: insert + read back via _row_to_trade with non-NULL value.
    # ... (see §G.1 discriminating tests for the full INSERT setup)
```

Row 12 in Phase 13 plan §H.3 cross-bundle pin schedule is APPENDED at T-A.6c.5 closer when the un-skip lands; the Phase 13 plan §H.3 row 11 (T2.SB6b parametrized pin) stays intact.

---

## §F Test scope projection

### §F.1 Fast-test delta forecast (per brainstorm spec §5.1 + §1.5.3 amendment)

| Bundle | Test count | Source |
|---|---|---|
| Delta A migration + paired surface | 8 | §G.1 Step 1 (per brainstorm spec §2.1) |
| Delta B migration + paired surface | 9 | §G.1 Step 1 (per brainstorm spec §2.2) |
| Migration runner backup-gate | 4 | §G.1 Step 1 (per brainstorm spec §B.5) |
| Cross-bundle pin row 12 parametrized | 2 (one per delta) | §E + §G.1 Step 1 |
| Gap A.1 hyp-rec detail chart | 3 | template + VM + route |
| Gap A.2 position detail chart | 3 | template + VM + route |
| Gap A.3 WatchlistVM template | 2 | template render + responsive zero-rows |
| Gap A.4 exemplar cache-miss write-through | 3 | cache-miss render + write-through + roundtrip |
| §1.5.1 amendment `_step_charts` write-through (4 surfaces) | 6-8 | per surface + F6 empty-bytes-rejection + DELETE-then-INSERT idempotency |
| Gap B.1 trend-template state live | 4 | VM extension + Phase 8 weather lookup + backward-looking session-anchor round-trip + template render |
| Gap B.2 volume profile live | 5 | VM + VolumeProfileRow dataclass validator + 30-session sum + 50d avg ratio + template render |
| §1.5.2 amendment labeler_evidence_json backfill | 5 | parse existing 3-key payload + synthesize rule_criteria + write augmented JSON back + idempotency + graceful no-op on already-augmented |
| Gap B.3 label_source split | 5 | positive (organic_trade_history) + negative (closed_loop_review) + ticker-proxy-regression discriminating test (T2.SB6b R1 MAJOR #3 LOCK) + confirm-decision-required + non-confirm-decision |
| Gap B.4 outcome distribution bucketing | 5 | reached_1r computation + hit_stop computation + suppression at n<5 + Wilson CI emission + VM template render |
| Gap B.5 metric tile reached_1r + hit_stop | 5 | LEFT JOIN denominator/numerator + per-pattern_class + suppression + Wilson CI + VM banner pin |
| Gap B.6 queue criterion 3 weather-state-aware | 4 | weather-state lookup + per-pattern_class baseline + weather-state-missing fallback + spec line 799 wording verbatim |
| Anchor-threading at POST /trades/entry (5-tier + claim-gate) | 13 | per §C.5 |
| Entry-path mapping fix at trades.py:1095 | 1 | UI origin -> EntryPath enum mapping |
| VM/builder extensions (EntryFormVM + HypRecsExpandedVM) | 2 | builder population per anchor field |
| Closer E2E + ruff sweep | 1 fast E2E | §G.5 |
| **Total estimated** | **~92-95 fast tests + 1 fast E2E** | Within dispatch brief §1.5.3 amendment range (~92-95 fast); breakdown: 17 schema + 4 backup-gate + 2 pin = 23 at T-A.6c.1; 11 chart-surface + 6-8 pipeline-write-through = 17-19 at T-A.6c.2; 9 review-form-completeness + 4 queue + 5 backfill = 18 at T-A.6c.3; 15 v21-dependent + 13 anchor-threading + 1 entry-path + 2 VM/builder = 31 at T-A.6c.4; 1 E2E at T-A.6c.5. Grand total: 90-92 fast + 1 E2E (the brief §1.5.3 says ~92-95; the +3-5 buffer covers cross-bundle pin parametrization + V1-completeness sanity tests likely surfaced at TDD step 1 per task). |

### §F.2 Slow-test delta

ZERO new slow tests. v21 migration is in-process (no Schwab API call, no yfinance fetch); all closure items are pure-VM extensions or in-process queries. The §1.5.1 pipeline-side write-through tests use the existing `_step_charts` fast-test harness (renderer mocked at test boundary).

### §F.3 Baseline + post-T2.SB6c

Baseline **5559 fast tests** UNCHANGED through this writing-plans phase (writing-plans touches docs only). Post-T2.SB6c executing-plans: **~5651-5654 fast tests** (5559 + 92-95 = 5651-5654). Schema v20 -> v21 LANDS at T-A.6c.1 (ending the 10+ sub-bundle v20-LOCKED streak).

### §F.4 Operator-witnessed gates (inherited from brainstorm spec §5.4 + §1.5 amendments)

- **S1 (inline)**: fast pytest + ruff + schema == v21.
- **S2 (browser)**: `/patterns/{candidate_id}/review` — confirm all 8 spec §5.10 checklist items render LIVE data (no `"n/a"` or `"(not available)"` stubs). Acceptance gate Item 4 + Item 6 + Item 8 closes out.
- **S3 (browser)**: hyp-rec detail page — confirm 800x500 SVG with pattern boundaries renders (Gap A.1).
- **S4 (browser)**: position detail page — confirm 800x500 SVG with fill markers renders (Gap A.2).
- **S5 (browser)**: `/watchlist` — confirm thumbnail charts render inline per row (Gap A.3).
- **S6 (browser)**: `/patterns/exemplars` — under cache-miss path, confirm live render fires + cache row is written through (Gap A.4); verify via DB query post-page-load that `chart_renders` has the new exemplar row.
- **S6b (DB query)**: after a pipeline run, confirm `chart_renders` has rows for ALL 4 surfaces touched by `_step_charts` write-through (watchlist_row + hyprec_detail + position_detail + market_weather) per the §1.5.1 amendment.
- **S7 (browser)**: `/metrics/pattern-outcomes` — confirm `reached_1r_pct` + `hit_stop_pct` columns render LIVE for cohorts with n>=5 (Gap B.5).
- **S8 (browser)**: `/patterns/queue` — confirm criterion 3 ranking matches current weather state (Gap B.6).
- **S9 (browser; data-shaped)**: open a fresh trade from `/recommendations/` form for a current pipeline candidate where a `pattern_evaluations` row exists for the (run, ticker) tuple; confirm new trade row gets BOTH `candidate_id` AND `pattern_evaluation_id` populated. Also: open a fresh `manual_off_pipeline` trade entry; confirm new trade row gets `candidate_id IS NULL` AND `pattern_evaluation_id IS NULL`.
- **S10 (browser; closed-loop)**: review the candidate at `/patterns/{candidate_id}/review` with `confirm` decision; confirm `pattern_exemplars` row is written with `label_source='organic_trade_history'` (Gap B.3).
- **S11 (operator-paired post-merge; one-shot)**: operator runs `python -m swing.cli patterns-exemplars-backfill-labeler-evidence` against operator DB; subsequent `/patterns/exemplars` renders show populated `rule_criteria` + `narrative` (§1.5.2 amendment closure). The CLI subcommand uses the Click-canonical hyphenated form `patterns-exemplars-backfill-labeler-evidence` (NOT the underscored Python function name `patterns_exemplars_backfill_labeler_evidence`) per the existing `swing/cli.py` convention (Click auto-converts function names to hyphen-separated subcommand names).

---

## §G Per-task decomposition T-A.6c.1..T-A.6c.5

### §G.1 T-A.6c.1 — v21 migration atomic landing (NO schema-dep; foundation)

**Files:**
- Create: `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`.
- Modify: `swing/data/models.py:Trade` (extend with 2 nullable INT fields at the end of the dataclass field list, preserving existing field order; use `field(default=None)` if `Trade` is a frozen dataclass or `= None` default if plain).
- Modify: `swing/data/repos/trades.py` — extend `_TRADE_SELECT_COLS` + `_row_to_trade` index map + `insert_trade_with_event` SVAI branch.
- Modify: `swing/data/db.py` — bump `EXPECTED_SCHEMA_VERSION = 21` at line 39; add `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` constant after line 111; add `_phase13_sb6c_backup_gate` function after the existing `_phase13_backup_gate` at line 634; add `_create_pre_phase13_sb6c_migration_backup` after `_create_pre_phase13_migration_backup` at line 446; wire `_phase13_sb6c_backup_gate` call after the existing `_phase13_backup_gate(...)` at line 728 in `run_migrations`.
- Create: `tests/data/test_v21_migration_trade_backlinks.py` (17 paired tests + 4 backup-gate tests = 21 tests).
- Create: `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` (2 parametrized pin tests).

**Acceptance criteria (per brainstorm spec §6.1):**
- Migration runs cleanly against v20-shape DB; `SELECT version FROM schema_version` returns 21.
- All 17 paired discriminating tests PASS + 4 backup-gate tests PASS + 2 cross-bundle pin tests PASS = 23 NEW tests PASS.
- Existing 5559 fast tests still PASS (no regression).
- Backup file `swing-pre-phase13-sb6c-migration-<ISO>.db` written before migration runs (verified via discriminating test).
- LOCK preserved: schema + dataclass + read-path mapper + write-path INSERT extension + ALL tests land in ONE commit per §A.14.
- ruff check swing/ clean.

Per superpowers:writing-plans bite-sized-step discipline + Codex R1 MAJOR #3 closure: the test-authoring work splits into 5 sub-steps (1a-1e), each ~5-10 minutes (one test-group per sub-step; tests within a group share fixture pattern). The skeleton below is for sub-step 1a's first test; the remaining tests in each sub-step follow the same shape with parameter variations per the brainstorm spec §2.1 + §2.2 + §B.5 + §E enumerations.

- [ ] **Step 1a: Write 8 Delta A discriminating tests** at `tests/data/test_v21_migration_trade_backlinks.py`.

Tests per brainstorm spec §2.1 enumeration:
  - `test_v21_migration_adds_candidate_id_column_at_position_52`
  - `test_v21_migration_adds_fk_to_candidates_id_on_delete_set_null`
  - `test_v21_migration_creates_idx_trades_candidate_id`
  - `test_v21_migration_backfills_existing_trades_with_null_candidate_id`
  - `test_row_to_trade_populates_candidate_id_from_row_52`
  - `test_row_to_trade_populates_candidate_id_None_when_null_column`
  - `test_insert_trade_with_candidate_id_persists_via_schema_aware_path`
  - `test_fk_cascade_on_candidates_delete_sets_trade_candidate_id_null`

Sample skeleton (first test; bodies for remaining 7 follow same fixture pattern):

```python
import sqlite3
from pathlib import Path
import pytest
from swing.data.db import run_migrations, EXPECTED_SCHEMA_VERSION

def test_v21_migration_adds_candidate_id_column_at_position_52(v20_db):
    """Delta A - schema position locked at row[52] per OQ-9."""
    run_migrations(v20_db, target_version=21)
    cols = v20_db.execute("PRAGMA table_info(trades)").fetchall()
    # PRAGMA table_info row shape: (cid, name, type, notnull, dflt_value, pk)
    by_name = {c[1]: c for c in cols}
    assert "candidate_id" in by_name
    assert by_name["candidate_id"][0] == 52  # column position
    assert by_name["candidate_id"][2] == "INTEGER"
    assert by_name["candidate_id"][3] == 0  # nullable
```

- [ ] **Step 1b: Write 9 Delta B discriminating tests** at the same test file. Tests per brainstorm spec §2.2 enumeration:
  - `test_v21_migration_adds_pattern_evaluation_id_column_at_position_53`
  - `test_v21_migration_adds_fk_to_pattern_evaluations_id_on_delete_set_null`
  - `test_v21_migration_creates_idx_trades_pattern_evaluation_id`
  - `test_v21_migration_backfills_existing_trades_with_null_pattern_evaluation_id`
  - `test_row_to_trade_populates_pattern_evaluation_id_from_row_53`
  - `test_row_to_trade_populates_pattern_evaluation_id_None_when_null_column`
  - `test_insert_trade_with_pattern_evaluation_id_persists`
  - `test_fk_cascade_on_pattern_evaluations_delete_sets_trade_pattern_evaluation_id_null`
  - `test_pattern_evaluations_direct_delete_sets_trade_pattern_evaluation_id_null` (per Codex R1 MAJOR #4 — direct row deletion, NOT chained cascade through pipeline_runs which is blocked by pre-existing trades.chart_pattern_classification_pipeline_run_id FK NO ACTION).

- [ ] **Step 1c: Write 4 backup-gate discriminating tests** at the same test file. Tests per brainstorm spec §B.5 + §2.4 enumeration:
  - `test_run_migrations_v20_to_v21_creates_backup_with_correct_filename` (asserts file `swing-pre-phase13-sb6c-migration-<ISO>.db` exists in backup_dir before migration body runs).
  - `test_run_migrations_v20_to_v21_strict_equality_pre_version_predicate` (asserts gate fires at pre_version==20; does NOT fire at pre_version==19 — consistent with existing `swing/data/db.py:575-581` semantics).
  - `test_run_migrations_v19_to_v21_skips_sb6c_backup_uses_phase13_v20_backup_only` (multi-version jump v19->v21: applies BOTH v20 + v21 migrations; SB6c-specific backup is NOT written because pre_version==19 at SB6c gate; v20 boundary's own backup IS written).
  - `test_expected_schema_version_constant_is_21_post_sb6c` (asserts `swing.data.db.EXPECTED_SCHEMA_VERSION == 21`).

- [ ] **Step 1d: Write 2 cross-bundle pin parametrized tests** at `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` per §E shape (parametrized over delta_label).

- [ ] **Step 1e: Run all 23 new tests; verify ALL FAIL.**

Run: `python -m pytest tests/data/test_v21_migration_trade_backlinks.py tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py -v`
Expected: All 23 FAIL with errors like `no such column: candidate_id` or `assert "candidate_id" in by_name` (FAIL).

- [ ] **Step 2: Author migration file** `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` per §B.4 body verbatim.

- [ ] **Step 3: Extend `swing/data/models.py:Trade`** with 2 new fields at the end of the field list (preserve existing field order; add default None):

```python
@dataclass(frozen=True)
class Trade:
    # ... existing fields 1..52 unchanged ...
    planned_target_R: float | None = None  # noqa: N815 (existing field at row[51])
    # Phase 13 / migration 0021 — v21 nullable FK backlinks (T2.SB6c).
    candidate_id: int | None = None
    pattern_evaluation_id: int | None = None
```

- [ ] **Step 4: Extend `swing/data/repos/trades.py:_TRADE_SELECT_COLS`** (line 47-66) with the 2 new columns appended after `planned_target_R`:

```python
_TRADE_SELECT_COLS = """
    id, ticker, entry_date, entry_price, initial_shares, initial_stop,
    current_stop, state, watchlist_entry_target,
    watchlist_initial_stop, notes, hypothesis_label,
    chart_pattern_algo, chart_pattern_algo_confidence,
    chart_pattern_operator, chart_pattern_classification_pipeline_run_id,
    sector, industry,
    reviewed_at, mistake_tags, entry_grade, management_grade,
    exit_grade, process_grade, disqualifying_process_violation,
    realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned,
    trade_origin, pre_trade_locked_at, current_size, current_avg_cost,
    last_fill_at,
    thesis, why_now, invalidation_condition, expected_scenario,
    premortem_technical, premortem_market_sector, premortem_execution,
    premortem_additional,
    event_risk_present, event_handling, event_type, event_date,
    gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
    market_regime, catalyst, catalyst_other_description,
    planned_target_R,
    candidate_id, pattern_evaluation_id
"""
```

Extend `_row_to_trade` (line 345-413) with the index map comment block + 2 new field reads:

```python
def _row_to_trade(row: tuple) -> Trade:
    """Map a SELECT row (column order = _TRADE_SELECT_COLS) to a Trade.

    Index map (must match _TRADE_SELECT_COLS):
      0:id 1:ticker 2:entry_date 3:entry_price 4:initial_shares 5:initial_stop
      # ... rows 6..50 unchanged ...
      51:planned_target_R (Phase 8 / migration 0016)
      52:candidate_id (Phase 13 / migration 0021)
      53:pattern_evaluation_id (Phase 13 / migration 0021)
    """
    # ... existing 0..51 assignments unchanged ...
    return Trade(
        # ... existing 0..51 fields unchanged ...
        planned_target_R=row[51],
        candidate_id=row[52],
        pattern_evaluation_id=row[53],
    )
```

- [ ] **Step 5: Extend `swing/data/repos/trades.py:insert_trade_with_event`** (line 102-189) with the SVAI runtime branch per §B.3. The branch tests for BOTH new columns present (NOT just one); legacy path used when either is missing:

```python
def insert_trade_with_event(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert a trade and an 'entry' trade_event in the same transaction.
    Caller wraps in `with conn:`. Returns the new trade id.

    SVAI: pre-v21 fixtures (tests using run_migrations(target_version<21))
    lack the 2 new trades columns. Detect via PRAGMA table_info and emit
    the legacy column list for backwards compat with existing v20 fixtures.
    """
    _validate_chart_pattern_invariant(trade)
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    if "candidate_id" in cols and "pattern_evaluation_id" in cols:
        cur = conn.execute(
            """
            INSERT INTO trades
                (ticker, entry_date, entry_price, initial_shares, initial_stop,
                 # ... existing column list verbatim through planned_target_R ...
                 planned_target_R,
                 candidate_id, pattern_evaluation_id)
            VALUES (?, ?, ?, ?, ?,
                    # ... existing placeholders verbatim ...
                    ?,
                    ?, ?)
            """,
            (
                # ... existing values verbatim through trade.planned_target_R ...
                trade.planned_target_R,
                trade.candidate_id, trade.pattern_evaluation_id,
            ),
        )
    else:
        # Legacy path: pre-v21 schema; omit the 2 new columns.
        cur = conn.execute(
            """
            INSERT INTO trades
                (ticker, entry_date, entry_price, initial_shares, initial_stop,
                 # ... existing column list verbatim through planned_target_R ...
                 planned_target_R)
            VALUES (?, ?, ?, ?, ?,
                    # ... existing placeholders verbatim ...
                    ?)
            """,
            (
                # ... existing values verbatim through trade.planned_target_R ...
                trade.planned_target_R,
            ),
        )
    trade_id = int(cur.lastrowid)
    # ... existing trade_events INSERT unchanged ...
    return trade_id
```

(The implementer at executing-plans phase fills in the full column lists from the existing `insert_trade_with_event` body — copy-paste-extend — both branches must spell out the full column list per the fills.py:53-89 precedent.)

- [ ] **Step 6: Extend `swing/data/db.py`** per §B.5:

(a) Line 39: bump `EXPECTED_SCHEMA_VERSION = 20` to `EXPECTED_SCHEMA_VERSION = 21`.

(b) After line 111 (after `PHASE13_PRE_MIGRATION_EXPECTED_TABLES`):

```python
# Phase 13 T2.SB6c backup gate (spec §3.5 + plan §B.5): when migrating from
# v20 -> v21+, snapshot the live v20 DB. Adds the 5 v20-shipped Phase 13
# tables to the PHASE13 set so provenance stays auditable.
# Derived deterministically from PHASE13 set per existing precedent.
# Filename pattern: ``swing-pre-phase13-sb6c-migration-<ISO>.db`` per plan §B.5 +
# CLAUDE.md migration-runner backup-gate strict-equality gotcha
# (``pre_version == 20`` STRICT EQUALITY, NOT ``<=``).
PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_PRE_MIGRATION_EXPECTED_TABLES
    | {
        "pattern_exemplars", "chart_renders", "pattern_evaluations",
        "watchlist_close_track_flags", "watchlist_close_track_flag_events",
    }
)
```

(c) After the existing `_create_pre_phase13_migration_backup` at line 446, add `_create_pre_phase13_sb6c_migration_backup`:

```python
def _create_pre_phase13_sb6c_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Mirror `_create_pre_phase13_migration_backup` with filename
    ``swing-pre-phase13-sb6c-migration-<ISO>.db`` (OQ-8 LOCK).
    """
    iso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-phase13-sb6c-migration-{iso}.db"
    # ... rest mirrors _create_pre_phase13_migration_backup body ...
    return backup_path
```

(d) After the existing `_phase13_backup_gate` at line 634, add `_phase13_sb6c_backup_gate`:

```python
def _phase13_sb6c_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 13 T2.SB6c backup-before-migrate gate (plan §B.5 + spec §A.14).

    Fires only when ``current_version == 20 AND target_version >= 21`` —
    i.e., a real production v20 DB about to receive Phase 13's migration
    0021. STRICT EQUALITY on pre_version per CLAUDE.md gotcha "Migration
    runner backup-gate equality form: pre_version == (target - 1) strict
    equality, NOT pre_version <= (target - 1)". Multi-step migration walks
    from pre-v20 baselines bypass this gate by design (matches Phase 9 /
    Phase 12 C.A / Phase 13 T-A.1.1 precedent).

    Filename: ``swing-pre-phase13-sb6c-migration-<ISO>.db``.
    """
    if target_version < 21 or current_version != 20:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-13-SB6c backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase13_sb6c_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-13-SB6c backup failed: {exc}"
        ) from exc
```

(e) Wire into `run_migrations` (after the existing `_phase13_backup_gate(...)` call at line 728):

```python
def run_migrations(
    conn: sqlite3.Connection,
    *,
    target_version: int = EXPECTED_SCHEMA_VERSION,
    backup_dir: Path | None = None,
) -> None:
    # ... existing body through _phase13_backup_gate(...) unchanged ...
    _phase13_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase13_sb6c_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    # ... rest of run_migrations body unchanged ...
```

- [ ] **Step 7: Run N-mirror audit + extend any direct-SQL trade column readers found.**

Run: `Grep "SELECT .* FROM trades" swing/` (excluding `_TRADE_SELECT_COLS`-using callsites). Expected ZERO additional callsites — `_row_to_trade` is canonical. If any direct readers are found, extend them in this same commit. Enumerate findings in the commit message body.

- [ ] **Step 8: Run all 23 tests; verify PASS.**

Run: `python -m pytest tests/data/test_v21_migration_trade_backlinks.py tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py -v`
Expected: All 23 PASS.

- [ ] **Step 9: Run full fast-test suite + ruff check; verify regression-free.**

Run: `python -m pytest -m "not slow" -q swing/ tests/`
Expected: 5559 + 23 = 5582 fast tests PASS, 0 fail.
Run: `ruff check swing/`
Expected: All checks passed.

- [ ] **Step 10: Commit** — `feat(phase13): v21 migration + trades backlinks atomic landing (T-A.6c.1)`

```bash
git add swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql swing/data/models.py swing/data/repos/trades.py swing/data/db.py tests/data/test_v21_migration_trade_backlinks.py tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py
git commit -m "feat(phase13): v21 migration + trades backlinks atomic landing (T-A.6c.1)"
```

Commit message body enumerates: 17 paired tests (8 Delta A + 9 Delta B) + 4 backup-gate tests + 2 cross-bundle pin tests = 23 NEW; SVAI runtime branch per fills.py:51-53 precedent; N-mirror audit findings (expected: ZERO additional callsites); §A.14 paired-discipline closure verbatim per Phase 12 C.A T-A.2 LOCK.

**Watch items (per dispatch brief §3 + brainstorm spec §8.2):**
- W1 (§A.14 paired discipline) — schema + dataclass + read-path mapper + write-path INSERT + tests in ONE commit.
- W2 (read-path mapping keeps pace with write-path) — `_row_to_trade` extended same task.
- W3 (N-mirror auditing) — grep for hardcoded SELECT-trade-column-lists; extend any found.
- W4 (backup-gate strict equality) — `pre_version == 20 AND target >= 21`; do NOT paraphrase to `<=`.
- W5 (`executescript()` implicit-COMMIT) — migration uses explicit `BEGIN`+`COMMIT`.
- W6 (`INSERT OR REPLACE` cascade-wipe BANNED) — no upsert intent in v21.
- W11 (Pre-Codex 7-expansion discipline) — Expansion #4 NEW refinement: every SQL JOIN's columns verified against actual `swing/data/migrations/*.sql` files.
- W15 (`Co-Authored-By` footer ZERO trailer drift) — preserve cumulative ~360+ commit streak.

### §G.2 T-A.6c.2 — SB6 closure Gap A chart-surface wiring + §1.5.1 pipeline-side write-through (NO schema dep; concurrent with T-A.6c.1)

**Files:**
- Modify: `swing/web/view_models/recommendations.py` (hyp-rec detail VM extension — Gap A.1).
- Modify: `swing/web/view_models/trades.py` (position detail VM extension — Gap A.2).
- Modify: `swing/web/templates/recommendations/detail.html.j2` (inline SVG render).
- Modify: `swing/web/templates/trades/detail.html.j2` (inline SVG render).
- Modify: `swing/web/templates/partials/watchlist_row.html.j2` (thumbnail render — Gap A.3).
- Modify: `swing/web/view_models/patterns/exemplars.py` (cache-miss write-through — Gap A.4).
- Modify: `swing/pipeline/runner.py:_step_charts` (§1.5.1 amendment — chart_renders write-through for 4 surfaces).
- Create: `tests/web/test_routes/test_recommendations_detail_chart.py` (Gap A.1; 3 tests).
- Create: `tests/web/test_routes/test_trades_detail_chart.py` (Gap A.2; 3 tests).
- Modify: `tests/web/test_routes/test_watchlist_template_thumbnail.py` (Gap A.3; 2 tests; create if missing).
- Modify: `tests/web/test_routes/test_patterns_exemplars_enhanced.py` (Gap A.4 write-through; 3 tests; extend existing).
- Create: `tests/pipeline/test_step_charts_chart_renders_write_through.py` (§1.5.1 amendment; 6-8 tests covering 4 surfaces + F6 + idempotency).

**Acceptance criteria:**
- 17-19 new tests PASS (11 Gap A + 6-8 §1.5.1 amendment).
- S3 + S4 + S5 + S6 + S6b operator-witnessed gates PASS.
- Existing 5559 + 23 (from T-A.6c.1 if executed first) tests still PASS.
- ruff check swing/ clean.

- [ ] **Step 1a: Write 11 failing Gap A tests** per surface (3 hyp-rec + 3 position + 2 watchlist + 3 exemplar cache-miss).

Sample skeleton (one per Gap):

```python
def test_hyprec_detail_vm_populates_chart_svg_bytes_from_cache(v20_db, sample_pattern_evaluation):
    """Gap A.1 — hyp-rec detail VM consumes chart_renders cache."""
    refresh_chart_render(
        v20_db,
        ChartRender(
            ticker="CVGI", surface="hyprec_detail",
            pipeline_run_id=sample_pattern_evaluation.pipeline_run_id,
            chart_svg_bytes=b"<svg>fake</svg>",
        ),
    )
    vm = build_recommendations_detail_vm(
        conn=v20_db, ticker="CVGI",
        pipeline_run_id=sample_pattern_evaluation.pipeline_run_id,
    )
    assert vm.hyprec_detail_chart_svg_bytes == b"<svg>fake</svg>"
```

(The remaining 10 Gap A tests follow the brainstorm spec §5.1 enumeration: template render presence + VM extension + cache-miss render invocation + cache-miss write-through + chart_renders row inserted + roundtrip read.)

- [ ] **Step 1b: Write 6-8 failing §1.5.1 amendment tests** at `tests/pipeline/test_step_charts_chart_renders_write_through.py`. Tests cover:

  - 4 surface-population tests (one per `watchlist_row` + `hyprec_detail` + `position_detail` + `market_weather`): plant a pipeline run + relevant input rows; invoke `_step_charts`; assert exactly 1 `chart_renders` row exists per active ticker for that surface with the correct cache key shape (run-bound = non-NULL pipeline_run_id; position_detail = NULL pipeline_run_id).
  - 1 F6 transient-empty-bytes defense test: monkeypatch the renderer to return `b""` for one ticker; assert `ChartRender(chart_svg_bytes=b"")` raises ValueError in `_step_charts`; assert pipeline step catches + WARN-logs + continues to remaining tickers; assert pre-existing cache rows for that ticker are preserved verbatim.
  - 1 DELETE-then-INSERT idempotency test: run `_step_charts` twice with the same input; assert the second run REPLACES the cache row (new `id` autoincrement; cache row count unchanged for the (ticker, surface, pipeline_run_id) tuple).
  - 1-2 multi-ticker / multi-surface sanity tests (assert all 4 surfaces are populated for at least 1 ticker across 1 pipeline run).

Sample skeleton:

```python
def test_step_charts_writes_through_chart_renders_for_watchlist_row_surface(
    v20_db, sample_pipeline_run, sample_watchlist_row,
):
    """§1.5.1 amendment — _step_charts writes chart_renders cache row per watchlist_row ticker."""
    from swing.pipeline.runner import _step_charts
    _step_charts(v20_db, run_id=sample_pipeline_run.id, ...)
    rows = v20_db.execute(
        """SELECT ticker, pipeline_run_id, surface
           FROM chart_renders WHERE surface = 'watchlist_row'""",
    ).fetchall()
    assert len(rows) == 1
    assert rows[0] == (sample_watchlist_row.ticker, sample_pipeline_run.id, "watchlist_row")
```

- [ ] **Step 2: Run tests; verify FAIL.**

Expected: 17-19 FAIL with VM-field-missing errors / cache-empty errors.

- [ ] **Step 3: Implement Gap A.1** — extend `RecommendationsVM` with `hyprec_detail_chart_svg_bytes: bytes | None = None`; extend `build_recommendations_detail_vm(...)` to call `get_cached_chart_svg(conn, ticker, surface='hyprec_detail', pipeline_run_id=pipeline_run_id)`; extend `swing/web/templates/recommendations/detail.html.j2` with `{% if vm.hyprec_detail_chart_svg_bytes %}{{ vm.hyprec_detail_chart_svg_bytes|safe }}{% endif %}` or similar inline SVG render.

- [ ] **Step 4: Implement Gap A.2** — same shape as A.1 against `TradeDetailVM` with `position_chart_svg_bytes: bytes | None = None`; cache key `surface='position_detail'`, `pipeline_run_id=None` (run-agnostic per v20 §3.2 LOCK).

- [ ] **Step 5: Implement Gap A.3** — extend `swing/web/templates/partials/watchlist_row.html.j2` to render `vm.watchlist_chart_svg_bytes` inline (the field is already populated on WatchlistVM at T2.SB6b R1 MAJOR #5 partial fix at commit `94e4418`; this is template-side only).

- [ ] **Step 6: Implement Gap A.4** — at `swing/web/view_models/patterns/exemplars.py` cache-miss path (look up the existing import at line 258 + the docstring at lines 290-296 "Cache NOT written back"): after `render_theme2_annotated_svg(...)` returns bytes, call `refresh_chart_render(conn, ChartRender(surface='theme2_annotated', ticker=..., pipeline_run_id=..., pattern_class=..., chart_svg_bytes=...))`. Update the docstring to remove the "Cache NOT written back" disclaimer.

- [ ] **Step 7: Implement §1.5.1 amendment** — extend `swing/pipeline/runner.py:_step_charts`. Inside the existing pipeline step transactional block, AFTER existing chart-rendering work (verify exact shape at executing-plans phase via `Grep "_step_charts" swing/pipeline/runner.py`), iterate over the active ticker set (open trades for `position_detail`; watchlist tickers for `watchlist_row`; hyp-rec tickers for `hyprec_detail`; `cfg.rs.benchmark_ticker` for `market_weather`) and call `refresh_chart_render(conn, ChartRender(...))` per surface. Wrap each per-surface block in a `try: ... except ValueError as exc: logger.warning("F6 transient empty chart skipped: ticker=%s surface=%s err=%s", ticker, surface, exc); continue` to catch construction-barrier rejections (per T2.SB6a R1 MAJOR #2 LOCK).

**Per Codex R2 MAJOR #4 closure**: the `market_weather` surface's ticker MUST be `cfg.rs.benchmark_ticker` (NOT `"^GSPC"` or any other hardcoded value). The dashboard reader at T2.SB6b ALREADY consumes `chart_renders` via `get_cached_chart_svg(conn, ticker=cfg.rs.benchmark_ticker, surface='market_weather', ...)`; if the writer uses a different ticker, the cache row IS written but is INVISIBLE to the dashboard read path. Discriminating round-trip test added at Step 1b: write `market_weather` cache row via `_step_charts` + read via `get_cached_chart_svg(conn, ticker=cfg.rs.benchmark_ticker, surface='market_weather', pipeline_run_id=run_id)`; assert bytes round-trip equality.

Cache key shape:
- `watchlist_row`: `ticker=<watchlist_ticker>`, `pipeline_run_id=<current_run_id>`, `pattern_class=None`.
- `hyprec_detail`: `ticker=<hyp_rec_ticker>`, `pipeline_run_id=<current_run_id>`, `pattern_class=None`.
- `position_detail`: `ticker=<open_position_ticker>`, `pipeline_run_id=None`, `pattern_class=None` (run-agnostic).
- `market_weather`: `ticker=cfg.rs.benchmark_ticker`, `pipeline_run_id=<current_run_id>`, `pattern_class=None`.

- [ ] **Step 8: Run all 17-19 new tests; verify PASS.**

- [ ] **Step 9: Run full fast-test suite + ruff check; verify regression-free.**

- [ ] **Step 10: Commit** — `feat(phase13): Gap A chart-surface wiring + pipeline-side chart_renders write-through (T-A.6c.2)`

```bash
git add swing/web/view_models/recommendations.py swing/web/view_models/trades.py swing/web/view_models/patterns/exemplars.py swing/web/templates/recommendations/detail.html.j2 swing/web/templates/trades/detail.html.j2 swing/web/templates/partials/watchlist_row.html.j2 swing/pipeline/runner.py tests/web/test_routes/test_recommendations_detail_chart.py tests/web/test_routes/test_trades_detail_chart.py tests/web/test_routes/test_watchlist_template_thumbnail.py tests/web/test_routes/test_patterns_exemplars_enhanced.py tests/pipeline/test_step_charts_chart_renders_write_through.py
git commit -m "feat(phase13): Gap A chart-surface wiring + pipeline-side chart_renders write-through (T-A.6c.2)"
```

Commit message body enumerates: 11 Gap A tests + 6-8 §1.5.1 amendment tests = 17-19 NEW; F6 transient-empty defense at ChartRender construction barrier verified via discriminating test; DELETE-then-INSERT idempotency via existing `refresh_chart_render` substrate (caller-tx-required); ZERO new substrate-API additions (L7 LOCK preserved).

**Watch items:**
- L7 (T2.SB6a substrate API surface FROZEN) — `swing/web/charts.py` + `swing/data/repos/chart_renders.py` + `swing/data/models.py:ChartRender` UNTOUCHED.
- L8 (`_CHART_SURFACE_VALUES` semantic LOCK) — imported from `swing/data/models.py`; no re-definition.
- L17 (substrate reuse) — Gap A.1 + A.2 + A.4 reuse `render_theme2_annotated_svg` + `get_cached_chart_svg` + `refresh_chart_render` verbatim.
- L18 (chart_renders cache write-through atomic via substrate) — invoke existing `refresh_chart_render`; no caller-side `INSERT OR REPLACE`.
- §C.3 F6 transient-empty defense at construction barrier (T2.SB6a R1 MAJOR #2 LOCK).
- §C.3 cache key shape per substrate `ChartRender.__post_init__` semantic validator (T2.SB6a R1 CRITICAL #1 LOCK).

### §G.3 T-A.6c.3 — SB6 closure Gap B no-schema review form data-completeness + §1.5.2 labeler_evidence_json backfill (NO schema dep; concurrent with T-A.6c.1)

**Files:**
- Modify: `swing/web/view_models/patterns/review_form.py` (Gap B.1 + B.2 — extend with `trend_template_state` + `volume_profile` fields + NEW `VolumeProfileRow` dataclass).
- Modify: `swing/web/view_models/patterns/queue.py` (Gap B.6 — extend `build_patterns_queue_vm(...)` to accept `cfg` + thread `cfg.rs.benchmark_ticker` into `prioritize_candidates`).
- Modify: `swing/web/templates/patterns/review.html.j2` (render new fields).
- Modify: `swing/patterns/active_learning.py:prioritize_candidates` (Gap B.6 — signature extension `benchmark_ticker: str = "QQQ"` + criterion 3 weather-state-aware variant).
- Modify: `swing/web/routes/patterns.py` (route handler populates VM extensions + threads `cfg` into `build_patterns_queue_vm`).
- Modify: `swing/data/repos/pattern_exemplars.py` (§1.5.2 amendment — NEW `update_exemplar_labeler_evidence_json` helper).
- Create: `swing/cli.py:patterns_exemplars_backfill_labeler_evidence` (§1.5.2 amendment — operator-invoked subcommand).
- Create: `tests/web/test_routes/test_patterns_review_data_completeness.py` (Gap B.1 + B.2; 9 tests).
- Modify: `tests/web/test_routes/test_patterns_queue.py` (Gap B.6; 4 tests).
- Create: `tests/cli/test_patterns_exemplars_backfill_labeler_evidence.py` (§1.5.2 amendment; 5 tests).

**Acceptance criteria:**
- 18 new tests PASS (9 Gap B.1+B.2 + 4 Gap B.6 + 5 §1.5.2 amendment).
- S2 + S8 + S11 operator-witnessed gates PASS.
- ruff check swing/ clean.

- [ ] **Step 1a: Write 9 failing Gap B.1 + B.2 tests** per brainstorm spec §5.1.

Sample skeleton (per Codex R2 MAJOR #2 closure — `current_stage` is the Phase 13 trend-template wrapper at `swing/patterns/foundation.py:745`, V1 returns only `'stage_2'` or `'undefined'`; NOT a weather-state read):

```python
def test_pattern_review_form_vm_populates_trend_template_state_live(v20_db, sample_evaluation):
    """Gap B.1 - trend-template state via current_stage(conn, ticker, window_end_date)."""
    # Plant a candidate with all 8 TT1-TT8 trend-template criteria passing for
    # the sample_evaluation's ticker + an action_session_date <= window_end_date.
    _seed_candidate_with_all_tt_criteria_pass(
        v20_db, ticker=sample_evaluation.ticker,
        action_session_date=sample_evaluation.window_end_date,
    )
    vm = build_pattern_review_form_vm(conn=v20_db, evaluation_id=sample_evaluation.id)
    assert vm.trend_template_state != "n/a"
    assert vm.trend_template_state == "stage_2"  # V1 semantic per foundation.py:789


def test_pattern_review_form_vm_populates_trend_template_state_undefined_when_criteria_fail(
    v20_db, sample_evaluation,
):
    """Gap B.1 negative - missing-criteria candidate -> 'undefined' per foundation.py:790."""
    _seed_candidate_with_partial_tt_criteria_pass(
        v20_db, ticker=sample_evaluation.ticker,
        action_session_date=sample_evaluation.window_end_date,
        pass_count=7,  # short by 1
    )
    vm = build_pattern_review_form_vm(conn=v20_db, evaluation_id=sample_evaluation.id)
    assert vm.trend_template_state == "undefined"
```

(The remaining 7 follow the §5.1 enumeration: VM extension; current_stage roundtrip; template render; VolumeProfileRow dataclass validator; 30-session sum; 50d avg ratio; template render.)

- [ ] **Step 1b: Write 4 failing Gap B.6 tests** at `tests/web/test_routes/test_patterns_queue.py` (extend existing).

- [ ] **Step 1c: Write 5 failing §1.5.2 amendment tests** at `tests/cli/test_patterns_exemplars_backfill_labeler_evidence.py`:

  - Parse existing 3-key payload (`confidence` + `evaluation` + `geometric_evidence_narrative`); assert `narrative` key emitted + `rule_criteria` array emitted with N entries (where N is the count of criteria in the synthesized array per spec §5.2-§5.6).
  - Synthesize `rule_criteria` from `geometric_score_json` per-rule pass/fail/threshold/tolerance; assert the array shape matches `[{"name": str, "status": "pass"|"fail", "evidence_value": str, "threshold": str, "tolerance": str|None}, ...]` per T-A.6.6b's `CriterionRow` shape.
  - Idempotency: run backfill twice; assert second run is a no-op on already-augmented payloads (detect via `rule_criteria` + `narrative` keys present pre-run); first-run output preserved exactly.
  - Graceful no-op on missing `geometric_score_json` (rare; should WARN-log + skip).
  - Round-trip via public reader: after backfill, `get_exemplar_by_id(conn, id).labeler_evidence_json` parses + contains the new keys.

Sample skeleton:

```python
def test_patterns_exemplars_backfill_labeler_evidence_synthesizes_rule_criteria_and_narrative(
    v20_db_with_34_exemplars,
):
    """§1.5.2 amendment — Path C backfill: synthesize rule_criteria + copy narrative."""
    from swing.cli import patterns_exemplars_backfill_labeler_evidence_run
    augmented, skipped = patterns_exemplars_backfill_labeler_evidence_run(conn=v20_db_with_34_exemplars)
    assert augmented == 34
    assert skipped == 0
    sample = v20_db_with_34_exemplars.execute(
        "SELECT labeler_evidence_json FROM pattern_exemplars LIMIT 1",
    ).fetchone()
    payload = json.loads(sample[0])
    assert "narrative" in payload
    assert "rule_criteria" in payload
    assert isinstance(payload["rule_criteria"], list)
    assert "geometric_evidence_narrative" in payload  # preserved
```

- [ ] **Step 2: Run tests; verify FAIL.**

- [ ] **Step 3: Implement Gap B.1** — extend `PatternReviewFormVM` with `trend_template_state: str` (value domain `'stage_2' | 'undefined'` per Phase 13 V1 wrapper at `swing/patterns/foundation.py:745`). The VM builder reads via `swing.patterns.foundation.current_stage(conn, ticker=evaluation.ticker, asof_date=date.fromisoformat(evaluation.window_end_date))` — using the pattern_evaluation's `window_end_date` (TEXT per migration 0020 line 248) parsed via `date.fromisoformat()` because `current_stage` signature requires a `date` object (not a string; calls `.isoformat()` internally per `swing/patterns/foundation.py:762`). Per Codex R3 MAJOR #2 closure: malformed `window_end_date` (rare; would indicate prior data corruption) raises `ValueError` at the `date.fromisoformat()` call; the VM builder should wrap in `try: ... except ValueError: trend_template_state = "undefined"` + WARN-log so a corrupt single row doesn't 500 the review form. Discriminating test: plant a row with `window_end_date = "not-a-date"`; assert VM populates `'undefined'` + WARN logged + page renders 200. Template inserts `<span class="trend-template-{{ vm.trend_template_state }}">{{ vm.trend_template_state }}</span>` or similar render.

- [ ] **Step 4: Implement Gap B.2** — NEW `VolumeProfileRow` frozen dataclass at `swing/web/view_models/patterns/review_form.py`:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class VolumeProfileRow:
    """30-session volume sum + 50d avg ratio for review form rendering."""
    recent_30session_volume_sum: int
    prior_50day_avg_volume: float
    ratio_pct: float

    def __post_init__(self) -> None:
        if self.recent_30session_volume_sum < 0:
            raise ValueError("recent_30session_volume_sum must be non-negative")
        if self.prior_50day_avg_volume < 0:
            raise ValueError("prior_50day_avg_volume must be non-negative")
        # ratio_pct is float; no specific bounds (could be 0..>>100).
```

Read OHLCV via `swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)` (OQ-14 LOCK); compute 30-session sum from latest 30 bars + 50d avg from preceding 50 bars; ratio_pct = `100.0 * recent / prior`. Template renders inline SVG sparkline (SVG bytes don't flow through stdout per Windows cp1252 safety).

- [ ] **Step 5: Implement Gap B.6** — extend `swing/patterns/active_learning.py:prioritize_candidates` criterion 3 (`underrepresented_regime`). The `pattern_exemplars` table has NO `weather_state_at_labeling` column (verified against `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:64-106`). Read-side derivation: JOIN to `weather_runs` at-or-before `pattern_exemplars.created_at` per Codex R1 CRITICAL #1 closure. Spec §5.10 line 799 LOCK: "low historical exemplar count for current weather state".

Column-verified schema (per `swing/data/migrations/0003_phase2_pipeline_trades.sql:4-15`): `weather_runs` columns `id`, `run_ts` (ISO timestamp), `asof_date`, `ticker` (default 'QQQ'; per-cfg via `cfg.rs.benchmark_ticker`), `status` (CHECK values: 'Bullish', 'Caution', 'Bearish'), close, sma10/20/50, etc.

Per Codex R2 MAJOR #3 closure — the current `prioritize_candidates(conn, *, top_k=20)` signature at `swing/patterns/active_learning.py:162-163` does NOT take cfg; the criterion 3 weather-state feature requires plumbing `benchmark_ticker` THROUGH the caller chain. T-A.6c.3 extends the signature to `prioritize_candidates(conn, *, top_k=20, benchmark_ticker: str = "QQQ")` AND extends the caller `build_patterns_queue_vm(conn, cfg, ...)` to read `cfg.rs.benchmark_ticker` + pass it forward. The route handler at `swing/web/routes/patterns.py:patterns_queue_page` already has access to `cfg` via the existing DI pattern (verify exact accessor at executing-plans phase via `Grep "def patterns_queue_page" swing/web/routes/patterns.py`). The plumbing requires changes to: (a) `prioritize_candidates` signature; (b) `build_patterns_queue_vm` signature; (c) `patterns_queue_page` call site. Default `"QQQ"` matches `weather_runs` schema default at migration 0003 line 8.

```python
def prioritize_candidates(
    conn: sqlite3.Connection, *, top_k: int = 20, benchmark_ticker: str = "QQQ",
) -> list[CandidatePriority]:
    """... existing docstring ...

    Criterion 3 (underrepresented_regime) — weather-state-aware per spec §5.10 line 799.
    For each candidate's pattern_class, count confirmed exemplars whose labeling-time
    weather status matches the CURRENT market weather status. Rank candidates whose
    pattern_class has the LOWEST same-status count (with tie-break by candidate id desc).

    benchmark_ticker: passed in from cfg.rs.benchmark_ticker by the caller
        (build_patterns_queue_vm). Defaults to 'QQQ' to match weather_runs schema default.
    """
    # Current weather status — use the canonical weather getter; ticker per caller's cfg.
    current_weather = get_latest(conn, ticker=benchmark_ticker)
    current_status = current_weather.status if current_weather else None

    # Criterion 3 query: per-pattern_class count of confirmed exemplars whose
    # labeling-time weather status (derived via at-or-before JOIN on weather_runs)
    # matches the current market status. NULL status for pre-Phase-8 exemplars
    # or no-weather-row-at-time excluded from the count (conservative).
    exemplar_counts: dict[str, int] = {}
    if current_status is not None:
        rows = conn.execute(
            """
            SELECT px.proposed_pattern_class AS pattern_class, COUNT(*) AS n
            FROM pattern_exemplars px
            INNER JOIN (
                SELECT px2.id AS exemplar_id, wr.status AS labeling_status
                FROM pattern_exemplars px2
                INNER JOIN weather_runs wr
                    ON wr.ticker = ?
                   AND wr.run_ts = (
                       SELECT MAX(run_ts) FROM weather_runs
                       WHERE ticker = ? AND run_ts <= px2.created_at
                   )
            ) lwr ON lwr.exemplar_id = px.id
            WHERE px.final_decision = 'confirmed'
              AND lwr.labeling_status = ?
            GROUP BY px.proposed_pattern_class
            """,
            (benchmark_ticker, benchmark_ticker, current_status),
        ).fetchall()
        exemplar_counts = {row[0]: row[1] for row in rows}

    # ... fold counts into per-candidate priority ranking; pattern_class with
    # the LOWEST count gets the highest criterion-3 priority weight ...
```

(Per Expansion #4 NEW refinement, the SQL skeleton's columns are verified at writing-plans phase. Per Codex R2 MAJOR #3 closure, the benchmark_ticker is threaded through the caller chain as a keyword argument rather than discovered via a `_resolve_benchmark_ticker(conn)` helper — the cfg is already available at the route handler boundary, so simple kwarg passing keeps the signature change minimal + explicit. Per Phase 13 closure intent, this is a read-side derivation — NO new column required.)

- [ ] **Step 6: Implement §1.5.2 amendment** — add to `swing/cli.py`. **CRITICAL per Codex R1 MAJOR #2 closure**: the `rule_criteria` synthesis source is the dedicated COLUMN `pattern_exemplars.geometric_score_json` (verified at migration 0020 line 94), NOT a key inside the `labeler_evidence_json` payload (existing 34 exemplars carry payload keys `['confidence', 'evaluation', 'geometric_evidence_narrative']` only). Pass the COLUMN value into the synthesizer.

Also add a NEW repo helper `update_exemplar_labeler_evidence_json(conn, exemplar_id, new_json)` to `swing/data/repos/pattern_exemplars.py` at T-A.6c.3 scope (existing repo exposes `insert_exemplar` + `get_exemplar_by_id` + `list_exemplars` per Codex R1 MINOR #1 audit; no update helper exists). The helper is a thin `UPDATE pattern_exemplars SET labeler_evidence_json = ? WHERE id = ?` executed inside the caller's transaction.

Note re Invariant #5 (migration 0020 lines 149-160): `labeler_evidence_json` is constrained NOT-NULL when `label_source IN ('claude_silver', 'codex_silver', 'curated_gold')` and NULL when `label_source IN ('closed_loop_review', 'organic_trade_history', 'synthetic', 'perturbation')`. The backfill only writes to rows where `labeler_evidence_json IS NOT NULL` (else the augmented payload would violate the NULL-required path). The backfill loop MUST filter to `WHERE labeler_evidence_json IS NOT NULL` (or rely on `list_exemplars` returning the column + skip rows where column is NULL).

```python
import json
import click
from swing.data.db import open_main_db
from swing.data.repos.pattern_exemplars import (
    list_exemplars, update_exemplar_labeler_evidence_json,
)

@click.command("patterns-exemplars-backfill-labeler-evidence")
def patterns_exemplars_backfill_labeler_evidence() -> None:
    """One-shot backfill: synthesize rule_criteria + narrative keys on existing pattern_exemplars.

    Idempotent: re-runs are no-ops on already-augmented payloads. Fail-soft per row.
    ASCII-only output per Windows cp1252 safety.
    """
    conn = open_main_db()
    augmented, skipped = patterns_exemplars_backfill_labeler_evidence_run(conn)
    click.echo(f"Augmented: {augmented}; Skipped: {skipped}")


def patterns_exemplars_backfill_labeler_evidence_run(conn) -> tuple[int, int]:
    """Backfill runner; returns (augmented_count, skipped_count). Idempotent.

    Synthesis rule (Path C per dispatch brief §1.5.2):
      rule_criteria: enumerate from row.geometric_score_json COLUMN per-rule
                     pass/fail/threshold/tolerance per spec §5.2-§5.6 patterns.
                     NOT from a key inside labeler_evidence_json (Codex R1 MAJOR #2 closure).
      narrative: copy from labeler_evidence_json payload's geometric_evidence_narrative
                 key (the only narrative-shaped value present in the existing 3-key payload
                 shape `['confidence', 'evaluation', 'geometric_evidence_narrative']`).

    Skips rows where labeler_evidence_json IS NULL (Invariant #5 LOCK: those rows
    have label_source in the NULL-required source class).
    """
    augmented, skipped = 0, 0
    for row in list_exemplars(conn):
        if row.labeler_evidence_json is None:
            # Invariant #5 NULL-required source class; nothing to augment.
            continue
        try:
            payload = json.loads(row.labeler_evidence_json)
            if "rule_criteria" in payload and "narrative" in payload:
                skipped += 1
                continue
            # Per Codex R2 MAJOR #5 closure: if rule_criteria is missing AND
            # the geometric_score_json column is NULL/empty, SKIP this row
            # (do NOT write an empty rule_criteria array; the consumer would
            # then have empty-evidence stamped permanently when the source
            # data is simply unavailable). Idempotency LOCK preserved because
            # the skip is per-row + per-run; a later backfill run after the
            # operator populates geometric_score_json will succeed.
            if "rule_criteria" not in payload and not row.geometric_score_json:
                logger.warning(
                    "backfill skipped exemplar %s: geometric_score_json is "
                    "NULL/empty; rule_criteria cannot be synthesized",
                    row.id,
                )
                skipped += 1
                continue
            if "narrative" not in payload:
                payload["narrative"] = payload.get("geometric_evidence_narrative", "")
            if "rule_criteria" not in payload:
                payload["rule_criteria"] = _synthesize_rule_criteria_from_geometric_score(
                    row.geometric_score_json,
                )
            with conn:
                update_exemplar_labeler_evidence_json(
                    conn, row.id, json.dumps(payload, sort_keys=True),
                )
            augmented += 1
        except Exception as exc:  # fail-soft per row
            logger.warning("backfill skipped exemplar %s: %s", row.id, exc)
            skipped += 1
    return augmented, skipped


def _synthesize_rule_criteria_from_geometric_score(
    geometric_score_json: str | None,
) -> list[dict]:
    """Synthesize rule_criteria array from geometric_score_json per-rule entries.

    Input: the geometric_score_json TEXT column value (NOT a key inside
           labeler_evidence_json). Existing exemplars have this column populated
           per Invariant #4 for label_source 'closed_loop_review', etc.; the
           34 existing exemplars' geometric_score_json values were emitted by
           the original silver-labeler dispatch + carry rule breakdown.
    Output: list of {"name": str, "status": "pass"|"fail", "evidence_value": str,
                     "threshold": str, "tolerance": str | None} entries.
    """
    if not geometric_score_json:
        return []
    parsed = json.loads(geometric_score_json)
    criteria: list[dict] = []
    # geometric_score_json shape varies per pattern_class but follows the
    # convention established at T2.SB1 silver-labeler emit contract: a top-level
    # "rules" dict OR a "criteria" array per the pattern's detector module
    # (verify exact shape against operator's sample rows at executing-plans
    # phase by reading a candidate row directly; the implementer notes the
    # actual shape in the executing-plans return report).
    for rule_name, rule_result in (parsed.get("rules") or {}).items():
        criteria.append({
            "name": rule_name,
            "status": "pass" if rule_result.get("pass") else "fail",
            "evidence_value": str(rule_result.get("value", "")),
            "threshold": str(rule_result.get("threshold", "")),
            "tolerance": (
                str(rule_result.get("tolerance"))
                if rule_result.get("tolerance") is not None else None
            ),
        })
    return criteria
```

**NEW repo helper** to add to `swing/data/repos/pattern_exemplars.py` (lands at T-A.6c.3; verify against existing repo's `insert_exemplar`/`get_exemplar_by_id`/`list_exemplars` signatures at executing-plans phase):

```python
def update_exemplar_labeler_evidence_json(
    conn: sqlite3.Connection, exemplar_id: int, new_json: str,
) -> None:
    """Update labeler_evidence_json for a single exemplar. Caller wraps in `with conn:`.

    Validates JSON parses; raises ValueError on missing exemplar id.
    Used by the one-shot labeler_evidence_json backfill subcommand (T-A.6c.3).
    """
    json.loads(new_json)  # validates; raises json.JSONDecodeError if malformed
    cur = conn.execute(
        "UPDATE pattern_exemplars SET labeler_evidence_json = ? WHERE id = ?",
        (new_json, exemplar_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"pattern_exemplar id={exemplar_id} not found")
```

Register the CLI subcommand in the existing `swing.cli` registry per the existing pattern (verify at executing-plans phase via `Grep "def patterns_" swing/cli.py`).

- [ ] **Step 7: Run all 18 new tests; verify PASS.**

- [ ] **Step 8: Run full fast-test suite + ruff check; verify regression-free.**

- [ ] **Step 9: Commit** — `feat(phase13): Gap B no-schema + labeler_evidence backfill (T-A.6c.3)`

```bash
git add swing/web/view_models/patterns/review_form.py swing/web/view_models/patterns/queue.py swing/web/templates/patterns/review.html.j2 swing/patterns/active_learning.py swing/web/routes/patterns.py swing/data/repos/pattern_exemplars.py swing/cli.py tests/web/test_routes/test_patterns_review_data_completeness.py tests/web/test_routes/test_patterns_queue.py tests/cli/test_patterns_exemplars_backfill_labeler_evidence.py
git commit -m "feat(phase13): Gap B no-schema + labeler_evidence backfill (T-A.6c.3)"
```

Commit message body enumerates: 9 Gap B.1+B.2 + 4 Gap B.6 + 5 §1.5.2 amendment = 18 NEW; Path C backfill rule (synthesize rule_criteria from `pattern_exemplars.geometric_score_json` COLUMN; copy narrative from `geometric_evidence_narrative` payload key; preserve original keys; idempotent; fail-soft per row); NEW repo helper `update_exemplar_labeler_evidence_json` lands in T-A.6c.3 scope at `swing/data/repos/pattern_exemplars.py` (per Codex R2 MINOR #1); benchmark_ticker plumbed through `prioritize_candidates` + `build_patterns_queue_vm` for Gap B.6 (per Codex R2 MAJOR #3); Path A V2-banked.

**Watch items:**
- Gap B.1 trend-template state uses `swing.patterns.foundation.current_stage(conn, ticker, date.fromisoformat(window_end_date))` — window-bound + deterministic; NOT session-anchor-bound (per Codex R2 MAJOR #2 + R3 MAJOR #2 closure). The CLAUDE.md "Session-anchor read/write mismatch" gotcha does NOT apply here because there is no read/write anchor mismatch — both write (V1 doesn't write; this is read-only) and read use the evaluation's own window_end_date. Discriminating test for malformed window_end_date asserts graceful fallback to 'undefined' (not 500).
- W16 (ASCII-only narrative + template literals) — labeler backfill emits ASCII-only.

**Step 10 (operator-paired post-merge; tracked separately):** operator runs `python -m swing.cli patterns-exemplars-backfill-labeler-evidence` against operator DB to augment existing 34 exemplar payloads; subsequent `/patterns/exemplars` renders show populated rule_criteria + narrative. This step is operator-invoked AFTER merge; NOT part of the implementer's commit chain.

### §G.4 T-A.6c.4 — SB6 closure Gap B v21-dependent + entry-form anchor threading + entry-path mapping fix + VM/builder extensions (consumes Delta A + B; sequential after T-A.6c.1)

**Files:**
- Modify: `swing/web/routes/patterns.py:patterns_review_post` (Gap B.3 label_source split via candidate-scope lookup).
- Modify: `swing/web/view_models/patterns/review_form.py:OutcomeDistributionRow` (Gap B.4 — extend with reached_1r_pct + hit_stop_pct).
- Modify: `swing/metrics/pattern_outcomes.py:build_pattern_outcome_rows` (Gap B.5 — LEFT JOIN trades; extend `PatternOutcomeRow`).
- Modify: `swing/web/routes/trades.py:398` (`GET /trades/entry/form` — populate hidden anchors via VM at form-render time).
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2` (canonical entry-form template — emit hidden inputs).
- Modify: `swing/web/view_models/trades.py` — extend `EntryFormVM` (or canonical entry-form VM; verify exact name) with 3 new fields + `build_entry_form_vm(...)` builder population.
- Modify: `swing/web/view_models/dashboard.py` — extend `HypRecsExpandedVM` (lines 567-603) with `pattern_evaluation_id` + `pipeline_run_id`; extend `build_hyp_recs_expanded(...)` builder.
- Modify: `swing/web/routes/trades.py:413` (`POST /trades/entry` — 5-tier rejection ladder + claim-consistency gate per §C.5).
- Modify: `swing/web/routes/trades.py:1095` (entry-path mapping fix per R6 MAJOR #2).
- Modify: `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` (line 41-45 — extend entry-form link with `pattern_evaluation_id` query param).
- Modify: `swing/trades/entry.py` (canonical trade entry service — populate `candidate_id` + `pattern_evaluation_id` per §C.5 + OQ-11 lifecycle).
- Modify: `tests/web/test_routes/test_patterns_review.py` (extend with B.3 + B.4 tests).
- Modify: `tests/web/test_routes/test_metrics_pattern_outcomes.py` (extend with B.5 tests).
- Create: `tests/trades/test_entry_populates_candidate_backlinks.py` (NEW lifecycle test).
- Modify: `tests/web/test_routes/test_trades_entry.py` (extend with anchor-threading + 5-tier rejection + claim gate tests; create if missing).

**Acceptance criteria (per brainstorm spec §6.4):**
- **31 new tests PASS** (15 closure: 5 B.3 + 5 B.4 + 5 B.5; 13 anchor-threading: 5-tier ladder + claim-gate + missing-symmetry + server-derived discipline; 1 entry-path-mapping; 2 VM/builder per R7 MAJOR #1).
- S2 (Item 8) + S7 + S9 + S10 operator-witnessed gates PASS.
- Existing prior-task fast tests still PASS (no regression).
- ruff check swing/ clean.

Per superpowers:writing-plans bite-sized-step discipline + Codex R1 MAJOR #3 closure: the 31-test authoring work splits into 5 sub-steps (1a-1e) grouped by behavior, plus 1f run-fail. Each sub-step is ~5-10 minutes of authoring with tests sharing fixture pattern within the group.

- [ ] **Step 1a: Write 5 failing Gap B.3 label_source split tests.**

Group A — Gap B.3 label_source split (5 tests):

```python
def test_patterns_review_post_label_source_organic_trade_history_when_trade_opened_on_same_candidate(
    v21_db, sample_pattern_evaluation, sample_trade_on_candidate,
):
    """Gap B.3 positive — operator confirm + matching trade -> organic_trade_history."""
    response = client.post(
        f"/patterns/{sample_pattern_evaluation.id}/review",
        data={"decision": "confirm", ...},
    )
    assert response.status_code == 200
    row = v21_db.execute(
        "SELECT label_source FROM pattern_exemplars WHERE evaluation_id = ?",
        (sample_pattern_evaluation.id,),
    ).fetchone()
    assert row[0] == "organic_trade_history"


def test_patterns_review_post_label_source_closed_loop_review_when_no_trade_opened(...):
    """Gap B.3 negative — operator confirm + no matching trade -> closed_loop_review."""
    ...


def test_patterns_review_post_label_source_does_not_regress_to_ticker_proxy_with_unrelated_candidate(...):
    """Gap B.3 ticker-proxy-regression LOCK (T2.SB6b R1 MAJOR #3) — discriminating test:
       2 trades on same ticker from candidate A + candidate B; review candidate A;
       assert label_source resolves via candidate-scope lookup, NOT ticker-proxy.
    """
    # Plant candidate A + trade_A on candidate A.
    # Plant candidate B + trade_B on candidate B (same ticker).
    # Review candidate A's pattern_evaluation.
    # Assert label_source == 'organic_trade_history' (trade_A matches).
    # Now review candidate B's pattern_evaluation independently.
    # Assert label_source == 'organic_trade_history' (trade_B matches).
    # Now plant candidate C with no trade.
    # Assert label_source == 'closed_loop_review' (no trade for candidate C
    # despite same ticker).
    ...


def test_patterns_review_post_label_source_only_emits_organic_when_decision_is_confirm(...): ...
def test_patterns_review_post_label_source_emits_closed_loop_when_decision_is_not_confirm(...): ...
```

- [ ] **Step 1b: Write 5 failing Gap B.4 outcome distribution bucketing tests.**

Group B — Gap B.4 outcome distribution bucketing (5 tests):

```python
def test_outcome_distribution_reached_1r_computation_via_max_daily_high(v21_db, ...):
    """Gap B.4 — reached_1r per OQ-6: max(daily_high since entry) >= entry + (entry - stop)."""
    ...

def test_outcome_distribution_hit_stop_computation_via_fill_at_or_below_initial_stop(...): ...
def test_outcome_distribution_suppression_at_n_lt_5_per_phase10_honesty(...): ...
def test_outcome_distribution_wilson_ci_emission_at_n_geq_5(...): ...
def test_outcome_distribution_vm_template_render_with_non_null_pcts(...): ...
```

- [ ] **Step 1c: Write 5 failing Gap B.5 metric tile tests.**

Group C — Gap B.5 metric tile (5 tests):

```python
def test_pattern_outcome_rows_left_join_denominator_via_confirmed_pattern_exemplars(...): ...
def test_pattern_outcome_rows_numerator_via_trades_candidate_id_with_outcome_bucket(...): ...
def test_pattern_outcome_rows_per_pattern_class_aggregation(...): ...
def test_pattern_outcome_rows_suppressed_at_denominator_lt_5(...): ...
def test_pattern_outcome_rows_banner_pin_populates_unresolved_count_and_link(...): ...
```

- [ ] **Step 1d: Write 13 failing anchor-threading tests at POST /trades/entry per §C.5.**

Group D — Anchor-threading at POST /trades/entry per §C.5 (13 tests):

```python
def test_entry_form_renders_pattern_evaluation_id_hidden_anchor_for_pipeline_origin(...): ...
def test_entry_form_omits_pattern_evaluation_id_hidden_anchor_for_manual_off_pipeline(...): ...
def test_entry_post_rejects_malformed_pattern_evaluation_id_anchor_400_clears_on_recovery(...): ...  # tier (a)
def test_entry_post_rejects_pattern_evaluation_id_not_found_400_clears(...): ...                       # tier (b)
def test_entry_post_rejects_pattern_evaluation_id_ticker_mismatch_400_clears(...): ...                 # tier (c)
def test_entry_post_rejects_pattern_evaluation_id_pipeline_run_mismatch_400_clears(...): ...           # tier (d) value
def test_entry_post_rejects_pattern_evaluation_id_present_with_pipeline_run_id_at_form_render_omitted_400_clears(...): ...  # tier (d) missing
def test_entry_post_rejects_server_derived_manual_off_pipeline_with_pattern_evaluation_id_anchor_400_clears(...): ...  # tier (e)
def test_entry_post_rejects_pattern_evaluation_id_anchor_present_with_claim_field_omitted_400_clears(...): ...  # claim coercion
def test_entry_post_rejects_claim_present_without_anchor_400_clears(...): ...                          # claim (i)
def test_entry_post_rejects_anchor_present_without_claim_400_clears(...): ...                          # claim (ii)
def test_entry_post_rejects_server_derived_manual_off_pipeline_with_claim_true_400_clears(...): ...    # claim (iii)
def test_entry_post_persists_null_pattern_evaluation_id_when_manual_off_pipeline_origin(...): ...      # negative coverage
```

- [ ] **Step 1e: Write 3 failing entry-path mapping + VM/builder extension tests.**

Group E — entry-path mapping fix + VM/builder extensions (3 tests):

```python
def test_entry_post_maps_ui_origin_hyp_recs_to_entry_path_hyp_recs_button(...): ...  # R6 MAJOR #2
def test_build_entry_form_vm_populates_pattern_evaluation_anchor_fields_when_pattern_evaluations_row_exists(...): ...  # R7 MAJOR #1
def test_build_hyp_recs_expanded_populates_pattern_evaluation_id_when_evaluation_row_exists(...): ...                  # R7 MAJOR #1
```

- [ ] **Step 1f: Run all 31 new tests; verify ALL FAIL.**

Run: `python -m pytest tests/web/test_routes/test_patterns_review.py tests/web/test_routes/test_metrics_pattern_outcomes.py tests/trades/test_entry_populates_candidate_backlinks.py tests/web/test_routes/test_trades_entry.py -v`
Expected: All 31 FAIL with VM-field-missing errors / SQL skeleton not yet implemented / POST handler unchanged from T2.SB6b.

- [ ] **Step 2: Implement Gap B.3** — extend `patterns_review_post` at `swing/web/routes/patterns.py` to resolve `candidates.id` via §D.3 SQL skeleton (JOIN through `pipeline_runs.evaluation_run_id`); look up trades via `trades.candidate_id`; if row exists AND decision is `confirm`, emit `label_source='organic_trade_history'`; else `label_source='closed_loop_review'`.

- [ ] **Step 3: Implement Gap B.4** — extend `OutcomeDistributionRow` with `reached_1r_pct: float | None` + `hit_stop_pct: float | None`. Compute via the §D.3 SQL skeleton with OQ-6 bucketing predicates. Suppression at n<5; Wilson CI per Phase 10 honesty.

- [ ] **Step 4: Implement Gap B.5** — extend `PatternOutcomeRow` + `build_pattern_outcome_rows` per §D.3 SQL skeleton. LEFT JOIN denominator = confirmed pattern_evaluations; numerator = subset with trades + outcome bucket met; per-pattern_class aggregation; suppression at denominator<5.

- [ ] **Step 5: Implement VM/builder extensions (Group E)** —

(a) Extend `EntryFormVM` (verify exact name via `Grep "class EntryFormVM\\|class EntryForm" swing/web/view_models/trades.py`) with 3 new fields:

```python
@dataclass(frozen=True)
class EntryFormVM:
    # ... existing fields unchanged ...
    pattern_evaluation_id: int | None = None
    claimed_pattern_evaluation_anchor: bool = False
    pipeline_run_id_at_form_render: int | None = None
```

(b) Extend `build_entry_form_vm(...)` to populate the 3 fields when the entry context provides a `pattern_evaluations` row (looked up via `(pipeline_run_id, ticker)` for `pipeline_aplus` / `pipeline_watch_hyp_recs` / `pipeline_watch_manual` origins). For `manual_off_pipeline`, all 3 fields stay at default (None / False).

(c) Extend `HypRecsExpandedVM` (existing dataclass at `swing/web/view_models/dashboard.py:567-603`) with `pattern_evaluation_id: int | None` + `pipeline_run_id: int | None` per hyp-rec row.

(d) Extend `build_hyp_recs_expanded(...)` to lookup `pattern_evaluations.id` for each hyp-rec row via `(pipeline_run_id, ticker, pattern_class)` — UNAMBIGUOUS per the unique index at `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:253-254` (`UNIQUE INDEX idx_pattern_evaluations_run_ticker_class ON pattern_evaluations(pipeline_run_id, ticker, pattern_class)`).

The hyp-rec card already carries `pattern_class` context (hyp-recs are pattern-class-based recommendations rendered per-class per-ticker). The builder uses the SPECIFIC pattern_class shown to the operator on the card as the third lookup-tuple element. Per Codex R1 MAJOR #1 closure: do NOT order-by composite_score + LIMIT 1; that would reintroduce the brainstorm-spec-rejected "highest composite" attribution. SQL skeleton:

```sql
SELECT id FROM pattern_evaluations
WHERE pipeline_run_id = ? AND ticker = ? AND pattern_class = ?;
```

If the hyp-rec row's `pattern_class` context is unavailable at builder time (rare; should not happen for valid hyp-recs — every hyp-rec row knows its class because the row was emitted by a pattern detector), populate `pattern_evaluation_id = None` + emit NO claim flag → manual_off_pipeline path applies + trade persists with `pattern_evaluation_id = NULL`. This honors operator-intent provenance per spec §2.2 OQ-12 disposition.

Discriminating test (mirroring §G.4 Group E test_build_hyp_recs_expanded): plant 2 `pattern_evaluations` rows for same `(pipeline_run_id, ticker)` tuple with DIFFERENT pattern_class values (e.g., VCP + flat_base); render the hyp-rec card for the VCP variant; assert `vm.pattern_evaluation_id` resolves to the VCP-class row's id (NOT the higher-composite flat_base row). This guards against the highest-composite regression.

- [ ] **Step 6: Implement template emission (Layer 2)** —

(a) Extend `swing/web/templates/partials/trade_entry_form.html.j2` to emit hidden inputs when VM fields populated:

```jinja
{% if vm.pattern_evaluation_id is not none %}
<input type="hidden" name="pattern_evaluation_id" value="{{ vm.pattern_evaluation_id }}">
<input type="hidden" name="claimed_pattern_evaluation_anchor" value="{{ 'true' if vm.claimed_pattern_evaluation_anchor else 'false' }}">
<input type="hidden" name="pipeline_run_id_at_form_render" value="{{ vm.pipeline_run_id_at_form_render }}">
{% endif %}
```

(b) Extend `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` at line 41-45 to pass `pattern_evaluation_id` query param when the hyp-rec row carries it:

```jinja
<a href="/trades/entry/form?ticker={{ row.ticker }}&origin=hyp-recs{% if row.pattern_evaluation_id %}&pattern_evaluation_id={{ row.pattern_evaluation_id }}{% endif %}">Enter trade</a>
```

(c) Audit any other entry-form-link emitters via `Grep -r "trade_entry_form\\|/trades/entry/form" swing/web/templates/` at executing-plans phase; extend each link emitter found.

- [ ] **Step 7: Implement POST handler 5-tier rejection ladder + claim-consistency gate + entry-path mapping fix (Layer 3 + Layer 4)** —

(a) Add `_reject_pattern_evaluation_anchor(...)` helper to `swing/web/routes/trades.py` (mirror `_reject_anchor` at line 896-911 EXACTLY; T3.SB1 precedent):

```python
def _reject_pattern_evaluation_anchor(
    request: Request, vm_for_recovery, message: str,
):
    """Render the entry form with the bad anchor + claim CLEARED on recovery
    (T3.SB1 R3 M#2 LOCK + T2.SB6c §C.5 recovery-clear discipline).
    """
    vm_clean = vm_for_recovery._replace(  # if NamedTuple; else use dataclasses.replace
        pattern_evaluation_id=None,
        claimed_pattern_evaluation_anchor=False,
        pipeline_run_id_at_form_render=None,
    )
    return TemplateResponse(
        request,
        "partials/trade_entry_form.html.j2",
        {"vm": vm_clean, "error_message": message},
        status_code=400,
    )
```

(b) In the existing POST `/trades/entry` handler at line 413, add the 5-tier rejection ladder + claim-consistency gate per §C.5 BEFORE the existing `insert_trade_with_event` call. The 5 tiers map verbatim to the 5 group-D tests above. After all 5 tiers + the 3-rule claim-consistency gate pass, the authoritative `pattern_evaluation_id` is the server-re-derived value from tier (b)'s row fetch (NOT the operator-submitted hidden input).

(c) Fix `swing/web/routes/trades.py:1095` per R6 MAJOR #2: replace hardcoded `entry_path=EntryPath.MANUAL_WEB_FORM` with mapping from UI `origin` form field:

```python
from swing.trades.origin import EntryPath  # verify exact import path at executing-plans phase

ui_origin = form_data.get("origin", "manual")
if ui_origin == "hyp-recs":
    entry_path = EntryPath.HYP_RECS_BUTTON
elif ui_origin == "watchlist":
    entry_path = EntryPath.MANUAL_WEB_FORM
else:
    entry_path = EntryPath.MANUAL_WEB_FORM
```

(d) Extend `swing/trades/entry.py:record_entry` (canonical trade entry service; verify exact function name at executing-plans phase via `Grep "def record_entry\\|insert_trade_with_event" swing/trades/`) to populate `candidate_id` + `pattern_evaluation_id` per §B.1 OQ-11 lifecycle + §C.5 Layer 3 server-derived value. The lookup queries (§B.1):

- Candidate resolution: prefer Path 1 (`evaluation_run_id` filter) if `_latest_complete_evaluation_run_id(conn)` returns a value matching the entry's pipeline-run context; else Path 2 (two-table JOIN via `pipeline_runs.id`). DO NOT MIX the two — passing an `evaluation_run_id` into a `pipeline_runs.id` filter would silently miss/wrong-match.
- Pattern_evaluations resolution: use the server-derived `pattern_evaluation_id` from the POST handler's 5-tier rejection ladder + claim-consistency gate (NOT the operator-submitted hidden input).

Both lookups execute INSIDE the entry service's own transactional block (which owns its `BEGIN IMMEDIATE` per existing entry service contract; do NOT re-open a separate transaction).

- [ ] **Step 8: Run all 31 new tests; verify PASS.**

- [ ] **Step 9: Run full fast-test suite + ruff check; verify regression-free.**

- [ ] **Step 10: Commit** — `feat(phase13): Gap B v21-dep + entry anchor threading (T-A.6c.4)`

```bash
git add swing/web/routes/patterns.py swing/web/view_models/patterns/review_form.py swing/metrics/pattern_outcomes.py swing/web/routes/trades.py swing/web/templates/partials/trade_entry_form.html.j2 swing/web/view_models/trades.py swing/web/view_models/dashboard.py swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2 swing/trades/entry.py tests/web/test_routes/test_patterns_review.py tests/web/test_routes/test_metrics_pattern_outcomes.py tests/trades/test_entry_populates_candidate_backlinks.py tests/web/test_routes/test_trades_entry.py
git commit -m "feat(phase13): Gap B v21-dep + entry anchor threading (T-A.6c.4)"
```

Commit message body enumerates: 15 closure (Gap B.3 + B.4 + B.5) + 13 anchor-threading + 1 entry-path-mapping + 2 VM/builder = 31 NEW; OQ-11 + OQ-12 lifecycle CLOSURE-COMMITTED; entry-path mapping fix at trades.py:1095; T3.SB1 4-tier extended to 5-tier with server-derived discipline.

**Watch items:**
- W7 (cross-row semantic audit — Expansion #7 BINDING) — Gap B.3 candidate-scope lookup MUST be per-candidate (NOT ticker-proxy); discriminating regression test planted in Group A above.
- W14 (Hidden anchor 5-tier rejection ladder + claimed-anchor consistency gate) — T3.SB1 LOCK extended.
- L9 (server-recompute at POST) — POST handler re-derives `pattern_evaluation_id` from canonical state, NOT operator-submitted hidden input.
- W10 (synthetic-fixture-vs-production-emitter shape drift) — Gap B.4 + B.5 tests use production-shape fixtures (real `pattern_evaluations.composite_score` + real `pattern_exemplars.final_decision='confirmed'` + real `fills` cross-join). NO synthetic shortcut shapes.
- §C.5 server-derived vs form-submitted value-domain discipline — claim consistency-check tier (iii) cites `derive_trade_origin` (server-derived), NOT form UI origin.

### §G.5 T-A.6c.5 — Closer (E2E + ruff sweep + cross-bundle pin row 12 promote; sequential after all)

**Files:**
- Create: `tests/integration/test_phase13_t2_sb6c_v21_closure_e2e.py` (1 fast E2E walking the full happy path).
- Modify: `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` — un-skip the row 12 parametrized pin if planted as `@pytest.mark.skip` in T-A.6c.1 (verify if a skip marker was used; remove if so).
- Modify: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §H.3 — append row 12 to the cross-bundle pin schedule table.

**Acceptance criteria:**
- 1 new fast E2E PASSES.
- 0 ruff E501 / E violations across `swing/`.
- All prior-task tests PASS in cumulative run.
- Phase 13 plan §H.3 row 12 documented as un-skipped.

- [ ] **Step 1: Write 1 fast E2E** at `tests/integration/test_phase13_t2_sb6c_v21_closure_e2e.py` walking the full happy path:

```python
def test_phase13_t2_sb6c_v21_closure_happy_path_e2e(v21_db, ...):
    """E2E: pipeline run -> pattern_evaluations rows -> trade entry with anchor
    -> outcome rolls forward via cohort metric tile.
    """
    # 1. Run a fake pipeline that emits pattern_evaluations + candidates.
    run_id = _seed_pipeline_run_with_evaluations_and_candidates(v21_db, ticker="CVGI")

    # 2. Operator submits trade entry via POST /trades/entry with anchor.
    response = client.post(
        "/trades/entry",
        data={
            "ticker": "CVGI",
            "origin": "hyp-recs",
            "pattern_evaluation_id": "<real_evaluation_id>",
            "claimed_pattern_evaluation_anchor": "true",
            "pipeline_run_id_at_form_render": str(run_id),
            # ... other entry form fields ...
        },
    )
    assert response.status_code == 204
    # Verify trade got candidate_id + pattern_evaluation_id populated.
    trade = v21_db.execute(
        "SELECT candidate_id, pattern_evaluation_id FROM trades WHERE ticker = 'CVGI'"
    ).fetchone()
    assert trade[0] is not None
    assert trade[1] is not None

    # 3. Operator confirms pattern at /patterns/<id>/review.
    response = client.post(
        f"/patterns/{evaluation_id}/review",
        data={"decision": "confirm", ...},
    )
    assert response.status_code in (200, 204)
    row = v21_db.execute(
        "SELECT label_source FROM pattern_exemplars WHERE evaluation_id = ?",
        (evaluation_id,),
    ).fetchone()
    assert row[0] == "organic_trade_history"  # Gap B.3 closure

    # 4. Outcome bucket: simulate trade hitting 1R.
    _seed_fill_at_1r_above_entry(v21_db, trade_id=...)

    # 5. Metric tile renders non-None reached_1r_pct.
    response = client.get("/metrics/pattern-outcomes")
    assert response.status_code == 200
    assert "reached_1r_pct" in response.text  # or VM field inspection
    # ... more granular assertion on cohort row for CVGI's pattern_class ...
```

- [ ] **Step 2: Run E2E; verify PASS.**

Run: `python -m pytest tests/integration/test_phase13_t2_sb6c_v21_closure_e2e.py -v`
Expected: 1 PASS.

- [ ] **Step 3: Run full fast-test suite + ruff sweep.**

Run: `python -m pytest -m "not slow" -q swing/ tests/`
Expected: 5559 + 92-95 = 5651-5654 fast tests PASS + 1 fast E2E PASS.
Run: `ruff check swing/`
Expected: All checks passed.

- [ ] **Step 4: Un-skip cross-bundle pin row 12** (if planted as `@pytest.mark.skip` in T-A.6c.1). Verify the pin tests are GREEN in the cumulative run.

- [ ] **Step 5: Append row 12 to Phase 13 plan §H.3 cross-bundle pin schedule** in `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` table after row 11:

```markdown
| `test_phase13_t2_sb6c_v21_trade_backlinks_schema_atomic` | T2.SB6c T-A.6c.1 | T2.SB6c T-A.6c.5 closer | v21 trades backlinks schema + FK + index + mapper + INSERT roundtrip per Delta |
```

- [ ] **Step 6: Commit** — `test(phase13): T2.SB6c closer + cross-bundle pin row 12 (T-A.6c.5)`

```bash
git add tests/integration/test_phase13_t2_sb6c_v21_closure_e2e.py tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md
git commit -m "test(phase13): T2.SB6c closer + cross-bundle pin row 12 (T-A.6c.5)"
```

Commit message body enumerates: 1 fast E2E covering full closure happy-path; cross-bundle pin row 12 promoted (un-skipped + GREEN); Phase 13 plan §H.3 documented; T2.SB6c arc CLOSURE (ZERO V1 STUBs remaining on §5.10 8-item checklist + chart_renders cache populated + labeler_evidence_json backfill subcommand shipped).

---

## §H Dispatch sequence + dependency graph

### §H.1 Sub-bundle dependency graph

```
main HEAD (c9bd715)
    |
    +----- T-A.6c.1 (v21 migration; foundation)
    |          | (no schema-dep blocks T-A.6c.2 or T-A.6c.3)
    |          v
    |      T-A.6c.4 (consumes Delta A + B; sequential)
    +----- T-A.6c.2 (Gap A wiring + §1.5.1; no schema dep; concurrent)
    |          v
    +----- T-A.6c.3 (Gap B no-schema + §1.5.2; no schema dep; concurrent)
                                v
                       T-A.6c.5 (closer; sequential after all 4)
```

### §H.2 Concurrent dispatch (RECOMMENDED per OQ-10 LOCK)

Per superpowers:dispatching-parallel-agents discipline: dispatch T-A.6c.1 + T-A.6c.2 + T-A.6c.3 concurrently as 3 separate subagent invocations from the orchestrator. Each subagent works in its own worktree branch (sub-branches off `main` HEAD `c9bd715`); each ships its own commit. After all 3 ship + are merged in any order (T-A.6c.2 + T-A.6c.3 do NOT depend on T-A.6c.1's schema; T-A.6c.1 introduces 2 NULLable columns + does NOT change existing schemas), T-A.6c.4 dispatches sequentially against the post-merge HEAD. T-A.6c.5 dispatches last after T-A.6c.4 merges.

Expected wall-clock savings ~30-40% per OQ-10 disposition.

**Merge ordering**: T-A.6c.1 merges FIRST to land v21 schema; T-A.6c.2 + T-A.6c.3 can merge in either order (no inter-dependency); T-A.6c.4 merges after the prior 3 ship to consume Delta A + B; T-A.6c.5 merges last.

**Per-task worktree** convention (per the dispatch brief): each T-A.6c.X dispatch gets its own branch `phase13-t2-sb6c-sub-bundle-T-A-6c-X` branched from main HEAD at dispatch time.

### §H.3 Sub-bundle merge gates

Each sub-bundle's executing-plans dispatch concludes with:

1. **Operator-witnessed gate** (S1-S11 per `§F.4`; specific gates per task: T-A.6c.1 → S1; T-A.6c.2 → S1+S3+S4+S5+S6+S6b; T-A.6c.3 → S1+S2+S8+S11; T-A.6c.4 → S1+S2(Item 8)+S7+S9+S10; T-A.6c.5 → S1).
2. **Implementer return report** with file:line evidence for each acceptance criterion (per forward-binding lesson #17 — implementer self-report accuracy gate).
3. **Orchestrator QA review** (per BINDING memory `feedback_orchestrator_qa_implementer_product.md`).
4. **Operator approval to merge**.
5. **Orchestrator drives merge + post-merge housekeeping** (per BINDING memory `feedback_orchestrator_performs_merge.md`).
6. **Cross-bundle pin row 12 verification** at T-A.6c.5 closer.

---

## §I Forward-binding lessons inherited

From T2.SB6c brainstorming return report §7 (8 lessons banked) + cumulative gotchas:

### §I.1 Eight lessons from brainstorming

1. **Brief-vs-actual schema reality check (Expansion #2 effective)**: T2.SB6c brainstorm caught the brief §2.3 OBSOLETE proposal at pre-Codex review. Future dispatches: when a brief proposes "NEW table X", verify against `swing/data/migrations/` before consuming brief verbatim. Pre-empt: dispatch-brief authoring at orchestrator side should grep migrations + spec line locks before publishing.

2. **SQL skeleton column verification (NEW Expansion #4 refinement)**: every SQL JOIN written into a spec/plan MUST have its column names verified against the actual schema migration files. The R1 CRITICAL caught `candidates.pipeline_run_id` (non-existent) vs `candidates.evaluation_run_id` (canonical per migration 0001). Pre-empt: at writing-plans phase, treat any SQL JOIN as a load-bearing claim requiring schema-file verification. Applied here: all §D.3 SQL skeletons are column-verified against `swing/data/migrations/0001_phase1_initial.sql:24-26` + `0003_phase2_pipeline_trades.sql:120-129` + `0006_pipeline_chart_linkage.sql:18` + `0020_phase13_charts_patterns_autofill_usability.sql:230-254`.

3. **Function name verification (NEW)**: spec/plan references to existing functions MUST be verified against actual source. R6 caught `resolve_trade_origin` vs `derive_trade_origin` at `swing/trades/origin.py:52`. Pre-empt: at writing-plans phase, grep for any cited function name before publishing. Applied here: §C.5 cites `derive_trade_origin` at line 52 verbatim.

4. **Hidden-anchor missing-value semantics (NEW)**: every hidden form field driving POST-time validation MUST specify the missing-value behavior. R5 caught `claimed_pattern_evaluation_anchor` missing semantics; R6 caught `pipeline_run_id_at_form_render` missing semantics. Default discipline: missing → safe default (typically `False` for boolean flags); rejects fire on missing-while-required pattern. Applied here: §C.5 tier (d) missing-symmetry + claim-coercion-to-false.

5. **Server-derived vs form-submitted value-domain discipline (NEW)**: validation rules that reference `trade_origin` MUST clarify whether the rule checks SERVER-DERIVED (via `swing/trades/origin.py:derive_trade_origin`) or FORM-SUBMITTED (UI origin field). R5 + R7 closed wording slippages between the two domains. Pre-empt: spec/plan rules involving derived domain values MUST cite the resolver function + line number. Applied here: §C.5 tier (e) + claim-consistency tier (iii) cite SERVER-DERIVED.

6. **EntryPath mapping load-bearing for trade_origin derivation (NEW)**: `derive_trade_origin(conn, ticker, entry_path: EntryPath)` cannot distinguish `pipeline_watch_hyp_recs` from `pipeline_watch_manual` if all web POSTs hardcode `EntryPath.MANUAL_WEB_FORM`. R6 caught this load-bearing defect at `swing/web/routes/trades.py:1095`. SB6c T-A.6c.4 fixes it as a side-effect of anchor-threading. Forward-binding: any future spec that consumes derived `trade_origin` MUST verify the entry-path mapping at the consumer's POST handler.

7. **VM/builder fields are part of anchor-threading scope (NEW)**: form-render hidden anchors require VM dataclass fields + builder population + template emission + POST validation. R7 caught the original scope omitting the VM/builder layer. Pre-empt: when specifying a new form anchor, enumerate all 4 layers (VM field + builder population + template emission + POST validation) AND their discriminating tests. Applied here: §C.5 Layer 1 + Layer 2 + Layer 3 + Layer 4 enumerated explicitly.

8. **Schema-version-aware INSERT for nullable columns (R1 expansion)**: even nullable column extensions warrant the `PRAGMA table_info` runtime branch pattern (T3.SB1 fills.py:51-53 precedent) for robustness against v20-fixture tests that bypass migration. Codex R1 MAJOR #2 flagged the "no SVAI needed for nullables" conclusion as unsafe. Applied here: §B.3 BINDING for both Delta A + Delta B.

### §I.2 Inherited cumulative gotchas (key items relevant to T2.SB6c)

From CLAUDE.md (BINDING):

- **Schema-CHECK + Python-constant + dataclass-validator MUST land in same task** (Phase 12 C.A T-A.2) — applied at §C.1.
- **Schema-CHECK widening MUST audit ALL Python-side surface guards** (T3.SB2 hotfix `cf3c489`) — applied at §C.1.7 N-mirror auditing.
- **Read-path mapping must keep pace with write-path** (T3.SB3 R1 M#1) — applied at §C.1.5.
- **Migration runner backup-gate strict equality** (Phase 12 C.A §0.5) — applied at §B.5.
- **`executescript()` implicit-COMMIT** (Phase 7 Sub-A R1 M3) — applied at §B.4 migration body.
- **`INSERT OR REPLACE` cascade-wipe** (Phase 8 daily-management spec §4.2) — BANNED at SB6c by L18 + W6.
- **Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts** (T2.SB6a R1 CRITICAL #1) — applied at §C.3 cache key shape per substrate `ChartRender.__post_init__` semantic validator LOCK.
- **F6 transient-empty at construction barrier** (T2.SB6a R1 MAJOR #2) — applied at §C.3 F6 defense in `_step_charts`.
- **Pre-Codex 7-expansion discipline + 2 NEW refinements** (T2.SB6b lessons + T2.SB6c brainstorm banking) — applied throughout per dispatch brief §3.1.
- **V1 simplification banking discipline** (T2.SB6b lessons) — T2.SB6c is a CLOSURE dispatch; ZERO new V1 STUBs introduced; §D.4 audit table BINDING.
- **Session-anchor read/write mismatch family** (Phase 8 + Phase 13 T1.SB0) — applied at Gap B.1 trend-template state via `get_latest(conn, ticker='^GSPC')` backward-looking anchor.
- **Synthetic-fixture-vs-production-emitter shape drift** (Phase 12 C.D + Phase 13 T2.SB1 + production-data-flow-derivation) — applied at W10 BINDING for Gap B.4 + B.5 tests.
- **`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM** — NO new BaseLayoutVM fields planned for SB6c.
- **HTMX 3-surface discipline** (Phase 5 R1 M1 + M2 + Phase 6 I3 + Phase 8 R2-R5) — applied where new POST routes touched; SB6c does NOT add new POST routes for Q4 (T4.SB owns); existing T2.SB6b POSTs preserved; the modified POST `/trades/entry` at T-A.6c.4 reuses existing HX-Request + HX-Redirect + target-route patterns from T3.SB1.
- **ASCII-only narrative + template literals + CLI output** (T2.SB6b R1 MAJOR #7 em-dash LOCK + Windows cp1252 stdout safety) — applied at §C.4 labeler backfill output + all template literals.

### §I.3 Pre-Codex 7-expansion discipline + 2 NEW refinements BINDING (26th cumulative validation expected at writing-plans phase)

| Expansion | Source | Plan-phase application |
|---|---|---|
| #1 hardcoded-duplicate audit | T3.SB2 hotfix `cf3c489` | §C.1.7 N-mirror auditing of trade SELECT column lists |
| #2 brief-vs-spec source-of-truth + **NEW brief-vs-actual schema reality check** | T2.SB4 R1 M1 + T2.SB6c brainstorm Expansion #2 catch | Plan §B verifies brief §1.5 amendments against actual code state (chart_renders empty; labeler payload 3-key shape) |
| #3 schema-CHECK-vs-semantic-contract gap audit | T2.SB6a R1 CRITICAL #1 | §C.3 cache key shape per ChartRender semantic validator |
| #4 CLAUDE.md gotcha specific-scenario trace + **NEW SQL skeleton column verification** | T2.SB6a R1 MAJOR #2 + T2.SB6c brainstorm R1 CRITICAL #1 banking | §D.3 SQL skeletons column-verified against `swing/data/migrations/*.sql`; F6 specific-scenario trace at §C.3 |
| #5 cross-section spec inventory grep | T2.SB6a R1 MAJOR #3 | Spec §5.10 enumeration cross-checked at §D.4 content-completeness audit table |
| #6 content-completeness audit (FIRST RUN BINDING at T2.SB6b → CONFIRMED at T2.SB6c brainstorm; BINDING at plan phase) | T2.SB6b lessons | §D.4 per-field disposition table; ZERO V1 STUBs post-SB6c |
| #7 cross-row semantic audit on operator-input flows (FIRST RUN BINDING at T2.SB6b → CONFIRMED at T2.SB6c brainstorm; BINDING at plan phase) + **NEW boundary clarification: cross-row semantic SCOPE audit does NOT subsume column/JOIN correctness; Expansion #4 owns that** | T2.SB6b lessons + T2.SB6c brainstorm banking | §D.3 SCOPE enumeration (per-candidate vs per-ticker etc.) DISTINCT from §D.3 SQL column-verification |

### §I.4 V1 simplifications + V2 candidates banked

V1 simplifications at T2.SB6c (closure dispatch — explicit + V2 dependency cited):

| V1 simplification | V2 dependency | Banked for |
|---|---|---|
| Existing pre-v21 trades persist `candidate_id = NULL` + `pattern_evaluation_id = NULL` (no retroactive heuristic match) | OQ-1 LOCK; operator-paired investigation of data quality required | V2 enrichment if operator surfaces value |
| Multi-pattern_class trade backlink = single anchor; one trade attaches to ONE pattern_evaluation | many-to-many `trade_pattern_evaluations` link table to capture "this trade was visible against N detector evaluations at lock time" | V2 schema dispatch |
| Volume profile fetch-on-cache-miss accepted as desired behavior (OQ-14 LOCK) | `get_cached_only` variant for pure read-only scenarios | V2 cache architecture |
| Backup-gate strict-equality skips backup on multi-version jump (v20→v22+) | `--enforce-stepwise` flag on `swing db-migrate` to refuse multi-version jumps | V2 migration-runner enhancement |
| `pattern_evaluations.candidate_id` direct column (alternative to JOIN via pipeline_runs.evaluation_run_id) | If Phase 13.5+ surfaces require frequent per-candidate cross-row lookups, this column would eliminate the two-table JOIN | V2 schema dispatch |
| Phase 6 `chart_pattern_algo` enum (`none`/`flag`) disjoint from Phase 13 detector enum | Unify the two enums via a separate spec dispatch | V2 schema migration |
| Path C labeler_evidence_json backfill (synthesis-from-existing) | Path A labeler subagent emit contract widening — fresh exemplars labeled post-T2.SB6c with rule_criteria + narrative emitted directly | V2 labeler subagent spec dispatch |

NO new V1 STUBs introduced by SB6c per §D.4 content-completeness audit + closure-dispatch intent.

---

## §J References

- **Brainstorm spec**: [`docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`](../specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md) (660 lines; 8 Codex rounds; ZERO ACCEPT-WITH-RATIONALE).
- **Brainstorming return report**: [`docs/phase13-t2-sb6c-brainstorm-return-report.md`](../../phase13-t2-sb6c-brainstorm-return-report.md) (188 lines; commit chain + per-expansion verdict + 8 forward-binding lessons + 6 V1 simplifications + V2 candidates).
- **Writing-plans dispatch brief (AMENDED)**: [`docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md`](../../phase13-t2-sb6c-writing-plans-dispatch-brief.md) at commit `c9bd715` (initial commit at `7297a2b`).
- **Brainstorming dispatch brief (predecessor)**: `docs/phase13-t2-sb6c-v21-closure-brainstorm-dispatch-brief.md`.
- **Phase 13 main plan**: [`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`](2026-05-18-phase13-charts-patterns-autofill-usability-plan.md) §A.14 (paired discipline) + §G.9 (T2.SB6 task §) + §H.3 (cross-bundle pin schedule).
- **Phase 13 main spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §3.2 (chart_renders cache schema) + §4.2 (chart surface inventory) + §5.10 (closed-loop surface 8-item checklist) + §7.2 (Q4 close-tracking flag with D-Q4.1 through D-Q4.7 sub-decisions; line 986 "Q4 schema FOLDS INTO v20" LOCK).
- **Phase 9 Sub-bundle A writing-plans precedent**: similar-scale schema migration ~1100 lines.
- **Phase 12 Sub-sub-bundle C.A writing-plans precedent**: schema-widening atomic-landing.
- **T2.SB6b return report**: `docs/phase13-t2-sb6b-return-report.md` §6 V1 simplifications (closure targets for SB6c).
- **T2.SB6a return report**: `docs/phase13-t2-sb6a-return-report.md` (substrate API surface FROZEN inheritance).
- **CLAUDE.md** at repo root — full cumulative gotcha set.
- **Schema files** (column-verified per Expansion #4 NEW refinement):
  - [`swing/data/migrations/0001_phase1_initial.sql:24-26`](../../../swing/data/migrations/0001_phase1_initial.sql) — `candidates` table keyed on `evaluation_run_id` (NOT `pipeline_run_id`).
  - [`swing/data/migrations/0003_phase2_pipeline_trades.sql:120-129`](../../../swing/data/migrations/0003_phase2_pipeline_trades.sql) — `pipeline_runs` table id-keyed.
  - [`swing/data/migrations/0006_pipeline_chart_linkage.sql:18`](../../../swing/data/migrations/0006_pipeline_chart_linkage.sql) — `pipeline_runs.evaluation_run_id` added (resolver-pattern enabler).
  - [`swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:230-254`](../../../swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql) — `pattern_evaluations` table FK to `pipeline_runs(id) ON DELETE CASCADE`.
- **Trades repo state (canonical for v21 atomic landing)**:
  - [`swing/data/repos/trades.py:47-66`](../../../swing/data/repos/trades.py) — `_TRADE_SELECT_COLS` (52 cols ending at `planned_target_R`).
  - [`swing/data/repos/trades.py:120-146`](../../../swing/data/repos/trades.py) — `INSERT INTO trades` callsite (52 cols + 41 placeholders + 41-tuple).
  - [`swing/data/repos/trades.py:345-413`](../../../swing/data/repos/trades.py) — `_row_to_trade` index map (0..51).
- **Trades dataclass**: [`swing/data/models.py:Trade`](../../../swing/data/models.py) — 52 current fields; v21 adds 2 nullable INTEGER backlinks.
- **Migration runner**: [`swing/data/db.py:39`](../../../swing/data/db.py) (`EXPECTED_SCHEMA_VERSION = 20`) + lines 108-111 (`PHASE13_PRE_MIGRATION_EXPECTED_TABLES`) + lines 446-470 (`_create_pre_phase13_migration_backup`) + lines 634-677 (`_phase13_backup_gate`) + line 728 (`run_migrations` wire-in).
- **Fills repo SVAI precedent**: [`swing/data/repos/fills.py:42-89`](../../../swing/data/repos/fills.py) (T3.SB1).
- **Trade entry path**: [`swing/trades/entry.py`](../../../swing/trades/entry.py) (canonical `record_entry`); [`swing/trades/origin.py:52`](../../../swing/trades/origin.py) (`derive_trade_origin`); [`swing/trades/origin.py:27-37`](../../../swing/trades/origin.py) (`_latest_complete_evaluation_run_id`); [`swing/trades/origin.py:10-11`](../../../swing/trades/origin.py) (BINDING text "candidates.evaluation_run_id is the join key").
- **Web entry POST handler**: [`swing/web/routes/trades.py:413`](../../../swing/web/routes/trades.py) + line 896-911 (`_reject_anchor` helper T3.SB1 precedent) + line 1095 (entry-path mapping fix R6 MAJOR #2 target).

---

*End of T2.SB6c writing-plans plan. v21 schema scope = 2 NULLable trades backlinks; 5-task decomposition with concurrent T-A.6c.1 + T-A.6c.2 + T-A.6c.3 + sequential T-A.6c.4 + T-A.6c.5; ~92-95 fast tests + 1 fast E2E projected (per §1.5.3 amendment range); v20 LOCKED streak ENDS at T-A.6c.1 executing-plans landing; ~360+ ZERO Co-Authored-By footer streak preserved through this commit; pre-Codex 7-expansion + 2 NEW refinements BINDING for 26th cumulative validation expected at writing-plans phase. PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding (separate from this dispatch).*
