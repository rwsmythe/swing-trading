# Chart-Scope Policy V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing chart-scope policy (A+ candidates + top-N near-trigger watchlist by proximity-only sort) with a three-tier policy (`aplus > open_position > tag_aware_top_n`), tighten the chart-scope-resolver drift race via a `PipelineRunBinding` pinned at request entry, and migrate the persistence taxonomy via SQLite migration `0011`.

**Architecture:** Single phase, ~10 tasks. The schema migration lands first so the new source values can be persisted. A `PipelineRunBinding` dataclass + `latest_completed_pipeline_run(conn)` helper become the single read-source for "which pipeline_run does this request bind to?"; `resolve_chart_scope` accepts the binding as a required keyword argument and never re-reads `pipeline_runs`. `_step_charts` rebuilds its target list as a precedence-ordered union of three tiers with ticker canonicalization and a shared `_tag_aware_sort_key` helper imported from `swing.web.view_models.dashboard`. Stop-line rendering becomes conditional on `stop > 0`. Wall-time monitoring lands as a soft (60s WARN) / hard (120s ERROR) log signal with a deterministic log-capture test.

**Tech Stack:** Python 3.11+ (3.14 on dev box), SQLite (migration `0011`), FastAPI + HTMX + Jinja2, mplfinance, click CLI.

**Spec:** `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md` (NO_NEW_CRITICAL_MAJOR after 4 adversarial Codex rounds; all 11 majors resolved via spec edits). Spec is settled — this plan executes it, not redesigns it.

**Brief:** `docs/chart-scope-policy-v2-writing-plans-brief.md`.

**Baseline:** `main` at HEAD when the executing-plans dispatch starts (currently `63036cf`); `python -m pytest -m "not slow" -q` green at 1145 tests; `schema_version = 10`.

**Phase isolation:** This plan modifies code under `swing/web/`, `swing/pipeline/`, `swing/data/migrations/`, `swing/config.py`, `swing/rendering/`. **Phase 2 carve-out:** the migration adds a SQL file under `swing/data/migrations/`; `swing/data/db.py:EXPECTED_SCHEMA_VERSION` bumps 10 → 11. Both are within the migration-cost amortization pattern established in chart-pattern flag-v1 Phase 2; no new repo-layer code under `swing/data/repos/` is touched. `swing/trades/` is NOT modified.

**No execution in this plan-drafting dispatch.** This file is the deliverable; per-task implementation is a future, separate `copowers:executing-plans` dispatch.

---

## Conventions for every task

- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change.
- **Commits:** Conventional Commits with task ID. Task implementation: `feat(area): Task N — <description>` or `feat(area): Task N (sub) — <description>` for in-task commits. Adversarial review-fix: `fix(area): Codex R<N> Major <M> — <description>`. Internal-Codex review-fix uses `(internal)` qualifier. NO Claude co-author footer. NO `--no-verify`. NO amending.
- **Subject-only ERE grep verification BEFORE each task implementation commit:** `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'`. The `-E` flag is required (BRE treats `+` as literal). For Codex-fix audit: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Codex R[0-9]'`.
- **Phase-end checkpoint:** `python -m pytest -m "not slow" -q` MUST be green before declaring the phase complete. Plan must NOT introduce new ruff violations beyond the CLAUDE.md-recorded baseline; run `ruff check swing/` after each phase and fix any phase-introduced issues before commit.
- **Spec cross-references:** every task header notes the spec section(s) it implements (e.g., "implements spec §A").
- **Discriminating-test discipline (per `feedback_regression_test_arithmetic` memory + Phase 4 + Bug 7 lessons):** every test produces a different outcome under post-fix code than under pre-fix code. Threshold-pair tests use ±epsilon around the boundary. Every test that asserts on a primary key must also temporarily disable the keyed-on element to confirm the test fails differently — verified empirically, not just on paper. Compounding-confound discipline: when alphabetical (or other deterministic-tiebreaker) ticker ordering coincides with the asserted-on key, INVERT the fixture so the bug-vs-correct outputs diverge on that exact case.
- **Synthetic-fixture mapping discipline (per Phase 1 lesson):** before threshold tests are committed, pull representative measurements from the fixture under known parameters and assert the expected values (e.g., `_flag_tags(by_ticker)` produces the tag tuples the test of `_step_charts` then asserts on). Otherwise threshold-pair tests are vacuous despite arithmetic that "should" distinguish.
- **FK-target seed discipline (per Phase 2 lesson):** when literal `pipeline_run_id` references appear in test bodies, seed a corresponding `pipeline_runs` row first OR use `_seed_pipeline_run` helper. PRAGMA foreign_keys=ON (project default) raises `IntegrityError` BEFORE any later check fires; tests asserting on later behavior need an existing FK target.
- **Reference-enumeration discipline (per Phase 1 lesson):** for ranking algorithms (the tag-aware composite sort) write parametrized tests that enumerate a representative input via the algorithm's helpers and assert the algorithm's verdict matches.
- **Manual visual verification (per Phase 6 + Tier-1 mathtext lessons):** any change that affects rendered chart output (stop-hline omission, title format change) requires a manual `Read` of a generated PNG before declaring the task done. String-equality on title strings is INSUFFICIENT.

---

# Phase 1 — Chart-scope policy v2

**Pre-conditions:** baseline fast suite green at HEAD; `schema_version = 10`; no in-flight migrations.

**Phase-end checkpoint:** all new tests green; `python -m pytest -m "not slow" -q` green; `ruff check swing/` shows no new violations beyond baseline; `schema_version = 11`; manual visual verification of one rendered PNG with `stop=0.0` confirms no stop hline appears.

**Spec sections:** §A (tier model + selection), §B (schema + persistence taxonomy), §C (resolver signature change + drift-race tightening), §D (configuration + rollout), §E (test plan).

---

### Task 1 — Migration `0011` (source-taxonomy expansion) + migration test

**Spec section:** §B.

**Goal:** Add `'open_position'` and `'tag_aware_top_n'` to the `pipeline_chart_targets.source` CHECK constraint via SQLite CREATE-COPY-DROP-RENAME, preserve all legacy `'near_proximity'` rows bit-identically, advance `schema_version` 10 → 11, and pin the schema-objects inventory invariant with a parametrized test.

**Files:**
- Create: `swing/data/migrations/0011_pipeline_chart_targets_source_taxonomy.sql`
- Modify: `swing/data/db.py` (constant: `EXPECTED_SCHEMA_VERSION` 10 → 11)
- Create: `tests/data/test_migration_0011.py`

- [ ] **Step 1: Pre-write inventory verification (manual; document in commit body)**

Run against a current production-shape DB (use `~/swing-data/swing.db` if available; otherwise spin up a fresh DB via `swing db-migrate` to schema_version=10 then inspect):

```bash
python -c "import sqlite3; c = sqlite3.connect('<path>'); print(list(c.execute(\"SELECT name, type, sql FROM sqlite_master WHERE tbl_name = 'pipeline_chart_targets'\")))"
```

Expected output: 1 table definition + 1 index (`idx_pipeline_chart_targets_run`). NO triggers, NO additional indexes, NO views. If divergence is found, the migration SQL below MUST be expanded to recreate ALL discovered objects before the DROP TABLE step. **Document the inventory output in the commit body** as proof of compliance with spec §B "Schema-objects inventory verification."

- [ ] **Step 2: Write failing migration test**

```python
# tests/data/test_migration_0011.py
"""Migration 0011 + source-taxonomy expansion tests.

Spec §B. Verifies:
- schema_version advances 10 → 11.
- New CHECK constraint accepts all 4 source values.
- New CHECK constraint rejects an unknown source value.
- Existing rows preserved bit-identically (count, ticker, source, chart_status,
  pipeline_run_id all intact post-migration; this includes legacy 'near_proximity').
- Index `idx_pipeline_chart_targets_run` re-created on the new table.
- Pre-migration vs post-migration index/trigger/view inventory matches
  (no objects silently dropped on DROP TABLE).
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import connect, ensure_schema


def _migrate_to_v10(conn: sqlite3.Connection) -> None:
    """Apply migrations 0001-0010 to bring an empty conn to schema_version=10.

    Reuses ensure_schema with a temporarily-clamped EXPECTED_SCHEMA_VERSION
    so the test exercises the v10 → v11 transition specifically.
    """
    # ensure_schema applies all migrations up to EXPECTED_SCHEMA_VERSION; tests
    # use the default to v10, then we manually run 0011 below in the assertion.
    # NOTE: in production, ensure_schema sees v11 and applies 0011 in one shot.
    # Test isolates the transition by stopping at v10 first.
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    cursor.execute("INSERT INTO schema_version(version) VALUES (0)")
    # Apply migrations 0001-0010 in order from disk.
    from swing.data import migrations  # package; loader path resolution
    from pathlib import Path
    migs_dir = Path(migrations.__file__).parent
    for n in range(1, 11):
        sql_files = sorted(migs_dir.glob(f"{n:04d}_*.sql"))
        assert len(sql_files) == 1, f"expected exactly one migration {n:04d}, got {sql_files}"
        cursor.executescript(sql_files[0].read_text())
    conn.commit()


def _seed_pipeline_run(conn: sqlite3.Connection, *, run_id: int) -> None:
    """Seed pipeline_runs row with the FK target for chart_target inserts.

    Per Phase 2 lesson (FK-references): tests that insert into
    pipeline_chart_targets MUST seed pipeline_runs first, otherwise the
    schema-layer FK fires before any plan-asserted behavior.
    """
    conn.execute(
        """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                       data_asof_date, action_session_date)
           VALUES (?, '2026-04-01T09:00:00', '2026-04-01T09:30:00', 'complete',
                   '2026-04-01', '2026-04-02')""",
        (run_id,),
    )


def test_migration_0011_advances_schema_version(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        _migrate_to_v10(conn)
        # Pre-condition: schema is at v10.
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 10
        # Apply 0011.
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        # Post-condition: schema is at v11.
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 11
    finally:
        conn.close()


def test_migration_0011_accepts_all_four_source_values(tmp_path):
    """Post-migration, INSERT with each of the 4 valid source values succeeds.

    Discriminating verification: pre-migration the CHECK is
    `source IN ('aplus', 'near_proximity')`; an INSERT with 'open_position'
    raises `sqlite3.IntegrityError: CHECK constraint failed`. Post-migration
    all 4 inserts succeed. The test would fail with IntegrityError on the
    pre-migration schema.
    """
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        _migrate_to_v10(conn)
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        _seed_pipeline_run(conn, run_id=1)
        for source in ("aplus", "near_proximity", "open_position", "tag_aware_top_n"):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (?, ?, ?, 'pending')""",
                (1, f"T{source[:4].upper()}", source),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT source FROM pipeline_chart_targets ORDER BY id"
        ).fetchall()
        assert {r[0] for r in rows} == {
            "aplus", "near_proximity", "open_position", "tag_aware_top_n",
        }
    finally:
        conn.close()


def test_migration_0011_rejects_unknown_source_value(tmp_path):
    """Post-migration, an unknown source value raises IntegrityError.

    Discriminating verification: catches a regression where the CHECK is
    accidentally widened (e.g., dropped or replaced with a permissive list).
    """
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        _migrate_to_v10(conn)
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        _seed_pipeline_run(conn, run_id=1)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (1, 'TEST', 'random_source', 'pending')""",
            )
    finally:
        conn.close()


def test_migration_0011_preserves_existing_rows_bit_identically(tmp_path):
    """Pre-existing rows under each legacy source value survive the migration
    with all columns intact.

    Discriminating verification: pre-fix path (DROP TABLE without an
    INSERT-from-old) would zero the row count; this test fails with
    `assert 2 == 0` if the migration accidentally truncates.
    """
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        _migrate_to_v10(conn)
        _seed_pipeline_run(conn, run_id=42)
        # Insert a legacy 'aplus' and a legacy 'near_proximity' row.
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (42, 'AAPL', 'aplus', 'ok')""",
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (42, 'NVDA', 'near_proximity', 'ok')""",
        )
        conn.commit()
        # Apply 0011.
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        rows = conn.execute(
            """SELECT pipeline_run_id, ticker, source, chart_status
               FROM pipeline_chart_targets ORDER BY ticker"""
        ).fetchall()
        assert rows == [(42, "AAPL", "aplus", "ok"), (42, "NVDA", "near_proximity", "ok")]
    finally:
        conn.close()


def test_migration_0011_recreates_index(tmp_path):
    """The `idx_pipeline_chart_targets_run` index exists post-migration.

    Discriminating verification: pre-migration the index exists on the OLD
    table; SQLite drops indexes when the underlying table is dropped.
    A migration that forgets `CREATE INDEX` after `RENAME` leaves the index
    missing. The test fails with `assert 0 == 1` if the migration omits the
    re-creation step.
    """
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        _migrate_to_v10(conn)
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        idx_count = conn.execute(
            """SELECT COUNT(*) FROM sqlite_master
               WHERE type = 'index' AND name = 'idx_pipeline_chart_targets_run'""",
        ).fetchone()[0]
        assert idx_count == 1
    finally:
        conn.close()


def test_migration_0011_inventory_objects_match(tmp_path):
    """Pre- and post-migration, the same set of NON-TABLE objects exists on
    `pipeline_chart_targets`. Spec §B "schema-objects inventory verification."

    Discriminating verification: this test catches a regression where a
    side-migration in 0007-0010 added a trigger or extra index that the
    0011 migration silently drops. If the inventory test passes pre-migration
    with a single index AND post-migration with a single index (same name),
    no objects were lost.
    """
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    try:
        _migrate_to_v10(conn)
        pre_objects = sorted(conn.execute(
            """SELECT name, type FROM sqlite_master
               WHERE tbl_name = 'pipeline_chart_targets' AND type IN ('index', 'trigger', 'view')""",
        ).fetchall())
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        post_objects = sorted(conn.execute(
            """SELECT name, type FROM sqlite_master
               WHERE tbl_name = 'pipeline_chart_targets' AND type IN ('index', 'trigger', 'view')""",
        ).fetchall())
        assert pre_objects == post_objects, (
            f"inventory drift: pre={pre_objects} post={post_objects}; "
            "migration must recreate ALL non-table objects after RENAME"
        )
    finally:
        conn.close()
```

- [ ] **Step 3: Run tests to see RED**

```bash
python -m pytest tests/data/test_migration_0011.py -v
```

Expected: 6 tests fail. Most fail with `FileNotFoundError` reading the missing migration SQL; the bit-identical-preservation test additionally proves a pre-fix path that drops without copy would zero rows.

- [ ] **Step 4: Write the migration SQL**

`swing/data/migrations/0011_pipeline_chart_targets_source_taxonomy.sql`:

```sql
-- Migration 0011: chart_targets source taxonomy expansion for chart-scope policy v2.
--
-- Adds 'open_position' and 'tag_aware_top_n' to the source CHECK constraint.
-- Retains 'near_proximity' for legacy rows from pipeline runs prior to this
-- migration (no backfill — historical accuracy preserved per audit-trail discipline).
--
-- After this migration, _step_charts writes 'tag_aware_top_n' for the watchlist
-- tier (never 'near_proximity'). The 'near_proximity' value is read-only legacy.

CREATE TABLE pipeline_chart_targets_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'aplus',
        'near_proximity',
        'open_position',
        'tag_aware_top_n'
    )),
    chart_status TEXT NOT NULL CHECK (chart_status IN ('ok', 'fetcher_failed', 'too_few_bars', 'pending')),
    UNIQUE (pipeline_run_id, ticker)
);

INSERT INTO pipeline_chart_targets_new (id, pipeline_run_id, ticker, source, chart_status)
SELECT id, pipeline_run_id, ticker, source, chart_status
FROM pipeline_chart_targets;

DROP TABLE pipeline_chart_targets;
ALTER TABLE pipeline_chart_targets_new RENAME TO pipeline_chart_targets;

CREATE INDEX idx_pipeline_chart_targets_run ON pipeline_chart_targets(pipeline_run_id);

UPDATE schema_version SET version = 11;
```

- [ ] **Step 5: Bump `EXPECTED_SCHEMA_VERSION`**

In `swing/data/db.py`, change the constant from `10` to `11`. Locate via `grep -n EXPECTED_SCHEMA_VERSION swing/data/db.py`.

- [ ] **Step 6: Run tests to see GREEN**

```bash
python -m pytest tests/data/test_migration_0011.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Run full fast suite to verify no regressions**

```bash
python -m pytest -m "not slow" -q
```

Expected: prior 1145 + 6 new = 1151 tests passing (count is approximate; trust pytest output per CLAUDE.md test-count-drift gotcha).

- [ ] **Step 8: Commit**

```bash
git add swing/data/migrations/0011_pipeline_chart_targets_source_taxonomy.sql swing/data/db.py tests/data/test_migration_0011.py
git commit -m "feat(data): Task 1 — migration 0011 chart_targets source taxonomy + tests"
```

**Acceptance:**
- All 6 migration tests PASS.
- Full fast suite GREEN (no regressions).
- `schema_version` advances 10 → 11.
- Legacy `'near_proximity'` rows preserved bit-identically.
- Inventory test confirms no objects dropped on rename.

**Adversarial-review watch items:**
- **Inventory verification was performed against the actual production DB schema** (Step 1 commit body) — not assumed from migration-file inspection alone. Codex R1 Major 6 is the source of this requirement; reviewer must confirm the commit body documents the verification.
- **`_seed_pipeline_run` helper is used everywhere a `pipeline_run_id` is referenced in test bodies.** Phase 2 lesson: PRAGMA foreign_keys=ON fires schema-layer FK errors before any later assertion. The helper has been threaded through all 6 tests; reviewer must confirm no literal `pipeline_run_id=N` appears without a prior seed.
- **`ensure_schema` upgrade-path test (later phases of this plan or future migrations).** Spec doesn't require, but a reviewer may flag: does the current `ensure_schema` flow auto-apply 0011 on next CLI launch? Yes — by raising `EXPECTED_SCHEMA_VERSION`, every read connection sees the migration applied lazily on `connect()`. Per existing precedent in migrations 0007–0010.
- **Codex may flag the inventory test as "this only catches what was already known to be missing."** Defense: the test is the spec's own invariant; future side-migrations could add an index or trigger and this test catches the silent drop.

---

### Task 2 — `PipelineRunBinding` dataclass + `latest_completed_pipeline_run` helper

**Spec section:** §C ("Resolver signature change + drift-race tightening").

**Goal:** Introduce `PipelineRunBinding` (frozen dataclass with 5 fields) and `latest_completed_pipeline_run(conn) -> PipelineRunBinding | None` as the single read-source for "which pipeline_run does this request bind to?". The helper uses `ORDER BY finished_ts DESC, id DESC LIMIT 1` (Codex R1 Minor 1 tiebreaker) and constructs the dataclass via named arguments (Codex R1 Minor 2 column-order safety).

**Files:**
- Modify: `swing/web/chart_scope.py`
- Modify: `tests/web/test_chart_scope.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_chart_scope.py — append (file already exists per project audit)

from swing.web.chart_scope import (
    PipelineRunBinding,
    latest_completed_pipeline_run,
)


def test_latest_completed_pipeline_run_returns_none_on_empty_db(seeded_db):
    """No completed runs → helper returns None.

    Discriminating verification: pre-fix code (no helper exists) raises
    ImportError. Post-fix the helper returns None. Asserting on None
    distinguishes from "raised some error" failure mode.
    """
    # seeded_db fixture omits any pipeline_runs by default — we'll wipe to be sure.
    with seeded_db as conn:
        conn.execute("DELETE FROM pipeline_runs")
        conn.commit()
        assert latest_completed_pipeline_run(conn) is None


def test_latest_completed_pipeline_run_returns_binding_with_all_fields(seeded_db):
    """Helper populates all 5 fields from the latest completed run.

    Discriminating verification: each field's value is checked against the
    seeded data; if the helper SELECTed the wrong column or omitted a field,
    the assertion fails on the specific mismatch.
    """
    with seeded_db as conn:
        conn.execute("DELETE FROM pipeline_runs")
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (10, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                       'complete', '2026-04-01', '2026-04-02', 'ok', 7)""",
        )
        conn.commit()
        binding = latest_completed_pipeline_run(conn)
        assert binding is not None
        assert binding.run_id == 10
        assert binding.finished_ts == "2026-04-01T09:30:00"
        assert binding.data_asof_date == "2026-04-01"
        assert binding.charts_status == "ok"
        assert binding.evaluation_run_id == 7


def test_latest_completed_pipeline_run_id_desc_tiebreaker(seeded_db):
    """When two completed runs share `finished_ts`, helper picks the higher id.

    Discriminating verification: pre-fix `ORDER BY finished_ts DESC LIMIT 1`
    relies on SQLite's natural-row-ordering for ties — non-deterministic.
    Post-fix `ORDER BY finished_ts DESC, id DESC LIMIT 1` deterministically
    picks the higher id. Codex R1 Minor 1.

    Compounding-confound discipline: ids are seeded in non-monotonic order
    (5 then 12 then 3) so a "natural row order" lookup would NOT pick id=12;
    the test would fail with id=3 or id=5 if the tiebreaker is missing.
    """
    with seeded_db as conn:
        conn.execute("DELETE FROM pipeline_runs")
        # Insert in non-monotonic order to defeat natural-row-order coincidence.
        for run_id in (5, 12, 3):
            conn.execute(
                """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                               data_asof_date, action_session_date,
                                               charts_status, evaluation_run_id)
                   VALUES (?, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                           'complete', '2026-04-01', '2026-04-02', 'ok', NULL)""",
                (run_id,),
            )
        conn.commit()
        binding = latest_completed_pipeline_run(conn)
        assert binding is not None
        assert binding.run_id == 12, (
            f"expected id-DESC tiebreaker to pick 12, got {binding.run_id}; "
            "regression: missing `id DESC` in ORDER BY"
        )


def test_latest_completed_pipeline_run_skips_in_progress_runs(seeded_db):
    """Runs with state != 'complete' are excluded.

    Discriminating verification: a run with finished_ts='2026-04-02T09:30:00'
    state='running' would WIN the ORDER BY if the WHERE clause were dropped.
    The test asserts the older 'complete' run is selected, which fails if
    the state filter is missing.
    """
    with seeded_db as conn:
        conn.execute("DELETE FROM pipeline_runs")
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (1, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                       'complete', '2026-04-01', '2026-04-02', 'ok', NULL)""",
        )
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (2, '2026-04-02T09:00:00', '2026-04-02T09:30:00',
                       'running', '2026-04-02', '2026-04-03', NULL, NULL)""",
        )
        conn.commit()
        binding = latest_completed_pipeline_run(conn)
        assert binding is not None
        assert binding.run_id == 1, (
            f"expected the only 'complete' run (id=1) to win; got id={binding.run_id}; "
            "regression: WHERE state='complete' filter dropped"
        )


def test_pipeline_run_binding_is_frozen():
    """Dataclass is frozen (immutable). A snapshot pinned at request entry
    must not be mutable mid-handler.

    Discriminating verification: assigning to a field on a frozen dataclass
    raises FrozenInstanceError; on a non-frozen dataclass the assignment
    silently succeeds. Catches a regression that drops `frozen=True`.
    """
    import dataclasses
    binding = PipelineRunBinding(
        run_id=1, finished_ts="t", data_asof_date="d",
        charts_status="ok", evaluation_run_id=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        binding.run_id = 999  # type: ignore[misc]
```

(`seeded_db` and other fixtures already exist in `tests/web/conftest.py` per current project — verify by reading that file before applying. If a test fixture has a different shape, adapt the test body but preserve the discriminating assertions.)

- [ ] **Step 2: Run tests to see RED**

```bash
python -m pytest tests/web/test_chart_scope.py -k "latest_completed_pipeline_run or pipeline_run_binding" -v
```

Expected: 5 tests fail with `ImportError: cannot import name 'PipelineRunBinding'`.

- [ ] **Step 3: Implement the dataclass + helper**

In `swing/web/chart_scope.py`, add at top after the existing imports:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineRunBinding:
    """Pinned pipeline_run state for race-free chart-scope resolution.

    Computed once at request entry by `latest_completed_pipeline_run(conn)`
    and passed to `resolve_chart_scope` so all downstream reads bind to the
    SAME run, even if a new run completes mid-request. Closes the R2 Major
    drift race surfaced in chart-access UX dispatch (commit `f0d13e8`,
    2026-04-27).
    """
    run_id: int
    finished_ts: str
    data_asof_date: str
    charts_status: str | None
    evaluation_run_id: int | None


def latest_completed_pipeline_run(conn) -> PipelineRunBinding | None:
    """Single-read source of truth for 'which pipeline_run does this request bind to?'.

    Returns None when no completed runs exist. Caller MUST handle the None
    case before calling resolve_chart_scope.

    ORDER BY adds `id DESC` tiebreaker (Codex R1 Minor 1) — defends against
    second-precision finished_ts collisions on rapid runs. Constructs by
    named arg, not positional unpack (Codex R1 Minor 2) — defensive against
    future SELECT column-order drift.
    """
    row = conn.execute(
        """SELECT id, finished_ts, data_asof_date, charts_status, evaluation_run_id
           FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC, id DESC LIMIT 1""",
    ).fetchone()
    if row is None:
        return None
    run_id, finished_ts, data_asof_date, charts_status, evaluation_run_id = row
    return PipelineRunBinding(
        run_id=run_id,
        finished_ts=finished_ts,
        data_asof_date=data_asof_date,
        charts_status=charts_status,
        evaluation_run_id=evaluation_run_id,
    )
```

- [ ] **Step 4: Run tests to see GREEN**

```bash
python -m pytest tests/web/test_chart_scope.py -k "latest_completed_pipeline_run or pipeline_run_binding" -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/chart_scope.py tests/web/test_chart_scope.py
git commit -m "feat(web): Task 2 — PipelineRunBinding + latest_completed_pipeline_run helper"
```

**Acceptance:**
- 5 new tests pass.
- Full fast suite green.
- `PipelineRunBinding` is frozen.
- Tiebreaker `id DESC` deterministic; in-progress runs filtered.

**Adversarial-review watch items:**
- **Field-name drift between dataclass and SELECT.** Tests assert on each field individually; reviewer should confirm no field is silently dropped or renamed (e.g., `evaluation_run_id` vs `eval_run_id`).
- **Codex may flag the `seeded_db` fixture as unverified.** Address by reading `tests/web/conftest.py` at execution time and confirming the fixture's actual contract matches the seeded shape used in tests.
- **Pre-existing tests on `resolve_chart_scope` stay green.** This task adds the dataclass + helper but does NOT yet change the resolver signature; existing callers continue to work. Verify by running the full fast suite at the end of Step 4.

---

### Task 3 — `resolve_chart_scope` signature + 3-tier copy + 3 caller migrations

**Spec section:** §C.

**Goal:** Convert `resolve_chart_scope` from "resolver re-reads pipeline_runs" to "resolver requires `binding: PipelineRunBinding` keyword arg." Update `CHART_REASON_MESSAGES["out-of-scope"]` to reflect the three-tier model. Migrate all 3 caller sites (`charts.py` route, `open_positions_row.py` builder, `watchlist.py` expand builder) to pin the binding at request entry and pass it through. Add the binding-scope contract to the resolver docstring.

**This is the largest task in the plan.** It bundles 4 logical sub-changes (resolver + copy + 3 callers) because they MUST land together — the signature change is breaking and there's no backward-compat shim per spec §C "No backward-compat shim." Sub-step commits are kept distinct (`Task 3 (sub) — <description>`) so the audit trail is granular.

**Files:**
- Modify: `swing/web/chart_scope.py`
- Modify: `swing/web/routes/charts.py`
- Modify: `swing/web/view_models/open_positions_row.py`
- Modify: `swing/web/view_models/watchlist.py`
- Modify: `tests/web/test_chart_scope.py`
- Modify: `tests/web/test_routes/test_charts_route.py`
- Modify: `tests/web/test_routes/test_open_positions_expand.py` (or equivalent — verify path at execution time)
- Modify: `tests/web/test_view_models/` watchlist expand test file (verify path at execution time)

- [ ] **Step 1: Write failing tests for stale-binding race**

```python
# tests/web/test_chart_scope.py — append

def test_resolve_chart_scope_uses_binding_run_id_not_latest_select(seeded_db, tmp_path):
    """Pass a deliberately-stale binding (runN) while runN+1 has completed
    AFTER the binding was captured. Resolver must answer from runN's
    chart_targets, NOT runN+1's.

    This is the spec §E race-tightening contract pin. Pre-fix the resolver
    re-reads pipeline_runs and binds to runN+1; post-fix the resolver uses
    `binding.run_id` directly and binds to runN.

    Discriminating verification: runN's chart_targets include AAPL only.
    runN+1's chart_targets include MSFT only. We pass binding=runN, query
    for AAPL → expect None (in-scope). Pre-fix would re-SELECT, find
    runN+1 (latest), and AAPL would be 'out-of-scope' there.
    """
    with seeded_db as conn:
        # Seed runN with AAPL.
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (100, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                       'complete', '2026-04-01', '2026-04-02', 'ok', NULL)""",
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets (pipeline_run_id, ticker, source, chart_status)
               VALUES (100, 'AAPL', 'aplus', 'ok')""",
        )
        # Seed runN+1 with MSFT (newer, would win a re-SELECT).
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (101, '2026-04-02T09:00:00', '2026-04-02T09:30:00',
                       'complete', '2026-04-02', '2026-04-03', 'ok', NULL)""",
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets (pipeline_run_id, ticker, source, chart_status)
               VALUES (101, 'MSFT', 'aplus', 'ok')""",
        )
        conn.commit()
        # Place PNGs on disk for runN's date.
        charts_dir = tmp_path / "charts"
        (charts_dir / "2026-04-01").mkdir(parents=True)
        (charts_dir / "2026-04-01" / "AAPL.png").write_bytes(b"png-stub")
        # Pin to runN (the older run).
        binding = PipelineRunBinding(
            run_id=100, finished_ts="2026-04-01T09:30:00",
            data_asof_date="2026-04-01", charts_status="ok",
            evaluation_run_id=None,
        )
        # AAPL is in-scope ONLY for runN. Pre-fix resolver re-reads
        # pipeline_runs, picks runN+1, finds no AAPL row, returns
        # 'out-of-scope'. Post-fix resolver uses binding.run_id=100 and
        # finds AAPL.
        reason, message = resolve_chart_scope(
            conn, binding=binding, ticker="AAPL",
            charts_dir=charts_dir, chart_top_n_watch=10,
        )
        assert reason is None, (
            f"binding-stale resolver returned {reason!r} ({message!r}); "
            "regression: resolver re-read pipeline_runs and bound to runN+1 "
            "instead of honoring the passed binding"
        )


def test_resolve_chart_scope_requires_binding_kwarg():
    """Calling resolve_chart_scope WITHOUT binding raises TypeError.

    Discriminating verification: pre-fix the function accepts call without
    binding; post-fix it raises. Catches a regression where binding default
    is reintroduced (e.g., `binding: PipelineRunBinding | None = None`).
    """
    import inspect
    sig = inspect.signature(resolve_chart_scope)
    binding_param = sig.parameters.get("binding")
    assert binding_param is not None, "resolve_chart_scope must accept `binding`"
    assert binding_param.default is inspect.Parameter.empty, (
        "binding MUST be required (no default); spec §C"
    )
    assert binding_param.kind == inspect.Parameter.KEYWORD_ONLY, (
        "binding MUST be keyword-only; spec §C"
    )


def test_chart_reason_messages_out_of_scope_lists_three_tiers():
    """The operator-facing 'out-of-scope' message reflects the three-tier
    model post-migration: A+ candidates, open positions, tag-aware top-10.

    Discriminating verification: pre-fix message was 'A+ names + top
    near-trigger watchlist'; post-fix message references all three tiers.
    Substring-match on each tier name catches a regression that reverts
    the message OR drops a tier from the list.
    """
    msg = CHART_REASON_MESSAGES["out-of-scope"]
    assert "A+" in msg
    assert "open position" in msg.lower(), (
        "out-of-scope message must reference open-position tier"
    )
    assert "watchlist" in msg.lower(), (
        "out-of-scope message must reference watchlist tier"
    )
```

- [ ] **Step 2: Run tests to see RED**

```bash
python -m pytest tests/web/test_chart_scope.py -k "binding or out_of_scope_lists" -v
```

Expected: 3 tests fail. The race test fails with `TypeError: resolve_chart_scope() got an unexpected keyword argument 'binding'`. The signature test fails with the same. The message test fails because the existing string doesn't include "open position".

- [ ] **Step 3: Implement the new resolver signature + message update**

In `swing/web/chart_scope.py`:

(a) Update `CHART_REASON_MESSAGES["out-of-scope"]`:

```python
    "out-of-scope": (
        "Chart unavailable — this ticker isn't in today's charting scope "
        "(A+ candidates, open positions, and tag-aware watchlist top-10)."
    ),
```

(b) Replace `resolve_chart_scope` signature + body. The new signature requires `binding: PipelineRunBinding`; the body uses `binding.*` directly and removes the `SELECT ... FROM pipeline_runs` at the top:

```python
def resolve_chart_scope(
    conn: sqlite3.Connection,
    *,
    binding: PipelineRunBinding,
    ticker: str,
    charts_dir: Path,
    chart_top_n_watch: int,
) -> tuple[str | None, str | None]:
    """Race-free chart-scope resolver.

    Caller MUST pin the binding at request handler entry via
    `latest_completed_pipeline_run(conn)`. Resolver does NOT re-read
    `pipeline_runs` internally. Returns `(reason, message)` — both None when
    chart is available; otherwise reason ∈ {no-run, engine-missing,
    pipeline-failed, out-of-scope, insufficient-data, fetcher_failed,
    too_few_bars} and message is the operator-facing copy.

    Binding contract (spec §C "Binding scope definition"):
    - One binding per HTTP request handler.
    - The binding closes the intra-request race between the caller's read
      of `pipeline_runs.data_asof_date` (used to construct chart URLs) and
      the resolver's read of `pipeline_chart_targets`.
    - Multiple `resolve_chart_scope` calls within the same request handler
      MUST share the same binding instance to honor the contract. Future
      surfaces composing multiple resolutions in one handler MUST pin the
      binding ONCE at the top and pass it through to all calls.
    - Inter-request races (different HTTP requests from the same dashboard)
      are NOT closed by this contract; cross-request session pinning is
      out-of-scope (spec §C "What the binding does NOT close").
    """
    if binding.charts_status == "skipped":
        return "engine-missing", CHART_REASON_MESSAGES["engine-missing"]
    if binding.charts_status == "failed":
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]
    if binding.charts_status != "ok":
        return "pipeline-failed", CHART_REASON_MESSAGES["pipeline-failed"]

    # charts_status == 'ok'.
    if binding.evaluation_run_id is not None:
        return _resolve_via_chart_targets(
            conn, ticker=ticker, pipeline_run_id=binding.run_id,
            data_asof_date=binding.data_asof_date, charts_dir=charts_dir,
        )
    return _resolve_via_heuristic(
        conn, ticker=ticker, finished_ts=binding.finished_ts,
        data_asof_date=binding.data_asof_date, charts_dir=charts_dir,
        chart_top_n_watch=chart_top_n_watch,
    )
```

The internal `latest = conn.execute(...)` block at lines 102–110 of the current `chart_scope.py` is REMOVED. The `if latest is None: return "no-run", ...` branch is REMOVED — this case is now caller responsibility (caller checks `binding is None` and emits `no-run` itself; see Step 4 caller migrations below).

- [ ] **Step 4 (sub-commit a): Update charts route caller**

In `swing/web/routes/charts.py:39-83`, replace the current handler with:

```python
@router.get("/charts/{ticker}.png")
def charts_redirect(request: Request, ticker: str):
    ticker_upper = ticker.upper()
    cfg = request.app.state.cfg
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            binding = latest_completed_pipeline_run(conn)
            if binding is None:
                return HTMLResponse(
                    _unavailable_html(
                        ticker=ticker_upper,
                        message=CHART_REASON_MESSAGES["no-run"],
                    ),
                    status_code=404,
                )
            reason, message = resolve_chart_scope(
                conn, binding=binding, ticker=ticker_upper,
                charts_dir=cfg.paths.charts_dir,
                chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
            )
            if reason is None:
                # binding.data_asof_date is paired with binding.run_id —
                # SAME run that produced `reason=None`. No drift race.
                redirect_date = binding.data_asof_date
    finally:
        conn.close()

    if reason is None:
        return RedirectResponse(
            url=f"/charts/{redirect_date}/{ticker_upper}.png",
            status_code=303,
        )
    return HTMLResponse(
        _unavailable_html(
            ticker=ticker_upper,
            message=message or CHART_REASON_MESSAGES.get(reason, "Chart unavailable."),
        ),
        status_code=404,
    )
```

Add `from swing.web.chart_scope import latest_completed_pipeline_run` to the top of `charts.py`.

Run existing route tests:

```bash
python -m pytest tests/web/test_routes/test_charts_route.py -v
```

Expected: existing tests still pass (date-prefix URL build now uses `binding.data_asof_date` which is identical to the prior behavior because both read the same row).

Add a new test asserting the binding pinning:

```python
# tests/web/test_routes/test_charts_route.py — append

def test_charts_redirect_uses_binding_data_asof_not_re_read(
    seeded_db, charts_dir, app_client, monkeypatch,
):
    """Charts route uses binding's data_asof_date for the redirect URL,
    NOT a re-read of pipeline_runs.

    Setup: seed two completed runs with different data_asof_date values
    AND different chart_targets (runN has AAPL, runN+1 has MSFT only).
    Place a PNG on disk for runN's date. Monkeypatch
    `latest_completed_pipeline_run` to return runN's binding (simulating
    request-entry pinning).

    Discriminating verification: pre-fix the route SELECTs data_asof_date
    independently → wins runN+1's date AAPL.png does not exist there → 404.
    Post-fix the route uses binding.data_asof_date (runN's) → 303 redirect
    to /charts/<runN-date>/AAPL.png. The test asserts the 303 redirect
    target's date matches runN's, NOT runN+1's.
    """
    from swing.web.chart_scope import PipelineRunBinding

    # Seed runN (older, with AAPL).
    with seeded_db as conn:
        conn.execute("DELETE FROM pipeline_runs")
        conn.execute("DELETE FROM pipeline_chart_targets")
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (200, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                       'complete', '2026-04-01', '2026-04-02', 'ok', NULL)""",
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (200, 'AAPL', 'aplus', 'ok')""",
        )
        # Seed runN+1 (newer; would win a re-SELECT).
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id)
               VALUES (201, '2026-04-02T09:00:00', '2026-04-02T09:30:00',
                       'complete', '2026-04-02', '2026-04-03', 'ok', NULL)""",
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (201, 'MSFT', 'aplus', 'ok')""",
        )
        conn.commit()
    # Place PNG on disk for runN's date only.
    (charts_dir / "2026-04-01").mkdir(parents=True, exist_ok=True)
    (charts_dir / "2026-04-01" / "AAPL.png").write_bytes(b"png-stub")

    # Monkeypatch the helper to return runN's binding deterministically.
    runN_binding = PipelineRunBinding(
        run_id=200, finished_ts="2026-04-01T09:30:00",
        data_asof_date="2026-04-01", charts_status="ok",
        evaluation_run_id=None,
    )
    monkeypatch.setattr(
        "swing.web.routes.charts.latest_completed_pipeline_run",
        lambda conn: runN_binding,
    )

    response = app_client.get("/charts/AAPL.png", follow_redirects=False)
    assert response.status_code == 303, (
        f"expected 303 redirect; got {response.status_code} body={response.text[:200]}"
    )
    location = response.headers["location"]
    assert location == "/charts/2026-04-01/AAPL.png", (
        f"expected runN's date in redirect; got {location!r}; "
        "regression: route re-read pipeline_runs and used runN+1's date"
    )
```

(The exact fixture names `seeded_db`/`charts_dir`/`app_client` depend on `tests/web/conftest.py`; the implementer MUST verify each fixture exists or substitute the project's actual equivalents at execution time. The body above is concrete enough to fail informatively if fixtures are missing.)

Commit:

```bash
git add swing/web/routes/charts.py tests/web/test_routes/test_charts_route.py
git commit -m "feat(web): Task 3 (sub) — charts route binds to PipelineRunBinding"
```

- [ ] **Step 5 (sub-commit b): Update open-positions builder caller**

In `swing/web/view_models/open_positions_row.py:160-197`, replace `build_open_positions_expanded` with:

```python
def build_open_positions_expanded(
    *, conn: sqlite3.Connection, cfg: Config, trade_id: int,
) -> OpenPositionsExpandedVM | None:
    trade = get_trade(conn, trade_id)
    if trade is None or trade.status != "open":
        return None

    binding = latest_completed_pipeline_run(conn)
    if binding is None:
        # No completed runs — chart unavailable AND data_asof_date is None.
        return OpenPositionsExpandedVM(
            trade_id=trade.id, ticker=trade.ticker,
            data_asof_date=None,
            chart_reason="no-run",
            chart_reason_message=CHART_REASON_MESSAGES["no-run"],
        )

    chart_reason, chart_reason_message = resolve_chart_scope(
        conn, binding=binding, ticker=trade.ticker,
        charts_dir=cfg.paths.charts_dir,
        chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
    )
    return OpenPositionsExpandedVM(
        trade_id=trade.id, ticker=trade.ticker,
        data_asof_date=binding.data_asof_date,
        chart_reason=chart_reason,
        chart_reason_message=chart_reason_message,
    )
```

Add `from swing.web.chart_scope import CHART_REASON_MESSAGES, latest_completed_pipeline_run, resolve_chart_scope` to the imports (replacing the existing single-name `resolve_chart_scope` import).

Run existing tests:

```bash
python -m pytest tests/web/test_routes/test_open_positions_expand.py -v
```

Expected: existing tests still pass.

Commit:

```bash
git add swing/web/view_models/open_positions_row.py
git commit -m "feat(web): Task 3 (sub) — open-positions expand binds to PipelineRunBinding"
```

- [ ] **Step 6 (sub-commit c): Update watchlist expand builder caller**

In `swing/web/view_models/watchlist.py:227-300`, refactor `build_watchlist_expanded`. The current body has two reads against `pipeline_runs` (lines 243 and 251). Both go away; the binding becomes the single source. The `eval_run_id` linkage continues to use `evaluation_runs` as before but the pipeline-side anchor now comes from `binding.evaluation_run_id`:

```python
def build_watchlist_expanded(
    *, cfg: Config, cache: PriceCache, ticker: str, executor,
) -> WatchlistExpandedVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            rows = list_active_watchlist(conn)
            row = next((r for r in rows if r.ticker == ticker), None)
            if row is None:
                return None
            binding = latest_completed_pipeline_run(conn)
            data_asof = binding.data_asof_date if binding else None
            eval_run_id: int | None = None
            if binding is not None:
                if binding.evaluation_run_id is not None:
                    # FK-backed path — bind candidates to the pipeline's own eval.
                    eval_run_id = binding.evaluation_run_id
                else:
                    # Legacy NULL-FK pipeline run — fall back to the heuristic
                    # eval-linkage lookup (same as the legacy resolver path).
                    linked = conn.execute(
                        """SELECT id FROM evaluation_runs
                           WHERE data_asof_date = ? AND run_ts <= ?
                           ORDER BY run_ts DESC LIMIT 1""",
                        (binding.data_asof_date, binding.finished_ts),
                    ).fetchone()
                    if linked is not None:
                        eval_run_id = linked[0]
            else:
                # Fresh-install / no-pipeline-yet path — fall back to latest eval
                # so criteria panel can render. Chart will be 'no-run'.
                fallback = conn.execute(
                    "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
                ).fetchone()
                if fallback is not None:
                    eval_run_id = fallback[0]
            candidate = None
            if eval_run_id is not None:
                for c in fetch_candidates_for_run(conn, eval_run_id):
                    if c.ticker == ticker:
                        candidate = c
                        break
            if binding is None:
                chart_reason = "no-run"
                chart_reason_message = CHART_REASON_MESSAGES["no-run"]
            else:
                chart_reason, chart_reason_message = resolve_chart_scope(
                    conn, binding=binding, ticker=ticker,
                    charts_dir=cfg.paths.charts_dir,
                    chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
                )
    finally:
        conn.close()
    snaps = cache.get_many(
        [ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = snaps.get(ticker)
    return WatchlistExpandedVM(
        ticker=ticker, entry=row, candidate=candidate,
        last_price=snap, data_asof_date=data_asof,
        chart_reason=chart_reason, chart_reason_message=chart_reason_message,
    )
```

Update imports: `from swing.web.chart_scope import CHART_REASON_MESSAGES, latest_completed_pipeline_run, resolve_chart_scope`.

Run existing watchlist-expand tests:

```bash
python -m pytest tests/web/ -k "watchlist_expand or build_watchlist_expanded" -v
```

Expected: existing tests still pass.

Commit:

```bash
git add swing/web/view_models/watchlist.py
git commit -m "feat(web): Task 3 (sub) — watchlist expand binds to PipelineRunBinding"
```

- [ ] **Step 7: Final commit (resolver + message update)**

After all 3 callers are migrated, commit the resolver + message update:

```bash
git add swing/web/chart_scope.py tests/web/test_chart_scope.py
git commit -m "feat(web): Task 3 — resolve_chart_scope requires PipelineRunBinding"
```

(The 3 sub-commits already landed; this commit lands the resolver change after the callers are migrated. This ordering is intentional — committing the resolver first would leave callers passing a kwarg that doesn't exist yet between commits.)

**Wait — that's reversed.** Re-read: the resolver change is breaking. If we commit the callers FIRST (passing `binding=`), the prior resolver doesn't accept that kwarg → tests fail. If we commit the resolver FIRST, the prior callers don't pass `binding=` → tests fail. **Resolution: combine resolver + first caller change in a single commit; subsequent caller changes can be smaller commits.** Adjust:

- Step 4 above becomes the FIRST commit and includes BOTH the resolver/message edits AND the charts-route caller migration in one commit:
  - `git add swing/web/chart_scope.py swing/web/routes/charts.py tests/web/test_chart_scope.py tests/web/test_routes/test_charts_route.py`
  - `git commit -m "feat(web): Task 3 (sub) — resolver signature + charts route migration"`
- Steps 5 + 6 commit cleanly because the resolver already has the new signature.
- Step 7 above is removed.

(Implementer must follow this revised order at execution time. The test order at end-of-task remains: full fast suite green.)

- [ ] **Step 8: Run full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: green.

**Acceptance:**
- 3 new chart-scope tests pass (race, signature, message).
- 1 new charts-route binding test passes (concrete body filled in).
- All existing chart-scope, route, expand tests pass.
- Full fast suite green.
- Resolver docstring states the binding-scope contract verbatim per spec §C.

**Adversarial-review watch items:**
- **Resolver+caller commit ordering.** Mid-task RED state would surface if the resolver lands without callers (or vice versa). The bundled first commit prevents this. Reviewer must confirm the actual commit chain has no ordering RED window.
- **`pass` placeholder in Step 4 test body.** The plan acknowledges this is the single placeholder; implementer MUST fill it in concretely with the seeded_db pattern from existing tests. If left as `pass`, the test passes vacuously and provides no discriminating value.
- **Watchlist expand builder's eval-linkage refactor.** The legacy heuristic eval-linkage query (lines 243-260 currently) still exists in the new code for the NULL-FK fallback case. Reviewer must verify this fallback is preserved unchanged for legacy `pipeline_runs` rows.
- **Out-of-scope copy update is small but breaks substring assertions in any test that currently asserts on the OLD copy.** Reviewer should grep for any other test asserting on `"top near-trigger"` substring before declaring the task done.
- **`charts_status` enum unchanged.** Spec §B confirms `chart_status` enum is unchanged. Reviewer must verify the migration preserves the OLD `chart_status` CHECK exactly (`'ok', 'fetcher_failed', 'too_few_bars', 'pending'`).
- **`engine-missing` reason was previously triggered by `charts_status == "skipped"`.** Confirm the new resolver preserves this branch verbatim (charts_status mapping is binding.charts_status, not a re-read).

---

### Task 4 — Extract shared `_tag_aware_sort_key` helper (byte-identity by construction)

**Spec section:** §A "Tag-aware composite definition" + §E "Tag-aware-sort byte-identity invariant" (option (a)).

**Goal:** Extract the 4-key composite sort logic from `_sort_watchlist` into a sibling helper `_tag_aware_sort_key(entry, flag_tags)` exported from `swing/web/view_models/dashboard.py`. `_sort_watchlist` calls the helper. `_step_charts` (Task 5) imports and calls the same helper. Byte-identity is guaranteed by construction.

**Files:**
- Modify: `swing/web/view_models/dashboard.py`
- Modify: `tests/web/test_view_models/test_dashboard_sort.py` (or equivalent — verify path at execution time)
- Create: `tests/web/test_view_models/test_tag_aware_sort_key.py`

- [ ] **Step 1: Write failing test pinning helper signature + key shape**

```python
# tests/web/test_view_models/test_tag_aware_sort_key.py
"""Pin _tag_aware_sort_key as the single source of truth for the
tag-aware composite sort key. Spec §A.

Byte-identity invariant: `_sort_watchlist` and `_step_charts` (Task 5) both
import this helper. Tests here pin the key shape; Task 5 tests pin the
identity-of-output between callers.
"""
from __future__ import annotations

from swing.data.models import WatchlistEntry
from swing.web.view_models.dashboard import _tag_aware_sort_key


def _wl(ticker: str, *, entry_target: float | None = 100.0,
        last_close: float | None = 99.0) -> WatchlistEntry:
    """Helper to build minimal WatchlistEntry for sort tests."""
    # Construct with the dataclass defaults at execution time; verify
    # field count matches via dataclasses.fields.
    return WatchlistEntry(
        ticker=ticker, entry_target=entry_target,
        initial_stop_target=None, last_close=last_close,
        # ... other required fields with safe defaults; see existing pattern in
        # tests/web/test_view_models/test_dashboard_sort.py
    )


def test_tag_aware_sort_key_returns_4_tuple():
    """Helper returns the documented 4-tuple shape:
    (-tag_count, -tag_precedence_score, abs_proximity, ticker).

    Discriminating verification: assert tuple length AND each element's
    sign/type. A regression that drops the ticker tiebreaker would fail
    the length check.
    """
    flag_tags = {"AAPL": ("A+",)}
    key = _tag_aware_sort_key(_wl("AAPL"), flag_tags)
    assert isinstance(key, tuple)
    assert len(key) == 4, f"expected 4-tuple, got {len(key)}: {key}"
    tag_count_neg, tag_score_neg, proximity, ticker = key
    assert tag_count_neg == -1
    assert tag_score_neg < 0  # A+ score is positive, so negated is negative
    assert proximity == 0.01  # |99.0 - 100.0| / 100.0 = 0.01
    assert ticker == "AAPL"


def test_tag_aware_sort_key_no_tags_returns_zeroed_first_two():
    """When the ticker has no tags, the first two slots are 0 (ties up
    at the bottom of the no-tag group).

    Discriminating verification: pre-fix code gave ticker tags from a
    transitively-imported map; post-fix code uses the explicit `flag_tags`
    arg. Catches a regression where the helper accidentally re-uses a
    module-level map.
    """
    key = _tag_aware_sort_key(_wl("ZZZ"), {})
    tag_count_neg, tag_score_neg, _proximity, _ticker = key
    assert tag_count_neg == 0
    assert tag_score_neg == 0


def test_sort_watchlist_uses_tag_aware_sort_key_helper():
    """Reference-enumeration discipline: build a 4-row watchlist with
    diverse tag profiles and assert the sorted order matches what
    `_tag_aware_sort_key` produces directly (verified-empirically pin).

    Discriminating verification: invariant is "_sort_watchlist's output
    order is identical to the order obtained by sorting with
    _tag_aware_sort_key directly." If the two diverge, this test fails;
    Task 5's identity claim depends on this.
    """
    from swing.web.view_models.dashboard import _sort_watchlist
    rows = [
        _wl("ZZZ", entry_target=100.0, last_close=99.0),  # no tags
        _wl("BBB", entry_target=100.0, last_close=99.5),  # no tags, closer
        _wl("AAA", entry_target=100.0, last_close=98.0),  # 1 tag (TT✓)
        _wl("CCC", entry_target=100.0, last_close=99.0),  # 2 tags (TT✓+VCP✓)
    ]
    flag_tags = {
        "AAA": ("TT✓",),
        "CCC": ("TT✓", "VCP✓"),
    }
    expected = sorted(rows, key=lambda w: _tag_aware_sort_key(w, flag_tags))
    actual = _sort_watchlist(list(rows), flag_tags)
    assert [w.ticker for w in actual] == [w.ticker for w in expected]
```

- [ ] **Step 2: Run tests to see RED**

```bash
python -m pytest tests/web/test_view_models/test_tag_aware_sort_key.py -v
```

Expected: 3 tests fail with `ImportError: cannot import name '_tag_aware_sort_key'`.

- [ ] **Step 3: Implement the helper**

In `swing/web/view_models/dashboard.py`, add a new function near the existing `_sort_watchlist` (between `_abs_proximity` and `_sort_watchlist`):

```python
def _tag_aware_sort_key(
    entry: WatchlistEntry,
    flag_tags: Mapping[str, tuple[str, ...]],
) -> tuple[int, int, float, str]:
    """4-key composite sort key. Spec §A.

    Returns (-tag_count, -tag_precedence_score, abs_proximity, ticker).

    Shared between _sort_watchlist (web view-model) and _step_charts
    (pipeline) — by-construction byte identity for the chart-scope
    tag-aware tier per spec §A "Tag-aware composite definition."
    """
    tags = flag_tags.get(entry.ticker, ())
    return (
        -len(tags),
        -_tag_precedence_score(tags),
        _abs_proximity(entry),
        entry.ticker,
    )
```

Refactor `_sort_watchlist` to use the helper:

```python
def _sort_watchlist(
    watchlist: list[WatchlistEntry],
    flag_tags: Mapping[str, tuple[str, ...]],
) -> list[WatchlistEntry]:
    """4-key composite via _tag_aware_sort_key. The trailing ticker key is
    part of the contract — without it, Python's stable sort preserves
    whatever order list_active_watchlist happens to return on full-equality
    ties, which is non-deterministic.
    """
    return sorted(watchlist, key=lambda w: _tag_aware_sort_key(w, flag_tags))
```

- [ ] **Step 4: Run tests to see GREEN**

```bash
python -m pytest tests/web/test_view_models/test_tag_aware_sort_key.py -v
python -m pytest tests/web/ -k "sort_watchlist" -v   # existing dashboard sort tests
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/test_view_models/test_tag_aware_sort_key.py
git commit -m "feat(web): Task 4 — extract _tag_aware_sort_key shared helper"
```

**Acceptance:**
- 3 new helper tests pass.
- Existing `_sort_watchlist` tests still green (helper preserves behavior byte-identically).
- Full fast suite green.

**Adversarial-review watch items:**
- **Helper exposed at module level even with leading underscore.** Spec §A "Tag-aware composite definition" says "writing-plans phase should consider extracting a shared `_tag_aware_sort_key(watchlist)` helper." The leading underscore signals "module-internal" but Task 5 imports it across modules. Convention in this project: leading underscore = "non-public" but cross-module imports are accepted (precedent: `swing/web/view_models/watchlist.py` imports `_flag_tags`, `_sort_watchlist` from `dashboard`). Reviewer should accept the precedent.
- **`Mapping[str, tuple[str, ...]]` type hint is unchanged from `_sort_watchlist`.** The helper preserves the existing import (`from typing import Mapping`); reviewer should verify no new type imports are needed.
- **Inversion of compounding-confound risk** (Phase 4 lesson): the test fixture uses tickers AAA, BBB, CCC, ZZZ where alphabetical order coincidentally matches the post-sort order. **Reviewer must check** that the test would fail if `_tag_aware_sort_key` returned only proximity (without tag count/score). With this fixture: alphabetical order [AAA, BBB, CCC, ZZZ] differs from tag-correct order [CCC, AAA, BBB, ZZZ] — so the test discriminates. Confirm by mentally running the bug case.

---

### Task 5 — `_step_charts` 3-tier policy rewrite

**Spec section:** §A "Chart-scope tier model + selection criteria," "Deduplication," "Pivot/stop sourcing for chart rendering."

**Goal:** Rewrite the target-composition section of `_step_charts` (lines 558-582 currently) as a 3-tier composition with precedence-ordered dedup, ticker canonicalization, tag-aware composite sort via the shared helper, and per-tier pivot/stop sourcing. Open positions emit pivot from `trades.entry_price` and stop from `trades.current_stop`. The target source values written to `pipeline_chart_targets` are now `'aplus'`, `'open_position'`, `'tag_aware_top_n'` — `'near_proximity'` is no longer emitted.

**Files:**
- Modify: `swing/pipeline/runner.py` (lines 541-595 only — no other changes inside `_step_charts`)
- Modify: `tests/pipeline/test_runner_chart_targets.py` (extend with new assertions)

- [ ] **Step 1: Write failing tests**

The test file already exists; extend it:

```python
# tests/pipeline/test_runner_chart_targets.py — append

def test_step_charts_emits_three_tier_targets_with_correct_sources(
    pipeline_test_context,  # existing fixture; provides cfg, lease, eval_run, fake fetcher
):
    """A+ candidate, open position, tag-aware top-N — three tickers with
    distinct sources end up in pipeline_chart_targets.

    Synthetic-fixture mapping discipline: BEFORE asserting on the targets,
    pull intermediate values to confirm the fixture sets up the expected
    state:
    - candidates contains exactly one 'aplus' bucket (T_APLUS).
    - list_open_trades returns exactly one trade (T_OPEN).
    - watchlist contains exactly one tagged-and-data-eligible row (T_WATCH).

    Discriminating verification: pre-fix code emits at most A+ + watchlist
    by proximity; T_OPEN would be missing. Post-fix all three appear.
    Each row's `source` value is asserted; pre-fix would write
    'near_proximity' for the watchlist row (still legal post-migration but
    spec §A says the new path emits 'tag_aware_top_n').
    """
    ctx = pipeline_test_context
    # ... fixture asserts (synthetic mapping check)
    # Run _step_charts
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    rows = ctx.conn.execute(
        """SELECT ticker, source FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? ORDER BY ticker""",
        (ctx.lease.run_id,),
    ).fetchall()
    assert {r[1] for r in rows} == {"aplus", "open_position", "tag_aware_top_n"}, (
        f"expected all three sources present; got rows={rows}"
    )


def test_step_charts_dedup_precedence_aplus_wins_over_open_position(
    pipeline_test_context,
):
    """Ticker present in BOTH aplus AND open_position tiers → recorded ONCE
    with source='aplus'.

    Compounding-confound discipline (Phase 4 lesson): the ticker name MUST
    differ from the alphabetically-first OR -last ticker in the test fixture
    so the deterministic ticker tiebreaker doesn't coincidentally produce
    the same outcome. Use 'MMMM' (mid-alphabet) to avoid the symmetry trap.

    Discriminating verification: pre-fix code (no precedence dedup) writes
    'open_position' OR 'aplus' depending on iteration order; post-fix
    always 'aplus'. Without precedence-conscious dedup, this test fails
    on the source value.
    """
    ctx = pipeline_test_context.with_overlap(ticker="MMMM")
    # MMMM is BOTH an 'aplus' candidate AND an open trade.
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    rows = ctx.conn.execute(
        """SELECT source FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? AND ticker = 'MMMM'""",
        (ctx.lease.run_id,),
    ).fetchall()
    assert len(rows) == 1, f"expected ONE row for MMMM, got {len(rows)}: {rows}"
    assert rows[0][0] == "aplus"


def test_step_charts_dedup_precedence_open_position_wins_over_tag_aware(
    pipeline_test_context,
):
    """Ticker in open_position AND tag_aware_top_n → recorded ONCE with
    source='open_position'.

    Discriminating verification: same compounding-confound discipline.
    """
    ctx = pipeline_test_context.with_open_and_watchlist_overlap(ticker="MMMM")
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    rows = ctx.conn.execute(
        """SELECT source FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? AND ticker = 'MMMM'""",
        (ctx.lease.run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "open_position"


def test_step_charts_dedup_ticker_in_all_three_tiers_records_aplus(
    pipeline_test_context,
):
    """Ticker present in ALL THREE tiers → recorded ONCE with source='aplus'.

    Discriminating verification: explicit edge case from spec §A
    "Edge case: ticker in all three tiers."
    """
    ctx = pipeline_test_context.with_all_three_overlap(ticker="MMMM")
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    rows = ctx.conn.execute(
        """SELECT source FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? AND ticker = 'MMMM'""",
        (ctx.lease.run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "aplus"


def test_step_charts_canonicalizes_ticker_case_before_dedup(
    pipeline_test_context,
):
    """Mixed-case tickers across tiers normalize to upper-case before dedup
    (Codex R1 Minor 3).

    Synthetic-fixture mapping discipline: candidates emit 'AAPL' (upper);
    a trade is seeded with ticker='aapl' (lower) — defensive worst case.
    Spec confirms watchlist + candidates + trades all currently emit
    upper-case in production, but the canonicalization is the
    defense-in-depth fix.

    Discriminating verification: pre-canonicalization code adds 'AAPL'
    and 'aapl' as DIFFERENT entries in `seen`, producing TWO rows that
    violate the UNIQUE (pipeline_run_id, ticker) constraint and raise
    IntegrityError. Post-fix the dedup sees both as 'AAPL' and writes one row.
    """
    ctx = pipeline_test_context.with_mixed_case(
        candidate_ticker="AAPL", trade_ticker="aapl",
    )
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    rows = ctx.conn.execute(
        """SELECT ticker, source FROM pipeline_chart_targets
           WHERE pipeline_run_id = ?""",
        (ctx.lease.run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "AAPL"
    assert rows[0][1] == "aplus"


def test_step_charts_open_position_pivot_from_trades_entry_price(
    pipeline_test_context,
):
    """Open-position tier sources pivot from `trades.entry_price` and stop
    from `trades.current_stop` (NOT from any watchlist join).

    Synthetic-fixture mapping discipline: seed a trade with
    entry_price=42.50, current_stop=40.00. Set the watchlist row for
    the same ticker to entry_target=999.00 (deliberate divergence).
    Run _step_charts; instrument render_chart to capture the pivot/stop
    args via a recording stub. Assert the captured values match
    entry_price/current_stop, NOT the watchlist row's values.

    Discriminating verification: pre-fix code (open_position tier doesn't
    exist; ticker only enters scope via watchlist tier) would render with
    pivot=999.00. Post-fix renders with pivot=42.50.
    """
    ctx = pipeline_test_context.with_open_position_pivot_pin(
        ticker="MMMM", entry_price=42.50, current_stop=40.00,
        watchlist_entry_target=999.00,  # deliberate red-herring
    )
    captured = []
    def recording_render(*, ticker, ohlcv, pivot, stop, output_path, pattern_overlay):
        captured.append((ticker, pivot, stop))
        # Behave like real render_chart: write a tiny PNG to satisfy the
        # status='ok' branch.
        output_path.write_bytes(b"png-stub")
        return output_path
    with monkeypatch_render_chart(recording_render):
        from swing.pipeline.runner import _step_charts
        _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                     data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    mmmm_calls = [c for c in captured if c[0] == "MMMM"]
    assert len(mmmm_calls) == 1
    _, pivot, stop = mmmm_calls[0]
    assert pivot == 42.50, f"expected entry_price=42.50, got pivot={pivot}"
    assert stop == 40.00, f"expected current_stop=40.00, got stop={stop}"


def test_step_charts_tag_aware_filter_intersection_limit(
    pipeline_test_context,
):
    """Watchlist row missing entry_target OR last_close does NOT enter
    chart-scope (spec §A "Residual filter-intersection limitation,
    Codex R1 Major 3").

    Synthetic-fixture mapping discipline: seed TWO watchlist rows —
    'GOOD' with entry_target + last_close populated; 'GAPS' with
    entry_target=None. Both are tagged equally.

    Discriminating verification: pre-fix code might filter at sort time
    (proximity=inf places it last but doesn't drop it); post-fix code
    excludes 'GAPS' from the tag-aware tier entirely. Test fails if 'GAPS'
    appears in pipeline_chart_targets. **Verified-empirically pin:**
    'GOOD' appears in scope, proving the tier ran and isn't always-empty.
    """
    ctx = pipeline_test_context.with_partial_watchlist_row(
        good_ticker="GOOD", gaps_ticker="GAPS",
    )
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    tickers = {r[0] for r in ctx.conn.execute(
        """SELECT ticker FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? AND source = 'tag_aware_top_n'""",
        (ctx.lease.run_id,),
    ).fetchall()}
    assert "GAPS" not in tickers, (
        "GAPS (entry_target=None) entered chart-scope; "
        "regression: filter-intersection limit not enforced"
    )
    assert "GOOD" in tickers, (
        "GOOD (data-eligible) NOT in chart-scope; "
        "regression: tag-aware tier returned empty (vacuous)"
    )


def test_step_charts_tag_aware_uses_shared_sort_key(pipeline_test_context):
    """The order of tag_aware_top_n tickers in pipeline_chart_targets matches
    the order produced by `_tag_aware_sort_key` (byte-identity invariant).

    Reference-enumeration discipline (Phase 1 lesson): build a 6-row
    watchlist; compute expected order via _tag_aware_sort_key directly;
    assert _step_charts output matches.

    Discriminating verification: pre-fix code sorts by proximity-only;
    post-fix uses 4-key composite. A regression that drops the helper
    import OR re-introduces a proximity-only sort fails the order check.
    """
    ctx = pipeline_test_context.with_diverse_watchlist_six_rows()
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    actual_order = [r[0] for r in ctx.conn.execute(
        """SELECT ticker FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? AND source = 'tag_aware_top_n'
           ORDER BY id""",  # insertion order
        (ctx.lease.run_id,),
    ).fetchall()]
    # Compute expected via the helper.
    from swing.web.view_models.dashboard import _tag_aware_sort_key, _flag_tags
    expected_order = [w.ticker for w in sorted(
        ctx.watchlist_data_eligible_only,
        key=lambda w: _tag_aware_sort_key(w, ctx.flag_tags),
    )][:ctx.cfg.pipeline.chart_top_n_watch]
    assert actual_order == expected_order
```

(Several tests reference fixture-method names like `with_overlap`, `with_open_and_watchlist_overlap`, etc. These methods do not exist on the current `pipeline_test_context` fixture. The implementer MUST add them as helper methods on the existing fixture or fixture-builder pattern, with one helper per test scenario. The fixture-helper extension pattern is established in `tests/pipeline/test_runner_chart_targets.py` — implementer reads existing helpers and follows the pattern.)

- [ ] **Step 2: Run tests to see RED**

```bash
python -m pytest tests/pipeline/test_runner_chart_targets.py -v
```

Expected: 8 new tests fail with various assertion errors related to missing tiers, wrong source values, or wrong sort orders.

- [ ] **Step 3: Implement the rewrite**

In `swing/pipeline/runner.py`, replace lines 558-595 (`aplus = ...` through end of pre-iteration target persistence) with:

```python
    # Spec §A — three-tier composition with precedence-ordered dedup.
    aplus = [c for c in candidates if c.bucket == "aplus"]

    # Open trades — sourced from list_open_trades; pivot from entry_price,
    # stop from current_stop. Read here (already inside the read-conn block).
    from swing.data.repos.trades import list_open_trades
    open_trades = list_open_trades(conn)

    # Tag-aware top-N from watchlist via the shared sort helper.
    # Filter to data-eligible rows first (entry_target + last_close populated)
    # to match the proximity-tiebreaker contract.
    data_eligible = [w for w in watchlist if w.entry_target and w.last_close]
    # flag_tags computed from candidates_by_ticker matches the dashboard's
    # _flag_tags exactly — same input set (THIS RUN's eval candidates), same
    # tag derivation. Byte-identity by construction.
    by_ticker = {c.ticker: c for c in candidates}
    from swing.web.view_models.dashboard import (
        _flag_tags as _dashboard_flag_tags,
        _tag_aware_sort_key,
    )
    flag_tags = _dashboard_flag_tags(by_ticker)
    tag_aware_sorted = sorted(
        data_eligible,
        key=lambda w: _tag_aware_sort_key(w, flag_tags),
    )
    tag_aware_top_n = tag_aware_sorted[:cfg.pipeline.chart_top_n_watch]

    # Spec §A "Deduplication": linear pass through tiers in precedence order
    # with ticker canonicalization (upper) before being added to `seen`
    # (Codex R1 Minor 3 defense-in-depth).
    seen: set[str] = set()
    targets: list[tuple[str, float, float, str]] = []  # ticker, pivot, stop, source
    for c in aplus:
        t_canon = c.ticker.upper()
        if t_canon in seen:
            continue
        seen.add(t_canon)
        targets.append((t_canon, c.pivot or 0.0, c.initial_stop or 0.0, "aplus"))
    for tr in open_trades:
        t_canon = tr.ticker.upper()
        if t_canon in seen:
            continue
        seen.add(t_canon)
        # Spec §A "Pivot/stop sourcing": entry_price as pivot proxy;
        # current_stop reflects post-stop_adjust value.
        targets.append((t_canon, tr.entry_price, tr.current_stop or 0.0, "open_position"))
    for w in tag_aware_top_n:
        t_canon = w.ticker.upper()
        if t_canon in seen:
            continue
        seen.add(t_canon)
        targets.append((
            t_canon, w.entry_target, w.initial_stop_target or 0.0,
            "tag_aware_top_n",
        ))
```

The remainder of `_step_charts` (the staging dir, per-target iteration, fenced writes, classifier counters, summary log, promote_staging) is unchanged.

- [ ] **Step 4: Run tests to see GREEN**

```bash
python -m pytest tests/pipeline/test_runner_chart_targets.py -v
```

Expected: 8 new tests + existing tests PASS.

- [ ] **Step 5: Run full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_runner_chart_targets.py
git commit -m "feat(pipeline): Task 5 — _step_charts 3-tier policy + canonical dedup"
```

**Acceptance:**
- 8 new policy tests pass.
- Existing chart-target tests pass.
- Full fast suite green.
- Source-value distribution post-run includes all 3 new values; `near_proximity` is no longer emitted.

**Adversarial-review watch items:**
- **`list_open_trades` is read inside the existing `with conn:` read block** — confirm the read happens BEFORE `conn.close()` so trades and candidates come from the same snapshot. The fence-then-iterate pattern of `_step_charts` does not need a write here.
- **Canonical-tickers in `targets` propagate to all downstream consumers.** `update_chart_target_status` and `insert_chart_target` both receive the canonicalized ticker; `render_chart`'s `output_path = staging.path / f"{ticker}.png"` uses the canonical form. Confirm no path-name regression (e.g., a `.png` filename with mixed case that doesn't match what the web layer expects).
- **The shared sort helper import crosses package layers** (`swing.web.view_models.dashboard` imported from `swing.pipeline.runner`). This is a NEW pipeline → web import direction. Verify no circular-import: `swing.web.view_models.dashboard` does NOT import from `swing.pipeline.*` — confirmed by reading the dashboard module's imports. Implementer should re-verify at execution time.
- **Filter-intersection test assertion uses `assert "GAPS" not in tickers AND assert "GOOD" in tickers`** — the second clause is the verified-empirically pin per spec §A "writing-plans phase MUST add a test that explicitly demonstrates the intersection limit." Reviewer must confirm both clauses are present.
- **Ticker 'MMMM' (mid-alphabet) in dedup tests** counters Phase 4's compounding-confound failure mode. Reviewer should mentally simulate: with alphabetical tiebreaker, would 'MMMM' coincidentally land where the bug case puts it? With 'MMMM' present in two tiers and AAPL/NVDA also in scope, alphabetical order is NVDA < MMMM < AAPL — so 'MMMM' is mid-list regardless. The dedup-precedence test asserts on `source` not order, so the tiebreaker isn't relevant to the discriminator anyway. Verified.
- **`tag_aware_top_n` slice limit (`[:cfg.pipeline.chart_top_n_watch]`)** uses the runtime config value. Task 8 changes the default 5→10; tests in this task must NOT hardcode `chart_top_n_watch` or they will become stale.

---

### Task 6 — Stop-hline omission for None/0 stops + chart title format

**Spec section:** §A "Edge cases for open-position pivot/stop sourcing" (Codex R2 Major 3).

**Goal:** When a trade has `current_stop is None` or `current_stop <= 0.0`, `render_chart` MUST omit the stop hline AND the chart title MUST NOT include the `stop X.XX` segment. Plotting `stop=0.0` would auto-scale the y-axis to include zero, compressing price action and implying false catastrophic downside.

**Files:**
- Modify: `swing/rendering/charts.py` (or whichever module hosts `render_chart` — verify path at execution time)
- Modify: `tests/rendering/test_chart_overlay.py` (or equivalent — verify path at execution time)

- [ ] **Step 1: Write failing tests**

```python
# tests/rendering/test_render_chart_stop_omission.py — new file

"""Stop-hline omission for None/0 stops. Spec §A.

Manual visual verification per Phase 6 + Tier-1 mathtext lessons:
string-equality on title is INSUFFICIENT for rendered output. After
implementing, manually `Read` a generated PNG to confirm the visual
is correct.
"""
from __future__ import annotations

import pandas as pd
import pytest

from swing.rendering.charts import render_chart


def _ohlcv(n: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": 100.0, "High": 102.0, "Low": 99.0, "Close": 101.0,
         "Volume": 1_000_000.0},
        index=idx,
    )


def test_render_chart_omits_stop_hline_when_stop_is_none(tmp_path):
    """Stop=None → no stop hline drawn AND no `stop X.XX` segment in title.

    Discriminating verification: capture the generated figure's HLines
    via mplfinance's returnfig=True. Pre-fix: hline drawn at y=0 (or
    raises). Post-fix: no hline at the stop position.
    """
    out = tmp_path / "AAPL.png"
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=None,
        output_path=out, pattern_overlay=None,
    )
    assert out.exists()
    # ... figure-level assertion: count HLines collections; pre-fix=2, post-fix=1.
    # Reuse the LineCollection-count comparison pattern from Phase 6
    # tests/rendering/test_chart_overlay.py:* (verify exact assertion shape
    # at execution time per existing test file).


def test_render_chart_omits_stop_hline_when_stop_is_zero(tmp_path):
    """Stop=0.0 → same omission behavior as None.

    Discriminating verification: pre-fix code passed `stop=0.0` directly to
    matplotlib hlines; mplfinance's auto-scale would expand y-axis to
    include 0 (compressing legitimate price action). Post-fix omits.
    """
    out = tmp_path / "AAPL.png"
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=0.0,
        output_path=out, pattern_overlay=None,
    )
    assert out.exists()
    # Same figure-level HLines count assertion as above.


def test_render_chart_title_omits_stop_segment_when_stop_is_zero(tmp_path):
    """When stop is None or 0, title must NOT contain `stop X.XX`.

    Discriminating verification: pre-fix the title format was something
    like `AAPL  pivot 110.00  stop 0.00`; post-fix becomes
    `AAPL  pivot 110.00`. Substring exclusion catches the regression.

    Note: per CLAUDE.md mathtext gotcha, the title format MUST also NOT
    introduce a `$` metacharacter. The post-fix format omits the `stop`
    segment entirely; reviewer must confirm no leading `$` is added in
    its place.

    Title-extraction pattern (Phase 6 lesson): mpf renders title via
    `fig.suptitle`, NOT `price_ax.set_title`. `price_ax.get_title()`
    returns empty string under mpf default. To capture the title for
    assertion, call `render_chart` through a wrapper that intercepts
    the title arg, OR refactor render_chart to expose the title string
    via the existing returnfig path. The simplest assertion: read the
    title arg passed to mpf.plot via monkeypatch capture (see Phase 6
    `test_chart_overlay.py` pattern for the capture helper).
    """
    captured_titles: list[str] = []

    def _capture_title(*args, **kwargs):
        # mpf.plot signature: positional first arg is the OHLCV df;
        # `title` kwarg is what render_chart passes through. Capture
        # the title for inspection, then call original to render.
        captured_titles.append(kwargs.get("title", ""))
        # Return a minimal stub so render_chart's downstream save call
        # behaves like a real mpf path. The actual save is intercepted
        # via tmp_path fixture, so we don't need a real figure here.
        return None

    import mplfinance as mpf
    monkeypatch_target = "swing.rendering.charts.mpf.plot"
    # Use pytest's monkeypatch fixture (passed in via test signature).
    # Implementer adds `monkeypatch` to the test's positional args.
    # Fall back: if mpf.plot is imported as `from mplfinance import plot`,
    # patch the imported name in swing.rendering.charts directly.
    out = tmp_path / "AAPL.png"
    # The actual assertion: render_chart with stop=0.0 produces a title
    # WITHOUT the 'stop' segment.
    # NOTE: this test asserts the CONTRACT of the title format, not the
    # mechanics of mpf.plot. Per Phase 6 lesson, the title-string format
    # is what render_chart constructs BEFORE passing to mpf.plot — we
    # assert on render_chart's output directly. If render_chart returns
    # the title (or exposes a helper `_build_chart_title(ticker, pivot,
    # stop)`), test that helper directly:
    from swing.rendering.charts import _build_chart_title  # NEW helper
    title_stop_zero = _build_chart_title(ticker="AAPL", pivot=110.0, stop=0.0)
    title_stop_none = _build_chart_title(ticker="AAPL", pivot=110.0, stop=None)
    title_stop_positive = _build_chart_title(ticker="AAPL", pivot=110.0, stop=95.0)
    assert "stop" not in title_stop_zero.lower(), (
        f"title still contains 'stop' segment when stop=0.0: {title_stop_zero!r}"
    )
    assert "stop" not in title_stop_none.lower(), (
        f"title still contains 'stop' segment when stop=None: {title_stop_none!r}"
    )
    assert "stop 95" in title_stop_positive.lower(), (
        f"verified-empirically pin failed: positive stop omits 'stop 95.00': {title_stop_positive!r}"
    )
    for t in (title_stop_zero, title_stop_none, title_stop_positive):
        # CLAUDE.md mathtext gotcha — no metacharacters in the title.
        assert "$" not in t and "^" not in t and "_" not in t, (
            f"title contains mathtext metacharacter: {t!r}"
        )


def test_render_chart_renders_stop_hline_when_stop_is_positive(tmp_path):
    """Verified-empirically pin: positive stop renders the hline as before.

    Discriminating verification: catches a regression that omits the hline
    even when stop > 0.
    """
    out = tmp_path / "AAPL.png"
    render_chart(
        ticker="AAPL", ohlcv=_ohlcv(), pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=None,
    )
    assert out.exists()
    # Figure-level HLines count assertion: pre-fix=2 (pivot+stop), post-fix=2.
```

- [ ] **Step 2: Run tests to see RED**

```bash
python -m pytest tests/rendering/test_render_chart_stop_omission.py -v
```

Expected: 4 tests fail. Two on the `stop=None` path (pre-fix code may TypeError on `float(None)`); two on the title format.

- [ ] **Step 3: Implement the conditional + extract `_build_chart_title` helper**

(a) Add a small pure helper `_build_chart_title` at module scope of `swing/rendering/charts.py` so the title-format contract is testable in isolation (per the title-format test in Step 1):

```python
def _build_chart_title(*, ticker: str, pivot: float, stop: float | None) -> str:
    """Build the chart title segment-by-segment.

    Spec §A: when stop is None or <= 0, the `stop X.XX` segment is omitted
    entirely (avoids matplotlib auto-scaling y-axis to include zero).
    Per CLAUDE.md mathtext gotcha, NO `$`, `^`, `_`, or unbalanced `\` in
    the format — those metacharacters trigger mathtext interpretation and
    silently italicize / consume glyphs.
    """
    parts = [ticker, f"pivot {pivot:.2f}"]
    if stop is not None and stop > 0.0:
        parts.append(f"stop {stop:.2f}")
    return "  ".join(parts)
```

(b) Update `render_chart` to use the helper for its title arg AND apply the conditional to the hline-build section:

```python
# Before (illustrative):
hlines = [pivot, stop]
labels = [f"pivot {pivot:.2f}", f"stop {stop:.2f}"]
title = f"{ticker}  pivot {pivot:.2f}  stop {stop:.2f}"

# After:
hlines = [pivot]
labels = [f"pivot {pivot:.2f}"]
if stop is not None and stop > 0.0:
    hlines.append(stop)
    labels.append(f"stop {stop:.2f}")
title = _build_chart_title(ticker=ticker, pivot=pivot, stop=stop)
```

The exact pre-existing code structure depends on the current `render_chart` signature; implementer reads the function at execution time and applies the conditional consistently to BOTH the hline list AND the title string. Both must omit the `stop` segment when `stop is None or stop <= 0.0`.

- [ ] **Step 4: Run tests to see GREEN**

```bash
python -m pytest tests/rendering/ -v
```

Expected: new tests pass; existing chart-rendering tests pass.

- [ ] **Step 5: Manual visual verification (per Phase 6 lesson)**

Generate two PNGs manually and `Read` them:

```bash
python -c "
import pandas as pd
from swing.rendering.charts import render_chart

idx = pd.date_range('2026-01-01', periods=80, freq='B')
df = pd.DataFrame(
    {'Open': 100.0, 'High': 102.0, 'Low': 99.0, 'Close': 101.0, 'Volume': 1_000_000.0},
    index=idx,
)
render_chart(ticker='AAPL', ohlcv=df, pivot=110.0, stop=0.0,
             output_path='/tmp/aapl-stopzero.png', pattern_overlay=None)
render_chart(ticker='AAPL', ohlcv=df, pivot=110.0, stop=95.0,
             output_path='/tmp/aapl-stoppositive.png', pattern_overlay=None)
"
```

Then `Read` both PNGs and confirm:
- `/tmp/aapl-stopzero.png`: no second hline; title shows "AAPL  pivot 110.00" (no `stop` segment).
- `/tmp/aapl-stoppositive.png`: two hlines; title shows "AAPL  pivot 110.00  stop 95.00".

Confirm visual evidence in the commit body. Per CLAUDE.md mathtext gotcha, also confirm the title has no `$`, `^`, `_`, or unbalanced `\` glyphs — the post-fix format string MUST NOT introduce mathtext metacharacters as a side effect of the omission.

- [ ] **Step 6: Commit**

```bash
git add swing/rendering/charts.py tests/rendering/test_render_chart_stop_omission.py
git commit -m "feat(rendering): Task 6 — omit stop hline + title segment when stop is None/0"
```

**Acceptance:**
- 4 new tests pass.
- Manual visual verification confirms no stop hline + correct title format.
- No mathtext metacharacters introduced.
- Full fast suite green.

**Adversarial-review watch items:**
- **Test bodies use `pass` in two cases** — implementer MUST flesh these out concretely (figure-level HLines count assertion + title extraction via `fig.suptitle`). Phase 6 lesson: monkeypatch-capture vacuousness; the captured figure must be inspected directly, not via `price_ax.get_title()` (returns empty in mpf default).
- **`stop=0.0` vs `stop is None` are SEPARATE branches** in production trades — `current_stop` column is `NOT NULL` per migration 0001 default but a stop_adjust to 0.0 is theoretically possible (operator-discipline violation). Both must be caught by the conditional. Test both paths.
- **CLAUDE.md mathtext gotcha** — the title format change must visually re-verify on a rendered PNG. Phase 6's lesson + the 2026-04-27 mathtext regression both reinforce this. Implementer MUST do the visual check before committing.
- **Existing tests on `render_chart` may assume the old 2-hline behavior.** Reviewer should grep for `hlines` / `stop` substring assertions in existing rendering tests; some may need updating for the new conditional. The plan's existing-tests-still-pass assertion in Step 4 catches this.

---

### Task 7 — Wall-time monitoring + log-capture test

**Spec section:** §A "Acceptance threshold" + "Test instrumentation" + "Timer-boundary specification."

**Goal:** Instrument `_step_charts` with a wall-time timer that brackets all chart-step work (from entry through last fenced write). Emit a WARNING log line if `> 60s` and an ERROR log line if `> 120s`. The integration test uses a synthetic-slow `fetcher.get` stub to make the timer cross thresholds deterministically; assertions are on log records (via `caplog`), not on real timing.

**Files:**
- Modify: `swing/pipeline/runner.py` (timer + log emit at end of `_step_charts`)
- Modify: `tests/pipeline/test_runner_chart_targets.py` (or a sibling — verify path at execution time)

- [ ] **Step 1: Write failing log-capture tests**

```python
# tests/pipeline/test_runner_chart_step_walltime.py — new file

"""Chart-step wall-time monitoring tests. Spec §A.

Timer boundary (Codex R3 Minor 2): timer starts at _step_charts entry
(before any DB read for tier composition); timer ends after the last
lease.fenced_write for chart_status updates. The metric is
chart_step_wall_time_seconds. Test instrumentation uses a synthetic-slow
fetcher stub — deterministic, no real timing dependency.
"""
from __future__ import annotations

import logging
import time

import pytest


def _slow_fetcher_stub(sleep_seconds: float):
    """Return a fetcher that sleeps `sleep_seconds` per .get call."""
    class SlowFetcher:
        def get(self, ticker, lookback_days, as_of_date):
            time.sleep(sleep_seconds)
            # Return minimal valid OHLCV (the rest of _step_charts proceeds).
            import pandas as pd
            idx = pd.date_range("2026-01-01", periods=80, freq="B")
            return pd.DataFrame(
                {"Open": 100.0, "High": 102.0, "Low": 99.0, "Close": 101.0,
                 "Volume": 1_000_000.0},
                index=idx,
            )
    return SlowFetcher()


def test_step_charts_logs_warning_when_walltime_above_soft_budget(
    pipeline_test_context, caplog,
):
    """Wall time > 60s → WARNING log line emitted.

    Discriminating verification: the test seeds `time.monotonic` (via
    monkeypatch) so the elapsed measurement returns 65.0s without the
    test waiting 65 real seconds. Caplog captures the WARNING record.
    Substring 'soft budget' in the log message catches the WARN-vs-ERROR
    discriminator (ERROR uses 'hard budget'); also asserts the actual
    measured value appears in the message body.

    Per Phase 3 lesson: the assertion is exact-string on the log line
    template, not just substring 'errors' on the message. Format:
    `chart-step wall-time exceeded soft budget: <actual>s > 60s; scope=<count> tickers; consider reducing chart_top_n_watch`.
    """
    ctx = pipeline_test_context
    # Monkeypatch time.monotonic to advance by exactly 65s between
    # _step_charts entry and exit.
    times = iter([0.0, 65.0])  # entry, exit
    monkeypatch_monotonic(times)
    caplog.set_level(logging.WARNING)
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING
                    and "chart-step wall-time" in r.message]
    assert len(warn_records) == 1, (
        f"expected exactly 1 chart-step WARNING; got {len(warn_records)}: "
        f"{[r.message for r in warn_records]}"
    )
    msg = warn_records[0].message
    assert "soft budget" in msg
    assert "65" in msg or "65.0" in msg, f"actual measured value missing from log: {msg}"


def test_step_charts_logs_error_when_walltime_above_hard_budget(
    pipeline_test_context, caplog,
):
    """Wall time > 120s → ERROR log line emitted (NOT just WARNING).

    Discriminating verification: the test asserts both that an ERROR-level
    record exists with 'hard budget' AND that no WARNING is emitted (the
    code path emits ONE log line per overrun, at the highest applicable
    severity). Pre-fix code might emit BOTH WARNING and ERROR; post-fix
    emits only ERROR for >120s.
    """
    ctx = pipeline_test_context
    times = iter([0.0, 130.0])
    monkeypatch_monotonic(times)
    caplog.set_level(logging.WARNING)
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR
                     and "chart-step wall-time" in r.message]
    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING
                    and "chart-step wall-time" in r.message]
    assert len(error_records) == 1, (
        f"expected exactly 1 chart-step ERROR; got {len(error_records)}"
    )
    assert len(warn_records) == 0, (
        f"expected NO chart-step WARNING when ERROR fires; got {len(warn_records)}"
    )
    assert "hard budget" in error_records[0].message


def test_step_charts_no_log_when_walltime_under_soft_budget(
    pipeline_test_context, caplog,
):
    """Wall time < 60s → no chart-step wall-time log emitted (verified-
    empirically pin per Phase 1 lesson).

    Discriminating verification: catches a regression where the timer
    always logs (even on healthy runs), spamming pipeline-run logs.
    """
    ctx = pipeline_test_context
    times = iter([0.0, 30.0])
    monkeypatch_monotonic(times)
    caplog.set_level(logging.WARNING)
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    walltime_records = [r for r in caplog.records
                        if "chart-step wall-time" in r.message]
    assert len(walltime_records) == 0, (
        f"expected NO chart-step wall-time log on healthy run; "
        f"got {len(walltime_records)}: {[r.message for r in walltime_records]}"
    )


def test_step_charts_pipeline_runs_charts_status_unchanged_on_overrun(
    pipeline_test_context, caplog,
):
    """`pipeline_runs.charts_status` remains 'ok' regardless of wall-time
    overrun (spec §A "Behavior on threshold exceed: pipeline continues normally").

    Discriminating verification: pre-fix code (or a buggy post-fix that
    flips status on overrun) would set charts_status='failed'. Post-fix
    keeps 'ok' — overrun is a soft monitoring signal, not a step failure.
    """
    ctx = pipeline_test_context
    times = iter([0.0, 130.0])
    monkeypatch_monotonic(times)
    caplog.set_level(logging.WARNING)
    from swing.pipeline.runner import _step_charts
    _step_charts(cfg=ctx.cfg, lease=ctx.lease, eval_run_id=ctx.eval_run_id,
                 data_asof=ctx.data_asof, fetcher=ctx.fetcher)
    # The run has not yet finalized (test fixture doesn't run the full
    # pipeline) — but the chart_step's per-ticker chart_status writes
    # are unchanged. Verify by spot-checking pipeline_chart_targets rows.
    rows = ctx.conn.execute(
        """SELECT chart_status FROM pipeline_chart_targets
           WHERE pipeline_run_id = ?""",
        (ctx.lease.run_id,),
    ).fetchall()
    assert all(r[0] in ("ok", "fetcher_failed", "too_few_bars") for r in rows), (
        f"expected normal chart_status values; got {[r[0] for r in rows]}"
    )
```

- [ ] **Step 2: Run tests to see RED**

```bash
python -m pytest tests/pipeline/test_runner_chart_step_walltime.py -v
```

Expected: 4 tests fail — pre-fix code emits NO timer log; tests asserting on the log message fail.

- [ ] **Step 3: Implement the timer**

In `swing/pipeline/runner.py:_step_charts`, add at the top of the function (immediately after `lease.verify_held()`):

```python
    import time as _time_module  # local-import to keep file imports tidy
    _walltime_start = _time_module.monotonic()
```

At the end of `_step_charts` (immediately before `return {t: promote.target_path / f"{t}.png" for t in out_paths}`), add:

```python
    _walltime_elapsed = _time_module.monotonic() - _walltime_start
    _scope_count = len(targets)
    if _walltime_elapsed > 120.0:
        log.error(
            f"chart-step wall-time exceeded hard budget: "
            f"{_walltime_elapsed:.1f}s > 120s; scope={_scope_count} tickers"
        )
    elif _walltime_elapsed > 60.0:
        log.warning(
            f"chart-step wall-time exceeded soft budget: "
            f"{_walltime_elapsed:.1f}s > 60s; scope={_scope_count} tickers; "
            "consider reducing chart_top_n_watch"
        )
```

The boundary spec (per Codex R3 Minor 2) covers tier composition + iteration + per-ticker fetch/classify/render/persist + final promote_staging — all of which happen between `lease.verify_held()` and `return`.

- [ ] **Step 4: Run tests to see GREEN**

```bash
python -m pytest tests/pipeline/test_runner_chart_step_walltime.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_runner_chart_step_walltime.py
git commit -m "feat(pipeline): Task 7 — chart-step wall-time monitoring + log-capture tests"
```

**Acceptance:**
- 4 wall-time tests pass.
- Full fast suite green.
- WARN/ERROR log emission is mutually exclusive (>120s emits ERROR not WARN).
- Healthy runs (<60s) emit no timer log.

**Adversarial-review watch items:**
- **`monkeypatch_monotonic` helper** referenced in test bodies must exist OR be added by the implementer. Use `monkeypatch.setattr('swing.pipeline.runner._time_module.monotonic', lambda: next(times))` pattern. Confirm at execution time that the import path matches the local-import name used in production code.
- **WARN/ERROR mutual exclusion** is the discriminator for the second test. Implementer's `if/elif` structure ensures this; reviewer must confirm no `if/if` (which would emit BOTH).
- **Per Phase 6 lesson "monkeypatch-capture failures":** verify the caplog records actually contain the WARNING — print `[r.message for r in caplog.records]` if the test fails. Substring-only assertions ("errors") would be vacuous; the tests use exact-substring on `'soft budget'` and the measured-value appearance.
- **Per Phase 3 lesson "discriminating-test discipline applies to log-line format":** the assertion includes BOTH the severity-discriminator string ('soft budget' vs 'hard budget') AND the measured-value substring. A regression that swaps severities OR drops the measured value fails the test.
- **Codex may flag the `slow` benchmark test (mentioned in spec §A) as missing.** Spec §A: "A separate benchmark-only test (skipped in `-m 'not slow'` fast suite; runs on demand via `-m slow` or a dedicated benchmark CI job)." This plan's scope is the deterministic log-capture mechanism (the actual regression-detection surface). The `-m slow` benchmark test is a follow-up; document in plan's "Open follow-ups" section below.

---

### Task 8 — Config knob default change (5 → 10)

**Spec section:** §D "Config knob change."

**Goal:** Update `swing/config.py` `PipelineConfig.chart_top_n_watch` default from `5` to `10`.

**Files:**
- Modify: `swing/config.py` (line ~118)
- Modify: `tests/test_config.py` (or wherever `PipelineConfig` defaults are pinned — verify path at execution time)

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py — append (or wherever defaults are pinned)

def test_pipeline_config_chart_top_n_watch_default_is_10():
    """Spec §D — chart_top_n_watch default raised 5 → 10 in chart-scope
    policy v2 (2026-04-27).

    Discriminating verification: pre-fix returns 5; post-fix returns 10.
    Asserting on the exact value catches both directions of regression.
    """
    from swing.config import PipelineConfig
    cfg = PipelineConfig()
    assert cfg.chart_top_n_watch == 10
```

- [ ] **Step 2: Run test to see RED**

```bash
python -m pytest tests/test_config.py -k "chart_top_n_watch" -v
```

Expected: `assert 5 == 10` → FAIL.

- [ ] **Step 3: Update the default**

In `swing/config.py`:

```python
@dataclass(frozen=True)
class PipelineConfig:
    ...
    chart_top_n_watch: int = 10  # was 5; raised in chart-scope policy v2 (2026-04-27)
```

- [ ] **Step 4: Run test + full fast suite**

```bash
python -m pytest tests/test_config.py -k "chart_top_n_watch" -v
python -m pytest -m "not slow" -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add swing/config.py tests/test_config.py
git commit -m "feat(config): Task 8 — chart_top_n_watch default 5 → 10"
```

**Acceptance:**
- New test passes.
- Full fast suite green.
- No other test asserted on `chart_top_n_watch=5` and now fails.

**Adversarial-review watch items:**
- **Tests that hardcoded `chart_top_n_watch=5` would silently fail.** Reviewer must grep for `chart_top_n_watch` substring in all of `tests/` and confirm any hardcoded 5 is updated OR is using the runtime config (which now resolves to 10).
- **Tests in Task 5 must NOT have hardcoded the old value.** Re-read Task 5 test bodies (`tag_aware_top_n[:cfg.pipeline.chart_top_n_watch]`) — uses `cfg`, so the new default is picked up automatically. Verified.
- **Operator-side override path** is `swing.config.toml`'s `[pipeline]` section. Reviewer should confirm no test config uses `chart_top_n_watch=5` either as a literal or via toml fixture. If found, update to `10` or remove the hardcoded value.

---

### Task 9 — Manual verification doc post-rollout note

**Spec section:** §F References + brief §1 "Verification doc updates."

**Goal:** Update `docs/chart-pattern-flag-v1-manual-verification.md` to reflect the post-V2 chart-scope set (3 tiers including open positions). The doc's §0 verification queries continue to work for legacy data; this update adds a note about the post-migration 0011 source taxonomy and the new operator workflow expectations.

**Files:**
- Modify: `docs/chart-pattern-flag-v1-manual-verification.md`

- [ ] **Step 1: Read the existing doc**

```bash
# Read the full file
```

Locate the section that documents chart-scope expectations + the §0 SQL queries. The new note will be appended (NOT inline-edited — operator audit-trail discipline).

- [ ] **Step 2: Write the post-rollout addendum**

Append a new section at the end of the doc:

```markdown
## Post-V2 chart-scope policy (2026-04-27)

After migration `0011` (chart-scope policy v2), `pipeline_chart_targets.source` accepts FOUR values: `aplus`, `near_proximity` (legacy, read-only post-migration), `open_position`, `tag_aware_top_n`.

Chart-scope set per pipeline run is now the precedence-ordered union:

1. `aplus` — A+ candidates (unchanged from V1).
2. `open_position` — currently-open trades from `list_open_trades(conn)`. Pivot from `trades.entry_price`, stop from `trades.current_stop`. **Charts are generated during the scheduled pipeline run; a position opened AFTER the latest completed run remains unchartable until the next pipeline run.**
3. `tag_aware_top_n` — top-N watchlist (default N=10, was 5) by Phase 4 4-key composite (tag count DESC, tag precedence DESC, proximity ASC, ticker ASC).

Deduplication precedence: `aplus > open_position > tag_aware_top_n`. A ticker in multiple tiers is recorded ONCE under the highest-precedence source.

### Verification queries (post-migration)

```sql
-- All chart-scope tickers for the latest completed run, with source
SELECT ticker, source, chart_status
FROM pipeline_chart_targets
WHERE pipeline_run_id = (
    SELECT id FROM pipeline_runs
    WHERE state = 'complete' ORDER BY finished_ts DESC, id DESC LIMIT 1
)
ORDER BY ticker;

-- Distribution of source values across the latest run
SELECT source, COUNT(*) AS cnt
FROM pipeline_chart_targets
WHERE pipeline_run_id = (
    SELECT id FROM pipeline_runs
    WHERE state = 'complete' ORDER BY finished_ts DESC, id DESC LIMIT 1
)
GROUP BY source;
```

### Wall-time monitoring

Each pipeline run logs `chart-step wall-time` if the chart step exceeds soft (60s) or hard (120s) budgets. Search pipeline-run logs for `chart-step wall-time exceeded`. If repeated overrun: dispatch a follow-up to reduce `chart_top_n_watch` from 10 to 5 OR implement tier-based shedding (see spec §A "Future hardening").

### Stop hline omission

Trades with `current_stop = NULL` or `current_stop = 0.0` render WITHOUT a stop hline (post-2026-04-27). Confirm visually if you encounter such a trade — the chart still renders pivot but no stop horizontal line, and the title omits the `stop X.XX` segment.
```

- [ ] **Step 3: Commit**

```bash
git add docs/chart-pattern-flag-v1-manual-verification.md
git commit -m "docs(chart-pattern): Task 9 — post-V2 chart-scope addendum + verification queries"
```

**Acceptance:**
- Doc updated with post-V2 addendum.
- Verification queries continue to work post-migration (the `WHERE state = 'complete'` filter + `ORDER BY finished_ts DESC, id DESC LIMIT 1` mirrors `latest_completed_pipeline_run`).
- No production code touched.

**Adversarial-review watch items:**
- **Append-only edit, not inline-modify.** The doc is an audit-trail artifact for V1; the V2 addendum is purely additive. Reviewer must confirm no V1 content was rewritten.
- **`ORDER BY finished_ts DESC, id DESC` matches `latest_completed_pipeline_run`'s ordering.** A reviewer might catch a discrepancy if the doc query lacks the `id DESC` tiebreaker (Codex R1 Minor 1). Match the helper's exact ordering.

---

### Task 10 — Phase checkpoint

**Spec section:** N/A (process gate).

**Goal:** Run the full fast suite + ruff to confirm no regressions; confirm spec §"Done criteria" each map to a passing test or verifiable behavior in the codebase; tag the working tree as plan-complete.

**Files:** none (verification + commit-message-only checkpoint)

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/
```

Expected: green; no new ruff violations beyond CLAUDE.md baseline (81 pre-existing).

- [ ] **Step 2: Walk the spec's "Test plan" §E**

Each item must point to a passing test:

- Migration `0011` schema_version, CHECK accept/reject, row preservation, index, inventory → Task 1's 6 tests.
- `_step_charts` 3-tier composition, dedup precedence, canonicalization, edge cases → Task 5's 8 tests.
- `latest_completed_pipeline_run`, `PipelineRunBinding`, race-tightening, signature → Task 2's 5 tests + Task 3's 3 chart-scope tests.
- Caller migration tests → Task 3 sub-commit (charts route + open-positions + watchlist).
- Tag-aware sort byte-identity → Task 4's 3 tests.
- Stop-hline omission → Task 6's 4 tests.
- Wall-time monitoring → Task 7's 4 tests.
- Config knob default → Task 8's 1 test.

If ANY item lacks a passing test, return to that task and add coverage before declaring the phase complete.

- [ ] **Step 3: Commit-message-only checkpoint commit (or skip if everything is already committed)**

If all tasks committed individually, no checkpoint commit is needed. If any work was done outside a task (e.g., ruff fix introduced by phase work), commit that as `style(area): Task 10 — ruff cleanup`.

**Acceptance:**
- Full fast suite green (1145 + ~30 new tests).
- Ruff clean (no new violations).
- Each spec §E item maps to a passing test.

**Adversarial-review watch items:**
- **Test-count drift.** CLAUDE.md gotcha: trust pytest output, not the plan's estimate. Confirm fast-suite test count matches reasonable post-task expectations.
- **Spec-coverage gap surface.** If Step 2 reveals a gap, treat as a plan defect — return to the gap-task and add coverage. Do not declare the phase complete with gaps.

---

# Out-of-V2 scope (per spec §F — plan must NOT include)

- Holdings-aware `CHART_REASON_MESSAGES` variant — open-position tier inclusion (Task 3) closes the underlying pain.
- Section-level OOB-refresh-on-stale recovery — cross-cutting; orthogonal.
- Defense-in-depth ticker-format regex on `/charts/{ticker}.png` — independent.
- Lowercase + dotted-symbol canonicalization tests (operator-facing) — independent.
- V1 expanded-row content scope-limit — different scope.
- Test pin for "no completed pipeline run" branch on open-positions expand — covered organically by Task 2 + Task 3 caller migrations.
- Today's `fetcher_failed` chart_targets investigation (yfinance / network operational issue).
- Task 7.3 / 7.4 classifier calibration (chart-pattern flag-v1 follow-up).
- CLI / journal / advisories / Phase 2 (`swing/trades/`, `swing/data/repos/`) code paths — untouched.
- Operator-facing chart-scope-source UI badges ("(open position)", "(A+)").
- Recommendation-table linkage for richer open-position pivot sourcing.
- Backfill of historical `'near_proximity'` rows to `'tag_aware_top_n'`.
- Per-tier N knobs.
- Open-position pin-duration / conditional-inclusion logic (kept always-on).
- Schema migrations beyond 0011.
- Sub-phase timing attribution (deferred per Codex R4 Minor 1).
- `pipeline_runs.charts_wall_time_ms` persisted column (deferred per Codex R3 Major 2).
- Tier-based shedding when wall time projected > soft budget (deferred per spec §A "Future hardening").

---

# Open follow-ups for future dispatches

These are concerns surfaced during plan drafting that are intentionally deferred:

1. **Slow-marked benchmark test for chart-step wall time.** Spec §A "Test instrumentation": "A separate benchmark-only test (skipped in `-m 'not slow'` fast suite; runs on demand via `-m slow` or a dedicated benchmark CI job) that measures real wall time on a representative scope and asserts the typical case is under 60s." This plan implements only the deterministic log-capture mechanism; the slow benchmark is a follow-up dispatch.
2. **`pipeline_runs.charts_wall_time_ms` persisted column.** Per spec §A "Future V2 hardening." If operator builds external alerting / monitoring, persist the wall-time as a queryable signal.
3. **Tier-based shedding.** Per spec §A "Future hardening (deferred to post-V1)." When wall time projected to exceed soft budget mid-step, skip remaining tag_aware_top_n tickers; new `chart_status='skipped_for_budget'` enum value.
4. **Reviewer-checklist hardening.** Per spec §C "Reviewer-checklist hardening (Codex R4 Minor 2)." Add explicit code-review checklist line: "Inspect all new `resolve_chart_scope` call sites; confirm each calls `latest_completed_pipeline_run` ONCE at request handler entry and passes the resulting binding through any downstream multi-call surface." Operator-side process item; not a code change.
5. **Future surfaces composing multiple `resolve_chart_scope` calls in one handler.** Per spec §C "Technical guardrail deferral." When such a surface emerges, the writing-plans phase for THAT surface MUST add explicit tests asserting the binding is shared across calls. Until then, YAGNI.
6. **Filter-intersection alignment between `_sort_watchlist` and `_step_charts`.** Per spec §A "Residual filter-intersection limitation." A separate dispatch could either widen `_step_charts` to include rows with proximity-undefined fallback OR narrow `_sort_watchlist` to only show fully-qualified rows. Not in V2 scope.
7. **Cross-request session pinning.** Inter-request races (different HTTP requests from the same dashboard) are NOT closed by `PipelineRunBinding`. Spec §C "What the binding does NOT close." Future dispatch could add session-state pinning if the inter-request inconsistency proves operator-visible.

---

# References

- Spec: `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md` (4 adversarial Codex rounds → NO_NEW_CRITICAL_MAJOR)
- Brief: `docs/chart-scope-policy-v2-writing-plans-brief.md`
- Predecessor (chart-pattern flag-v1): `docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`
- Predecessor brief (chart-access UX): `docs/chart-pattern-flag-v1-chart-access-ux-brief.md`
- CLAUDE.md gotchas (root) — yfinance rate-limit, HTMX OOB-swap drift, base-layout 5-VM rule, mathtext metacharacters, weather lookup keying.
- Orchestrator-context lessons captured: `docs/orchestrator-context.md` §"Lessons captured" (Phase 1 synthetic-fixture + cfg-injection sensitivity; Phase 2 FK-references + biconditional truth-table; Phase 3 log-line exact-string; Phase 4 compounding-confound + ticker-symmetry; Phase 6 monkeypatch-capture vacuousness + manual visual verification; Tier-1 mathtext fix discipline)
- Existing surfaces touched: `swing/web/chart_scope.py`, `swing/web/routes/charts.py`, `swing/web/view_models/open_positions_row.py`, `swing/web/view_models/watchlist.py`, `swing/web/view_models/dashboard.py`, `swing/pipeline/runner.py:541-595`, `swing/rendering/charts.py`, `swing/config.py`, `swing/data/db.py`
- Migration precedent: `swing/data/migrations/0006_pipeline_chart_linkage.sql`
