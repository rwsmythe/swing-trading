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

**Open question for orchestrator triage (NOT a re-litigation; this is an internal contradiction in the dispatch brief):** Brief §2.2 names "Hyp-recs row expansion (HTMX-expanded panel under `partials/`)" as a V1 display surface. **No such expansion exists yet.** `partials/hypothesis_recommendations.html.j2` is a flat read-only `<table>` with 7 columns and no `hx-get`/expand wiring; the corresponding HTMX expansion mechanism is the deliverable of the queued **hyp-recs trade-prep expansion brainstorm** (`docs/phase3e-todo.md` 2026-04-28 §"hyp-recs trade-prep expansion"). The brief itself acknowledges this conflict in §1: *"Hyp-recs expansion will consume sector as a pre-captured field; that's a downstream concern — out of scope for THIS dispatch."* This plan resolves the contradiction by adding sector + industry as **two new columns** in the existing flat hyp-recs table (Task 9). This delivers the operator-visible data on the hyp-recs surface NOW; when the future expansion brainstorm ships, it will move them from columns to the expanded panel as a structural relocation, not new data plumbing. Surfaced in the writing-plans return report so the orchestrator can confirm the interpretation before executing-plans dispatches.

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
- `swing/web/view_models/dashboard.py` — `HypothesisRecommendation` gains `sector: str` + `industry: str`; `active_recommendations` builder reads from `candidates_by_ticker` (Task 9).
- `swing/web/templates/partials/hypothesis_recommendations.html.j2` — add Sector and Industry `<th>` headers + `<td>` cells (Task 9).
- `swing/web/view_models/watchlist.py` — `WatchlistExpandedVM.candidate` already carries the candidate; sector/industry are accessed via `expanded.candidate.sector` / `.industry` directly. **No VM-field addition needed.** (Task 8 — template-only change.)
- `swing/web/templates/partials/watchlist_expanded.html.j2` — add Sector + Industry rows when `expanded.candidate` is present (Task 8).
- `swing/web/templates/partials/open_positions_row.html.j2` — add Sector + Industry cells (consumed via `row.trade.sector` / `.industry`); update `colspan` in `open_positions_expanded.html.j2` to match the new cell count (Task 10).

**Test files:**
- `tests/data/test_migrations.py` — migration 0012 schema-shape tests (Task 1).
- `tests/data/test_candidates.py` — Candidate insert+select roundtrip (Task 2).
- `tests/data/test_trades.py` — Trade insert+select roundtrip (Task 4).
- `tests/pipeline/test_step_evaluate.py` (or co-located) — sector/industry flow from finviz CSV → candidate rows (Task 3).
- `tests/trades/test_entry.py` — `record_entry` passes sector/industry through AS-IS (Task 5).
- `tests/cli/test_trade_entry.py` — CLI auto-resolves from candidate; empty-string fallback when no candidate (Task 7).
- `tests/web/test_routes/test_trades_entry.py` — POST flow + soft_warn_confirm round-trip (Task 6).
- `tests/web/test_view_models/test_trade_entry_form_vm.py` — VM populated from candidate (Task 6).
- `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` — HypothesisRecommendation populated (Task 9).
- `tests/web/test_templates/test_hypothesis_recommendations_partial.py` (or content equivalent) — partial renders columns (Task 9).
- `tests/web/test_templates/test_watchlist_expanded.py` — partial renders sector/industry rows (Task 8).
- `tests/web/test_templates/test_open_positions_row.py` — partial renders sector/industry cells (Task 10).

> **Test-path verification.** During each task, the implementer must `Glob`/`Grep` the test file path before creating it — existing test layout may use slightly different filenames. Use the closest existing file under the matching directory; if none exists, create with the path shown above.

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
- Test: `tests/data/test_migrations.py` (or `tests/data/test_db.py` — verify which exists; if both, prefer `test_migrations.py`).

**Discriminating-test sanity-check.** The migration test asserts the four new columns exist by name AND by NOT NULL DEFAULT '' constraint shape AND by non-NULL value on a fresh INSERT that omits the columns (defaults must apply). If the migration only added the columns without the DEFAULT clause, the third assertion fails (omitted columns persist as NULL on INSERT, violating NOT NULL). **Would this test fail if the implementation never actually applied the migration? Yes — `_current_version(conn)` returns 11 (or 0), and the assertion `cursor.execute("PRAGMA table_info(candidates)")` returns no row matching `name='sector'`, both of which fail explicitly.**

- [ ] **Step 1.1: Verify current state.**

```bash
grep -n "EXPECTED_SCHEMA_VERSION" swing/data/db.py
ls swing/data/migrations/ | tail -5
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1'
```

Expected: `EXPECTED_SCHEMA_VERSION = 11`; `0011_pipeline_chart_targets_source_taxonomy.sql` is the last migration; grep returns empty.

- [ ] **Step 1.2: Write the failing migration tests.**

Append to `tests/data/test_migrations.py` (or the analogous file — verify path first):

```python
def test_migration_0012_adds_sector_industry_to_candidates_and_trades(tmp_path):
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

If the existing test module uses a different fixture/helper (e.g., `seeded_db`, `db_conn`), inline this test verbatim — do NOT call shared helpers that may set the schema_version differently. Verify by running the existing tests in that file with `pytest tests/data/test_migrations.py -v` first to confirm baseline.

- [ ] **Step 1.3: Run the failing test.**

```bash
python -m pytest tests/data/test_migrations.py::test_migration_0012_adds_sector_industry_to_candidates_and_trades -v
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
python -m pytest tests/data/test_migrations.py::test_migration_0012_adds_sector_industry_to_candidates_and_trades -v
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
git add swing/data/migrations/0012_sector_industry.sql swing/data/db.py tests/data/test_migrations.py
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
- Test: `tests/data/test_candidates.py` (verify path; create if absent).

**Discriminating-test sanity-check.** Test inserts a Candidate with sector="Healthcare" + industry="Biotechnology" (specific to this test — no other test fixture should use these values), then reads back via `fetch_candidates_for_run` and asserts both fields are populated with those EXACT strings (`assert c.sector == "Healthcare"` not `assert c.sector`). If `insert_candidates` silently dropped the sector/industry params or `_row_to_candidate` ignored those columns, the test would observe `""` (the schema default) on read-back, failing the assertion. **Would this test fail if the implementation never actually called the new code? Yes — without modifying `insert_candidates`'s SQL the column values are not bound, default `""` is persisted, and the read-back equality check fails.**

- [ ] **Step 2.1: Write the failing test.**

Append to `tests/data/test_candidates.py` (or create if absent):

```python
def test_candidate_sector_industry_roundtrip(tmp_path):
    """A Candidate with sector + industry inserted via insert_candidates is
    fetched back with both fields populated AS-IS. Distinct values
    ("Healthcare" / "Biotechnology") chosen to discriminate against any
    test fixture default that might mask a passthrough bug."""
    from swing.data.db import ensure_schema
    from swing.data.models import Candidate, EvaluationRun
    from swing.data.repos.candidates import (
        fetch_candidates_for_run,
        insert_candidates,
        insert_evaluation_run,
    )

    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
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
python -m pytest tests/data/test_candidates.py::test_candidate_sector_industry_roundtrip tests/data/test_candidates.py::test_candidate_default_sector_industry_empty -v
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
python -m pytest tests/data/test_candidates.py::test_candidate_default_sector_industry_empty -v
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
python -m pytest tests/data/test_candidates.py::test_candidate_sector_industry_roundtrip -v
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
git add swing/data/models.py swing/data/repos/candidates.py tests/data/test_candidates.py
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
- Test: `tests/pipeline/test_step_evaluate_sector_industry.py` (or extend an existing `_step_evaluate` test file).

**Discriminating-test sanity-check.** Test seeds a Finviz CSV with rows where ticker → (sector, industry) mapping is INVERTED relative to alphabetical: e.g., ticker `AAPL` → `Healthcare / Pharmaceuticals`, ticker `ZZZB` → `Energy / Oil & Gas E&P`. Asserts that `fetch_candidates_for_run`'s output rows have the EXACT mapping the CSV specified (not a swapped or default mapping). **Inversion-against-alphabetical** prevents the Phase 4 R2 ticker-symmetry vacuousness pattern: if the implementation accidentally bound sectors by row INDEX (i.e., post-evaluate_batch's alphabetically-sorted output) instead of by TICKER, the test catches it. **Would this test fail if the implementation never actually called the new code? Yes — without the post-`evaluate_batch` plumbing, candidate rows persist `sector=""` (schema default) and the assertion `c.sector == "Healthcare"` fails for AAPL.**

Also asserts: held-position tickers (added via `held_tickers`, may not be in finviz) persist empty strings (graceful degradation per brief §5.8). ETF-blocklist tickers persist empty strings. Error-tickers (OHLCV fetch failed) persist empty strings.

- [ ] **Step 3.1: Write the failing test.**

Place in `tests/pipeline/test_step_evaluate_sector_industry.py` (or extend the closest existing pipeline test file under `tests/pipeline/`):

```python
def test_step_evaluate_persists_sector_industry_from_finviz_csv(tmp_path, monkeypatch):
    """_step_evaluate plumbs Sector + Industry from the Finviz CSV into the
    candidate row. Inversion test: AAPL → Healthcare / Pharmaceuticals;
    ZZZB → Energy / Oil & Gas E&P. Bug class guarded: binding by row-index
    instead of by ticker would yield AAPL → Energy / Oil & Gas E&P.
    """
    # The exact harness pattern depends on existing tests for _step_evaluate;
    # this is a SKELETON — implementer adapts to the project's pipeline-test
    # fixture pattern (likely `tests/pipeline/test_runner.py` or similar).
    # Required scaffolding:
    #   1. Build a Finviz CSV with REQUIRED_COLUMNS at tmp_path / "finviz.csv".
    #      Two ticker rows: AAPL with Sector='Healthcare', Industry='Pharmaceuticals';
    #      ZZZB with Sector='Energy', Industry='Oil & Gas E&P'.
    #   2. Stub OHLCV fetcher to return enough bars so both pass the bars_needed
    #      filter (or fail-fast and route to error_tickers — the assertion below
    #      handles both branches).
    #   3. Build a minimal Config + universe + lease, run _step_evaluate.
    #   4. Open the resulting DB, fetch candidates, assert the mapping.
    #
    # Implementer: see tests/pipeline/test_runner.py (or wherever _step_evaluate
    # is exercised) for the existing fixture pattern; copy that pattern verbatim.
    # If no _step_evaluate test fixture exists yet, this task ALSO commits the
    # fixture (single commit per TDD red-green discipline).
    raise NotImplementedError(
        "Adapt to existing test scaffolding; see implementation notes."
    )


def test_step_evaluate_holds_persist_empty_sector_industry(tmp_path, monkeypatch):
    """Open-trade tickers that get appended via held_tickers but are absent
    from the finviz CSV persist sector='' and industry='' (graceful
    degradation; matches the hypothesis_label free-text behavior).
    Same harness pattern as the previous test."""
    raise NotImplementedError(
        "Adapt to existing test scaffolding; see implementation notes."
    )


def test_step_evaluate_error_tickers_persist_empty_sector_industry(tmp_path, monkeypatch):
    """Tickers in finviz CSV whose OHLCV fetch failed land in error_tickers
    (synthesized Candidate with bucket='error'). They DO have sector/industry
    in the CSV — assert the synthesized error candidate carries those values
    rather than empty strings (consistent with the 'data is in CSV' framing)."""
    raise NotImplementedError(
        "Adapt to existing test scaffolding; see implementation notes."
    )
```

> **Test-skeleton replacement guidance.** The plan keeps these tests as skeletons because the existing `_step_evaluate` test scaffolding is project-specific (lease fixture, fetcher stub, config). The implementer's first action in Task 3 is to find the existing `_step_evaluate` test file via `grep -rn "_step_evaluate\|def _step_evaluate" tests/pipeline/` and adapt the harness. If no existing test exercises `_step_evaluate` end-to-end (in which case the cheapest route is unit-test the post-`evaluate_batch` plumbing in isolation), use `dataclasses.replace` directly: construct a list of `Candidate` instances, build the same sector/industry dict from a stub finviz_df, apply the replace pattern, assert the mapping. **Either form satisfies the discriminating-test discipline above; the inversion-against-alphabetical assertion is what matters.**

- [ ] **Step 3.2: Run the failing test.**

```bash
python -m pytest tests/pipeline/test_step_evaluate_sector_industry.py -v
```

Expected: FAIL with NotImplementedError (skeleton) OR with sector/industry mismatch (after harness is adapted).

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
python -m pytest tests/pipeline/test_step_evaluate_sector_industry.py -v
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
git add swing/pipeline/runner.py tests/pipeline/test_step_evaluate_sector_industry.py
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
- Test: `tests/data/test_trades.py` (verify path; create if absent).

**Discriminating-test sanity-check.** Test inserts a Trade with `sector="Energy"` + `industry="Oil & Gas E&P"`, reads back via `get_trade`, `list_open_trades`, `list_closed_trades` (after closing), `find_any_open_trade`, and `find_open_trade_by_match` — asserts ALL FIVE SELECT paths return the EXACT values set on insert. The 5 SELECT paths all hand-roll their column lists (no shared SELECT helper). If any one path's SELECT or `_row_to_trade` mapping is missed, the test for that path observes empty strings (schema default after migration 0012) and the assertion fails. **Would this test fail if the implementation never actually called the new code? Yes — five distinct read paths each fail individually if their SELECT list isn't extended.**

- [ ] **Step 4.1: Write the failing test.**

Append to `tests/data/test_trades.py`:

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
python -m pytest tests/data/test_trades.py::test_trade_sector_industry_roundtrip_all_select_paths tests/data/test_trades.py::test_trade_default_sector_industry_empty -v
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
python -m pytest tests/data/test_trades.py::test_trade_default_sector_industry_empty -v
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
python -m pytest tests/data/test_trades.py::test_trade_sector_industry_roundtrip_all_select_paths -v
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
git add swing/data/models.py swing/data/repos/trades.py tests/data/test_trades.py
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
- Test: `tests/trades/test_entry.py` (verify path; create if absent).

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
- Test: `tests/web/test_view_models/test_trade_entry_form_vm.py` and `tests/web/test_routes/test_trades_entry.py` (verify paths; create if absent).

**Discriminating-test sanity-check.** Test for VM populates the candidate row's sector/industry to specific test-only values (`"Sector-T6-A"` / `"Industry-T6-A"`) and asserts the constructed VM exposes those exact values. Test for the POST route submits a multipart form with hidden `sector="Sector-T6-B"` and `industry="Industry-T6-B"`; asserts the persisted Trade row carries those values. The Test-prefixed sentinel values guarantee NO production code path defaults to them — if the field plumbing is broken, the persisted value diverges from the sentinel and the assertion fails. **Would these tests fail if the implementation never actually called the new code? Yes — VM construction without the candidate-row-lookup branch returns `sector=""`; POST handler that ignores the form fields constructs EntryRequest with default `""`; both fail the assertion.**

Test for soft_warn_confirm round-trip: first POST hits soft_warn cap, route returns the confirm fragment, fragment's hidden inputs MUST include `sector` and `industry` with the values from the original POST; second POST with `force=true` from the confirm fragment persists the original sector/industry on the Trade.

- [ ] **Step 6.1: Write the failing tests.**

In `tests/web/test_view_models/test_trade_entry_form_vm.py` (or extend the existing test file):

```python
def test_build_entry_form_vm_populates_sector_industry_from_candidate(tmp_path, monkeypatch):
    """build_entry_form_vm reads the candidate row by ticker against the
    latest completed pipeline_run's evaluation_run_id and exposes
    sector/industry on the VM. Test-prefixed sentinel values guarantee
    no fallback path masks the bug."""
    # Implementer: adapt to existing TradeEntryFormVM test fixture pattern.
    # Key shape:
    #   1. Seed pipeline_runs (state='complete', evaluation_run_id set).
    #   2. Seed candidates row with ticker='ZZZG', sector='Sector-T6-A',
    #      industry='Industry-T6-A'.
    #   3. Seed watchlist row for 'ZZZG' so build_entry_form_vm finds wl_entry.
    #   4. Construct a stub PriceCache + Config; call build_entry_form_vm.
    #   5. Assert vm.sector == 'Sector-T6-A' and vm.industry == 'Industry-T6-A'.
    raise NotImplementedError("Adapt to existing fixture pattern.")


def test_build_entry_form_vm_no_candidate_for_ticker_defaults_empty(tmp_path):
    """When no candidate row exists for the entered ticker (e.g., ticker
    rotated out of finviz), the VM exposes empty strings — graceful
    degradation per brief §5.8."""
    raise NotImplementedError("Adapt to existing fixture pattern.")
```

In `tests/web/test_routes/test_trades_entry.py`:

```python
def test_entry_post_persists_sector_industry_from_form(tmp_path, ...):
    """POST /trades/entry with hidden sector + industry form fields persists
    them on the Trade row AS-IS (snapshot-at-entry-surface ToCToU)."""
    raise NotImplementedError("Adapt to existing fixture pattern.")


def test_entry_post_soft_warn_confirm_preserves_sector_industry(tmp_path, ...):
    """First POST that trips the soft_warn cap returns the soft_warn_confirm
    fragment carrying sector + industry as hidden inputs. Second POST
    (force=true) persists those values on the Trade. Mirrors the chart_pattern
    snapshot preservation pattern (Phase 5 Codex R1 Major 2)."""
    raise NotImplementedError("Adapt to existing fixture pattern.")
```

> **Adapt to existing test scaffolding.** Look for `tests/web/test_routes/test_trade_entry*.py` or any file containing `entry_post` test patterns. Use the same `TestClient(app)` + `with TestClient(app) as client:` pattern (CLAUDE.md gotcha: lifespan-required for `app.state.price_fetch_executor`). The chart_pattern soft_warn_confirm tests (Phase 5) are the closest precedent.

- [ ] **Step 6.2: Run the failing tests.**

```bash
python -m pytest tests/web/test_view_models/test_trade_entry_form_vm.py tests/web/test_routes/test_trades_entry.py -v -k "sector_industry or soft_warn_confirm_preserves"
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

In `build_entry_form_vm`, extend the read-snapshot block to also fetch sector/industry from the candidate row by ticker (against the SAME pipeline_run resolution already performed for chart-pattern). Concrete change inside the `with conn:` block:

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
            # NEW: Reuse the same row to also fetch the candidate's sector
            # + industry via the FK-backed evaluation_run_id when present.
            pipeline_eval_id = (
                pipeline_eval_row[1] if pipeline_eval_row else None
            )
            cand_sector = ""
            cand_industry = ""
            if pipeline_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (pipeline_eval_id, ticker),
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

> **Why query directly here instead of `fetch_candidates_for_run` + iterate?** `fetch_candidates_for_run` returns the full Candidate (criteria + all metric columns) and triggers an N+1-style criteria SELECT per candidate. For the entry-form VM we need only sector + industry — a single 2-column SELECT bound to `(evaluation_run_id, ticker)` is the minimum query. **Verify** by checking the candidates schema's index coverage in `swing/data/migrations/0001_*.sql` (or wherever `candidates` is created); there should be an index on `evaluation_run_id` (else the query is a table scan, but at the scale of 5-200 candidates per run that's harmless). If the schema lacks the index, NOTE — do not add one in this dispatch (out of scope; surface as follow-up).

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
python -m pytest tests/web/test_view_models/test_trade_entry_form_vm.py tests/web/test_routes/test_trades_entry.py -v -k "sector_industry or soft_warn_confirm_preserves"
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
        tests/web/test_view_models/test_trade_entry_form_vm.py \
        tests/web/test_routes/test_trades_entry.py
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
- Test: `tests/cli/test_trade_entry.py` (verify path; create if absent).

**Discriminating-test sanity-check.** Test invokes `swing trade entry` against a DB seeded with a candidate row that has sector="CLI-Sector-T7" / industry="CLI-Industry-T7"; asserts the persisted Trade carries those exact values. Second test uses a ticker NOT in the candidate table; asserts the persisted Trade has empty strings. Test-prefixed sentinels prevent any default-string mask. **Would this test fail if the implementation never actually called the new code? Yes — without the candidate-row lookup the EntryRequest gets default `""`, and the persisted trade row's sector/industry don't match the seeded sentinels.**

- [ ] **Step 7.1: Write the failing tests.**

```python
def test_trade_entry_cli_resolves_sector_industry_from_candidate(tmp_path, ...):
    """`swing trade entry` reads sector + industry from the latest candidate
    row by ticker (FK-backed pipeline_run path); persists AS-IS via record_entry."""
    raise NotImplementedError("Adapt to existing CLI test fixture pattern.")


def test_trade_entry_cli_no_candidate_persists_empty(tmp_path, ...):
    """When no candidate row exists for the entered ticker, `swing trade entry`
    persists sector='' + industry='' (graceful degradation; matches
    hypothesis_label free-text behavior). Pipeline-bypass / off-watchlist
    trade entries are explicitly supported per brief §5.8."""
    raise NotImplementedError("Adapt to existing CLI test fixture pattern.")
```

> **Adapt to existing CLI test fixture pattern.** `tests/cli/test_trade_entry.py` (or whichever existing file uses `CliRunner` / `click.testing`) has the precedent for invoking `swing trade entry` against a temp DB. Look for tests that already exercise hypothesis pre-fill or chart_pattern resolution; mirror that fixture.

- [ ] **Step 7.2: Run the failing tests.**

```bash
python -m pytest tests/cli/test_trade_entry.py -v -k "sector_industry"
```

Expected: FAIL.

- [ ] **Step 7.3: Implement candidate-row lookup in `trade_entry_cmd`.**

In `swing/cli.py`, modify `trade_entry_cmd`'s body. Right after the existing `pipeline_eval_row = conn.execute(...)` query (around line 412), add a parallel query for sector/industry:

```python
        # Phase 5 spec §3.6 ToCToU fix — chart-pattern cache resolved once
        # at command start (existing). Migration 0012 — sector + industry
        # resolved from the same candidate row in the same read snapshot.
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
            # NEW: candidate-row lookup for sector/industry against the
            # FK-backed evaluation_run_id when present. Single 2-column
            # SELECT — no fallback to legacy heuristic resolver, because
            # this is the BEST-KNOWN view of metadata at command time;
            # legacy NULL-FK pipeline_runs predate migration 0012 anyway.
            pipeline_eval_id = pipeline_eval_row[1]
            if pipeline_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (pipeline_eval_id, ticker.upper()),
                ).fetchone()
                if cand_row is not None:
                    cli_sector = cand_row[0] or ""
                    cli_industry = cand_row[1] or ""
```

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
python -m pytest tests/cli/test_trade_entry.py -v -k "sector_industry"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 7.5: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 7'
```

```bash
git add swing/cli.py tests/cli/test_trade_entry.py
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
- Test: `tests/web/test_templates/test_watchlist_expanded.py` (verify path; create if absent).

**Discriminating-test sanity-check.** Test renders the partial with a `WatchlistExpandedVM` whose `candidate.sector="WL-Sector-T8"` + `candidate.industry="WL-Industry-T8"`; asserts the rendered HTML contains the EXACT string `"WL-Sector-T8"` (substring match against the test-prefixed sentinel). Second test renders with `candidate=None` and asserts the rendered HTML contains NEITHER `Sector:` heading NOR `Industry:` heading (the rows are gated on `candidate` being present, mirroring the existing Trend Template / VCP grids gating). **Would these tests fail if the implementation never actually called the new code? Yes — without the new template lines the rendered HTML omits `WL-Sector-T8` entirely; the substring assertion fails. The candidate=None test guards against unconditional rendering.**

- [ ] **Step 8.1: Write the failing test.**

```python
def test_watchlist_expanded_renders_sector_industry_when_candidate_present(...):
    """Partial renders Sector and Industry rows when expanded.candidate is set,
    using the exact test-only values from candidate.sector / .industry."""
    # Construct a WatchlistExpandedVM with a Candidate carrying
    # sector='WL-Sector-T8' + industry='WL-Industry-T8'; render the partial
    # via Jinja; assert both strings appear in the rendered HTML.
    raise NotImplementedError("Adapt to existing template-test pattern.")


def test_watchlist_expanded_no_sector_industry_when_candidate_none(...):
    """Partial does NOT emit Sector or Industry rows when expanded.candidate
    is None (e.g., off-pipeline watchlist entry)."""
    raise NotImplementedError("Adapt to existing template-test pattern.")
```

> **Adapt to existing template-test pattern.** Look for `tests/web/test_templates/` or any test that renders a partial via `app.state.templates.get_template(...).render(...)`. The chart_pattern partial test from Phase 5 is the closest precedent.

- [ ] **Step 8.2: Run the failing test.**

```bash
python -m pytest tests/web/test_templates/test_watchlist_expanded.py -v -k "sector_industry"
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
python -m pytest tests/web/test_templates/test_watchlist_expanded.py -v -k "sector_industry"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

- [ ] **Step 8.5: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 8'
```

```bash
git add swing/web/templates/partials/watchlist_expanded.html.j2 \
        tests/web/test_templates/test_watchlist_expanded.py
git commit -m "feat(web): Task 8 — watchlist expansion renders sector + industry rows

Reads from expanded.candidate.sector / .industry (no new VM field — Candidate
already carries them post Task 2). Rows gated inside the existing
{% if expanded.candidate %} guard so off-pipeline watchlist entries
(candidate=None) render gracefully without the headings.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 8'\` empty pre-commit.
"
```

---

## Task 9: Hypothesis recommendations — display sector + industry as new columns

**Files:**
- Modify: `swing/web/view_models/dashboard.py:154-185` (`HypothesisRecommendation`), `swing/web/view_models/dashboard.py:552-581` (`active_recommendations` builder)
- Modify: `swing/web/templates/partials/hypothesis_recommendations.html.j2`
- Test: `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` and equivalent template test (verify paths; create if absent).

> **Surface interpretation note (re-stated from header).** Brief §2.2 names "Hyp-recs row expansion (HTMX-expanded panel under `partials/`)" but no such expansion exists yet — the expansion mechanism is the deliverable of the queued hyp-recs trade-prep expansion brainstorm. This plan ships sector + industry as **new columns** in the existing flat hyp-recs table. Surfaced for orchestrator confirmation before executing-plans dispatch.

**Discriminating-test sanity-check.** Test seeds a candidate with `sector="HR-Sector-T9"` / `industry="HR-Industry-T9"` for ticker `ZZZH` and verifies that the corresponding `HypothesisRecommendation` VM exposes those exact values (sentinel + substring assert). Template test renders the partial with a HypothesisRecommendation carrying the same sentinel values; asserts the rendered HTML's `<td>` cells contain the strings. Second template test renders with empty-string sector/industry; asserts the rendered HTML contains a placeholder `—` (or empty cell — whichever the template chooses) so the column structure stays intact. **Would these tests fail if the implementation never actually called the new code? Yes — without the VM-builder change, `HypothesisRecommendation.sector == ""`; without the template change, the `<td>` cells don't render the new columns at all (and column count drops from 9 to 7 → also a structural regression).**

- [ ] **Step 9.1: Write the failing tests.**

In `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py`:

```python
def test_active_recommendations_carries_sector_industry_from_candidate(...):
    """active_recommendations builder reads sector + industry from
    candidates_by_ticker[r.candidate_ticker] and exposes them on
    HypothesisRecommendation."""
    raise NotImplementedError("Adapt to existing dashboard-test fixture pattern.")


def test_hypothesis_recommendation_default_sector_industry_empty():
    """HypothesisRecommendation constructed without sector/industry uses ''."""
    from swing.web.view_models.dashboard import HypothesisRecommendation
    r = HypothesisRecommendation(
        ticker="X", current_price=None, hypothesis_id=1,
        hypothesis_name="hy", hypothesis_progress_n=0,
        hypothesis_progress_target=10, tripwire_fired=False,
        tripwire_reason=None, suggested_label="lbl",
    )
    assert r.sector == ""
    assert r.industry == ""
```

In a template-rendering test (`tests/web/test_templates/test_hypothesis_recommendations_partial.py` or content-equivalent under existing dashboard route tests):

```python
def test_hyp_recs_partial_renders_sector_industry_columns(...):
    """The partial renders Sector and Industry as additional <th> + <td>
    columns. Test-prefixed sentinel values guard against default-string
    masks. Column count check: 9 <th> headers (was 7 pre-this-task)."""
    raise NotImplementedError("Adapt to existing template-test pattern.")
```

- [ ] **Step 9.2: Run the failing tests.**

```bash
python -m pytest tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py tests/web/test_templates/test_hypothesis_recommendations_partial.py -v -k "sector_industry"
```

Expected: FAIL.

- [ ] **Step 9.3: Add fields to HypothesisRecommendation.**

In `swing/web/view_models/dashboard.py`, modify `HypothesisRecommendation`:

```python
@dataclass(frozen=True)
class HypothesisRecommendation:
    """One row of the dashboard's "Hypothesis-driven recommendations" panel."""
    ticker: str
    current_price: float | None
    hypothesis_id: int
    hypothesis_name: str
    hypothesis_progress_n: int
    hypothesis_progress_target: int
    tripwire_fired: bool
    tripwire_reason: str | None
    suggested_label: str
    pivot_price: float | None = None
    # Migration 0012 — sector/industry sourced from candidates_by_ticker
    # at build time. Decorative DISPLAY-ONLY — does NOT enter any sort
    # or prioritization tuple (sort-neutrality structurally guaranteed).
    sector: str = ""
    industry: str = ""
```

- [ ] **Step 9.4: Update the active_recommendations builder.**

In `swing/web/view_models/dashboard.py`, modify the `HypothesisRecommendation(...)` construction inside the `active_recommendations = tuple(...)` comprehension:

```python
    active_recommendations = tuple(
        HypothesisRecommendation(
            ticker=r.candidate_ticker,
            current_price=(
                prices[r.candidate_ticker].price
                if r.candidate_ticker in prices else None
            ),
            pivot_price=(
                candidates_by_ticker[r.candidate_ticker].pivot
                if r.candidate_ticker in candidates_by_ticker else None
            ),
            sector=(
                candidates_by_ticker[r.candidate_ticker].sector
                if r.candidate_ticker in candidates_by_ticker else ""
            ),
            industry=(
                candidates_by_ticker[r.candidate_ticker].industry
                if r.candidate_ticker in candidates_by_ticker else ""
            ),
            hypothesis_id=r.hypothesis_id,
            hypothesis_name=r.hypothesis_name,
            # ... unchanged ...
        )
        for r in top_recommendations
    )
```

- [ ] **Step 9.5: Update the template.**

In `swing/web/templates/partials/hypothesis_recommendations.html.j2`, add Sector and Industry header cells + data cells. Insert AFTER the `<th>Suggested label</th>` row's closing `</tr>` is wrong — insert at end of `<thead>` row to match the `<td>` order:

```html+jinja
<section id="hypothesis-recommendations" class="hypothesis-recommendations">
  <h2>Hypothesis-driven recommendations</h2>
  <table class="hypothesis-recommendations">
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Price</th>
        <th>Pivot</th>
        <th>Sector</th>
        <th>Industry</th>
        <th>Hypothesis</th>
        <th>Progress</th>
        <th>Tripwire</th>
        <th>Suggested label</th>
      </tr>
    </thead>
    <tbody>
      {% for rec in vm.active_recommendations %}
        <tr {% if rec.tripwire_fired %}class="tripwire-fired"{% endif %}>
          <td>{{ rec.ticker }}</td>
          <td>{% if rec.current_price is not none %}${{ "%.2f"|format(rec.current_price) }}{% else %}—{% endif %}</td>
          <td>{% if rec.pivot_price is not none %}${{ "%.2f"|format(rec.pivot_price) }}{% else %}—{% endif %}</td>
          <td>{{ rec.sector or "—" }}</td>
          <td>{{ rec.industry or "—" }}</td>
          <td>{{ rec.hypothesis_name }}</td>
          <td>{{ rec.hypothesis_progress_n }} / {{ rec.hypothesis_progress_target }}</td>
          <td>{% if rec.tripwire_fired %}<strong>FIRED</strong>: {{ rec.tripwire_reason or "" }}{% else %}—{% endif %}</td>
          <td title="{{ rec.suggested_label }}">{{ rec.suggested_label[:60] }}{% if rec.suggested_label|length > 60 %}…{% endif %}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</section>
```

> **Column ordering rationale.** Sector + Industry placed AFTER Pivot and BEFORE Hypothesis to keep `(Ticker, Price, Pivot)` together as the price-anchored block, then `(Sector, Industry)` as a classification block, then `(Hypothesis, Progress, Tripwire, Suggested label)` as the recommendation block. **Operator-confirm at executing-plans time:** if the orchestrator prefers Sector+Industry at the END of the row (least disruption to existing column order memory), the swap is a 4-line change.

- [ ] **Step 9.6: Run the tests + full suite.**

```bash
python -m pytest tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py tests/web/test_templates/test_hypothesis_recommendations_partial.py -v -k "sector_industry"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

- [ ] **Step 9.7: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 9'
```

```bash
git add swing/web/view_models/dashboard.py \
        swing/web/templates/partials/hypothesis_recommendations.html.j2 \
        tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py \
        tests/web/test_templates/test_hypothesis_recommendations_partial.py
git commit -m "feat(web): Task 9 — hyp-recs displays sector + industry as new columns

HypothesisRecommendation gains sector + industry fields (DISPLAY-ONLY — does
NOT enter any sort/prioritization tuple). Builder reads from candidates_by_ticker.
Template adds 2 new columns between Pivot and Hypothesis.

Brief §2.2 names 'hyp-recs row expansion' as the V1 surface but no such
expansion partial exists; column-based display is the V1 interpretation
flagged for orchestrator confirmation. Future hyp-recs trade-prep expansion
brainstorm will move these to the expanded panel as a structural
relocation; the data plumbing is now in place.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 9'\` empty pre-commit.
"
```

---

## Task 10: Open positions row — display sector + industry

**Files:**
- Modify: `swing/web/templates/partials/open_positions_row.html.j2`
- Modify: `swing/web/templates/partials/open_positions_expanded.html.j2:20` (update `colspan` to match new cell count)
- Test: `tests/web/test_templates/test_open_positions_row.py` (verify path).

**Discriminating-test sanity-check.** Test renders the partial with an `OpenPositionsRowVM` whose `trade.sector="OP-Sector-T10"` + `trade.industry="OP-Industry-T10"`; asserts the rendered HTML contains both strings. Test also asserts the colspan in `open_positions_expanded.html.j2` matches the new column count (was 8; +2 cells → 10). **Would these tests fail if the implementation never actually called the new code? Yes — without the new `<td>` cells the rendered HTML omits both sentinel strings; without the colspan update the chart-display fragment is structurally misaligned with the row.**

- [ ] **Step 10.1: Write the failing tests.**

```python
def test_open_positions_row_renders_sector_industry(...):
    """Partial renders Sector + Industry cells from row.trade.sector / .industry."""
    raise NotImplementedError("Adapt to existing template-test pattern.")


def test_open_positions_expanded_colspan_matches_new_row_cell_count():
    """colspan in open_positions_expanded.html.j2 matches the cell count
    in open_positions_row.html.j2 — was 8, becomes 10 with sector + industry."""
    from pathlib import Path
    expanded = Path("swing/web/templates/partials/open_positions_expanded.html.j2").read_text()
    assert 'colspan="10"' in expanded, (
        "colspan must be 10 to match open_positions_row.html.j2's 10 cells "
        "(Ticker, Entry date, Entry price, Shares, Current stop, Last, "
        "Sector, Industry, Advisory, Actions)."
    )
```

- [ ] **Step 10.2: Run the failing tests.**

```bash
python -m pytest tests/web/test_templates/test_open_positions_row.py -v -k "sector_industry or colspan"
```

Expected: FAIL.

- [ ] **Step 10.3: Update `open_positions_row.html.j2`.**

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

- [ ] **Step 10.4: Update colspan in `open_positions_expanded.html.j2`.**

Edit `swing/web/templates/partials/open_positions_expanded.html.j2` line 20:

```html+jinja
  <td colspan="10">
```

(Was `colspan="8"` — add 2 for sector + industry.)

Also update the docstring comment block at the top of `open_positions_expanded.html.j2` to reflect the new cell count: `"Colspan must match the compact open_positions_row.html.j2 cell count (10 cells: Ticker, Entry date, Entry price, Shares, Current stop, Last, Sector, Industry, Advisory, Actions)."`

- [ ] **Step 10.5: Check parent table column header.**

Search for the parent template that renders the open-positions `<table>` header (`<thead>` with `<th>`s):

```bash
grep -rn "Open Positions\|open_positions_row\|<th>Ticker" swing/web/templates/ | head -10
```

If the parent template (likely `partials/open_positions.html.j2` or `dashboard.html.j2`) hand-rolls the `<thead>`, ADD `<th>Sector</th>` and `<th>Industry</th>` between `<th>Last</th>` and `<th>Advisory</th>` in that file too. Failure to do so produces a header/data column mismatch that the eye notices but tests may not (HTML allows mismatch).

- [ ] **Step 10.6: Run tests + full suite.**

```bash
python -m pytest tests/web/test_templates/test_open_positions_row.py -v -k "sector_industry or colspan"
python -m pytest -m "not slow" -q 2>&1 | tail -10
```

- [ ] **Step 10.7: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 10'
```

```bash
git add swing/web/templates/partials/open_positions_row.html.j2 \
        swing/web/templates/partials/open_positions_expanded.html.j2 \
        tests/web/test_templates/test_open_positions_row.py
# Plus the parent-table file if Step 10.5 surfaced one.
git commit -m "feat(web): Task 10 — open positions row displays sector + industry

Reads from row.trade.sector / .industry directly (Task 4 already populated
these fields on Trade across all SELECT paths). Two new <td> cells between
Last and Advisory; colspan in open_positions_expanded bumped 8 → 10 to
match. Parent-table <thead> updated if applicable.

Observable verification: \`git log -E --grep='^[a-z]+\\([a-z]+\\): Task 10'\` empty pre-commit.
"
```

---

## Task 11: Final verification

**Files:** none (verification only).

- [ ] **Step 11.1: Full fast-suite run + delta count.**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -5
```

Expected: `>= 1216 passed, 1 skipped, 8 deselected` (1203 baseline + at least 13 new tests across Tasks 1, 2, 3 (×3), 4 (×2), 5 (×2), 6 (×4), 7 (×2), 8 (×2), 9 (×3), 10 (×2) — actual count varies based on per-task fixture skeleton expansion; no decreases).

- [ ] **Step 11.2: Subject-only grep audit — exactly one task implementation per task.**

```bash
for n in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== Task $n ==="
  git log -E --pretty='%s' --grep="^[a-z]+\([a-z]+\): Task $n( |—|$)"
done
```

Expected: each task has EXACTLY ONE matching commit (plus optional Codex review-fix commits, which use `Codex R<n>` not `Task <n>` in the subject line).

- [ ] **Step 11.3: Schema integrity verification.**

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

- [ ] **Step 11.4: ruff check.**

```bash
ruff check swing/ 2>&1 | tail -5
```

Expected: 91 errors (baseline; no new violations introduced by this dispatch).

- [ ] **Step 11.5: TOML-shadowing audit (per 2026-04-28 lesson).**

```bash
grep -rn "sector\|industry" swing.config.toml swing/config.py
```

Expected: zero matches. Sector/industry are data fields, not config defaults; no toml override surface. If any match surfaces, investigate before declaring the dispatch complete.

- [ ] **Step 11.6: Production-state verification (post-merge, operator-paced).**

After all tasks land on `main`, the operator runs `swing db-migrate` then `swing pipeline run` against a fresh Finviz CSV; verifies via SQL that candidates have non-empty sector/industry on the new run. THIS STEP IS OPERATOR-PACED and is NOT part of the implementer's deliverable; surface in the executing-plans return report as a manual-verification gate.

---

## Self-Review

**Spec coverage** (per dispatch brief §3 + §6):
- A. Schema migration 0012 — Task 1.
- B. Pipeline ingestion — Tasks 2 + 3.
- C. Trade entry capture (frozen-at-entry) — Tasks 4 + 5 + 6 + 7.
- D. Display surfaces (4 surfaces) — Tasks 6 (trade entry form), 8 (watchlist), 9 (hyp-recs), 10 (open positions). All four surfaces covered.
- Test count baseline pinned: 1203 fast tests at HEAD `ba2b252`.

**Placeholder scan:** Tasks 3, 6, 7, 8, 9, 10 contain `NotImplementedError` skeletons for tests. These are deliberate — the project's existing test-fixture patterns are non-trivial (lease fixtures for `_step_evaluate`; lifespan-bound TestClient for web routes; CliRunner for CLI; Jinja-context construction for templates). Each skeleton includes a sentence telling the implementer where to find the existing fixture pattern. The plan does NOT skip the test code; it scopes it as fixture-adapter work that must complete before the failing test runs. **Acceptable per the spec rationale** — the production code in each task is fully specified and the skeleton's sentinel-value discipline is enforced.

**Type consistency:** `sector: str` / `industry: str` are consistent across `Candidate`, `Trade`, `EntryRequest`, `TradeEntryFormVM`, `HypothesisRecommendation`. Default `""` everywhere. No type drift.

**Open question for orchestrator triage** (re-stated):
1. Hyp-recs surface — column-based vs deferred-to-future-expansion. Plan currently implements column-based.

If the orchestrator confirms Option A (column-based), Task 9 ships as written. If the orchestrator selects "defer all hyp-recs display until the hyp-recs trade-prep expansion brainstorm," delete Task 9 (data is still captured on candidates and the future expansion brainstorm consumes it directly from `candidates_by_ticker` — no data plumbing rework). Either choice ships sector/industry on the OTHER three V1 surfaces (watchlist expansion, trade entry, open positions) without modification.

**Migration safety:** Migration 0012 is `ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT ''` — additive, O(metadata), no historical row rewrite. No existing query filters on `sector IS NULL` (verified via `grep -rn "sector\|industry" swing/`). No FK introduced. No CHECK constraints (V1 trusts Finviz; no field-format invariants).

**Sort-neutrality verified:** Hyp-recs (Task 9), watchlist (Task 8), open positions (Task 10) — sector/industry are decorative display fields ONLY. NOT included in `_sort_watchlist`, NOT included in hyp-recs prioritizer, NOT included in any other sort tuple. Per chart-pattern flag-v1 R1 M2 lesson: sort-neutrality is structurally guaranteed because the new fields never enter the existing sort tuple.

**Base-layout 5-VM rule does NOT apply:** verified via `grep -n "sector\|industry" swing/web/templates/base.html.j2` returns zero matches.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`.**

This plan was authored under the `copowers:writing-plans` wrapper. Adversarial Codex review will follow per the wrapper's standard cycle (3-5 rounds typical, terminating at `NO_NEW_CRITICAL_MAJOR`). Open questions surfaced inline; no inline assumptions about the orchestrator's choice on the hyp-recs surface ambiguity.

Recommended execution mode after Codex sign-off: `superpowers:subagent-driven-development` per binding conventions (single-subagent dispatch + observable verification + 4-tier commit-message convention; ZERO-rogue track record across 8 phases).
