# Sector/Industry Capture + Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Finviz `Sector` + `Industry` (currently ingested but discarded) on `candidates` (per-pipeline-run) and on `trades` (frozen-at-entry); display on 4 surfaces (hyp-recs, watchlist expansion, trade entry, open positions).

**Architecture:** Mirrors the snapshot-at-entry-surface pattern from `hypothesis_label` (migration 0007) and `chart_pattern_*` (migration 0010). Schema migration 0012 adds 2 columns to `candidates` and 2 to `trades` via `ALTER TABLE ADD COLUMN` (no CREATE-COPY-DROP-RENAME needed — additive only, no cross-column invariants). Pipeline ingestion plumbs sector/industry from Finviz CSV into the candidate row post-`evaluate_batch` via `dataclasses.replace` (evaluator stays domain-pure: it works on OHLCV, sector/industry are CSV passthrough). Trade entry uses the existing ToCToU snapshot pattern: `build_entry_form_vm` resolves sector/industry from the candidate row at GET render time; hidden form fields carry through POST; `record_entry` persists AS-IS. CLI auto-resolves from candidate row by ticker; persists empty strings when no candidate exists (graceful degradation, mirrors `hypothesis_label` free-text pattern).

**Tech Stack:** Python 3.14, SQLite (WAL mode, foreign_keys=ON), dataclasses (frozen=True), FastAPI + Starlette + Jinja2 + HTMX, click CLI, pytest.

**Test baseline (HEAD `ba2b252`):** 1203 fast tests passing, 1 skipped (Task 7.3 fixture-gated), 8 deselected. Verified via `python -m pytest -m "not slow" -q`.

**Migration version:** 0012 (current `EXPECTED_SCHEMA_VERSION = 11`).

**Locked decisions (per dispatch brief §2 — DO NOT re-litigate):**
1. Persist BOTH sector AND industry; display BOTH on display surfaces.
2. Display surfaces (V1): hyp-recs row, watchlist row expansion, trade entry form, open positions row. Out of scope (V2): journal review aggregation, sector concentration warnings.
3. Frozen-at-entry on `trades` table (mirrors `hypothesis_label` / `chart_pattern_*`).
4. Source-of-truth: Finviz only. No yfinance reconciliation.

**Hyp-recs surface deferred (R1 Codex Major 3 RESOLVED).** Brief §2.2 names "Hyp-recs row expansion (HTMX-expanded panel under `partials/`)" as a V1 display surface. **No such expansion exists yet** — `partials/hypothesis_recommendations.html.j2` is a flat read-only `<table>` with 7 columns and zero expand wiring. The HTMX expansion mechanism is the deliverable of the queued **hyp-recs trade-prep expansion brainstorm** (`docs/phase3e-todo.md` 2026-04-28 §"hyp-recs trade-prep expansion"). Brief §1 explicitly says: *"Hyp-recs expansion will consume sector as a pre-captured field; that's a downstream concern — out of scope for THIS dispatch."* This plan therefore HONORS the brief's §1 framing and DEFERS hyp-recs display to the future expansion brainstorm. The data IS captured on `candidates` (Task 2) and on `trades` (Task 4), so the future brainstorm consumes from `candidates_by_ticker` (already in scope at the dashboard build site, [swing/web/view_models/dashboard.py:552-581](../../swing/web/view_models/dashboard.py)) without any rework. **Surfaced as a deferred-by-spec-conflict item in the writing-plans return report.** Per dispatch brief §8: "If a locked decision (§2) appears impossible to implement as written: STOP, surface in return report. Do NOT silently re-design." The §2.2 listing is impossible as written (the panel does not exist); the §1 framing makes the deferral explicit; this plan respects the brief's own escape hatch rather than inventing a column-based interpretation that re-shapes the operator's intended UX.

**Hyp-recs sort key NOT touched.** Per orchestrator-context "sort-neutrality is structurally guaranteed when the new tag never enters the existing sort tuple" lesson (chart-pattern-flag-v1 R1 M2). Hyp-recs prioritization is hypothesis-aware (progress, target distance, tripwire) and lives in `swing.recommendations.hypothesis`. Sector/industry are decorative display fields ONLY — they do NOT enter any sort or prioritization tuple. Watchlist `_sort_watchlist` is also untouched.

**Base-layout 5-VM rule does NOT apply.** Verified at plan-time: `grep -n "sector\|industry" swing/web/templates/base.html.j2` returns zero matches. Sector/industry are consumer-scoped to row-level partials and dashboard-section partials; per the 2026-04-26 lesson (chart-pattern flag-v1 Phase 4) the 5-VM rule applies only when `base.html.j2` actually dereferences the new field. This plan does NOT propagate sector/industry to `PipelineVM`, `JournalVM`, or `PageErrorVM`.

---

## File Map

**Created:**
- `swing/data/migrations/0012_sector_industry.sql` — schema migration (Task 1).

**Modified:**
- `swing/data/db.py` — bump `EXPECTED_SCHEMA_VERSION` 11 → 12 (Task 1).
- `swing/data/models.py` — add `sector: str` + `industry: str` to `Candidate` and `Trade` dataclasses (Tasks 2 + 4).
- `swing/data/repos/candidates.py` — extend INSERT and SELECT SQL; populate fields in `_row_to_candidate` (Task 2).
- `swing/data/repos/trades.py` — extend INSERT and 5 SELECT call sites (`get_trade`, `list_open_trades`, `list_closed_trades` (both branches), `find_any_open_trade`, `find_open_trade_by_match` (both branches)); update `_row_to_trade` (Task 4).
- `swing/pipeline/runner.py` — `_step_evaluate` plumbs sector/industry from finviz CSV → candidate rows post-`evaluate_batch` (Task 3).
- `swing/trades/entry.py` — extend `EntryRequest` dataclass + `record_entry` to plumb sector/industry through to the persisted `Trade` (Task 5).
- `swing/cli.py` — `trade_entry_cmd` resolves sector/industry from latest candidate row at command start; persists empty strings if no candidate (Task 7).
- `swing/web/routes/trades.py` — `entry_post` accepts sector/industry as Form fields; passes to `EntryRequest`; serializes into `soft_warn_confirm` `form_values` dict (Task 6).
- `swing/web/view_models/trades.py` — `TradeEntryFormVM` gains `sector: str` + `industry: str`; `build_entry_form_vm` resolves from candidate-by-ticker query inside the existing read snapshot (Task 6).
- `swing/web/templates/partials/trade_entry_form.html.j2` — render read-only sector/industry rows + hidden inputs (Task 6).
- `swing/web/view_models/watchlist.py` — `WatchlistExpandedVM.candidate` already carries the candidate; sector/industry are accessed via `expanded.candidate.sector` / `.industry` directly. **No VM-field addition needed.** (Task 8 — template-only change.)
- `swing/web/templates/partials/watchlist_expanded.html.j2` — add Sector + Industry rows when `expanded.candidate` is present (Task 8).
- `swing/web/templates/partials/open_positions_row.html.j2` — add Sector + Industry cells (consumed via `row.trade.sector` / `.industry`); update `colspan` in `open_positions_expanded.html.j2` to match the new cell count (Task 9).
- `swing/web/templates/partials/open_positions.html.j2` — add `<th>Sector</th>` + `<th>Industry</th>` to the open-positions `<thead>` to keep header/data column counts aligned (Task 9).

**Test files (R1 Codex Major 2 RESOLVED — paths verified against actual tree at HEAD `ba2b252`):**
- Create: `tests/data/test_migration_0012.py` — migration 0012 schema-shape tests (Task 1). Mirrors `tests/data/test_migration_0011.py` pattern (sequential migration apply via `_migrate_to_v<N>` helper, FK seed, schema_version assertion).
- Extend: `tests/data/test_repos_candidates.py` — Candidate insert+select roundtrip (Task 2). Existing file with `tmp_db` fixture + concrete Candidate fixture.
- Extend: `tests/data/test_repos_trades.py` — Trade insert+select all-paths roundtrip (Task 4). Existing file with `_trade()` factory + `tmp_path` pattern.
- Extend: `tests/pipeline/test_runner_chart_targets.py` — sector/industry flow from finviz CSV → candidate rows (Task 3). Existing file with `_csv()` finviz fixture, `_make_cfg()`, `run_pipeline_internal` end-to-end pattern; `_csv()` already emits `Sector,Industry` columns.
- Extend: `tests/trades/test_entry.py` — `record_entry` passes sector/industry through AS-IS (Task 5). Existing file with `_req()` EntryRequest factory and `ensure_schema(tmp_path / "swing.db")` pattern.
- Extend: `tests/cli/test_cli_trade_entry_chart_pattern.py` — CLI auto-resolves from candidate; empty-string fallback (Task 7). Existing file with `_setup` (CliRunner + `_minimal_config` + `db-migrate`) + `seed_pipeline_with_classification` precedent. Sector/industry tests can reuse the same scaffolding plus a candidate-row seed.
- Extend: `tests/web/test_routes/test_trade_entry_chart_pattern.py` — POST flow + soft_warn_confirm round-trip preserves sector/industry (Task 6). Existing file with `seeded_db` fixture + `seed_pipeline_with_classification` + TestClient lifespan-bound pattern.
- Extend: `tests/web/test_view_models/test_trade_entry_form_classification.py` — VM populated from candidate (Task 6). Existing file with `seeded_db` + `seed_pipeline_with_classification` + `MagicMock` cache pattern.
- Extend: `tests/web/test_view_models/test_watchlist.py` — partial renders sector/industry rows in expansion (Task 8). Existing file with `seeded_db` + `upsert_watchlist_entry` + `TestClient(app)` template-render pattern (line 153 precedent: `test_watchlist_expanded_template_renders_reason_message`).
- Extend: `tests/web/test_routes/test_open_positions_expand.py` — partial renders sector/industry cells + colspan match (Task 9). Existing file at line 521 has the colspan-alignment pattern Codex referenced.

> **Test-path verification at executing-plans dispatch.** Implementer should `Read` the precedent test files BEFORE adding the new tests so the new tests adopt the existing scaffolding pattern (fixture imports, helper invocations, assertion shape). Mid-file insertion, not new-file creation, is the V1 plan unless an existing file is structurally incompatible.

---

## Compounding-Confound + Discriminating-Test Discipline (binding for ALL tasks)

Per orchestrator-context lessons (Phase 4 R1 + R2; Phase 6 monkeypatch-capture; chart-scope policy v2 R3 + R4): every task with a discriminating test in this plan includes a **"would this test fail if the implementation never actually called the new code?" sanity-check** sentence in the task body. Where applicable, setups INVERT default sort orders, alphabetical tiebreakers, or fallback values so the bug's output diverges from the correct output. Specific watch items per the dispatch brief §5:

- **Hard-coded "Technology" / "Software" defaults are FORBIDDEN as discriminators.** Tests must use SECTOR + INDUSTRY values that are visually distinct from any plausible default and from each other across rows (e.g., `"Healthcare" / "Biotechnology"` for ticker A; `"Energy" / "Oil & Gas E&P"` for ticker B). A test that asserts only "sector field is non-empty" or "sector == 'Technology'" with a Technology-defaulted code path would pass both pre-fix and post-fix.
- **Where the bug's symptom would be "field appears empty"**, the test setup persists a NON-EMPTY value and asserts the rendered output contains the specific characters of that value (no substring-match against generic words like "Sector").
- **Mocked candidate fixtures** must populate sector + industry to known non-empty values that DIFFER from any test-helper default; any task asserting on rendered sector text must use a value the test itself sets (e.g., `"Test-Sector-Apr28"`) so a regression where the field is populated from a fallback path would fail the assertion.

---

## Per-Task Observable-Verification Subject-Only Grep (binding per orchestrator-context)

Before each task implementation commit, run:

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
```

Replace `<N>` with the task number (e.g., `'Task 1'`, `'Task 2'`). The `-E` flag is REQUIRED — git's default BRE treats `+` as literal, returning empty even when matches exist (the "expected empty" output then matches for the wrong reason; see 2026-04-27 ERE refinement lesson). Include the command's output (which should be empty for a fresh task) in the commit body. If the grep returns ANY existing commit subjects with the same task ID, ABORT — a prior subagent or session has already implemented the task.

For Codex/internal-Codex round labels use `'^[a-z]+\([a-z]+\): Codex R[0-9]'` (POSIX `[0-9]` instead of `\d`).

---

## Commit-Message Convention (4-tier, binding)

- **Task implementations:** `feat(<area>): Task N — <description>` or `feat(<area>): Task N.M — <description>`.
- **Internal code-review fix commits:** `fix(<area>): code-review I<n> — <description>` (Phase 5 precedent).
- **Internal-Codex within-task fix commits:** `fix(<area>): Codex R<n> Major <m> (internal) — <description>`.
- **Adversarial review-fix commits (orchestrator wrapper):** `fix(<area>): Codex R<n> Major <m> — <description>`.
- **Format-only / cleanup commits:** `style(<area>): <description>` (no task ID).

No Claude co-author footer. No `--no-verify`. No amending. Conventional-commits subject prefix MUST match the regex above so the observable-verification grep finds exactly one match per task after commit.

---

## Task 1: Schema migration 0012 — add sector/industry columns to candidates + trades

**Files:**
- Create: `swing/data/migrations/0012_sector_industry.sql`
- Modify: `swing/data/db.py:9` (EXPECTED_SCHEMA_VERSION 11 → 12)
- Test: create `tests/data/test_migration_0012.py` — mirrors `tests/data/test_migration_0011.py` pattern (sequential `_migrate_to_v<N>` helper, schema_version assertion, NOT NULL DEFAULT '' shape verification).

**Discriminating-test sanity-check.** The migration test asserts the four new columns exist by name AND by NOT NULL DEFAULT '' constraint shape AND by non-NULL value on a fresh INSERT that omits the columns (defaults must apply). If the migration only added the columns without the DEFAULT clause, the third assertion fails (omitted columns persist as NULL on INSERT, violating NOT NULL). **Would this test fail if the implementation never actually applied the migration? Yes — `_current_version(conn)` returns 11 (or 0), and the assertion `cursor.execute("PRAGMA table_info(candidates)")` returns no row matching `name='sector'`, both of which fail explicitly.**

- [ ] **Step 1.1: Verify current state.**

```bash
grep -n "EXPECTED_SCHEMA_VERSION" swing/data/db.py
ls swing/data/migrations/ | tail -5
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1'
```

Expected: `EXPECTED_SCHEMA_VERSION = 11`; `0011_pipeline_chart_targets_source_taxonomy.sql` is the last migration; grep returns empty.

- [ ] **Step 1.2: Write the failing migration test.**

Create `tests/data/test_migration_0012.py` (modeled on `tests/data/test_migration_0011.py`):

```python
"""Migration 0012 — sector + industry columns on candidates + trades."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def test_migration_0012_adds_sector_industry_to_candidates_and_trades(tmp_path: Path):
    """Migration 0012 adds NOT NULL DEFAULT '' sector + industry columns to
    BOTH candidates and trades. Default values apply on INSERTs that omit
    the columns, preserving backfill behavior on historical rows."""
    from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        # EXPECTED_SCHEMA_VERSION must be 12 once the migration is included.
        assert EXPECTED_SCHEMA_VERSION == 12

        # Schema version actually advanced.
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 12

        # Both tables have the new columns.
        for table in ("candidates", "trades"):
            cols = {
                row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")
            }
            assert "sector" in cols, f"{table}.sector missing"
            assert "industry" in cols, f"{table}.industry missing"
            # PRAGMA table_info row: (cid, name, type, notnull, dflt_value, pk)
            assert cols["sector"][2].upper() == "TEXT"
            assert cols["industry"][2].upper() == "TEXT"
            assert cols["sector"][3] == 1, f"{table}.sector must be NOT NULL"
            assert cols["industry"][3] == 1, f"{table}.industry must be NOT NULL"
            # SQLite renders TEXT default as "''".
            assert cols["sector"][4] == "''", f"{table}.sector default must be ''"
            assert cols["industry"][4] == "''", f"{table}.industry default must be ''"

        # Functional check: INSERT omitting sector/industry must succeed and
        # persist empty strings (not NULL — NOT NULL violation would surface here).
        conn.execute(
            """INSERT INTO evaluation_runs
               (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                tickers_evaluated, aplus_count, watch_count, skip_count,
                excluded_count, error_count)
               VALUES ('2026-04-28T00:00:00','2026-04-25','2026-04-28',
                       NULL,0,0,0,0,0,0)"""
        )
        eval_run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO candidates
               (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
                rs_return_12w_vs_spy, rs_method, pattern_tag, notes)
               VALUES (?, 'TEST', 'watch', 100.0, 105.0, 95.0,
                       2.0, 5, NULL, NULL, NULL, NULL, 'fallback_spy',
                       NULL, NULL)""",
            (eval_run_id,),
        )
        row = conn.execute(
            "SELECT sector, industry FROM candidates WHERE ticker='TEST'"
        ).fetchone()
        assert row == ("", "")

        conn.execute(
            """INSERT INTO trades
               (ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, status)
               VALUES ('TEST','2026-04-28',100.0,10,95.0,95.0,'open')"""
        )
        row = conn.execute(
            "SELECT sector, industry FROM trades WHERE ticker='TEST'"
        ).fetchone()
        assert row == ("", "")
    finally:
        conn.close()
```

> **Why a new file rather than appending to `tests/data/test_db.py` (which holds general schema tests).** Migration 0011 ships its tests in a dedicated `test_migration_0011.py` (one file per migration). 0012 follows the same precedent — new file = clean diff, no risk of fixture coupling with unrelated tests.

- [ ] **Step 1.3: Run the failing test.**

```bash
python -m pytest tests/data/test_migration_0012.py::test_migration_0012_adds_sector_industry_to_candidates_and_trades -v
```

Expected: FAIL — `EXPECTED_SCHEMA_VERSION == 11` (not 12), or schema_version table reports 11, or the columns don't exist.

- [ ] **Step 1.4: Write the migration SQL.**

Create `swing/data/migrations/0012_sector_industry.sql`:

```sql
-- Migration 0012: capture Finviz Sector + Industry on candidates + trades.
--
-- Both columns are already validated by `swing/pipeline/finviz_schema.py`'s
-- REQUIRED_COLUMNS (ingested but discarded pre-this-migration). This migration
-- closes the gap: candidates carry the per-pipeline-run snapshot; trades
-- freeze the value at entry-time per the snapshot-at-entry-surface pattern
-- (precedents: hypothesis_label / migration 0007; chart_pattern_* / 0010).
--
-- Additive only: NOT NULL DEFAULT '' so historical rows pre-migration get
-- empty strings rather than NULL; this preserves any future query that
-- filters on `sector != ''` from accidentally matching backfilled rows
-- and avoids NULL-handling at every read site. ALTER TABLE ADD COLUMN with
-- a constant DEFAULT is O(metadata) on SQLite (no row rewrite).
--
-- No cross-column invariants in V1 (unlike chart_pattern_*'s 4 invariants):
-- sector + industry are independent free-text descriptors. V1 trusts Finviz
-- as source of truth; future V2 may add concentration constraints but not
-- field-format invariants.

ALTER TABLE candidates ADD COLUMN sector TEXT NOT NULL DEFAULT '';
ALTER TABLE candidates ADD COLUMN industry TEXT NOT NULL DEFAULT '';

ALTER TABLE trades ADD COLUMN sector TEXT NOT NULL DEFAULT '';
ALTER TABLE trades ADD COLUMN industry TEXT NOT NULL DEFAULT '';

UPDATE schema_version SET version = 12;
```

- [ ] **Step 1.5: Bump EXPECTED_SCHEMA_VERSION.**

Edit `swing/data/db.py` line 9:

```python
# pipeline_pattern_classifications + trade chart_pattern columns (migrations 0009 + 0010)
# chart_targets source taxonomy expansion (migration 0011)
# sector + industry capture on candidates + trades (migration 0012)
EXPECTED_SCHEMA_VERSION = 12
```

- [ ] **Step 1.6: Run the test to verify it passes.**

```bash
python -m pytest tests/data/test_migration_0012.py::test_migration_0012_adds_sector_industry_to_candidates_and_trades -v
```

Expected: PASS.

- [ ] **Step 1.7: Verify no other test broke from EXPECTED_SCHEMA_VERSION change.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -20
```

Expected: All previously-passing tests still pass. If any test asserted `EXPECTED_SCHEMA_VERSION == 11` directly, update it to 12 in the same task (record the file in the commit message). Other tests may break because INSERTs into `candidates` / `trades` that omit sector + industry now succeed (which was the goal); those would surface as NEW pass-through tests, not regressions.

- [ ] **Step 1.8: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1'
```

Expected: empty.

```bash
git add swing/data/migrations/0012_sector_industry.sql swing/data/db.py tests/data/test_migration_0012.py
git commit -m "feat(data): Task 1 — migration 0012 adds sector + industry to candidates + trades

Schema migration 0012 closes the gap from Finviz CSV ingestion: Sector + Industry
are validated at CSV-ingestion time but currently discarded before persistence.
NOT NULL DEFAULT '' on both columns mirrors the snapshot-at-entry-surface pattern
(hypothesis_label / migration 0007; chart_pattern_* / migration 0010) — empty
strings preserve historical rows without NULL-handling at read sites.

EXPECTED_SCHEMA_VERSION bumped 11 → 12.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 1'\` empty pre-commit.
"
```

---

## Task 2: Candidate dataclass + repo extension

**Files:**
- Modify: `swing/data/models.py:18-33` (add fields to Candidate dataclass)
- Modify: `swing/data/repos/candidates.py` (extend `insert_candidates` SQL, `fetch_candidates_for_run` SQL, candidate-row construction).
- Test: extend `tests/data/test_repos_candidates.py` (existing file — uses `tmp_db` fixture from `tests/conftest.py` and the standard `Candidate` factory pattern at lines 36-54).

**Discriminating-test sanity-check.** Test inserts a Candidate with sector="Healthcare" + industry="Biotechnology" (specific to this test — no other test fixture should use these values), then reads back via `fetch_candidates_for_run` and asserts both fields are populated with those EXACT strings (`assert c.sector == "Healthcare"` not `assert c.sector`). If `insert_candidates` silently dropped the sector/industry params or `_row_to_candidate` ignored those columns, the test would observe `""` (the schema default) on read-back, failing the assertion. **Would this test fail if the implementation never actually called the new code? Yes — without modifying `insert_candidates`'s SQL the column values are not bound, default `""` is persisted, and the read-back equality check fails.**

- [ ] **Step 2.1: Write the failing test.**

Append to `tests/data/test_repos_candidates.py` — the `tmp_db` fixture (declared in `tests/conftest.py`) and existing imports (`ensure_schema`, `Candidate`, `EvaluationRun`, `fetch_candidates_for_run`, `insert_candidates`, `insert_evaluation_run`) are already in scope from the file's existing tests:

```python
def test_candidate_sector_industry_roundtrip(tmp_db):
    """A Candidate with sector + industry inserted via insert_candidates is
    fetched back with both fields populated AS-IS. Distinct values
    ("Healthcare" / "Biotechnology") chosen to discriminate against any
    test fixture default that might mask a passthrough bug."""
    conn = ensure_schema(tmp_db)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-04-28T00:00:00",
                data_asof_date="2026-04-25", action_session_date="2026-04-28",
                finviz_csv_path=None,
                tickers_evaluated=1, aplus_count=0, watch_count=1,
                skip_count=0, excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="ZZZA", bucket="watch",
                    close=100.0, pivot=105.0, initial_stop=95.0,
                    adr_pct=2.0, tight_streak=5, pullback_pct=None,
                    prior_trend_pct=None, rs_rank=None,
                    rs_return_12w_vs_spy=None, rs_method="fallback_spy",
                    pattern_tag=None, notes=None,
                    sector="Healthcare", industry="Biotechnology",
                    criteria=(),
                ),
            ])
        rows = fetch_candidates_for_run(conn, run_id)
        assert len(rows) == 1
        assert rows[0].ticker == "ZZZA"
        assert rows[0].sector == "Healthcare"
        assert rows[0].industry == "Biotechnology"
    finally:
        conn.close()


def test_candidate_default_sector_industry_empty(tmp_path):
    """A Candidate constructed without explicit sector/industry uses empty
    strings as defaults — preserves call sites that don't carry these fields."""
    from swing.data.models import Candidate
    c = Candidate(
        ticker="DFLT", bucket="watch",
        close=None, pivot=None, initial_stop=None,
        adr_pct=None, tight_streak=None, pullback_pct=None,
        prior_trend_pct=None, rs_rank=None,
        rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes=None, criteria=(),
    )
    assert c.sector == ""
    assert c.industry == ""
```

- [ ] **Step 2.2: Run the test.**

```bash
python -m pytest tests/data/test_repos_candidates.py::test_candidate_sector_industry_roundtrip tests/data/test_repos_candidates.py::test_candidate_default_sector_industry_empty -v
```

Expected: FAIL — `Candidate.__init__()` raises `TypeError: got an unexpected keyword argument 'sector'`.

- [ ] **Step 2.3: Add fields to Candidate dataclass.**

In `swing/data/models.py`, modify the `Candidate` class:

```python
@dataclass(frozen=True)
class Candidate:
    ticker: str
    bucket: str  # 'aplus' | 'watch' | 'skip' | 'error' | 'excluded'
    close: float | None
    pivot: float | None
    initial_stop: float | None
    adr_pct: float | None
    tight_streak: int | None
    pullback_pct: float | None
    prior_trend_pct: float | None
    rs_rank: int | None
    rs_return_12w_vs_spy: float | None
    rs_method: str  # 'universe' | 'fallback_spy' | 'unavailable'
    pattern_tag: str | None
    notes: str | None
    criteria: tuple[CriterionResult, ...]
    # Migration 0012 — Finviz Sector + Industry passthrough. Defaults to
    # empty string so any caller that constructs Candidate without these
    # fields (older test fixtures, ETF-blocklist / open-position synthesis
    # in _step_evaluate, classifier-error rows) continues to work; the
    # _step_evaluate path uses dataclasses.replace to populate from CSV.
    sector: str = ""
    industry: str = ""
```

> **Field-ordering note.** `criteria` MUST stay as the last field WITHOUT a default to preserve positional construction at the existing call sites in `evaluator.py` and `runner.py`. Sector + industry are appended AFTER `criteria` with defaults — same pattern as `HypothesisRecommendation.pivot_price` (orchestrator-context: "appended with a default rather than inserted between..."). Test the ordering by constructing a Candidate via positional args (e.g., `Candidate("X", "watch", 1.0, ..., (), )` — the existing form) and confirming it still works. Verify no test file constructs Candidate via positional args past index 14; if any does, the field order requires that those continue to map to `criteria`, which requires `criteria` to remain at position 14 (after `notes`) and sector/industry to come AFTER. Alternative: insert sector/industry BEFORE `criteria` with defaults — `criteria` already has no default and is always passed positionally, so this works ONLY if Python honors the default-after-non-default rule (which it doesn't for kwargs but does in dataclass synthesis when defaults are at the END). Conclusion: **append after `criteria` with defaults; that is the only ordering Python accepts and that matches the precedent.**

- [ ] **Step 2.4: Run the dataclass-construction test (only the second one) to verify it passes.**

```bash
python -m pytest tests/data/test_repos_candidates.py::test_candidate_default_sector_industry_empty -v
```

Expected: PASS. The roundtrip test still fails (repo not yet updated).

- [ ] **Step 2.5: Update repo SQL and `_row_to_candidate` equivalent.**

In `swing/data/repos/candidates.py`, modify `insert_candidates`:

```python
def insert_candidates(
    conn: sqlite3.Connection, run_id: int, candidates: Sequence[Candidate]
) -> None:
    """Insert candidate + criteria rows. Does NOT commit — caller wraps in a transaction."""
    for c in candidates:
        cur = conn.execute(
            """
            INSERT INTO candidates
                (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                 adr_pct, tight_streak, pullback_pct, prior_trend_pct,
                 rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
                 sector, industry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                c.ticker, c.bucket, c.close, c.pivot, c.initial_stop,
                c.adr_pct, c.tight_streak, c.pullback_pct, c.prior_trend_pct,
                c.rs_rank, c.rs_return_12w_vs_spy, c.rs_method,
                c.pattern_tag, c.notes,
                c.sector, c.industry,
            ),
        )
        cid = int(cur.lastrowid)
        for crit in c.criteria:
            conn.execute(
                """
                INSERT INTO candidate_criteria
                    (candidate_id, criterion_name, layer, result, value, rule)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cid, crit.criterion_name, crit.layer, crit.result, crit.value, crit.rule),
            )
```

And modify `fetch_candidates_for_run` to SELECT and populate the new columns:

```python
def fetch_candidates_for_run(conn: sqlite3.Connection, run_id: int) -> list[Candidate]:
    cand_rows = conn.execute(
        """
        SELECT id, ticker, bucket, close, pivot, initial_stop, adr_pct,
               tight_streak, pullback_pct, prior_trend_pct, rs_rank,
               rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
               sector, industry
        FROM candidates
        WHERE evaluation_run_id = ?
        ORDER BY ticker
        """,
        (run_id,),
    ).fetchall()

    result: list[Candidate] = []
    for row in cand_rows:
        cid = row[0]
        crit_rows = conn.execute(
            """
            SELECT criterion_name, layer, result, value, rule
            FROM candidate_criteria
            WHERE candidate_id = ?
            ORDER BY criterion_name
            """,
            (cid,),
        ).fetchall()
        criteria = tuple(
            CriterionResult(name, layer, res, val, rule)
            for (name, layer, res, val, rule) in crit_rows
        )
        result.append(
            Candidate(
                ticker=row[1], bucket=row[2], close=row[3], pivot=row[4],
                initial_stop=row[5], adr_pct=row[6], tight_streak=row[7],
                pullback_pct=row[8], prior_trend_pct=row[9],
                rs_rank=row[10], rs_return_12w_vs_spy=row[11],
                rs_method=row[12], pattern_tag=row[13], notes=row[14],
                sector=row[15], industry=row[16],
                criteria=criteria,
            )
        )
    return result
```

- [ ] **Step 2.6: Run the roundtrip test.**

```bash
python -m pytest tests/data/test_repos_candidates.py::test_candidate_sector_industry_roundtrip -v
```

Expected: PASS.

- [ ] **Step 2.7: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

Expected: All previously-passing tests still pass. New tests added.

- [ ] **Step 2.8: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2'
```

Expected: empty.

```bash
git add swing/data/models.py swing/data/repos/candidates.py tests/data/test_repos_candidates.py
git commit -m "feat(data): Task 2 — Candidate dataclass + repo carry sector/industry

Adds sector + industry fields to Candidate (defaults '' to preserve call sites
that don't yet plumb them), extends insert_candidates SQL + fetch_candidates_for_run
SQL + candidate row construction. Roundtrip test uses 'Healthcare' / 'Biotechnology'
to discriminate against any default-string mask.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 2'\` empty pre-commit.
"
```

---

## Task 3: Pipeline ingestion — Sector + Industry flow from finviz CSV → candidate rows

**Files:**
- Modify: `swing/pipeline/runner.py:321-477` (`_step_evaluate`)
- Test: extend `tests/pipeline/test_runner_chart_targets.py` — existing file with `_csv()` finviz fixture (already emits `Sector,Industry` columns), `_make_cfg()` cfg builder, monkey-patched `PriceFetcher.get`, and `run_pipeline_internal` end-to-end pattern.

**Discriminating-test sanity-check.** Test seeds a Finviz CSV with rows where ticker → (sector, industry) mapping is INVERTED relative to alphabetical: e.g., ticker `AAPL` → `Healthcare / Pharmaceuticals`, ticker `ZZZB` → `Energy / Oil & Gas E&P`. Asserts that `fetch_candidates_for_run`'s output rows have the EXACT mapping the CSV specified (not a swapped or default mapping). **Inversion-against-alphabetical** prevents the Phase 4 R2 ticker-symmetry vacuousness pattern: if the implementation accidentally bound sectors by row INDEX (i.e., post-evaluate_batch's alphabetically-sorted output) instead of by TICKER, the test catches it. **Would this test fail if the implementation never actually called the new code? Yes — without the post-`evaluate_batch` plumbing, candidate rows persist `sector=""` (schema default) and the assertion `c.sector == "Healthcare"` fails for AAPL.**

**Error-ticker semantics CLARIFIED (R1 Codex Major 5 RESOLVED).** Error tickers (OHLCV fetch failed) ARE in the finviz CSV (they came from `tickers = finviz_df["Ticker"]....`); the sector/industry dict.get() lookup will return their CSV values. The post-evaluate_batch `dataclasses.replace` loop applies UNIFORMLY to every Candidate (a+, watch, skip, error, excluded) — sector/industry source is "whatever is in the CSV for this ticker; empty if not." So:
- **Tickers in CSV (any bucket: aplus / watch / skip / error / excluded-via-ETF-blocklist):** persist sector + industry FROM THE CSV.
- **Held-position tickers appended via `held_tickers` and NOT in CSV:** persist empty strings (graceful degradation; the CSV does not contain a row for them, dict.get(default=("","")) returns empty).

This is internally consistent — sector/industry are CSV-derived metadata, present whenever the CSV has the ticker.

- [ ] **Step 3.1: Write the failing tests.**

Append to `tests/pipeline/test_runner_chart_targets.py`. Reuse the existing `_csv`, `_ohlcv`, and `_make_cfg` helpers + `run_pipeline_internal` pattern. Add a custom `_csv_inverted` helper that produces an inversion-against-alphabetical mapping (and a fixture that seeds a held-position trade for the empty-string case):

```python
def _csv_inverted(inbox: Path) -> Path:
    """Inversion-against-alphabetical: AAPL → Healthcare / Pharmaceuticals;
    ZZZB → Energy / Oil & Gas E&P. Guards against row-index-vs-ticker
    binding bug (Phase 4 R2 ticker-symmetry class).
    """
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    )
    csv.write_text(
        cols + "\n"
        "1,AAPL,Healthcare,Pharmaceuticals,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n"
        "2,ZZZB,Energy,Oil & Gas E&P,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3.5e9\n",
        encoding="utf-8",
    )
    return csv


def test_step_evaluate_persists_sector_industry_from_finviz_csv(
    tmp_path: Path, monkeypatch,
):
    """_step_evaluate plumbs Sector + Industry from the Finviz CSV into the
    candidate row. AAPL → Healthcare / Pharmaceuticals; ZZZB → Energy /
    Oil & Gas E&P. Inversion-against-alphabetical: a row-index binding bug
    would yield AAPL → Energy / Oil & Gas E&P (alphabetical-first row
    bound to alphabetical-first ticker).
    """
    cfg = _make_cfg(tmp_path)
    _csv_inverted(cfg.paths.finviz_inbox_dir)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        cands = conn.execute(
            "SELECT ticker, sector, industry FROM candidates "
            "WHERE evaluation_run_id = ? ORDER BY ticker",
            (run.evaluation_run_id,),
        ).fetchall()
        assert (
            "AAPL", "Healthcare", "Pharmaceuticals",
        ) in cands, f"AAPL → Healthcare/Pharmaceuticals expected, got: {cands}"
        assert (
            "ZZZB", "Energy", "Oil & Gas E&P",
        ) in cands, f"ZZZB → Energy/Oil & Gas E&P expected, got: {cands}"
    finally:
        conn.close()


def test_step_evaluate_held_position_not_in_csv_persists_empty_sector_industry(
    tmp_path: Path, monkeypatch,
):
    """Held-trade tickers that aren't in the finviz CSV (rotated out of
    screener) get appended to the candidate set via _step_evaluate's
    held_tickers loop with bucket='excluded'. Sector/industry default to
    empty strings (the dict.get(t, ('','')) lookup misses)."""
    cfg = _make_cfg(tmp_path)
    _csv_inverted(cfg.paths.finviz_inbox_dir)
    # Seed an open trade for a ticker NOT in the CSV — appears via held_tickers.
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="HELD", entry_date="2026-04-10",
                entry_price=50.0, initial_shares=10, initial_stop=45.0,
                current_stop=45.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-10T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        held_row = conn.execute(
            "SELECT bucket, sector, industry FROM candidates "
            "WHERE evaluation_run_id = ? AND ticker = 'HELD'",
            (run.evaluation_run_id,),
        ).fetchone()
        assert held_row is not None, "held-position ticker missing from candidates"
        assert held_row == ("excluded", "", ""), (
            f"held-position ticker should be excluded with empty sector/industry; got {held_row}"
        )
    finally:
        conn.close()


def test_step_evaluate_csv_ticker_with_fetch_failure_keeps_sector_industry(
    tmp_path: Path, monkeypatch,
):
    """A ticker that's in the finviz CSV AND has its OHLCV fetch fail lands
    as bucket='error' — but its sector/industry come from the CSV (the
    post-evaluate_batch dict.get() lookup hits)."""
    cfg = _make_cfg(tmp_path)
    _csv_inverted(cfg.paths.finviz_inbox_dir)

    def selective_fetcher(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "AAPL":
            raise RuntimeError("simulated yfinance outage for AAPL")
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", selective_fetcher)
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        aapl = conn.execute(
            "SELECT bucket, sector, industry FROM candidates "
            "WHERE evaluation_run_id = ? AND ticker='AAPL'",
            (run.evaluation_run_id,),
        ).fetchone()
        assert aapl is not None
        assert aapl[0] == "error"
        # Sector/industry STILL persist from CSV even though OHLCV failed.
        assert aapl[1] == "Healthcare"
        assert aapl[2] == "Pharmaceuticals"
    finally:
        conn.close()
```

- [ ] **Step 3.2: Run the failing tests.**

```bash
python -m pytest tests/pipeline/test_runner_chart_targets.py -v -k "sector_industry or held_position_not_in_csv or fetch_failure_keeps_sector"
```

Expected: FAIL — candidates have empty sector/industry pre-implementation; assertion mismatches.

- [ ] **Step 3.3: Implement the post-`evaluate_batch` plumbing.**

In `swing/pipeline/runner.py`'s `_step_evaluate`, build a sector/industry dict from the finviz_df immediately after the `tickers = finviz_df["Ticker"]....` line, then apply via `dataclasses.replace` to `candidates` after the existing `candidates.append(...)` blocks for excluded + error tickers. Concrete patch:

```python
def _step_evaluate(
    *, cfg, fetcher, csv_path: Path, universe, universe_hash: str,
    run_now: _dt, action_session: _date, lease: Lease,
) -> int:
    lease.verify_held()
    import pandas as pd
    from dataclasses import replace as _dc_replace  # NEW
    finviz_df = pd.read_csv(csv_path)
    if "Ticker" not in finviz_df.columns:
        raise ValueError(f"finviz CSV missing 'Ticker' column: {list(finviz_df.columns)}")
    tickers = finviz_df["Ticker"].dropna().astype(str).str.upper().tolist()

    # NEW: Build sector/industry lookup from the SAME DataFrame columns the
    # finviz_schema validator already required (REQUIRED_COLUMNS includes
    # 'Sector' + 'Industry' — guaranteed present at this point). Empty / NaN
    # cells normalize to '' so downstream NOT NULL DEFAULT '' is honored.
    sector_industry_by_ticker: dict[str, tuple[str, str]] = {}
    for _, fv_row in finviz_df.iterrows():
        t_raw = fv_row.get("Ticker")
        if pd.isna(t_raw):
            continue
        ticker_key = str(t_raw).upper()
        sec = fv_row.get("Sector", "")
        ind = fv_row.get("Industry", "")
        sec = "" if pd.isna(sec) else str(sec)
        ind = "" if pd.isna(ind) else str(ind)
        sector_industry_by_ticker[ticker_key] = (sec, ind)

    # ... existing held-position append, OHLCV fetch, evaluate_batch ... unchanged ...

    candidates = evaluate_batch(contexts)
    # (existing for t in excluded_tickers / for t in error_tickers loops here ...)

    # NEW: Plumb sector/industry from the CSV onto every candidate row.
    # Held-position + ETF-blocklist + error tickers that aren't in the CSV
    # default to ('', '') — graceful degradation matches the hypothesis_label
    # free-text behavior.
    candidates = [
        _dc_replace(
            c,
            sector=sector_industry_by_ticker.get(c.ticker, ("", ""))[0],
            industry=sector_industry_by_ticker.get(c.ticker, ("", ""))[1],
        )
        for c in candidates
    ]

    # ... existing run = EvaluationRun(...) + insert_evaluation_run + insert_candidates ...
```

> **Why post-evaluate_batch and not threading through `CandidateContext`?** Sector/industry are pure CSV passthrough; the evaluator works on OHLCV and has no domain interest in them. Plumbing through `CandidateContext` would force every criterion to know about non-numeric metadata. `dataclasses.replace` after `evaluate_batch` keeps the evaluator domain-pure and adds the metadata at the persistence boundary, which is semantically where it belongs.

> **Source of `sector_industry_by_ticker`** is the SAME `finviz_df` already read at the top of `_step_evaluate`; no second CSV read. The validator at `swing/pipeline/finviz_schema.py:11-16` makes `Sector` and `Industry` REQUIRED — if either is missing, the CSV is rejected and `_step_evaluate` is never called. So `.get(..., default)` is defensive only against per-row NaN, not against missing columns.

- [ ] **Step 3.4: Run the test.**

```bash
python -m pytest tests/pipeline/test_runner_chart_targets.py -v -k "sector_industry or held_position_not_in_csv or fetch_failure_keeps_sector"
```

Expected: PASS for the inversion test, the holds-empty test, and the error-tickers-from-CSV test.

- [ ] **Step 3.5: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

Expected: All previously-passing tests still pass. Net `+3` (or whatever count the harness produces).

- [ ] **Step 3.6: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3'
```

Expected: empty.

```bash
git add swing/pipeline/runner.py tests/pipeline/test_runner_chart_targets.py
git commit -m "feat(pipeline): Task 3 — _step_evaluate plumbs Sector + Industry from CSV

Builds a per-CSV sector/industry dict from the same finviz_df already loaded;
applies via dataclasses.replace to candidates post-evaluate_batch. Held-position
+ ETF-blocklist tickers default to ('', '') — graceful degradation mirrors
hypothesis_label free-text behavior. Inversion-against-alphabetical fixture
guards against row-index-vs-ticker confusion (Phase 4 R2 ticker-symmetry class).

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 3'\` empty pre-commit.
"
```

---

## Task 4: Trade dataclass + repo extension

**Files:**
- Modify: `swing/data/models.py:53-77` (Trade dataclass)
- Modify: `swing/data/repos/trades.py` (insert_trade_with_event SQL + 5 SELECT call sites + `_row_to_trade`)
- Test: extend `tests/data/test_repos_trades.py` (existing file with `_trade()` factory + `tmp_path / "swing.db"` pattern; precedent: `test_insert_trade_persists_hypothesis_label` at line 99).

**Discriminating-test sanity-check.** Test inserts a Trade with `sector="Energy"` + `industry="Oil & Gas E&P"`, reads back via `get_trade`, `list_open_trades`, `list_closed_trades` (after closing), `find_any_open_trade`, and `find_open_trade_by_match` — asserts ALL FIVE SELECT paths return the EXACT values set on insert. The 5 SELECT paths all hand-roll their column lists (no shared SELECT helper). If any one path's SELECT or `_row_to_trade` mapping is missed, the test for that path observes empty strings (schema default after migration 0012) and the assertion fails. **Would this test fail if the implementation never actually called the new code? Yes — five distinct read paths each fail individually if their SELECT list isn't extended.**

- [ ] **Step 4.1: Write the failing test.**

Append to `tests/data/test_repos_trades.py`:

```python
def test_trade_sector_industry_roundtrip_all_select_paths(tmp_path):
    """Trade with sector + industry roundtrips through ALL FIVE repo SELECT
    paths. Each path hand-rolls its column list — missing one path while
    fixing the others is the recurring repo-SELECT-coverage bug."""
    from swing.data.db import ensure_schema
    from swing.data.models import Trade
    from swing.data.repos.trades import (
        find_any_open_trade,
        find_open_trade_by_match,
        get_trade,
        insert_trade_with_event,
        list_closed_trades,
        list_open_trades,
    )
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(conn, Trade(
                id=None, ticker="ZZZE", entry_date="2026-04-28",
                entry_price=100.0, initial_shares=10,
                initial_stop=95.0, current_stop=95.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, hypothesis_label=None,
                sector="Energy", industry="Oil & Gas E&P",
            ), event_ts="2026-04-28T00:00:00")
        # Path 1: get_trade
        t1 = get_trade(conn, trade_id)
        assert t1 is not None and t1.sector == "Energy"
        assert t1.industry == "Oil & Gas E&P"
        # Path 2: list_open_trades
        opens = list_open_trades(conn)
        assert any(t.ticker == "ZZZE" and t.sector == "Energy" for t in opens)
        # Path 3a: find_any_open_trade
        t3 = find_any_open_trade(conn, ticker="ZZZE")
        assert t3 is not None and t3.sector == "Energy"
        assert t3.industry == "Oil & Gas E&P"
        # Path 3b: find_open_trade_by_match (with shares)
        t4 = find_open_trade_by_match(
            conn, ticker="ZZZE", entry_date="2026-04-28", initial_shares=10,
        )
        assert t4 is not None and t4.sector == "Energy"
        # Path 3c: find_open_trade_by_match (without shares)
        t5 = find_open_trade_by_match(
            conn, ticker="ZZZE", entry_date="2026-04-28", initial_shares=None,
        )
        assert t5 is not None and t5.industry == "Oil & Gas E&P"
        # Path 4: list_closed_trades — close the trade first.
        with conn:
            conn.execute(
                "UPDATE trades SET status='closed' WHERE id=?", (trade_id,),
            )
        closed_all = list_closed_trades(conn)
        assert any(
            t.ticker == "ZZZE" and t.sector == "Energy" and
            t.industry == "Oil & Gas E&P" for t in closed_all
        )
        # Path 4b: list_closed_trades with since_date branch (requires an
        # exits row to satisfy the EXISTS subquery; insert directly).
        with conn:
            conn.execute(
                """INSERT INTO exits
                   (trade_id, exit_date, exit_price, shares, reason,
                    realized_pnl, r_multiple, notes)
                   VALUES (?, '2026-04-28', 100.0, 10, 'manual', 0.0, 0.0, NULL)""",
                (trade_id,),
            )
        closed_since = list_closed_trades(conn, since_date="2026-04-01")
        assert any(
            t.ticker == "ZZZE" and t.sector == "Energy" for t in closed_since
        )
    finally:
        conn.close()


def test_trade_default_sector_industry_empty():
    """Trade constructed without sector/industry uses '' defaults."""
    from swing.data.models import Trade
    t = Trade(
        id=None, ticker="DFLT", entry_date="2026-04-28",
        entry_price=100.0, initial_shares=10,
        initial_stop=95.0, current_stop=95.0, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    assert t.sector == ""
    assert t.industry == ""
```

- [ ] **Step 4.2: Run the failing tests.**

```bash
python -m pytest tests/data/test_repos_trades.py::test_trade_sector_industry_roundtrip_all_select_paths tests/data/test_repos_trades.py::test_trade_default_sector_industry_empty -v
```

Expected: FAIL — `Trade.__init__()` raises `TypeError`.

- [ ] **Step 4.3: Add fields to Trade dataclass.**

In `swing/data/models.py` modify `Trade`:

```python
@dataclass(frozen=True)
class Trade:
    id: int | None
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    status: str  # 'open' | 'closed'
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    hypothesis_label: str | None = None
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_operator: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Migration 0012 — Finviz Sector + Industry, frozen-at-entry per the
    # snapshot-at-entry-surface pattern (precedents: hypothesis_label /
    # 0007; chart_pattern_* / 0010). Defaults to empty string so callers
    # that don't yet plumb these fields keep working; the entry surface
    # (web form + CLI) resolves the actual value from the candidate row
    # at form/CLI render time and persists AS-IS via record_entry.
    sector: str = ""
    industry: str = ""
```

- [ ] **Step 4.4: Run the dataclass-default test only.**

```bash
python -m pytest tests/data/test_repos_trades.py::test_trade_default_sector_industry_empty -v
```

Expected: PASS.

- [ ] **Step 4.5: Update `insert_trade_with_event` SQL.**

In `swing/data/repos/trades.py`, modify `insert_trade_with_event`:

```python
def insert_trade_with_event(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Insert a trade and an 'entry' trade_event in the same transaction.
    Caller wraps in `with conn:`. Returns the new trade id."""
    _validate_chart_pattern_invariant(trade)
    cur = conn.execute(
        """
        INSERT INTO trades
            (ticker, entry_date, entry_price, initial_shares, initial_stop,
             current_stop, status, watchlist_entry_target,
             watchlist_initial_stop, notes, hypothesis_label,
             chart_pattern_algo, chart_pattern_algo_confidence,
             chart_pattern_operator,
             chart_pattern_classification_pipeline_run_id,
             sector, industry)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (trade.ticker, trade.entry_date, trade.entry_price, trade.initial_shares,
         trade.initial_stop, trade.current_stop, trade.status,
         trade.watchlist_entry_target, trade.watchlist_initial_stop, trade.notes,
         trade.hypothesis_label, trade.chart_pattern_algo,
         trade.chart_pattern_algo_confidence, trade.chart_pattern_operator,
         trade.chart_pattern_classification_pipeline_run_id,
         trade.sector, trade.industry),
    )
    trade_id = int(cur.lastrowid)
    payload = {
        "ticker": trade.ticker,
        "entry_date": trade.entry_date,
        "entry_price": trade.entry_price,
        "initial_shares": trade.initial_shares,
        "initial_stop": trade.initial_stop,
    }
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'entry', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
    return trade_id
```

> **Note: `payload_json` is NOT extended.** The audit-event `payload_json` snapshot is per existing pattern (Phase 5 hypothesis_label is also NOT in payload_json). Sector + industry live in the `trades` row exclusively for V1; if a future audit-trail need requires them in `trade_events.payload_json`, add as a follow-up migration with explicit operator approval.

- [ ] **Step 4.6: Update the 5 SELECT paths + `_row_to_trade`.**

Each of these SELECTs in `swing/data/repos/trades.py` currently lists 16 columns; they MUST be extended to 18 (adding `sector, industry` at the end):

1. `get_trade` (around line 195) — extend SELECT list AND `_row_to_trade` mapping.
2. `list_open_trades` (around line 209) — extend SELECT list.
3. `list_closed_trades`, `since_date` branch (around line 227) — extend SELECT list.
4. `list_closed_trades`, no-since-date branch (around line 242) — extend SELECT list.
5. `find_any_open_trade` (around line 317) — extend SELECT list.
6. `find_open_trade_by_match`, with-shares branch (around line 338) — extend SELECT list.
7. `find_open_trade_by_match`, without-shares branch (around line 351) — extend SELECT list.

The exact SELECT extension is the same in every case — append `sector, industry` to the column list, in that order. Example for `get_trade`:

```python
def get_trade(conn: sqlite3.Connection, trade_id: int) -> Trade | None:
    row = conn.execute(
        """
        SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
               current_stop, status, watchlist_entry_target,
               watchlist_initial_stop, notes, hypothesis_label,
               chart_pattern_algo, chart_pattern_algo_confidence,
               chart_pattern_operator, chart_pattern_classification_pipeline_run_id,
               sector, industry
        FROM trades WHERE id = ?
        """,
        (trade_id,),
    ).fetchone()
    return _row_to_trade(row) if row else None
```

And update `_row_to_trade` (around line 364) to populate the new fields:

```python
def _row_to_trade(row: tuple) -> Trade:
    return Trade(
        id=row[0], ticker=row[1], entry_date=row[2], entry_price=row[3],
        initial_shares=row[4], initial_stop=row[5], current_stop=row[6],
        status=row[7], watchlist_entry_target=row[8],
        watchlist_initial_stop=row[9], notes=row[10],
        hypothesis_label=row[11],
        chart_pattern_algo=row[12],
        chart_pattern_algo_confidence=row[13],
        chart_pattern_operator=row[14],
        chart_pattern_classification_pipeline_run_id=row[15],
        sector=row[16], industry=row[17],
    )
```

> **Verification step.** After edits, `grep -n "FROM trades" swing/data/repos/trades.py` to enumerate all SELECTs. Each should now reference `sector, industry` in the column list. Count must be the same as the count before edits + the new column references — no SELECT overlooked.

- [ ] **Step 4.7: Run the roundtrip test.**

```bash
python -m pytest tests/data/test_repos_trades.py::test_trade_sector_industry_roundtrip_all_select_paths -v
```

Expected: PASS.

- [ ] **Step 4.8: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

Expected: previously-passing tests still pass.

- [ ] **Step 4.9: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4'
```

Expected: empty.

```bash
git add swing/data/models.py swing/data/repos/trades.py tests/data/test_repos_trades.py
git commit -m "feat(data): Task 4 — Trade dataclass + repo carry sector/industry on all SELECT paths

Adds sector + industry to Trade with '' defaults; extends insert_trade_with_event
SQL + all 5 SELECT call sites + _row_to_trade. Discriminating roundtrip exercises
get_trade / list_open_trades / list_closed_trades (both since-date branches) /
find_any_open_trade / find_open_trade_by_match (both shares branches) — guards
against the recurring repo-SELECT-coverage bug.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 4'\` empty pre-commit.
"
```

---

## Task 5: EntryRequest + record_entry — sector/industry passthrough

**Files:**
- Modify: `swing/trades/entry.py:80-109` (`EntryRequest`), `swing/trades/entry.py:158-232` (`record_entry`)
- Test: extend `tests/trades/test_entry.py` (existing file with `_req()` EntryRequest factory + `ensure_schema(tmp_path / "swing.db")` pattern at lines 19-26).

**Discriminating-test sanity-check.** Test constructs an `EntryRequest` with `sector="Healthcare"` + `industry="Pharmaceuticals"`; calls `record_entry`; asserts the persisted Trade row carries those exact strings. If `record_entry`'s `Trade(...)` construction omits the new fields (or hard-codes empty defaults), the assertion fails. **Would this test fail if the implementation never actually called the new code? Yes — without explicit pass-through, the Trade is constructed with default `""` for both fields, and the assertion `t.sector == "Healthcare"` fails.**

- [ ] **Step 5.1: Write the failing test.**

```python
def test_record_entry_persists_sector_industry_as_is(tmp_path):
    """record_entry persists EntryRequest.sector + .industry AS-IS on the
    Trade row (snapshot-at-entry-surface — no re-resolve at submit time)."""
    from swing.data.db import ensure_schema
    from swing.data.repos.trades import get_trade
    from swing.trades.entry import EntryRequest, record_entry
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        req = EntryRequest(
            ticker="ZZZF", entry_date="2026-04-28", entry_price=100.0,
            shares=10, initial_stop=95.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="2026-04-28T00:00:00",
            sector="Healthcare", industry="Pharmaceuticals",
        )
        result = record_entry(conn, req, soft_warn=999, hard_cap=999, force=False)
        t = get_trade(conn, result.trade_id)
        assert t is not None
        assert t.sector == "Healthcare"
        assert t.industry == "Pharmaceuticals"
    finally:
        conn.close()


def test_entry_request_default_sector_industry_empty():
    """EntryRequest constructed without sector/industry uses '' defaults."""
    from swing.trades.entry import EntryRequest
    req = EntryRequest(
        ticker="DFLT", entry_date="2026-04-28", entry_price=100.0,
        shares=10, initial_stop=95.0,
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, rationale="aplus-setup",
        event_ts="2026-04-28T00:00:00",
    )
    assert req.sector == ""
    assert req.industry == ""
```

- [ ] **Step 5.2: Run the failing tests.**

```bash
python -m pytest tests/trades/test_entry.py::test_record_entry_persists_sector_industry_as_is tests/trades/test_entry.py::test_entry_request_default_sector_industry_empty -v
```

Expected: FAIL with `TypeError: got an unexpected keyword argument 'sector'`.

- [ ] **Step 5.3: Add fields to EntryRequest.**

In `swing/trades/entry.py`, append to `EntryRequest`:

```python
@dataclass(frozen=True)
class EntryRequest:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    rationale: str
    event_ts: str
    hypothesis_label: str | None = None
    chart_pattern_operator: str | None = None
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Migration 0012 — sector/industry snapshot-at-entry-surface. Resolved
    # at form/CLI render time from the candidate row; persisted AS-IS by
    # record_entry. Defaults '' so off-pipeline / off-watchlist trade entries
    # (no candidate row to read) persist empty strings — graceful
    # degradation matches the hypothesis_label free-text behavior.
    sector: str = ""
    industry: str = ""
```

- [ ] **Step 5.4: Update `record_entry` to plumb through.**

In `swing/trades/entry.py`, modify `record_entry`'s `Trade(...)` construction:

```python
    trade = Trade(
        id=None, ticker=req.ticker, entry_date=req.entry_date,
        entry_price=req.entry_price, initial_shares=req.shares,
        initial_stop=req.initial_stop, current_stop=req.initial_stop,
        status="open",
        watchlist_entry_target=req.watchlist_entry_target,
        watchlist_initial_stop=req.watchlist_initial_stop,
        notes=req.notes,
        hypothesis_label=canonicalize_hypothesis_label(req.hypothesis_label),
        chart_pattern_algo=req.chart_pattern_algo,
        chart_pattern_algo_confidence=req.chart_pattern_algo_confidence,
        chart_pattern_operator=canonicalize_hypothesis_label(req.chart_pattern_operator),
        chart_pattern_classification_pipeline_run_id=req.chart_pattern_classification_pipeline_run_id,
        sector=req.sector,
        industry=req.industry,
    )
```

> **No canonicalization for sector/industry.** Per dispatch brief §5.1 + spec rationale: sector/industry are NOT operator-typed free text — they come from Finviz CSV on the ingestion path; from a candidate-row lookup on the entry path. The existing `canonicalize_hypothesis_label` helper applies NFC + control-char + whitespace normalization meant for operator typing surfaces. Sector/industry feed from a structured source; canonicalizing them adds risk (silently rewriting Finviz values) without benefit. **If a future use case requires canonicalization (e.g., aggregation key with operator-overridable variants), add a separate canonicalizer at that point — V1 does not.**

- [ ] **Step 5.5: Run the test.**

```bash
python -m pytest tests/trades/test_entry.py::test_record_entry_persists_sector_industry_as_is tests/trades/test_entry.py::test_entry_request_default_sector_industry_empty -v
```

Expected: PASS.

- [ ] **Step 5.6: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

- [ ] **Step 5.7: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 5'
```

```bash
git add swing/trades/entry.py tests/trades/test_entry.py
git commit -m "feat(trades): Task 5 — EntryRequest + record_entry plumb sector/industry to Trade

Snapshot-at-entry-surface: form / CLI resolve from candidate row at render time;
record_entry persists AS-IS (no re-resolve at submit). Per V1 §3.6 + brief §5.1
no canonicalization (sector/industry are structured CSV passthrough, not
operator-typed text).

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 5'\` empty pre-commit.
"
```

---

## Task 6: Trade entry web form — render-time snapshot + hidden fields + soft-warn round-trip

**Files:**
- Modify: `swing/web/view_models/trades.py:21-167` (`TradeEntryFormVM` + `build_entry_form_vm`)
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2`
- Modify: `swing/web/routes/trades.py:218-403` (`entry_post` Form params, `req` construction, soft_warn_confirm `form_values` dict, `_rerender_entry_form_with_error` preservation path)
- Test (VM): extend `tests/web/test_view_models/test_trade_entry_form_classification.py` — existing file with `seeded_db` fixture, `seed_pipeline_with_classification` precedent helper, `MagicMock` cache pattern.
- Test (route + soft_warn round-trip): extend `tests/web/test_routes/test_trade_entry_chart_pattern.py` — existing file with `seeded_db` fixture + `seed_pipeline_with_classification` + `TestClient(app)` lifespan-bound pattern.

**Discriminating-test sanity-check.** Test for VM populates the candidate row's sector/industry to specific test-only values (`"Sector-T6-A"` / `"Industry-T6-A"`) and asserts the constructed VM exposes those exact values. Test for the POST route submits a multipart form with hidden `sector="Sector-T6-B"` and `industry="Industry-T6-B"`; asserts the persisted Trade row carries those values. The Test-prefixed sentinel values guarantee NO production code path defaults to them — if the field plumbing is broken, the persisted value diverges from the sentinel and the assertion fails. **Would these tests fail if the implementation never actually called the new code? Yes — VM construction without the candidate-row-lookup branch returns `sector=""`; POST handler that ignores the form fields constructs EntryRequest with default `""`; both fail the assertion.**

Test for soft_warn_confirm round-trip: first POST hits soft_warn cap, route returns the confirm fragment, fragment's hidden inputs MUST include `sector` and `industry` with the values from the original POST; second POST with `force=true` from the confirm fragment persists the original sector/industry on the Trade.

- [ ] **Step 6.1: Write the failing tests.**

Append to `tests/web/test_view_models/test_trade_entry_form_classification.py` (extend the existing file — `seeded_db` fixture and `seed_pipeline_with_classification` helper are already imported):

```python
def test_entry_form_vm_populates_sector_industry_from_candidate(seeded_db):
    """build_entry_form_vm reads sector + industry from the candidate row
    by ticker. Sentinel values 'Sector-T6-A' / 'Industry-T6-A' guarantee
    no production code path defaults to them."""
    from unittest.mock import MagicMock
    from swing.data.db import connect
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    # Reuse the seed helper for the pipeline_run + watchlist scaffold,
    # then UPDATE the candidate row's sector/industry to the sentinels.
    run_id, eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    conn = connect(cfg.paths.db_path)
    try:
        # Seed a candidates row keyed on the FK-backed eval_id with the sentinels.
        conn.execute(
            """INSERT INTO candidates
               (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
                rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
                sector, industry)
               VALUES (?, 'AAPL', 'watch', 100.0, 105.0, 95.0,
                       2.0, 5, NULL, NULL, NULL, NULL, 'fallback_spy',
                       NULL, NULL, 'Sector-T6-A', 'Industry-T6-A')""",
            (eval_id,),
        )
        conn.commit()
    finally:
        conn.close()
    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )
    assert vm.sector == "Sector-T6-A"
    assert vm.industry == "Industry-T6-A"


def test_entry_form_vm_no_candidate_row_defaults_empty_sector_industry(seeded_db):
    """When no candidate row exists for the entered ticker (off-pipeline
    entry), the VM exposes empty strings — graceful degradation per
    brief §5.8."""
    from unittest.mock import MagicMock
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    # Seed pipeline + watchlist but NOT a candidates row for the ticker.
    seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="OTHER", pattern="flag", confidence=0.5,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )
    assert vm.sector == ""
    assert vm.industry == ""
```

Append to `tests/web/test_routes/test_trade_entry_chart_pattern.py` (extend the existing file — `seeded_db` + `seed_pipeline_with_classification` + `TestClient(app)` pattern already in scope; existing soft-warn tests at line 510 are the closest precedent):

```python
def test_post_entry_persists_sector_industry_from_form(seeded_db):
    """POST /trades/entry with hidden sector + industry form fields persists
    them on the Trade row AS-IS (snapshot-at-entry-surface ToCToU)."""
    from fastapi.testclient import TestClient
    from swing.data.db import connect
    from swing.data.repos.trades import find_any_open_trade
    from swing.web.app import create_app
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/trades/entry", data={
            "ticker": "AAPL", "entry_date": "2026-04-28",
            "entry_price": "100.0", "shares": "1", "initial_stop": "95.0",
            "rationale": "aplus-setup",
            "sector": "Sector-Route-T6-B",
            "industry": "Industry-Route-T6-B",
        }, headers={"HX-Request": "true"})
    assert r.status_code == 200, r.text
    conn = connect(cfg.paths.db_path)
    try:
        t = find_any_open_trade(conn, ticker="AAPL")
    finally:
        conn.close()
    assert t is not None
    assert t.sector == "Sector-Route-T6-B"
    assert t.industry == "Industry-Route-T6-B"


def test_post_entry_soft_warn_confirm_preserves_sector_industry(seeded_db):
    """First POST trips soft_warn cap → returns soft_warn_confirm fragment
    carrying sector + industry as hidden inputs. Second POST (force=true)
    persists those values on the Trade. Mirrors the chart_pattern
    snapshot preservation pattern (Phase 5 Codex R1 Major 2)."""
    from fastapi.testclient import TestClient
    from swing.data.db import connect
    from swing.data.repos.trades import find_any_open_trade, insert_trade_with_event
    from swing.data.models import Trade
    from swing.web.app import create_app
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    # Seed enough open trades to trip soft_warn (default soft_warn_open=4).
    conn = connect(cfg.paths.db_path)
    try:
        for i, tk in enumerate(["TK1", "TK2", "TK3", "TK4"]):
            with conn:
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=tk, entry_date="2026-04-20",
                    entry_price=100.0, initial_shares=1, initial_stop=95.0,
                    current_stop=95.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-20T09:30:0{i}")
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # First POST — trips soft_warn.
        r1 = client.post("/trades/entry", data={
            "ticker": "AAPL", "entry_date": "2026-04-28",
            "entry_price": "100.0", "shares": "1", "initial_stop": "95.0",
            "rationale": "aplus-setup",
            "sector": "Sector-SoftWarn-T6", "industry": "Industry-SoftWarn-T6",
        }, headers={"HX-Request": "true"})
        assert r1.status_code == 200
        # Confirm fragment carries sector/industry as hidden inputs.
        body = r1.text
        assert 'name="sector" value="Sector-SoftWarn-T6"' in body
        assert 'name="industry" value="Industry-SoftWarn-T6"' in body
        # Second POST — force=true; round-trip submits the snapshot.
        r2 = client.post("/trades/entry", data={
            "ticker": "AAPL", "entry_date": "2026-04-28",
            "entry_price": "100.0", "shares": "1", "initial_stop": "95.0",
            "rationale": "aplus-setup",
            "sector": "Sector-SoftWarn-T6", "industry": "Industry-SoftWarn-T6",
            "force": "true",
        }, headers={"HX-Request": "true"})
        assert r2.status_code == 200, r2.text
    conn = connect(cfg.paths.db_path)
    try:
        t = find_any_open_trade(conn, ticker="AAPL")
    finally:
        conn.close()
    assert t is not None
    assert t.sector == "Sector-SoftWarn-T6"
    assert t.industry == "Industry-SoftWarn-T6"
```

- [ ] **Step 6.2: Run the failing tests.**

```bash
python -m pytest tests/web/test_view_models/test_trade_entry_form_classification.py tests/web/test_routes/test_trade_entry_chart_pattern.py -v -k "sector_industry or persists_sector_industry or soft_warn_confirm_preserves_sector_industry"
```

Expected: FAIL with NotImplementedError (skeleton) or sector/industry mismatch (after harness).

- [ ] **Step 6.3: Add fields to TradeEntryFormVM and resolve from candidate.**

In `swing/web/view_models/trades.py`, modify `TradeEntryFormVM`:

```python
@dataclass(frozen=True)
class TradeEntryFormVM:
    ticker: str
    entry_date: str
    entry_price: float
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    suggested_shares: int
    risk_dollars: float
    risk_pct: float
    soft_warn_threshold: int
    hard_cap: int
    open_count: int
    force: bool = False
    rationale: str = ""
    notes: str = ""
    input_shares: int = 0
    rationale_options: tuple[tuple[str, str], ...] = ()
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_algo_evaluated: bool = False
    chart_pattern_algo_computed_at: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Migration 0012 — sector/industry snapshot resolved once at form-render
    # time from the candidate row; carried via hidden form fields and
    # persisted AS-IS on POST. Empty strings when no candidate row exists
    # for the ticker (off-pipeline / off-watchlist entry); graceful
    # degradation matches the hypothesis_label free-text behavior.
    sector: str = ""
    industry: str = ""
```

In `build_entry_form_vm`, extend the read-snapshot block to ALSO fetch sector/industry. **Use the canonical `latest_evaluation_run_id()` helper** (`swing/web/view_models/dashboard.py:64-95`) so the entry form binds to the SAME evaluation run anchor the dashboard hyp-rec surface uses — closes the cross-surface drift Codex R1 Major 4 flagged. Falling back to the helper preserves the dashboard's two-step selection (pipeline-bound complete → fallback to latest standalone eval). Concrete change inside the `with conn:` block:

```python
        with conn:
            wl = list_active_watchlist(conn)
            wl_entry = next((w for w in wl if w.ticker == ticker), None)
            open_trades = list_open_trades(conn)
            exits = list_all_exits(conn)
            cash_movements = list_cash(conn)
            pipeline_eval_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            pipeline_run_id = (
                pipeline_eval_row[0] if pipeline_eval_row else None
            )
            # NEW (R1 Codex Major 4): use the canonical helper for
            # candidate-row binding to keep entry surfaces aligned with
            # the dashboard's hyp-rec surface. The helper falls back to
            # the latest standalone eval when no completed pipeline-bound
            # eval exists — same fallback the dashboard uses, so a
            # post-pipeline standalone `swing eval` produces consistent
            # sector/industry across the two surfaces.
            from swing.web.view_models.dashboard import latest_evaluation_run_id
            cand_sector = ""
            cand_industry = ""
            sector_eval_id = latest_evaluation_run_id(conn)
            if sector_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (sector_eval_id, ticker),
                ).fetchone()
                if cand_row is not None:
                    cand_sector = cand_row[0] or ""
                    cand_industry = cand_row[1] or ""
            if pipeline_run_id is not None:
                from swing.data.repos.pattern_classifications import (
                    get_classification,
                )
                cls = get_classification(
                    conn, pipeline_run_id=pipeline_run_id, ticker=ticker,
                )
```

Then thread `sector=cand_sector, industry=cand_industry` into the final `TradeEntryFormVM(...)` construction at the bottom of the function.

> **Why query candidates directly instead of `fetch_candidates_for_run` + iterate?** `fetch_candidates_for_run` returns the full Candidate (criteria + all metric columns) and triggers an N+1-style criteria SELECT per candidate. For the entry-form VM we need only sector + industry — a single 2-column SELECT bound to `(evaluation_run_id, ticker)` is the minimum query.

> **Why decouple the candidate-row eval anchor from the chart_pattern pipeline_run anchor?** Chart-pattern classifications are keyed on `pipeline_run_id` — they require a completed PIPELINE run, not just an eval. Sector/industry are on the candidate row, which is keyed on `evaluation_run_id` — the dashboard binds candidates_by_ticker via `latest_evaluation_run_id()` (which prefers pipeline-bound complete but falls back to latest standalone eval). The entry-form VM should match the dashboard's anchor for sector/industry; the chart-pattern resolution stays on the pipeline-run anchor. The two queries are independent reads in the same transaction; no risk of inconsistency.

- [ ] **Step 6.4: Update the trade_entry_form template.**

In `swing/web/templates/partials/trade_entry_form.html.j2`, add a sector/industry display block before the rationale block (near line 45, just after the chart_pattern_section include). The block emits both a visible read-only line AND hidden inputs (so the value rides on POST):

```html+jinja
      {% include "partials/trade_entry_chart_pattern_section.html.j2" %}
      <div><label>Sector</label>
        <span>{{ vm.sector or "—" }}</span>
        <input type="hidden" name="sector" value="{{ vm.sector }}">
      </div>
      <div><label>Industry</label>
        <span>{{ vm.industry or "—" }}</span>
        <input type="hidden" name="industry" value="{{ vm.industry }}">
      </div>
      <div><label>Rationale &#9733;</label>
```

> **Why hidden inputs even when empty?** The POST handler must accept the field whether it's populated or empty (Form param has `default=""`). Always emitting the hidden input keeps the form contract uniform between candidate-present and candidate-absent paths.

- [ ] **Step 6.5: Update `entry_post` to accept + plumb sector/industry.**

In `swing/web/routes/trades.py`, add Form parameters to `entry_post` AFTER the chart_pattern fields:

```python
def entry_post(
    request: Request,
    ticker: str = Form(...),
    entry_date: str = Form(...),
    entry_price: float = Form(...),
    shares: int = Form(...),
    initial_stop: float = Form(...),
    rationale: str = Form(...),
    notes: str | None = Form(None),
    watchlist_target: float | None = Form(None),
    watchlist_stop: float | None = Form(None),
    force: str | None = Form(None),
    chart_pattern_algo: str | None = Form(None),
    chart_pattern_algo_confidence: float | None = Form(None),
    chart_pattern_classification_pipeline_run_id: int | None = Form(None),
    chart_pattern_operator: str | None = Form(None),
    chart_pattern_operator_other: str | None = Form(None),
    sector: str = Form(""),
    industry: str = Form(""),
):
```

In the `req = EntryRequest(...)` construction, add `sector=sector` and `industry=industry`:

```python
    req = EntryRequest(
        ticker=ticker.upper(),
        # ... existing fields unchanged ...
        chart_pattern_classification_pipeline_run_id=cp_anchor_value,
        sector=sector,
        industry=industry,
    )
```

In the SoftWarnException branch's `form_values` dict, add:

```python
            form_values = {
                # ... existing keys ...
                "chart_pattern_operator": chart_pattern_operator or "",
                "chart_pattern_operator_other": chart_pattern_operator_other or "",
                "sector": sector,
                "industry": industry,
                "open_count": actual_open,
                "soft_warn": cfg.position_limits.soft_warn_open,
                "hard_cap": cfg.position_limits.hard_cap_open,
            }
```

> **soft_warn_confirm partial requires NO change.** It iterates `form_values` and emits a hidden input for every key not in `("open_count", "soft_warn", "hard_cap")`. Adding sector + industry to the dict automatically extends the round-trip — same pattern the chart_pattern fields use. **Verify** by reading `swing/web/templates/partials/soft_warn_confirm.html.j2` and confirming the iterator covers all dict keys except the three exclusions.

> **`_rerender_entry_form_with_error` requires NO direct preservation work for sector/industry.** That helper rebuilds the VM via `build_entry_form_vm` (which now reads sector/industry from the candidate row) and replaces only operator-typed fields (entry_date, entry_price, initial_stop, input_shares, rationale, notes). Sector/industry come from the same candidate-row lookup the GET would do — they are server-resolved, not operator-input — so the rebuild path is correct without explicit preservation.

- [ ] **Step 6.6: Run the failing tests + full fast suite.**

```bash
python -m pytest tests/web/test_view_models/test_trade_entry_form_classification.py tests/web/test_routes/test_trade_entry_chart_pattern.py -v -k "sector_industry or persists_sector_industry or soft_warn_confirm_preserves_sector_industry"
```

Expected: PASS.

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

Expected: previously-passing tests still pass.

- [ ] **Step 6.7: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 6'
```

```bash
git add swing/web/view_models/trades.py swing/web/routes/trades.py \
        swing/web/templates/partials/trade_entry_form.html.j2 \
        tests/web/test_view_models/test_trade_entry_form_classification.py \
        tests/web/test_routes/test_trade_entry_chart_pattern.py
git commit -m "feat(web): Task 6 — trade-entry form snapshots sector/industry at GET, persists at POST

build_entry_form_vm resolves sector + industry from the candidate row by
ticker against the latest completed pipeline_run's evaluation_run_id (in
the same read-snapshot transaction as the chart_pattern resolution).
Hidden inputs ride POST → entry_post → EntryRequest → record_entry.
soft_warn_confirm round-trip preserves both fields via form_values dict
extension (no template change — iterator covers new keys automatically).

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 6'\` empty pre-commit.
"
```

---

## Task 7: CLI trade-entry command — auto-resolve sector/industry from candidate

**Files:**
- Modify: `swing/cli.py:355-491` (`trade_entry_cmd`)
- Test: extend `tests/cli/test_cli_trade_entry_chart_pattern.py` — existing file with `_setup` (CliRunner + `_minimal_config` + `db-migrate`), `seed_pipeline_with_classification` precedent, and `_db_path_for_cfg` helper at line 62.

**Discriminating-test sanity-check.** Test invokes `swing trade entry` against a DB seeded with a candidate row that has sector="CLI-Sector-T7" / industry="CLI-Industry-T7"; asserts the persisted Trade carries those exact values. Second test uses a ticker NOT in the candidate table; asserts the persisted Trade has empty strings. Test-prefixed sentinels prevent any default-string mask. **Would this test fail if the implementation never actually called the new code? Yes — without the candidate-row lookup the EntryRequest gets default `""`, and the persisted trade row's sector/industry don't match the seeded sentinels.**

- [ ] **Step 7.1: Write the failing tests.**

Append to `tests/cli/test_cli_trade_entry_chart_pattern.py` (extend the existing file — `_setup`, `_db_path_for_cfg`, `seed_pipeline_with_classification` already in scope from existing imports):

```python
def _seed_candidate_row(
    db_path: Path, *, eval_id: int, ticker: str,
    sector: str, industry: str,
):
    """Seed one candidates row keyed on the FK-backed eval_id."""
    from swing.data.db import connect
    conn = connect(db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
                    rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
                    sector, industry)
                   VALUES (?, ?, 'watch', 100.0, 105.0, 95.0,
                           2.0, 5, NULL, NULL, NULL, NULL, 'fallback_spy',
                           NULL, NULL, ?, ?)""",
                (eval_id, ticker, sector, industry),
            )
    finally:
        conn.close()


def test_cli_trade_entry_resolves_sector_industry_from_candidate(tmp_path: Path):
    """`swing trade entry` reads sector + industry from the candidate row
    via `latest_evaluation_run_id()` (canonical helper used by dashboard
    + hypothesis pre-fill); persists AS-IS on the trade row. Sentinel
    'CLI-Sector-T7' / 'CLI-Industry-T7' guards against any default-string
    mask."""
    runner, cfg = _setup(tmp_path)
    db_path = _db_path_for_cfg(cfg)
    _, eval_id = seed_pipeline_with_classification(
        db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    _seed_candidate_row(
        db_path, eval_id=eval_id, ticker="AAPL",
        sector="CLI-Sector-T7", industry="CLI-Industry-T7",
    )
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-26",
        "--entry-price", "10.0", "--shares", "1", "--initial-stop", "9.0",
        "--rationale", "aplus-setup",
    ])
    assert result.exit_code == 0, result.output
    from swing.data.db import connect
    from swing.data.repos.trades import find_any_open_trade
    conn = connect(db_path)
    try:
        t = find_any_open_trade(conn, ticker="AAPL")
    finally:
        conn.close()
    assert t is not None
    assert t.sector == "CLI-Sector-T7"
    assert t.industry == "CLI-Industry-T7"


def test_cli_trade_entry_no_candidate_persists_empty_sector_industry(tmp_path: Path):
    """When no candidate row exists for the entered ticker, `swing trade entry`
    persists sector='' + industry='' (graceful degradation per brief §5.8;
    matches the hypothesis_label free-text behavior). Pipeline-bypass /
    off-watchlist trade entries are explicitly supported."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-26",
        "--entry-price", "10.0", "--shares", "1", "--initial-stop", "9.0",
        "--rationale", "aplus-setup",
    ])
    assert result.exit_code == 0, result.output
    from swing.data.db import connect
    from swing.data.repos.trades import find_any_open_trade
    db_path = _db_path_for_cfg(cfg)
    conn = connect(db_path)
    try:
        t = find_any_open_trade(conn, ticker="AAPL")
    finally:
        conn.close()
    assert t is not None
    assert t.sector == ""
    assert t.industry == ""
```

- [ ] **Step 7.2: Run the failing tests.**

```bash
python -m pytest tests/cli/test_cli_trade_entry_chart_pattern.py -v -k "sector_industry"
```

Expected: FAIL.

- [ ] **Step 7.3: Implement candidate-row lookup in `trade_entry_cmd`.**

In `swing/cli.py`, modify `trade_entry_cmd`'s body. **Use the canonical `latest_evaluation_run_id()` helper** (R1 Codex Major 4 RESOLVED) so the CLI binds to the SAME evaluation anchor the dashboard uses for sector/industry — same anchor the existing CLI hypothesis pre-fill helper uses (`swing/cli.py:296+`). Right after the existing chart-pattern resolution block (around line 442), add the sector/industry resolution:

```python
        # Phase 5 spec §3.6 ToCToU fix — chart-pattern cache resolved once
        # at command start (existing). Migration 0012 — sector + industry
        # resolved from the candidate row via latest_evaluation_run_id() so
        # the CLI binds to the SAME evaluation anchor the dashboard uses
        # (Codex R1 Major 4 — closes cross-surface drift; matches the
        # hypothesis pre-fill helper's anchor at swing/cli.py:296+).
        cp_algo: str | None = None
        cp_conf: float | None = None
        cp_anchor: int | None = None
        cp_evaluated = False
        cli_sector = ""
        cli_industry = ""
        pipeline_eval_row = conn.execute(
            """SELECT id, evaluation_run_id FROM pipeline_runs
               WHERE state='complete'
               ORDER BY finished_ts DESC LIMIT 1"""
        ).fetchone()
        if pipeline_eval_row is not None and pipeline_eval_row[0] is not None:
            from swing.data.repos.pattern_classifications import (
                get_classification,
            )
            cls = get_classification(
                conn, pipeline_run_id=pipeline_eval_row[0],
                ticker=ticker.upper(),
            )
            if cls is not None and cls.pattern in ("flag", "none"):
                cp_algo = cls.pattern
                cp_conf = cls.confidence
                cp_anchor = cls.pipeline_run_id
                cp_evaluated = True

        # NEW: sector/industry candidate-row lookup via the canonical helper.
        from swing.web.view_models.dashboard import latest_evaluation_run_id
        sector_eval_id = latest_evaluation_run_id(conn)
        if sector_eval_id is not None:
            cand_row = conn.execute(
                """SELECT sector, industry FROM candidates
                   WHERE evaluation_run_id = ? AND ticker = ?""",
                (sector_eval_id, ticker.upper()),
            ).fetchone()
            if cand_row is not None:
                cli_sector = cand_row[0] or ""
                cli_industry = cand_row[1] or ""
```

> **Why import from `swing.web.view_models.dashboard`?** That's where the canonical helper lives. The CLI consuming a web-VM helper is precedent: `swing/cli.py:296+` (`_lookup_active_recommendation_label`) already pulls from the dashboard's hypothesis prioritizer. Reusing the helper preserves cross-surface anchor consistency without duplicating the two-step selection logic.

Add `sector=cli_sector, industry=cli_industry` to the `req = EntryRequest(...)` construction:

```python
        req = EntryRequest(
            ticker=ticker.upper(), entry_date=entry_date, entry_price=entry_price,
            shares=shares, initial_stop=initial_stop,
            watchlist_entry_target=watchlist_target,
            watchlist_initial_stop=watchlist_stop,
            notes=notes, rationale=rationale,
            event_ts=_dt.now().isoformat(timespec="seconds"),
            hypothesis_label=hypothesis,
            chart_pattern_operator=chart_pattern_operator,
            chart_pattern_algo=cp_algo,
            chart_pattern_algo_confidence=cp_conf,
            chart_pattern_classification_pipeline_run_id=cp_anchor,
            sector=cli_sector,
            industry=cli_industry,
        )
```

> **No `--sector` / `--industry` CLI flags in V1.** Per brief §5.8 + dispatch §3.C: V1 auto-resolves only. Adding flags creates an override surface that V1 trusts Finviz exclusively. If a future use case requires manual override, add the flags as a follow-up dispatch with explicit operator approval (and answer the canonicalization question that comes with operator-typed input — see Task 5 §5.4 sidebar).

- [ ] **Step 7.4: Run the test + full suite.**

```bash
python -m pytest tests/cli/test_cli_trade_entry_chart_pattern.py -v -k "sector_industry"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 7.5: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 7'
```

```bash
git add swing/cli.py tests/cli/test_cli_trade_entry_chart_pattern.py
git commit -m "feat(cli): Task 7 — \`swing trade entry\` auto-resolves sector/industry from candidate

Single 2-column SELECT against the FK-backed evaluation_run_id within the
existing read snapshot; persists empty strings when no candidate row exists
for the ticker (graceful degradation per brief §5.8). No --sector / --industry
flags in V1 — V1 trusts Finviz; manual override deferred.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 7'\` empty pre-commit.
"
```

---

## Task 8: Watchlist row expansion — display sector + industry

**Files:**
- Modify: `swing/web/templates/partials/watchlist_expanded.html.j2`
- Test: extend `tests/web/test_view_models/test_watchlist.py` — existing file with `seeded_db` fixture, `upsert_watchlist_entry` + `TestClient(app)` template-render pattern (line 153 precedent: `test_watchlist_expanded_template_renders_reason_message`).

**Discriminating-test sanity-check.** Test renders the partial with a `WatchlistExpandedVM` whose `candidate.sector="WL-Sector-T8"` + `candidate.industry="WL-Industry-T8"`; asserts the rendered HTML contains the EXACT string `"WL-Sector-T8"` (substring match against the test-prefixed sentinel). Second test renders with `candidate=None` and asserts the rendered HTML contains NEITHER `Sector:` heading NOR `Industry:` heading (the rows are gated on `candidate` being present, mirroring the existing Trend Template / VCP grids gating). **Would these tests fail if the implementation never actually called the new code? Yes — without the new template lines the rendered HTML omits `WL-Sector-T8` entirely; the substring assertion fails. The candidate=None test guards against unconditional rendering.**

- [ ] **Step 8.1: Write the failing tests.**

Append to `tests/web/test_view_models/test_watchlist.py` (extend existing file — `seeded_db`, `upsert_watchlist_entry`, `WatchlistEntry`, `TestClient(app)` already in scope from existing tests):

```python
def test_watchlist_expanded_renders_sector_industry_when_candidate_present(
    seeded_db, monkeypatch,
):
    """GET /watchlist/AAPL/expand renders sector + industry rows pulled
    from the candidate row. Sentinel 'WL-Sector-T8' / 'WL-Industry-T8'
    guards against any default-string mask."""
    from fastapi.testclient import TestClient
    from swing.data.db import connect
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache
    from tests.web.test_view_models._pattern_classification_seed import (
        seed_pipeline_with_classification,
    )
    cfg, cfg_path = seeded_db
    # Reuse the seed helper for pipeline + watchlist scaffold (creates
    # an active watchlist row for AAPL); then add a candidates row with
    # the sentinel sector/industry on the FK-backed eval.
    _, eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
                    rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
                    sector, industry)
                   VALUES (?, 'AAPL', 'watch', 100.0, 105.0, 95.0,
                           2.0, 5, NULL, NULL, NULL, NULL, 'fallback_spy',
                           NULL, NULL, 'WL-Sector-T8', 'WL-Industry-T8')""",
                (eval_id,),
            )
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/AAPL/expand")
    assert r.status_code == 200
    body = r.text
    assert "WL-Sector-T8" in body
    assert "WL-Industry-T8" in body


def test_watchlist_expanded_no_sector_industry_when_candidate_none(
    seeded_db, monkeypatch,
):
    """When no candidate row exists for the ticker (off-pipeline watchlist
    entry), partial does NOT emit the Classification heading or Sector /
    Industry rows. Only the watchlist row + chart-unavailable block render."""
    from fastapi.testclient import TestClient
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/AAPL/expand")
    assert r.status_code == 200
    body = r.text
    # Classification heading + sector/industry rows are gated on candidate
    # being present; absent here.
    assert "<h4>Classification</h4>" not in body
    assert "Sector:" not in body
    assert "Industry:" not in body
```

- [ ] **Step 8.2: Run the failing test.**

```bash
python -m pytest tests/web/test_view_models/test_watchlist.py -v -k "sector_industry"
```

Expected: FAIL.

- [ ] **Step 8.3: Update the partial.**

In `swing/web/templates/partials/watchlist_expanded.html.j2`, add a Sector/Industry block inside the `{% if expanded.candidate %}` guard, between the existing VCP grid and the chart-img block:

```html+jinja
    {% if expanded.candidate %}
      <h4>Trend Template</h4>
      <ul class="tt-grid">
        {% for cr in expanded.candidate.criteria if cr.layer == 'trend_template' %}
          <li class="{{ cr.result }}">{{ cr.criterion_name }}: {{ cr.result }}</li>
        {% endfor %}
      </ul>
      <h4>VCP</h4>
      <ul class="vcp-grid">
        {% for cr in expanded.candidate.criteria if cr.layer == 'vcp' %}
          <li class="{{ cr.result }}">{{ cr.criterion_name }}: {{ cr.result }}</li>
        {% endfor %}
      </ul>
      <h4>Classification</h4>
      <p>Sector: {{ expanded.candidate.sector or "—" }}</p>
      <p>Industry: {{ expanded.candidate.industry or "—" }}</p>
    {% endif %}
```

> **No new VM field.** The VM already carries `candidate: Candidate | None`; sector/industry are accessed via `expanded.candidate.sector` / `.industry` directly. Task 2 ensured the Candidate dataclass + repo populate these fields.

- [ ] **Step 8.4: Run the test + full suite.**

```bash
python -m pytest tests/web/test_view_models/test_watchlist.py -v -k "sector_industry"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

- [ ] **Step 8.5: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 8'
```

```bash
git add swing/web/templates/partials/watchlist_expanded.html.j2 \
        tests/web/test_view_models/test_watchlist.py
git commit -m "feat(web): Task 8 — watchlist expansion renders sector + industry rows

Reads from expanded.candidate.sector / .industry (no new VM field — Candidate
already carries them post Task 2). Rows gated inside the existing
{% if expanded.candidate %} guard so off-pipeline watchlist entries
(candidate=None) render gracefully without the headings.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 8'\` empty pre-commit.
"
```

---

## Task 9: Open positions row — display sector + industry

**Files:**
- Modify: `swing/web/templates/partials/open_positions_row.html.j2` (add Sector + Industry `<td>` cells)
- Modify: `swing/web/templates/partials/open_positions.html.j2:8` (add Sector + Industry `<th>` to the `<thead>` — known parent header file; per Codex R1 Minor 2)
- Modify: `swing/web/templates/partials/open_positions_expanded.html.j2:20` (update `colspan` 8 → 10 to match new cell count)
- Test: extend `tests/web/test_routes/test_open_positions_expand.py` (existing file with route + colspan-alignment pattern at line 521 per Codex R1 Major 2 reference).

**Discriminating-test sanity-check.** Test seeds an open Trade with `sector="OP-Sector-T9"` + `industry="OP-Industry-T9"`; renders the open-positions section via TestClient; asserts the rendered HTML contains both sentinel strings. Test also asserts colspan in `open_positions_expanded.html.j2` is `"10"` (was `"8"`). **Would these tests fail if the implementation never actually called the new code? Yes — without the new `<td>` cells the rendered HTML omits both sentinel strings; without the colspan update the chart-display fragment is structurally misaligned with the row.**

- [ ] **Step 9.1: Write the failing tests.**

Append to `tests/web/test_routes/test_open_positions_expand.py` (extend existing file — TestClient + Trade-seeding patterns already in scope):

```python
def test_open_positions_row_renders_sector_industry(seeded_db, monkeypatch):
    """Open positions row renders Sector + Industry from trade.sector / .industry.
    Sentinel 'OP-Sector-T9' / 'OP-Industry-T9' guards against default-string
    masks."""
    from fastapi.testclient import TestClient
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, sector="OP-Sector-T9", industry="OP-Industry-T9",
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "OP-Sector-T9" in body
    assert "OP-Industry-T9" in body


def test_open_positions_expanded_colspan_matches_new_row_cell_count():
    """colspan in open_positions_expanded.html.j2 must match the cell count
    in open_positions_row.html.j2 — was 8, becomes 10 with sector + industry."""
    from pathlib import Path
    expanded = Path("swing/web/templates/partials/open_positions_expanded.html.j2").read_text(encoding="utf-8")
    assert 'colspan="10"' in expanded, (
        "colspan must be 10 to match open_positions_row.html.j2's 10 cells "
        "(Ticker, Entry date, Entry price, Shares, Current stop, Last, "
        "Sector, Industry, Advisory, Actions)."
    )
```

- [ ] **Step 9.2: Run the failing tests.**

```bash
python -m pytest tests/web/test_routes/test_open_positions_expand.py -v -k "sector_industry or colspan_matches"
```

Expected: FAIL.

- [ ] **Step 9.3: Update `open_positions_row.html.j2`.**

In `swing/web/templates/partials/open_positions_row.html.j2`, add Sector and Industry cells AFTER the Last (price) cell and BEFORE the Advisory cell:

```html+jinja
<tr id="open-position-{{ row.trade.id }}"
    hx-get="/trades/open/{{ row.trade.id }}/expand"
    hx-target="closest tr"
    hx-swap="outerHTML"
    hx-headers='{"HX-Request": "true"}'>
  <td>{{ row.trade.ticker }}</td>
  <td>{{ row.trade.entry_date }}</td>
  <td>${{ '%.2f' | format(row.trade.entry_price) }}</td>
  <td>{{ row.remaining_shares }} / {{ row.trade.initial_shares }}</td>
  <td>${{ '%.2f' | format(row.trade.current_stop) }}</td>
  <td>
    {% if row.price_snapshot %}
      ${{ '%.2f' | format(row.price_snapshot.price) }}
      {% if row.price_snapshot.is_stale %}<span class="stale">(stale)</span>{% endif %}
    {% else %}—{% endif %}
  </td>
  <td>{{ row.trade.sector or "—" }}</td>
  <td>{{ row.trade.industry or "—" }}</td>
  <td>
    {% for s in row.advisories %}
      <div>{{ s.message }}</div>
    {% endfor %}
  </td>
  <td class="row-actions">
    <button onclick="event.stopPropagation()"
            hx-get="/trades/{{ row.trade.id }}/exit/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Exit</button>
    <button onclick="event.stopPropagation()"
            hx-get="/trades/{{ row.trade.id }}/stop/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Adjust stop</button>
  </td>
</tr>
```

- [ ] **Step 9.4: Update colspan in `open_positions_expanded.html.j2`.**

Edit `swing/web/templates/partials/open_positions_expanded.html.j2` line 20:

```html+jinja
  <td colspan="10">
```

(Was `colspan="8"` — add 2 for sector + industry.)

Also update the docstring comment block at the top of `open_positions_expanded.html.j2` to reflect the new cell count: `"Colspan must match the compact open_positions_row.html.j2 cell count (10 cells: Ticker, Entry date, Entry price, Shares, Current stop, Last, Sector, Industry, Advisory, Actions)."`

- [ ] **Step 9.5: Update parent-table `<thead>`.**

Edit `swing/web/templates/partials/open_positions.html.j2:8` (parent header file confirmed by Codex R1 Minor 2). Add `<th>Sector</th>` + `<th>Industry</th>` between `<th>Last</th>` and `<th>Advisory</th>`:

```html+jinja
<thead>
  <tr>
    <th>Ticker</th>
    <th>Entry date</th>
    <th>Entry price</th>
    <th>Shares</th>
    <th>Current stop</th>
    <th>Last</th>
    <th>Sector</th>
    <th>Industry</th>
    <th>Advisory</th>
    <th>Actions</th>
  </tr>
</thead>
```

> **Verification.** Read `swing/web/templates/partials/open_positions.html.j2` first to confirm the existing `<thead>` shape; if it differs (e.g., wraps under a different selector or uses a class-only `<tr>`), match the existing structure exactly.

- [ ] **Step 9.6: Run tests + full suite.**

```bash
python -m pytest tests/web/test_routes/test_open_positions_expand.py -v -k "sector_industry or colspan_matches"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

- [ ] **Step 9.7: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 9'
```

```bash
git add swing/web/templates/partials/open_positions_row.html.j2 \
        swing/web/templates/partials/open_positions.html.j2 \
        swing/web/templates/partials/open_positions_expanded.html.j2 \
        tests/web/test_routes/test_open_positions_expand.py
git commit -m "feat(web): Task 9 — open positions row displays sector + industry

Reads from row.trade.sector / .industry directly (Task 4 already populated
these fields on Trade across all SELECT paths). Two new <td> cells between
Last and Advisory; matching <th> additions in the parent open_positions.html.j2;
colspan in open_positions_expanded bumped 8 → 10 to match.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 9'\` empty pre-commit.
"
```

---

## Task 10: Final verification

**Files:** none (verification only).

- [ ] **Step 10.1: Full fast-suite run + delta count.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -5
```

Expected: `>= 1218 passed, 1 skipped, 8 deselected` (1203 baseline + at least 15 new tests across Tasks 1 (×1), 2 (×2), 3 (×3), 4 (×2), 5 (×2), 6 (×4), 7 (×2), 8 (×2), 9 (×2); actual count varies; no decreases).

- [ ] **Step 10.2: Subject-only grep audit — exactly one task implementation per task.**

```bash
for n in 1 2 3 4 5 6 7 8 9; do
  echo "=== Task $n ==="
  git log -E --pretty='%s' --grep="^[a-z]+\([a-z]+\): Task $n( |—|$)"
done
```

Expected: each task has EXACTLY ONE matching commit (plus optional Codex review-fix commits, which use `Codex R<n>` not `Task <n>` in the subject line).

- [ ] **Step 10.3: Schema integrity verification.**

```bash
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"
```

Expected: `12`.

```bash
python -c "
import sqlite3, tempfile, pathlib
from swing.data.db import ensure_schema
with tempfile.TemporaryDirectory() as td:
    conn = ensure_schema(pathlib.Path(td) / 'swing.db')
    cands = {r[1]: r for r in conn.execute('PRAGMA table_info(candidates)')}
    trades = {r[1]: r for r in conn.execute('PRAGMA table_info(trades)')}
    assert 'sector' in cands and 'industry' in cands
    assert 'sector' in trades and 'industry' in trades
    print('OK: schema 12 with sector + industry on candidates + trades')
"
```

- [ ] **Step 10.4: ruff check.**

```bash
ruff check swing/ 2>&1 | tail -5
```

Expected: 91 errors (baseline; no new violations introduced by this dispatch).

- [ ] **Step 10.5: TOML-shadowing audit (per 2026-04-28 lesson).**

```bash
grep -rn "sector\|industry" swing.config.toml swing/config.py
```

Expected: zero matches. Sector/industry are data fields, not config defaults; no toml override surface. If any match surfaces, investigate before declaring the dispatch complete.

- [ ] **Step 10.6: Production-state verification (post-merge, operator-paced).**

After all tasks land on `main`, the operator runs `swing db-migrate` then `swing pipeline run` against a fresh Finviz CSV; verifies via SQL that candidates have non-empty sector/industry on the new run. THIS STEP IS OPERATOR-PACED and is NOT part of the implementer's deliverable; surface in the executing-plans return report as a manual-verification gate.

---

## Self-Review

**Spec coverage** (per dispatch brief §3 + §6):
- A. Schema migration 0012 — Task 1.
- B. Pipeline ingestion — Tasks 2 + 3.
- C. Trade entry capture (frozen-at-entry) — Tasks 4 + 5 + 6 + 7.
- D. Display surfaces — Tasks 6 (trade entry form), 8 (watchlist expansion), 9 (open positions). **Hyp-recs row expansion DEFERRED** to the future hyp-recs trade-prep expansion brainstorm per brief §1's explicit "downstream concern — out of scope for THIS dispatch" framing (R1 Codex Major 3 RESOLVED). 3 of 4 V1 display surfaces shipping; the 4th (hyp-recs) consumes the data plumbed by Tasks 2 + 4 when the future brainstorm ships.
- Test count baseline pinned: 1203 fast tests at HEAD `ba2b252`.

**Placeholder scan:** All `NotImplementedError` skeletons removed in R1 fix pass (Codex R1 Major 1 RESOLVED). Every test task now contains concrete test code that exercises the discriminating-test discipline against real fixture patterns from the existing test tree.

**Type consistency:** `sector: str` / `industry: str` are consistent across `Candidate`, `Trade`, `EntryRequest`, `TradeEntryFormVM`. Default `""` everywhere. `HypothesisRecommendation` does NOT gain these fields in V1 — deferred with the hyp-recs display surface.

**Cross-surface anchor consistency (R1 Codex Major 4 RESOLVED).** Sector/industry candidate-row lookups in `build_entry_form_vm` (Task 6) and `trade_entry_cmd` (Task 7) use the canonical `latest_evaluation_run_id()` helper (`swing/web/view_models/dashboard.py:64-95`) — same anchor the dashboard candidates_by_ticker binding uses, and same anchor the existing CLI hypothesis pre-fill helper uses. No raw `pipeline_runs` SELECT bypasses the helper.

**Error-ticker semantics unambiguous (R1 Codex Major 5 RESOLVED).** Tickers in the finviz CSV (any bucket, including `error`) persist sector/industry FROM the CSV. Held-position tickers appended via `held_tickers` and NOT in the CSV persist empty strings. Test prose and implementation aligned on this rule.

**Migration safety:** Migration 0012 is `ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT ''` — additive, O(metadata), no historical row rewrite. No existing query filters on `sector IS NULL` (verified via `grep -rn "sector\|industry" swing/`). No FK introduced. No CHECK constraints (V1 trusts Finviz; no field-format invariants).

**Sort-neutrality verified:** sector/industry are decorative display fields ONLY. NOT included in `_sort_watchlist`, NOT included in hyp-recs prioritizer, NOT included in any other sort tuple. Per chart-pattern flag-v1 R1 M2 lesson: sort-neutrality is structurally guaranteed because the new fields never enter the existing sort tuple. Watchlist (Task 8) and open positions (Task 9) read from existing dataclass fields without disturbing any sort key.

**Base-layout 5-VM rule does NOT apply:** verified via `grep -n "sector\|industry" swing/web/templates/base.html.j2` returns zero matches.

**Open question for orchestrator triage:**
1. **Hyp-recs row expansion is deferred to the future expansion brainstorm.** Operator should confirm before executing-plans dispatch that this is the desired V1 scope (vs forcing column-based display now). The brief's §1 framing supports the deferral explicitly; this plan honors that framing.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`.**

This plan was authored under the `copowers:writing-plans` wrapper. Adversarial Codex review will follow per the wrapper's standard cycle (3-5 rounds typical, terminating at `NO_NEW_CRITICAL_MAJOR`). Open questions surfaced inline; no inline assumptions about the orchestrator's choice on the hyp-recs surface ambiguity.

Recommended execution mode after Codex sign-off: `superpowers:subagent-driven-development` per binding conventions (single-subagent dispatch + observable verification + 4-tier commit-message convention; ZERO-rogue track record across 8 phases).
