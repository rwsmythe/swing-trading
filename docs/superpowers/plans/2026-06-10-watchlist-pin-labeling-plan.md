# Watchlist Pin + Hypothesis-Labeling Effectiveness Implementation Plan (Phase 16 / Arc 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hypothesis labeling effective in the operator's web-first workflow via a per-ticker watchlist **pin** (keeps a ticker fetched + fully evaluated + retained until unpinned) and a **matcher-driven auto-label** (web/CLI entry prefill yields `Broad-watch baseline (watch); failed: …` for watch candidates with no narrow match).

**Architecture:** Five independently-testable units communicating through existing interfaces: (1) additive `watchlist` schema + repo plumbing; (2) a PURE pin-veto in `compute_watchlist_changes`; (3) `_step_evaluate`/`_step_watchlist` universe injection + audit lines; (4) a one-line `include_baseline=True` flip in the entry-prefill; (5) a render-time per-row cohort hint helper consumed by three sites. No matcher logic changes — only two new opt-in *callers*, bounded by an inventory guard. The only schema touch is the additive migration.

**Tech Stack:** Python 3.14, SQLite, FastAPI + HTMX/Jinja2, pytest (`-m "not slow"` fast suite via xdist), ruff. WSL Codex CLI for the adversarial review.

**Source spec (LOCKED, Codex-converged, merged):** [`docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md`](../specs/2026-06-10-watchlist-pin-labeling-design.md). Every task maps to a spec §10 contract — do NOT re-litigate the design.

---

## STEP-0 resolution (frozen for this plan; executing re-verifies at ITS branch time)

- **P0 entry-intent arc has LANDED on main** (`cc9a2b46`, migration `0027_entry_intent`); the live DB is migrated to **v27** (P0 FULLY CLOSED). Confirmed at plan time: `ls swing/data/migrations/*.sql | tail -3` → `0025…`, `0026_broad_watch_baseline.sql`, `0027_entry_intent.sql`. Main HEAD at worktree creation: `46d97f60`.
- **Therefore this arc takes migration `0028` (v27 → v28).** The `#11` version-pin sweep targets **v28**. The backup-gate fires on **strict equality `current_version == 27 AND target_version >= 28`**.
- **Shared-file grounding is POST-P0.** `trade_entry_form.html.j2` + `routes/trades.py` are already at their post-`cc9a2b46` shape on main; this arc adds **no** field to the entry form and **no** route to `routes/trades.py` (the pin route lives in `routes/watchlist.py`), so the "small merge reconciliation with P0" the spec §12 anticipated is already absorbed into this grounding — there is nothing left to reconcile.
- **Executing-phase precondition:** at executing-branch time, re-run `ls swing/data/migrations/*.sql | tail -3`. If a `0028_*.sql` from another lane has appeared, take `0029` and re-target the `#11` sweep + backup gate to `v28 → v29`. (As of this plan, `0028` is free.)

## Arc-6 synergy (verified — no extra plumbing)

Pinned tickers are unioned into `tickers` (`runner.py:1396-1400` seam) **before** the OHLCV fetch loop (`runner.py:1433 for t in tickers:`) and **before** the Arc-6 batched pre-warm (`_prewarm_evaluate_archives(..., candidate_tickers=tickers, …)`, `runner.py:1416-1419`). So a pinned off-screen ticker automatically joins the Arc-6 warm cohort and the serial fetch — **no extra fetch plumbing is required** (spec §3/§5 claim confirmed at HEAD).

---

## File map (decomposition lock-in)

| File | Create/Modify | Responsibility |
|---|---|---|
| `swing/data/migrations/0028_watchlist_pin.sql` | Create | 3 additive `ALTER TABLE watchlist ADD COLUMN` + version bump to 28 |
| `swing/data/db.py` | Modify | `EXPECTED_SCHEMA_VERSION` → 28; `_arc7_watchlist_pin_backup_gate` + registration |
| `swing/data/models.py` | Modify | `WatchlistEntry` gains `pinned`/`pin_note`/`pinned_at` (defaults) |
| `swing/data/repos/watchlist.py` | Modify | SELECTs + `_row_to_entry` widened; `upsert` INSERT widened / DO-UPDATE EXCLUDES pin cols; new `set_watchlist_pin`; `WatchlistEntryNotFoundError` reused |
| `swing/watchlist/service.py` | Modify | `pinned_tickers` kw-only param; `suppressed_removes` lane; veto branch; last_\*-preservation rule (PURE) |
| `swing/pipeline/runner.py` | Modify | `_step_evaluate` pinned-universe injection + audit line + `error_tickers`-vs-`excluded` dedup; `_step_watchlist` plumbs `pinned_tickers` + `run_warnings` + suppressed-remove warnings |
| `swing/recommendations/hypothesis_prefill.py` | Modify | flip the prefill matcher call to `include_baseline=True` (opt-in #1) |
| `swing/web/view_models/watchlist.py` | Modify | shared `cohort_hint_for` helper (LONE hint opt-in) + `WatchlistVM.cohort_hints` + `WatchlistRowVM.cohort_hint` |
| `swing/web/view_models/dashboard.py` | Modify | `DashboardVM.cohort_hints` via FUNCTION-LOCAL import of `cohort_hint_for` |
| `swing/web/routes/watchlist.py` | Modify | `POST /watchlist/{ticker}/pin`; `/row` route passes `cohort_hint` in context |
| `swing/web/templates/partials/watchlist_row.html.j2` | Modify | pin badge in Ticker cell + cohort chip in Tags cell |
| `swing/web/templates/partials/watchlist_expanded.html.j2` | Modify | embedded pin form |
| `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md` | Modify | append the dated §ADDENDUM (verbatim from Arc-7 spec §13) |
| Tests | Create/Modify | the 10 §10 contracts + the migration/backup-gate tests (per task below) |

**NOT touched** (R6 lock — propagate verbatim): `recommendations/hypothesis.py` matcher logic + its two-phase gate; `dashboard.py`'s two `match_candidate_to_hypotheses` call sites (`:540`, `:1061`, stay default `include_baseline=False`); `swing/metrics/tier.py` + the deviation allowlist; the `hypothesis_registry` rows + `hypothesis_status_history`; the shadow engine / temporal log / measurement chain; the 16 historical trade labels; `mistake_tags`/`process_grade`; `build_dashboard`'s OHLCV scope; `swing/trades/`. No new production dependency. Schema: the additive `0028` migration ONLY.

---

## Task ordering (dependency-driven)

1. Migration `0028` + `db.py` version/gate (schema half of #11).
2. Model + repo plumbing (read + write widened in ONE task — #11 atomicity).
3. Pure service veto + last_\*-preservation.
4. Runner injection + audit + dedup + `_step_watchlist` plumbing.
5. Prefill flip + R5 round-trip + label-match contract.
6. `cohort_hint_for` + three render sites + containment + inventory guard.
7. HTMX pin UI (route + templates).
8. §13 addendum to the 0026 spec + full suite + ruff.

---

### Task 1: Migration `0028` + schema version + backup gate

**Files:**
- Create: `swing/data/migrations/0028_watchlist_pin.sql`
- Modify: `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION`; new `_arc7_watchlist_pin_backup_gate`; registration in the migration runner)
- Test: Create `tests/data/test_migration_0028_watchlist_pin.py`; Modify (the #11 sweep) the HEAD-schema-version pins across `tests/data/` (27→28, Step 5b)

**Reference reading before you start:** open `swing/data/migrations/0026_broad_watch_baseline.sql` and `0027_entry_intent.sql` for the exact `BEGIN;…UPDATE schema_version…COMMIT;` shape (#9), and `swing/data/db.py` — find `EXPECTED_SCHEMA_VERSION`, the existing `_phase16_backup_gate` (Arc-1 0025), and how gates are registered/invoked in `run_migrations`. Copy the STRICT-equality clause shape verbatim.

- [ ] **Step 1: Write the migration file**

Create `swing/data/migrations/0028_watchlist_pin.sql`:

```sql
-- Migration 0028: watchlist pin (Phase 16 / Arc 7). ADDITIVE columns only —
-- no table rewrite, no change to existing rows. Explicit BEGIN;...COMMIT; per
-- gotcha #9 (_apply_migration runs executescript in autocommit; 0023-0027 all wrap).
BEGIN;
ALTER TABLE watchlist ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1));
ALTER TABLE watchlist ADD COLUMN pin_note TEXT;
ALTER TABLE watchlist ADD COLUMN pinned_at TEXT;
UPDATE schema_version SET version = 28;
COMMIT;
```

- [ ] **Step 2: Write the failing migration test**

Create `tests/data/test_migration_0028_watchlist_pin.py`. **Mirror `tests/data/test_migration_0027_entry_intent.py` VERBATIM** for the harness — `run_migrations` takes a `sqlite3.Connection` (NOT a path) with keyword-only `target_version`/`backup_dir` (`swing/data/db.py:1267`; Codex R1-Major). Use the exact `_migrate` helper shape from the 0027 test:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _watchlist_pin_backup_gate,
    run_migrations,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def test_expected_schema_version_is_28():
    assert EXPECTED_SCHEMA_VERSION == 28


def test_migrate_to_28_adds_three_pin_columns(tmp_path):
    conn = _migrate(tmp_path, 28)
    assert _current_version(conn) == 28
    cols = {r[1] for r in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
    assert {"pinned", "pin_note", "pinned_at"} <= cols
    # default 0 for an insert that omits pinned:
    conn.execute(
        "INSERT INTO watchlist (ticker, added_date, status, qualification_count, "
        "not_qualified_streak, last_data_asof_date) VALUES "
        "('AAAA','2026-06-10','watch',1,0,'2026-06-10')")
    row = conn.execute("SELECT pinned, pin_note, pinned_at FROM watchlist WHERE ticker='AAAA'").fetchone()
    assert row == (0, None, None)
    # CHECK rejects 2:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE watchlist SET pinned = 2 WHERE ticker='AAAA'")
    conn.close()


def test_backup_gate_fires_strict_on_v27(tmp_path):
    """Mirror 0027's test_backup_gate_fires_strict_on_v26. Per
    feedback_regression_test_arithmetic: fire on current==27, inert on
    current==28 and on a multi-version jump (current==26)."""
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    _watchlist_pin_backup_gate(conn, current_version=28, target_version=28, backup_dir=inert)
    _watchlist_pin_backup_gate(conn, current_version=26, target_version=28, backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    with pytest.raises(MigrationBackupRequiredException):
        _watchlist_pin_backup_gate(conn, current_version=27, target_version=28, backup_dir=fire)


def test_run_migrations_wires_watchlist_pin_gate(tmp_path):
    backups = tmp_path / "v27_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 27); conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=28, backup_dir=backups)
    assert _current_version(conn) == 28
    snaps = list(backups.glob("swing-pre-watchlist-pin-migration-*.db"))
    assert len(snaps) == 1
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 28)
    run_migrations(conn, target_version=28)  # current >= target -> early return
    assert _current_version(conn) == 28
    cols = [r[1] for r in conn.execute("PRAGMA table_info(watchlist)").fetchall()]
    assert cols.count("pinned") == 1  # not double-added
    conn.close()
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/data/test_migration_0028_watchlist_pin.py -v`
Expected: FAIL — `EXPECTED_SCHEMA_VERSION == 27` (not yet bumped); `_watchlist_pin_backup_gate` undefined.

- [ ] **Step 4: Bump `EXPECTED_SCHEMA_VERSION` + add the backup gate in `db.py` (mirror the 0027 architecture EXACTLY)**

Codex R1-Major: `db.py` does NOT have a `_require_backup_snapshot`/`_EXPECTED_TABLES_V27`. The real architecture is: a named expected-tables constant (chained per phase, `db.py:241`), a per-phase `_create_pre_*_migration_backup` helper (`db.py:721` for 0027), a gate function (`db.py:1229` for 0027), and registration in `run_migrations` (`db.py:1357`). **Read `_create_pre_entry_intent_migration_backup` (db.py:721-738) + `_entry_intent_backup_gate` (db.py:1229-1264) and mirror them line-for-line.**

In `swing/data/db.py`:

1. Bump `EXPECTED_SCHEMA_VERSION` from `27` to `28`.

2. Add the expected-tables constant after `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES` (db.py:241). Migration 0028 adds **columns only, no new table**, so the v27 table set equals the pre-0027 set:

```python
# 0028 (watchlist pin) adds columns to `watchlist` only — no new table — so the
# pre-v28 (v27) table set is identical to the entry_intent pre-migration set.
WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES
)
```

3. Add the backup helper after `_create_pre_entry_intent_migration_backup` (db.py:738), mirroring it (only the filename slug changes):

```python
def _create_pre_watchlist_pin_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """watchlist-pin (0028) mirror. SQLite-native Connection.backup() before the
    0028 migration. Backup file ``swing-pre-watchlist-pin-migration-<ISO>.db``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-watchlist-pin-migration-{timestamp}.db"
    src_conn = open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path
```

4. Add the gate after `_entry_intent_backup_gate` (db.py:1264), mirroring it (STRICT equality `current_version == 27 AND target_version >= 28`):

```python
def _watchlist_pin_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """watchlist-pin (0028) backup-before-migrate gate.

    Fires ONLY when ``current_version == 27 AND target_version >= 28`` -- a real
    production v27 DB about to cross v28. STRICT EQUALITY on pre_version per the
    ``pre_version == (target - 1)`` gotcha (NOT ``<=``); multi-version jumps from
    pre-v27 baselines bypass this gate by design.
    """
    if target_version < 28 or current_version != 27:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-watchlist-pin backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_watchlist_pin_migration_backup(
            src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-watchlist-pin backup failed: {exc}"
        ) from exc
```

5. Register it in `run_migrations` immediately after the `_entry_intent_backup_gate(...)` call (db.py:1357):

```python
    _watchlist_pin_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
```

- [ ] **Step 5: Run the new 0028 migration + gate tests**

Run: `python -m pytest tests/data/test_migration_0028_watchlist_pin.py -v`
Expected: PASS (all five — version, columns/CHECK, strict-gate fire/inert, runner-wires-gate, migrate-twice no-op).

- [ ] **Step 5b: The #11 version-pin sweep (ATOMIC with the bump — Codex R6-Major)**

Bumping `EXPECTED_SCHEMA_VERSION` to 28 breaks every existing test that pins the HEAD schema version at 27 — those MUST bump 27→28 in the SAME commit (#11 atomic consistency; the 0025/0026/0027 sweeps are the exact playbook). Enumerate them:

```bash
# All HEAD-schema-version pins (the constant assertion + the ensure_schema/run-to-HEAD walk assertions):
grep -rn "EXPECTED_SCHEMA_VERSION == 27" tests/ --include="*.py"
grep -rn "== 27\b" tests/data/ --include="*.py"
```

**Bump 27 → 28** in these (the set as of this plan — re-run the grep at execution time; the list is stable but verify):
- `assert EXPECTED_SCHEMA_VERSION == 27` → `== 28` in: `tests/data/test_b7_failure_mode_schema.py`, `test_db_v8.py`, `test_migration_0012.py`, `test_migration_0015_finviz_api_calls.py`, `test_migration_0017.py`, `test_migration_0018.py`, `test_migration_0019_atomic_apply.py`, `test_migration_0025_phase16.py`, `test_migration_0026_broad_watch_baseline.py`, `test_migration_0027_entry_intent.py`, `test_no_schema_change_v3.py`, `test_phase13_t3_sb1_prerequisite.py`, `test_temporal_log_migration.py`, `test_v20_migration.py`, `test_v21_migration_trade_backlinks.py`, `test_v23_migration.py`.
- The **walk-to-HEAD** assertions (`version == 27` / `row[0] == 27` / `cur.fetchone()[0] == 27`, where the value comes from `ensure_schema`/a run-to-HEAD) → `== 28`: `test_migration_0010_trade_chart_pattern.py:18`, `test_migration_0013.py:27`, `test_migration_0015_finviz_api_calls.py:18`, `test_migration_0016.py:38`, `test_migration_0017.py:49`, `test_migration_0018.py:70`, `test_migration_0019_atomic_apply.py:70,86`, `test_phase13_t3_sb1_prerequisite.py:199`, `test_v20_migration.py:233,833`, `test_v21_migration_trade_backlinks.py:787`.

**DO NOT touch** (these `== 27` are NOT the HEAD schema version):
- `tests/research/double_bottom_w_backtest/test_io.py:64` + `tests/research/w_bottom_ruleset_comparison/test_io.py:55` — `len(RESULTS_CSV_HEADER) == 27` is a CSV COLUMN COUNT.
- `tests/data/test_migration_0027_entry_intent.py:54,168,170,174,182,183,191,192` — these DELIBERATELY migrate to `target_version=27` and assert `_current_version == 27` (apply-ceiling caps the walk at 27 even with HEAD=28; they still pass). Only line 45 (`EXPECTED_SCHEMA_VERSION == 27`) in that file bumps.
- Any `test_migration_0025_phase16.py` inline COMMENT referencing old ceilings (cosmetic).

**Per `feedback_regression_test_arithmetic`:** for any swept assertion, confirm the value is HEAD-tracking (bumped at each prior migration) vs a deliberate intermediate-version pin — bump only the former. After the sweep, run the data suite:

Run: `python -m pytest tests/data/ -q`
Expected: PASS (the swept pins now read 28; the deliberate intermediate-version tests still pass via apply-ceiling).

- [ ] **Step 6: Commit (the bump + sweep together — #11 atomic)**

```bash
git add swing/data/migrations/0028_watchlist_pin.sql swing/data/db.py tests/data/test_migration_0028_watchlist_pin.py tests/data/
git commit -m "feat(data): migration 0028 — additive watchlist pin columns (schema v28)

Adds nullable pinned/pin_note/pinned_at to watchlist; bumps
EXPECTED_SCHEMA_VERSION to 28; registers the strict-equality v27->v28
backup gate. Sweeps the HEAD-schema-version test pins 27->28 (#11
atomic, the 0025/0026/0027 playbook). ADDITIVE only — no table rewrite."
```

(The `git add tests/data/` stages the swept pins; verify with `git status` that ONLY the version-pin lines changed — `git diff --cached tests/data/ | grep '^[-+]' | grep -v '28\|27'` should be empty of unrelated edits.)

---

### Task 2: Model + repo plumbing (#11 — read + write in one task)

**Files:**
- Modify: `swing/data/models.py` (`WatchlistEntry`, ~L400)
- Modify: `swing/data/repos/watchlist.py` (`upsert_watchlist_entry`, `get_watchlist_entry`, `list_active_watchlist`, `_row_to_entry`; new `set_watchlist_pin`)
- Test: `tests/data/repos/test_watchlist_pin_repo.py`

**Why one task:** read-path mappers (`_row_to_entry`, SELECT column lists) MUST widen in the SAME task as the write-path (`upsert` INSERT list) — the #11 atomic-consistency rule. A schema-version-aware split would desync row shape.

- [ ] **Step 1: Add the three model fields**

In `swing/data/models.py`, `WatchlistEntry` (frozen dataclass at ~L400) — add after the existing fields (defaults so existing construction sites compile unchanged):

```python
    pinned: bool = False
    pin_note: str | None = None
    pinned_at: str | None = None
```

- [ ] **Step 2: Write the failing repo tests**

Create `tests/data/repos/test_watchlist_pin_repo.py`:

```python
import sqlite3

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import (
    WatchlistEntryNotFoundError,
    get_watchlist_entry,
    list_active_watchlist,
    set_watchlist_pin,
    upsert_watchlist_entry,
)


def _conn(tmp_path) -> sqlite3.Connection:
    # run_migrations takes a sqlite3.Connection (NOT a path), keyword-only
    # target_version/backup_dir — mirror the 0027 test harness (Codex R2-Major).
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    return conn


def _entry(ticker: str, **kw) -> WatchlistEntry:
    base = dict(
        ticker=ticker, added_date="2026-06-01", last_qualified_date="2026-06-01",
        status="watch", qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-06-01", entry_target=10.0, initial_stop_target=9.0,
        last_close=10.5, last_pivot=10.0, last_stop=9.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )
    base.update(kw)
    return WatchlistEntry(**base)


def test_row_to_entry_maps_pin_columns(tmp_path):
    conn = _conn(tmp_path)
    try:
        upsert_watchlist_entry(conn, _entry("AAAA"))
        set_watchlist_pin(conn, "AAAA", pinned=True, pin_note="keep me", pinned_at="2026-06-10T12:00:00")
        e = get_watchlist_entry(conn, "AAAA")
        assert e is not None
        assert (e.pinned, e.pin_note, e.pinned_at) == (True, "keep me", "2026-06-10T12:00:00")
        # list path maps too
        listed = {x.ticker: x for x in list_active_watchlist(conn)}
        assert listed["AAAA"].pinned is True
    finally:
        conn.close()


def test_upsert_do_update_EXCLUDES_pin_columns(tmp_path):
    """DISCRIMINATING (regression-test arithmetic): pin a ticker, then upsert a
    nightly entry whose pinned=False/None — the stored pin MUST survive. Under a
    naive ON CONFLICT that includes `pinned=excluded.pinned`, the upsert would
    zero pinned -> this test FAILS. That is the intended tripwire."""
    conn = _conn(tmp_path)
    try:
        upsert_watchlist_entry(conn, _entry("BBBB"))
        set_watchlist_pin(conn, "BBBB", pinned=True, pin_note="hold", pinned_at="2026-06-10T00:00:00")
        # A nightly streak_increment-shaped entry that does NOT know about the pin:
        nightly = _entry("BBBB", not_qualified_streak=1, last_data_asof_date="2026-06-11",
                         pinned=False, pin_note=None, pinned_at=None)
        upsert_watchlist_entry(conn, nightly)
        e = get_watchlist_entry(conn, "BBBB")
        assert e.pinned is True, "pin must survive a nightly upsert (DO UPDATE excludes pin cols)"
        assert e.pin_note == "hold"
        assert e.pinned_at == "2026-06-10T00:00:00"
        # the non-pin fields DID update:
        assert e.not_qualified_streak == 1
        assert e.last_data_asof_date == "2026-06-11"
    finally:
        conn.close()


def test_set_watchlist_pin_404_on_absent_ticker(tmp_path):
    """Codex R2-Minor: UPDATE rowcount authority, no SELECT-first race."""
    conn = _conn(tmp_path)
    try:
        with pytest.raises(WatchlistEntryNotFoundError):
            set_watchlist_pin(conn, "ZZZZ", pinned=True, pin_note=None, pinned_at="2026-06-10T00:00:00")
    finally:
        conn.close()


def test_set_watchlist_pin_unpin_clears_note_and_timestamp(tmp_path):
    conn = _conn(tmp_path)
    try:
        upsert_watchlist_entry(conn, _entry("CCCC"))
        set_watchlist_pin(conn, "CCCC", pinned=True, pin_note="x", pinned_at="2026-06-10T00:00:00")
        set_watchlist_pin(conn, "CCCC", pinned=False, pin_note=None, pinned_at=None)
        e = get_watchlist_entry(conn, "CCCC")
        assert (e.pinned, e.pin_note, e.pinned_at) == (False, None, None)
    finally:
        conn.close()
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/data/repos/test_watchlist_pin_repo.py -v`
Expected: FAIL — `set_watchlist_pin` undefined; `_row_to_entry` does not yet map pin columns.

- [ ] **Step 4: Widen the repo (read + write) + add `set_watchlist_pin`**

In `swing/data/repos/watchlist.py`:

(a) Widen the SELECT column lists in `get_watchlist_entry` AND `list_active_watchlist` to append `, pinned, pin_note, pinned_at` (keep them LAST so positional mapping is append-only):

```sql
SELECT ticker, added_date, last_qualified_date, status, qualification_count,
       not_qualified_streak, last_data_asof_date, entry_target,
       initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
       missing_criteria, notes, pinned, pin_note, pinned_at
FROM watchlist ...
```

(b) Widen `_row_to_entry` to map the three trailing columns (cast `pinned` to bool):

```python
def _row_to_entry(row: tuple) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=row[0], added_date=row[1], last_qualified_date=row[2],
        status=row[3], qualification_count=row[4], not_qualified_streak=row[5],
        last_data_asof_date=row[6], entry_target=row[7], initial_stop_target=row[8],
        last_close=row[9], last_pivot=row[10], last_stop=row[11], last_adr_pct=row[12],
        missing_criteria=row[13], notes=row[14],
        pinned=bool(row[15]), pin_note=row[16], pinned_at=row[17],
    )
```

(Confirm the existing positional indices against the file before editing — match the current mapper's index base; append 15/16/17.)

(c) Widen `upsert_watchlist_entry`'s INSERT column-list + VALUES to write the three columns (fresh adds carry `pinned`/`pin_note`/`pinned_at` from the entry — defaults `False`/`None`/`None`), and **leave the `ON CONFLICT(ticker) DO UPDATE SET` list UNCHANGED** (it MUST NOT include the pin columns — operator-owned, preserved across nightly upserts, identical to the FROZEN `entry_target`/`initial_stop_target` treatment):

```python
INSERT INTO watchlist
    (ticker, added_date, last_qualified_date, status, qualification_count,
     not_qualified_streak, last_data_asof_date, entry_target,
     initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
     missing_criteria, notes, pinned, pin_note, pinned_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ticker) DO UPDATE SET
    last_qualified_date = excluded.last_qualified_date,
    status = excluded.status,
    qualification_count = excluded.qualification_count,
    not_qualified_streak = excluded.not_qualified_streak,
    last_data_asof_date = excluded.last_data_asof_date,
    last_close = excluded.last_close,
    last_pivot = excluded.last_pivot,
    last_stop = excluded.last_stop,
    last_adr_pct = excluded.last_adr_pct,
    missing_criteria = excluded.missing_criteria,
    notes = excluded.notes
    -- entry_target / initial_stop_target / pinned / pin_note / pinned_at
    -- are FROZEN/operator-owned — never overwritten by a nightly upsert.
```

Add the three values to the params tuple (in column order):

```python
(e.ticker, ..., e.missing_criteria, e.notes,
 1 if e.pinned else 0, e.pin_note, e.pinned_at),
```

(d) Add the writer (rowcount authority — NO SELECT-first; `WatchlistEntryNotFoundError` already exists in this module):

```python
def set_watchlist_pin(
    conn: sqlite3.Connection, ticker: str, *,
    pinned: bool, pin_note: str | None, pinned_at: str | None,
) -> None:
    """Authoritative pin write. The UPDATE rowcount IS the existence check —
    rowcount != 1 raises (no SELECT-then-UPDATE race; Codex R2-Minor). Caller
    wraps in `with conn:`."""
    cur = conn.execute(
        "UPDATE watchlist SET pinned = ?, pin_note = ?, pinned_at = ? WHERE ticker = ?",
        (1 if pinned else 0, pin_note, pinned_at, ticker),
    )
    if cur.rowcount != 1:
        raise WatchlistEntryNotFoundError(ticker)
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/data/repos/test_watchlist_pin_repo.py -v`
Expected: PASS (all four).

- [ ] **Step 6: Commit**

```bash
git add swing/data/models.py swing/data/repos/watchlist.py tests/data/repos/test_watchlist_pin_repo.py
git commit -m "feat(data): watchlist pin model fields + repo plumbing

WatchlistEntry gains pinned/pin_note/pinned_at; SELECTs + _row_to_entry
widened; upsert writes them on INSERT but the DO-UPDATE EXCLUDES them
(operator-owned, frozen across nightly upserts); set_watchlist_pin uses
UPDATE rowcount as the authoritative existence check."
```

---

### Task 3: Pure pin-veto service + last_\*-preservation

**Files:**
- Modify: `swing/watchlist/service.py` (`WatchlistDelta`, `compute_watchlist_changes`)
- Test: `tests/watchlist/test_pin_veto_service.py`

**Stays PURE:** no DB, no I/O. Signature gains a keyword-only `pinned_tickers: frozenset[str] = frozenset()` (default empty → existing callers/tests unaffected).

- [ ] **Step 1: Write the failing service tests (with streak arithmetic both ways)**

Create `tests/watchlist/test_pin_veto_service.py`:

```python
from swing.data.models import Candidate, Criterion, WatchlistEntry
from swing.watchlist.service import AGING_STREAK_THRESHOLD, compute_watchlist_changes


def _failing_candidate(ticker: str, *, bucket="skip", close=12.0) -> Candidate:
    # All stable criteria FAIL → not-qualifies.
    crits = tuple(
        Criterion(criterion_name=n, result="fail", detail="") for n in
        ("prior_trend", "ma_stack_10_20_50", "ma_short_rising", "adr",
         "pullback", "orderliness", "risk_feasibility")
    )
    return Candidate(
        ticker=ticker, bucket=bucket, close=close, pivot=None, initial_stop=None,
        adr_pct=2.0, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes="", criteria=crits,
    )


def _prior(ticker: str, *, streak: int, pinned: bool, **kw) -> WatchlistEntry:
    base = dict(
        ticker=ticker, added_date="2026-06-01", last_qualified_date="2026-06-05",
        status="watch", qualification_count=2, not_qualified_streak=streak,
        last_data_asof_date="2026-06-09", entry_target=10.0, initial_stop_target=9.0,
        last_close=10.5, last_pivot=10.0, last_stop=9.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None, pinned=pinned, pin_note=("n" if pinned else None),
        pinned_at=("2026-06-10T00:00:00" if pinned else None),
    )
    base.update(kw)
    return WatchlistEntry(**base)


def test_pinned_ticker_vetoes_age_off_and_keeps_streak_honest():
    """DISCRIMINATING: prior streak=2, threshold=3, candidate fails → new_streak=3.
    PINNED: zero removes; ONE streak_increment carrying not_qualified_streak==3
    (NOT frozen at 2); ONE suppressed_removes entry. A veto that froze the streak
    would yield streak==2 (or no increment) → this assertion FAILS it."""
    assert AGING_STREAK_THRESHOLD == 3
    prior = _prior("PINP", streak=2, pinned=True)
    cand = _failing_candidate("PINP")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset({"PINP"}),
    )
    assert delta.removes == []
    assert len(delta.streak_increments) == 1
    assert delta.streak_increments[0].not_qualified_streak == 3
    assert delta.streak_increments[0].pinned is True
    assert len(delta.suppressed_removes) == 1
    assert delta.suppressed_removes[0].ticker == "PINP"


def test_unpinned_same_setup_ages_off():
    """Same streak=2 + failing candidate, but NOT pinned → removes fires,
    streak_increments empty. Proves the test distinguishes the veto."""
    prior = _prior("UNPN", streak=2, pinned=False)
    cand = _failing_candidate("UNPN")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset(),
    )
    assert len(delta.removes) == 1
    assert delta.removes[0].ticker == "UNPN"
    assert delta.streak_increments == []
    assert delta.suppressed_removes == []


def test_pinned_below_threshold_is_ordinary_streak_increment():
    """streak=0 → new_streak=1 < 3 → ordinary streak_increment, no suppression,
    pin threaded through."""
    prior = _prior("LOWP", streak=0, pinned=True)
    cand = _failing_candidate("LOWP")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset({"LOWP"}),
    )
    assert delta.suppressed_removes == []
    assert delta.removes == []
    assert delta.streak_increments[0].not_qualified_streak == 1
    assert delta.streak_increments[0].pinned is True


def test_error_candidate_preserves_last_values_and_missing_criteria():
    """Codex R1-Critical / F6: a pinned ticker whose candidate is bucket='error'
    (close=None, empty criteria) must NOT blank last_close/last_pivot/last_stop/
    last_adr_pct/missing_criteria — they carry forward from `existing`."""
    prior = _prior("DEAD", streak=1, pinned=True, last_close=22.2, last_pivot=21.0,
                   last_stop=19.5, last_adr_pct=4.1, missing_criteria="tightness")
    err_cand = Candidate(
        ticker="DEAD", bucket="error", close=None, pivot=None, initial_stop=None,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
    )
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[err_cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset({"DEAD"}),
    )
    inc = delta.streak_increments[0]
    assert inc.not_qualified_streak == 2          # streak still increments under the veto
    assert inc.last_close == 22.2                 # NOT None
    assert inc.last_pivot == 21.0
    assert inc.last_stop == 19.5
    assert inc.last_adr_pct == 4.1
    assert inc.missing_criteria == "tightness"    # NOT the synthetic all-missing set


def test_default_empty_pinned_tickers_keeps_legacy_behavior():
    """No pinned_tickers arg → identical to today: streak=2 + fail → removes."""
    prior = _prior("LEGC", streak=2, pinned=False)
    cand = _failing_candidate("LEGC")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
    )
    assert len(delta.removes) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/watchlist/test_pin_veto_service.py -v`
Expected: FAIL — `compute_watchlist_changes` has no `pinned_tickers` kwarg; `WatchlistDelta` has no `suppressed_removes`.

- [ ] **Step 3: Implement the veto + preservation (PURE)**

In `swing/watchlist/service.py`:

(a) Add the audit lane to `WatchlistDelta`:

```python
@dataclass(frozen=True)
class WatchlistDelta:
    adds: list[WatchlistEntry] = field(default_factory=list)
    requalifies: list[WatchlistEntry] = field(default_factory=list)
    streak_increments: list[WatchlistEntry] = field(default_factory=list)
    removes: list[WatchlistArchiveEntry] = field(default_factory=list)
    suppressed_removes: list[WatchlistArchiveEntry] = field(default_factory=list)
```

(b) Add a small helper near `_missing_dynamic` to centralise the F6 carry-forward decision:

```python
def _has_fresh_price(c: Candidate) -> bool:
    """A not-qualifies candidate carries no usable price data when it is an
    error bucket or has no close (F6 / Codex R1-Critical). Such a candidate
    must NOT overwrite last_*/missing_criteria — carry `existing` forward."""
    return c.bucket != "error" and c.close is not None
```

(c) Add the keyword-only param:

```python
def compute_watchlist_changes(
    *, prior: Iterable[WatchlistEntry], today_candidates: Iterable[Candidate],
    data_asof_date: str, pinned_tickers: frozenset[str] = frozenset(),
) -> WatchlistDelta:
```

(d) Rewrite the not-qualifies branch (replaces the current `else:` block at L123-150). The pin fields thread through every constructed entry; the last_\*/missing_criteria carry forward when no fresh price:

```python
        else:
            if existing is None:
                continue
            new_streak = existing.not_qualified_streak + 1
            fresh = _has_fresh_price(candidate)
            # F6 / R1-Critical: degraded candidate carries forward prior values.
            last_close = candidate.close if fresh else existing.last_close
            last_pivot = candidate.pivot if fresh else existing.last_pivot
            last_stop = candidate.initial_stop if fresh else existing.last_stop
            last_adr_pct = candidate.adr_pct if fresh else existing.last_adr_pct
            missing = _missing_dynamic(candidate) if fresh else existing.missing_criteria

            if new_streak >= AGING_STREAK_THRESHOLD:
                archive = WatchlistArchiveEntry(
                    id=None, ticker=ticker, added_date=existing.added_date,
                    removed_date=data_asof_date,
                    reason=f"aged out (failed stable {new_streak} consecutive runs)",
                    qualification_count=existing.qualification_count,
                    last_data_asof_date=data_asof_date,
                    notes=existing.notes,
                )
                if ticker in pinned_tickers:
                    # Pin vetoes the age-off. Keep the streak HONEST (R2: streak
                    # counting continues) by persisting the incremented streak,
                    # AND record the suppression for audit (#27 — see _step_watchlist).
                    delta.suppressed_removes.append(archive)
                    delta.streak_increments.append(WatchlistEntry(
                        ticker=ticker, added_date=existing.added_date,
                        last_qualified_date=existing.last_qualified_date,
                        status=existing.status,
                        qualification_count=existing.qualification_count,
                        not_qualified_streak=new_streak,
                        last_data_asof_date=data_asof_date,
                        entry_target=existing.entry_target,
                        initial_stop_target=existing.initial_stop_target,
                        last_close=last_close, last_pivot=last_pivot,
                        last_stop=last_stop, last_adr_pct=last_adr_pct,
                        missing_criteria=missing, notes=existing.notes,
                        pinned=True, pin_note=existing.pin_note,
                        pinned_at=existing.pinned_at,
                    ))
                else:
                    delta.removes.append(archive)
            else:
                delta.streak_increments.append(WatchlistEntry(
                    ticker=ticker, added_date=existing.added_date,
                    last_qualified_date=existing.last_qualified_date,
                    status=existing.status,
                    qualification_count=existing.qualification_count,
                    not_qualified_streak=new_streak,
                    last_data_asof_date=data_asof_date,
                    entry_target=existing.entry_target,
                    initial_stop_target=existing.initial_stop_target,
                    last_close=last_close, last_pivot=last_pivot,
                    last_stop=last_stop, last_adr_pct=last_adr_pct,
                    missing_criteria=missing, notes=existing.notes,
                    pinned=existing.pinned, pin_note=existing.pin_note,
                    pinned_at=existing.pinned_at,
                ))
```

(e) Thread the pin fields through the `adds` (→ `pinned=False`, defaults) and `requalifies` (→ copied from `existing`) branches as well, so a requalify never silently clears a pin. For `adds` the dataclass defaults already give `pinned=False`; for `requalifies` add `pinned=existing.pinned, pin_note=existing.pin_note, pinned_at=existing.pinned_at` to the `WatchlistEntry(...)` constructor. (Qualifying candidates always have fresh price — `candidate.pivot is None` is already guarded at L91 — so the F6 rule only bites the not-qualifies path; leave the qualify branch's `last_*` as the candidate values.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/watchlist/test_pin_veto_service.py -v`
Expected: PASS (all six).

- [ ] **Step 5: Run the existing watchlist-service suite (no regression)**

Run: `python -m pytest tests/watchlist/ -q`
Expected: PASS — the default `pinned_tickers=frozenset()` keeps legacy callers/tests unchanged.

- [ ] **Step 6: Commit**

```bash
git add swing/watchlist/service.py tests/watchlist/test_pin_veto_service.py
git commit -m "feat(watchlist): pure pin-veto + F6 last-value preservation

compute_watchlist_changes gains keyword-only pinned_tickers (default
empty). A pinned removal-grade ticker diverts to a streak_increment
(streak kept honest) + a suppressed_removes audit lane instead of a
removes row. Degraded (error/None) not-qualifies candidates carry
existing last_*/missing_criteria forward (F6, Codex R1-Critical).
Stays a pure function."
```

---

### Task 4: Runner injection + audit line + dedup + `_step_watchlist` plumbing

**Files:**
- Modify: `swing/pipeline/runner.py` (`_step_evaluate` ~L1396-1521; `_step_watchlist` ~L1565-1589; the `_step_watchlist` call site ~L861)
- Test: `tests/pipeline/test_step_evaluate_pin_injection.py`, `tests/pipeline/test_step_watchlist_pin_warnings.py`

**Reference reading:** re-read `runner.py:1389-1521` (the held-ticker seam, the OHLCV loop, the `excluded`/`error_tickers` candidate-assembly loops) and `runner.py:1565-1589` (`_step_watchlist`). The injection seam is RIGHT AFTER the `held_tickers` union (L1396-1400). `_step_evaluate` already accepts `run_warnings`; `_step_watchlist` does NOT — add it.

- [ ] **Step 1: Write the failing pin-injection test**

Create `tests/pipeline/test_step_evaluate_pin_injection.py`. This is a focused unit test on the assembly logic — prefer a test that drives `_step_evaluate` with stubbed `fetcher`/`universe`, OR (simpler + more robust) a test asserting the assembled candidate set. Look at the existing `tests/pipeline/` evaluate tests for the established harness (stub fetcher + a temp DB seeded with a pinned watchlist row + an open trade). The discriminating assertions:

```python
# Pseudocode-precise — adapt to the existing _step_evaluate test harness shape.
def test_pinned_offscreen_ticker_is_evaluated_not_excluded(harness):
    """A pinned ticker NOT on the finviz screen and NOT held is unioned into
    the eval universe and flows through evaluate_batch → a REAL candidate
    (bucket in watch/skip/aplus or error), NOT 'excluded'."""
    harness.seed_watchlist_pin("PINX", pinned=True)         # off-screen, not held
    harness.finviz_screen(["AAAA", "BBBB"])                 # PINX absent
    run_warnings = []
    candidates = harness.run_step_evaluate(run_warnings=run_warnings)
    by = {c.ticker: c for c in candidates}
    assert "PINX" in by
    assert by["PINX"].bucket != "excluded"                  # evaluated, not excluded
    # audit line emitted for the off-screen injection:
    pin_lines = [w for w in run_warnings if w.get("kind") == "pin_injection"]
    assert len(pin_lines) == 1
    assert pin_lines[0]["count"] == 1
    assert "PINX" in pin_lines[0]["tickers"]


def test_pinned_held_ticker_stays_excluded(harness):
    """A pinned ticker that is ALSO an open trade stays excluded (held wins);
    it is already retained by the open-trade injection — NOT listed in the
    pin-injection audit (it is held-native / screen-native)."""
    harness.seed_open_trade("HELD")
    harness.seed_watchlist_pin("HELD", pinned=True)
    harness.finviz_screen(["AAAA"])
    run_warnings = []
    candidates = harness.run_step_evaluate(run_warnings=run_warnings)
    by = {c.ticker: c for c in candidates}
    assert by["HELD"].bucket == "excluded"
    pin_lines = [w for w in run_warnings if w.get("kind") == "pin_injection"]
    # HELD was already in `seen` via held_tickers → not an off-screen injection:
    assert all("HELD" not in w["tickers"] for w in pin_lines)


def test_held_and_fetch_failing_ticker_yields_exactly_one_candidate(harness):
    """Codex R1-Major dedup: a ticker both held (in excluded) AND fetch-failing
    yields EXACTLY ONE candidates row (the excluded one), not a duplicate error
    row. Under no dedup, error_tickers re-appends it -> 2 rows."""
    harness.seed_open_trade("FAILH")
    harness.fetch_fails_for(["FAILH"])
    harness.finviz_screen(["AAAA"])
    candidates = harness.run_step_evaluate(run_warnings=[])
    failh_rows = [c for c in candidates if c.ticker == "FAILH"]
    assert len(failh_rows) == 1
    assert failh_rows[0].bucket == "excluded"
```

(If the existing harness cannot express `seed_watchlist_pin`/`fetch_fails_for`, build the minimal helpers in the test module against a temp DB + a stub fetcher whose `.get(t)` raises for the fail set. Use the closest existing `_step_evaluate` test as the template — do NOT invent a parallel harness.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/pipeline/test_step_evaluate_pin_injection.py -v`
Expected: FAIL — no pin injection; the held+error dedup not present (2 rows); no audit line.

- [ ] **Step 3: Implement the `_step_evaluate` injection + dedup + audit**

In `swing/pipeline/runner.py`, immediately AFTER the `held_tickers` union block (after L1400, before the `_warm_pipeline_marketdata` call), add the pinned-universe injection:

```python
    # Arc 7: union PINNED watchlist tickers into the evaluated universe so a
    # name the operator is tracking stays fetched + fully evaluated even when it
    # has fallen off the finviz screen. Unlike held tickers (added to `excluded`
    # below → close-only), pinned tickers flow through evaluate_batch and get a
    # REAL criteria/bucket/streak every night. A pinned ticker already in `seen`
    # (screen-native or held) is NOT re-injected.
    pin_conn = connect(cfg.paths.db_path)
    try:
        pinned_eval_tickers = sorted({
            e.ticker.upper() for e in list_active_watchlist(pin_conn) if e.pinned
        })
    finally:
        pin_conn.close()
    injected_pins = [t for t in pinned_eval_tickers if t not in seen]
    for t in injected_pins:
        tickers.append(t)
        seen.add(t)
    if injected_pins and run_warnings is not None:
        run_warnings.append({
            "step": "evaluate", "kind": "pin_injection",
            "count": len(injected_pins), "tickers": injected_pins,
        })
```

(`list_active_watchlist` is already imported in `runner.py` — confirm; if not, add it to the existing `from swing.data.repos.watchlist import …`.)

Then, in the candidate-assembly section, de-dupe `error_tickers` against `excluded` BEFORE the error-append loop (Codex R1-Major). Locate the `for t in error_tickers:` loop (~L1514) and insert immediately before it:

```python
    # Codex R1-Major: a held/blocklisted ticker (in `excluded`) whose fetch also
    # failed lands in error_tickers too; compute_watchlist_changes collapses
    # today_candidates last-write-wins, so the error row (appended last) would
    # win and blank the excluded row. De-dupe so an excluded ticker never also
    # emits an error candidate. A pinned-but-NOT-held failing ticker is NOT in
    # `excluded` → it still gets its single error candidate (the §5.1 path).
    error_tickers = [t for t in error_tickers if t not in excluded]
    for t in error_tickers:
        candidates.append(Candidate(
            ...  # unchanged
        ))
```

**Important:** `excluded` is defined at L1481 (`excluded = set(...) | held_set`), AFTER the OHLCV loop that builds `error_tickers` but BEFORE the error-append loop — so the dedup line has `excluded` in scope. Confirm by reading; place the dedup AFTER L1481 and before L1514. (Leave `error_count=len(error_tickers)` at L1549 reading the de-duped list — the count then reflects the actual emitted error candidates; this is correct.)

- [ ] **Step 4: Implement `_step_watchlist` plumbing (pinned_tickers + warnings)**

(a) At the call site (~L861), pass `run_warnings`:

```python
                _step_watchlist(cfg=cfg, eval_run_id=eval_run_id,
                                data_asof_date=lease_data_asof(cfg, lease),
                                lease=lease, run_warnings=run_warnings)
```

(b) Update `_step_watchlist` (L1565) to accept `run_warnings`, derive `pinned_tickers` from `prior`, pass it to the service, and emit the suppressed-remove warnings (#27 — warnings, NOT a phantom archive row; archiving a suppressed remove would DELETE the live row):

```python
def _step_watchlist(
    *, cfg, eval_run_id: int, data_asof_date: str, lease: Lease,
    run_warnings: list[dict] | None = None,
) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    read_conn = connect(cfg.paths.db_path)
    try:
        prior = list_active_watchlist(read_conn)
        candidates = fetch_candidates_for_run(read_conn, eval_run_id)
    finally:
        read_conn.close()
    pinned_tickers = frozenset(e.ticker for e in prior if e.pinned)
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=candidates,
        data_asof_date=data_asof_date, pinned_tickers=pinned_tickers,
    )
    with lease.fenced_write() as conn:
        for entry in delta.adds:
            upsert_watchlist_entry(conn, entry)
        for entry in delta.requalifies:
            upsert_watchlist_entry(conn, entry)
        for entry in delta.streak_increments:
            upsert_watchlist_entry(conn, entry)
        for archive in delta.removes:
            archive_watchlist_entry(conn, archive)
    # #27: a suppressed removal is NOT archived (that would delete the live row);
    # emit a per-ticker run-warning so the pin veto is auditable, not silent.
    if run_warnings is not None:
        for sup in delta.suppressed_removes:
            run_warnings.append({
                "step": "watchlist", "kind": "pin_suppressed_removal",
                "ticker": sup.ticker,
                "streak": int(sup.reason.split()[-3]) if sup.reason else None,
                "detail": "pin prevented age-off",
            })
```

(The `streak` extraction is cosmetic; if brittle, carry the streak on the archive's `reason` string only and emit `"detail": sup.reason`. Keep it simple — the load-bearing part is that a warning is emitted per suppressed ticker.)

- [ ] **Step 5: Write the `_step_watchlist` suppressed-warning test**

Create `tests/pipeline/test_step_watchlist_pin_warnings.py`:

```python
def test_step_watchlist_emits_suppressed_removal_warning(harness):
    """A pinned ticker at removal-grade streak produces a pin_suppressed_removal
    run-warning and NO watchlist_archive row (the live row survives)."""
    harness.seed_watchlist("KEEP", streak=2, pinned=True)
    harness.seed_candidates_failing(["KEEP"])             # → new_streak=3, veto
    run_warnings = []
    harness.run_step_watchlist(run_warnings=run_warnings)
    sup = [w for w in run_warnings if w.get("kind") == "pin_suppressed_removal"]
    assert len(sup) == 1 and sup[0]["ticker"] == "KEEP"
    assert harness.watchlist_has("KEEP")                  # not archived
    assert harness.archive_count("KEEP") == 0
    assert harness.watchlist_streak("KEEP") == 3          # streak still advanced
```

(Adapt to the existing `_step_watchlist` test harness; reuse a temp DB seeded via the repo + `insert_candidates`.)

- [ ] **Step 6: Run both pipeline tests + the existing pipeline suite**

Run: `python -m pytest tests/pipeline/test_step_evaluate_pin_injection.py tests/pipeline/test_step_watchlist_pin_warnings.py -v`
Expected: PASS.
Run: `python -m pytest tests/pipeline/ -q`
Expected: PASS (no regression from the new `run_warnings` param / dedup).

- [ ] **Step 7: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_evaluate_pin_injection.py tests/pipeline/test_step_watchlist_pin_warnings.py
git commit -m "feat(pipeline): inject pinned tickers into the eval universe + audit

_step_evaluate unions pinned watchlist tickers into the fetch+eval set
(off-screen pins get a real bucket; held/blocklisted pins stay excluded),
emits a pin_injection run-warning, and de-dupes error_tickers vs excluded
so a held+failing ticker yields exactly one candidate (Codex R1-Major).
_step_watchlist passes pinned_tickers to the service and emits per-ticker
pin_suppressed_removal warnings instead of archiving (#27)."
```

---

### Task 5: Prefill `include_baseline=True` flip + R5 round-trip + label-match contract

**Files:**
- Modify: `swing/recommendations/hypothesis_prefill.py` (the matcher call, ~L55)
- Test: `tests/recommendations/test_prefill_broad_watch.py`, `tests/metrics/test_label_match_broad_watch_contract.py`, `tests/web/test_routes/test_trade_entry_broad_watch_round_trip.py`

- [ ] **Step 1: Write the label-match contract test (opt-in site #1 downstream guarantee)**

Create `tests/metrics/test_label_match_broad_watch_contract.py`:

```python
import pytest

from swing.metrics.label_match import label_matches_hypothesis

BROAD = "Broad-watch baseline"
NARROW_NAMES = [  # the four narrow registry names — read them from the live registry seed
    # e.g. "H1 ...", "H2 ...", "H3 ...", "H4 ..."
]


def test_descriptive_label_matches_broad_watch():
    assert label_matches_hypothesis("Broad-watch baseline (watch); failed: tightness", BROAD) is True


@pytest.mark.parametrize("name", NARROW_NAMES)
def test_descriptive_label_does_not_match_narrow(name):
    assert label_matches_hypothesis("Broad-watch baseline (watch); failed: tightness", name) is False
    # and a narrow descriptive label does not match Broad-watch:
    assert label_matches_hypothesis(f"{name} (watch); failed: x", BROAD) is False
```

(Populate `NARROW_NAMES` from the registry seed used in tests — find the fixture/seed the existing hypothesis tests use; the 0026 spec §6 already proved no prefix collision, this re-asserts at the persisted-label layer.)

- [ ] **Step 2: Write the prefill test (produces the broad-watch label for a watch candidate)**

Create `tests/recommendations/test_prefill_broad_watch.py`:

```python
def test_prefill_returns_broad_watch_for_watch_candidate(harness):
    """A pure-watch candidate (no narrow match) + an active Broad-watch registry
    row → lookup_active_recommendation_label returns 'Broad-watch baseline
    (watch); failed: …'. Under include_baseline=False (the old default) it
    returns None — this is the effectiveness fix."""
    label = harness.lookup_label_for_watch_candidate("WCH")
    assert label is not None
    assert label.startswith("Broad-watch baseline")


def test_prefill_returns_narrow_label_when_narrow_matches(harness):
    """Narrow-first is structural (matcher two-phase gate): a candidate fitting
    a narrow hypothesis still prefills the narrow label, not broad-watch."""
    label = harness.lookup_label_for_narrow_candidate("NAR")
    assert label is not None
    assert not label.startswith("Broad-watch baseline")
```

(Reuse the existing `hypothesis_prefill` test harness — find `tests/recommendations/test_hypothesis_prefill*.py`; it already seeds a completed run + candidates + registry. Add a pure-watch candidate to it.)

- [ ] **Step 3: Run to verify both fail**

Run: `python -m pytest tests/recommendations/test_prefill_broad_watch.py tests/metrics/test_label_match_broad_watch_contract.py -v`
Expected: prefill test FAILS (returns `None` under the default `include_baseline=False`); the label-match contract may already pass (it tests existing `label_match` behavior) — that's fine, it is a guard.

- [ ] **Step 4: Flip the one line**

In `swing/recommendations/hypothesis_prefill.py`, the matcher call (currently `match_candidate_to_hypotheses(cand, registry=registry)`):

```python
    matches = match_candidate_to_hypotheses(cand, registry=registry, include_baseline=True)
```

Everything downstream is unchanged: `_descriptive_label` emits `Broad-watch baseline (watch); failed: <criteria>`; `prioritize_recommendations` ranks the single match first; the entry-form VM renders it into the display span + hidden input; the POST persists via `canonicalize_hypothesis_label`.

- [ ] **Step 5: Write the R5 soft-warn / force round-trip regression**

Create `tests/web/test_routes/test_trade_entry_broad_watch_round_trip.py`. **CLONE the existing, proven test `tests/web/test_routes/test_trade_entry_hypothesis_thread.py`** — specifically `test_post_entry_soft_warn_round_trip_via_fragment_faithful_resubmit` (its lines ~210-312). Reuse its real helpers verbatim: `full_phase7_entry_payload` (`tests.web.conftest`), `_read_persisted_hypothesis_label(db_path, ticker)`, and `_parse_hidden_inputs(html)` (the regex hidden-input extractor). The substitutions: (a) seed a **watch**-bucket candidate (clone its `_seed_aplus_pipeline` but `bucket='watch'`, criteria failing the dynamic set so the descriptive label has a `failed:` suffix) for ticker `WCH` PLUS an ACTIVE `Broad-watch baseline` registry row; (b) the expected value is the SERVER-RESOLVED broad-watch label.

**Architecture note the test MUST honour (Codex R5-Major):** the label is server-stamped at **form render** by `build_entry_form_vm` and exposed in the GET `/trades/entry/form?ticker=WCH` form's hidden `hypothesis_label` input. `POST /trades/entry` does NOT re-resolve — it TRUSTS the submitted `hypothesis_label: Form("")` and persists `hypothesis_label or None` (`routes/trades.py:490`). So the browser-faithful flow is **GET the form → read the stamped hidden value → thread THAT value into the POST**. (This is exactly the snapshot-trust model the cited test exercises; R3 changes only what the GET render resolves.) Concrete bodies (no placeholders):

```python
import re
from fastapi.testclient import TestClient
from swing.web.app import create_app
from tests.web.conftest import full_phase7_entry_payload
# clone _seed_watch_pipeline + _seed_active_broad_watch_registry_row + the
# _read_persisted_hypothesis_label / _parse_hidden_inputs helpers from
# test_trade_entry_hypothesis_thread.py (do NOT re-derive — copy them).

BROAD_PREFIX = "Broad-watch baseline"


def _rendered_hypothesis_label(client, ticker: str) -> str:
    html = client.get(f"/trades/entry/form?ticker={ticker}").text   # GET route: trades.py:400
    m = re.search(r'name="hypothesis_label"\s+value="([^"]*)"', html)
    assert m, "entry form must render a hidden hypothesis_label input"
    return m.group(1)


def test_entry_form_server_stamps_broad_watch_label(seeded_db, monkeypatch):
    """Form render server-stamps the broad-watch label into the hidden input
    (the effectiveness fix; prefill now opts in). Under the old default the value
    would be empty -> discriminating."""
    cfg, cfg_path = seeded_db
    _seed_watch_pipeline(cfg.paths.db_path, "WCH")
    _seed_active_broad_watch_registry_row(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        label = _rendered_hypothesis_label(client, "WCH")
    assert label.startswith(BROAD_PREFIX), (
        f"entry form must server-stamp the broad-watch label; got {label!r}")


def test_broad_watch_label_persists_through_soft_warn_force_resubmit(seeded_db, monkeypatch):
    """The server-stamped broad-watch label survives the soft-warn confirm +
    force=true resubmit (R5 hidden-anchor family). Mirrors
    test_post_entry_soft_warn_round_trip_via_fragment_faithful_resubmit, watch
    substitution. The POST threads the GET-rendered hidden value (snapshot trust;
    POST does not re-resolve)."""
    cfg, cfg_path = seeded_db
    _seed_watch_pipeline(cfg.paths.db_path, "WCH")
    _seed_active_broad_watch_registry_row(cfg.paths.db_path)
    _seed_n_open_trades_to_trip_soft_warn(cfg.paths.db_path, n=4)  # default soft_warn_open=4
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        stamped = _rendered_hypothesis_label(client, "WCH")
        assert stamped.startswith(BROAD_PREFIX)
        # First POST threads the stamped label (browser-faithful) → soft-warn fragment.
        payload = full_phase7_entry_payload(ticker="WCH", entry_price=180.0,
                                            shares=10, initial_stop=170.0)
        payload["hypothesis_label"] = stamped
        r_first = client.post("/trades/entry", data=payload, headers={"HX-Request": "true"})
        assert r_first.status_code == 200
        fragment = _parse_hidden_inputs(r_first.text)
        assert fragment.get("hypothesis_label", "").startswith(BROAD_PREFIX), (
            f"soft-warn fragment must carry the broad-watch label; got {fragment!r}")
        fragment["force"] = "true"
        r_second = client.post("/trades/entry", data=fragment, headers={"HX-Request": "true"})
        assert r_second.status_code in (200, 204)
    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "WCH")
    assert persisted is not None and persisted.startswith(BROAD_PREFIX), (
        f"force-resubmit MUST persist the broad-watch label, not NULL; got {persisted!r}")
```

(The `_seed_*` helpers are thin clones of the cited test's seeders — copy them into this module, changing `bucket='aplus'` → `bucket='watch'` and adding the active registry row. Confirm `full_phase7_entry_payload`'s required kwargs + the `seeded_db` fixture in `tests/web/conftest.py`; the GET `/trades/entry/form?ticker=` shape is verified in `tests/web/test_routes/test_entry_form_auto_fill.py:115`.)

- [ ] **Step 6: Run to verify all pass**

Run: `python -m pytest tests/recommendations/test_prefill_broad_watch.py tests/metrics/test_label_match_broad_watch_contract.py tests/web/test_routes/test_trade_entry_broad_watch_round_trip.py -v`
Expected: PASS.

- [ ] **Step 7: Run the existing prefill + trade-entry suites (no regression)**

Run: `python -m pytest tests/recommendations/ tests/web/test_routes/ -q -k "prefill or trade_entry or hypothesis"`
Expected: PASS — narrow-first is structural, so existing narrow-label tests are unaffected.

- [ ] **Step 8: Commit**

```bash
git add swing/recommendations/hypothesis_prefill.py tests/recommendations/test_prefill_broad_watch.py tests/metrics/test_label_match_broad_watch_contract.py tests/web/test_routes/test_trade_entry_broad_watch_round_trip.py
git commit -m "feat(recommendations): entry prefill opts into the broad-watch baseline

lookup_active_recommendation_label now calls the matcher with
include_baseline=True (opt-in site #1) so a web/CLI-entered watch trade
with no narrow match server-stamps 'Broad-watch baseline (watch);
failed: …'. Narrow-first is structural (two-phase gate). The label
round-trips the soft-warn confirm + force=true (R5, hidden-anchor)."
```

---

### Task 6: `cohort_hint_for` helper + three render sites + containment + inventory guard

**Files:**
- Modify: `swing/web/view_models/watchlist.py` (`cohort_hint_for` helper [LONE hint opt-in]; `WatchlistVM.cohort_hints`; `WatchlistRowVM.cohort_hint`; both builders populate via the helper)
- Modify: `swing/web/view_models/dashboard.py` (`DashboardVM.cohort_hints` populated via FUNCTION-LOCAL import of `cohort_hint_for`)
- Modify: `swing/web/routes/watchlist.py` (the `/row` collapse route passes `cohort_hint` in the `TemplateResponse` context)
- Modify: `swing/web/templates/partials/watchlist_row.html.j2` (Step 6b — the `tag-cohort` chip in the Tags cell)
- Modify: `swing/web/templates/watchlist.html.j2` + `swing/web/templates/partials/watchlist_top5_section.html.j2` (Step 6b — the `{% set cohort_hint %}` before the row include)
- Test: `tests/web/view_models/test_cohort_hint.py`, `tests/web/view_models/test_dashboard_broad_watch_containment.py`, `tests/integration/test_include_baseline_inventory_guard.py`

**Reference reading:** open `swing/web/view_models/watchlist.py` and find the existing `pattern_tag`/`pattern_tags` threading (the model at `watchlist.py:23` imports `_pattern_tags` from `dashboard.py`; `WatchlistRowVM.pattern_tag: str | None` at ~L104; `pattern_tags` field at ~L55). Mirror it EXACTLY. Confirm `build_watchlist` already loads `candidates_by_ticker` (the by-ticker candidate map) and `list_hypotheses` is importable.

- [ ] **Step 1: Write the inventory guard test (TRIPWIRE — exactly 3 literal opt-in sites)**

Create `tests/integration/test_include_baseline_inventory_guard.py`:

```python
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]   # adjust depth to repo root

EXPECTED_OPT_IN_FILES = {
    "swing/recommendations/hypothesis_prefill.py",
    "swing/web/view_models/watchlist.py",
    "research/harness/shadow_expectancy/attribution.py",
}


def test_include_baseline_true_call_sites_are_exactly_three():
    """A NEW literal include_baseline=True must fail this test → forces a
    governance touch (the 0026 §ADDENDUM amendment path). TRIPWIRE only — the
    behavioral containment test (test_dashboard_broad_watch_containment) is the
    load-bearing defense against a transitive opt-in via a shared helper."""
    hits = set()
    for base in ("swing", "research"):
        for p in (REPO / base).rglob("*.py"):
            if "include_baseline=True" in p.read_text(encoding="utf-8"):
                hits.add(p.relative_to(REPO).as_posix())
    assert hits == EXPECTED_OPT_IN_FILES, (
        f"include_baseline=True opt-in set drifted. Found: {sorted(hits)}. "
        f"Add a 0026 §ADDENDUM governance amendment before adding a new opt-in."
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integration/test_include_baseline_inventory_guard.py -v`
Expected: FAIL — only `research/harness/shadow_expectancy/attribution.py` currently has the literal (prefill flipped in Task 5 — so after Task 5 there are 2; this task adds the 3rd in `watchlist.py`). The test goes green only once `cohort_hint_for` (Step 4) lands. (If run right after Task 5, `hits` == {prefill, attribution} → fails until Step 4.)

- [ ] **Step 3: Write the cohort-hint helper + three-site propagation test**

Create `tests/web/view_models/test_cohort_hint.py`:

```python
def test_cohort_hint_for_watch_candidate_returns_broad_watch(registry, watch_candidate):
    from swing.web.view_models.watchlist import cohort_hint_for
    assert cohort_hint_for(watch_candidate, registry) == "broad-watch"


def test_cohort_hint_for_narrow_candidate_returns_narrow_name(registry, narrow_candidate):
    from swing.web.view_models.watchlist import cohort_hint_for
    hint = cohort_hint_for(narrow_candidate, registry)
    assert hint and hint != "broad-watch"


def test_cohort_hint_for_none_candidate_returns_none(registry):
    from swing.web.view_models.watchlist import cohort_hint_for
    assert cohort_hint_for(None, registry) is None


def test_chip_renders_identically_at_all_three_sites(client, seeded_watch_candidate):
    """Codex R2-Major: the chip renders identically at (a) the standalone
    watchlist page, (b) the dashboard top-5 section, (c) the /watchlist/{t}/row
    collapse response — all share watchlist_row.html.j2."""
    with client:
        page = client.get("/watchlist").text
        dash = client.get("/").text
        row = client.get("/watchlist/WCH/row").text
    for body in (page, dash, row):
        assert "tag-cohort" in body
        assert "broad-watch" in body   # the WCH watch candidate's hint
```

(Use the established VM/route test fixtures. Find the existing `pattern_tag` three-site test if one exists and mirror it; otherwise build the fixtures from a seeded completed run + an active broad-watch registry row + a watch candidate for `WCH`.)

- [ ] **Step 4: Implement the helper + VM fields + builder population**

In `swing/web/view_models/watchlist.py`:

(a) Add the shared helper (the LONE `include_baseline=True` for the hint — keeps the inventory guard's literal count at 3 even though two builders call it):

```python
def cohort_hint_for(candidate, registry) -> str | None:
    """Render-time attribution PREVIEW chip: the narrow hypothesis name (abbrev)
    a candidate WOULD attribute as on entry, or 'broad-watch', or None. Read-only
    — surfaces no recommendation row, drives no ranking (does NOT call
    prioritize_recommendations). This is opt-in site #2 (0026 §ADDENDUM)."""
    if candidate is None:
        return None
    from swing.recommendations.hypothesis import match_candidate_to_hypotheses
    matches = match_candidate_to_hypotheses(candidate, registry=registry, include_baseline=True)
    if not matches:
        return None
    return _hint_label(matches[0].hypothesis_name)


def _hint_label(name: str) -> str:
    """Map a matched hypothesis name to a short chip: 'broad-watch' for the
    baseline, else the abbreviated narrow name."""
    if name == "Broad-watch baseline":
        return "broad-watch"
    return name.split()[0] if name else name   # abbreviate to the leading token (e.g. 'H2')
```

(Confirm the matched object's attribute is `.hypothesis_name` — read `match_candidate_to_hypotheses`' return type; adjust if it is `.name`.)

(b) Add `cohort_hints: Mapping[str, str] = field(default_factory=dict)` to `WatchlistVM` and `cohort_hint: str | None = None` to `WatchlistRowVM` (mirror `pattern_tags` / `pattern_tag`).

(c) In `build_watchlist`, load the registry **while `conn` is still open** (it closes at `watchlist.py:202`, and `by_ticker` is built AFTER at `:203` — Codex R1-Major), then compute hints AFTER close from the in-memory registry (registry loaded ONCE per page, not per row):

```python
    # INSIDE the try, before `conn.close()` at watchlist.py:202:
    from swing.data.repos.hypothesis import list_hypotheses
    registry = list_hypotheses(conn)
    # ... existing close happens ...
    # AFTER close, where `by_ticker` is built (watchlist.py:203):
    cohort_hints: dict[str, str] = {}
    for r in rows:
        hint = cohort_hint_for(by_ticker.get(r.ticker), registry)
        if hint:
            cohort_hints[r.ticker] = hint
```

and pass `cohort_hints=cohort_hints` into the `WatchlistVM(...)` construction. For `build_watchlist_row` (the `/row` collapse builder — closes at `watchlist.py:274`, builds `by_ticker` at `:275`), load `registry = list_hypotheses(conn)` before the close too, then after the close set `cohort_hint=cohort_hint_for(by_ticker.get(ticker), registry)` on the `WatchlistRowVM`.

- [ ] **Step 5: Implement the dashboard top-5 population (FUNCTION-LOCAL import — Codex R3)**

In `swing/web/view_models/dashboard.py`:

(a) Add `cohort_hints: Mapping[str, str] = field(default_factory=dict)` to `DashboardVM`. **Do NOT add it to `base.html.j2`'s VM contract** — like `pattern_tags`, it is referenced only inside `watchlist_row.html.j2` via `{% set %}`, so it stays scoped to `DashboardVM` + `WatchlistVM` and does NOT need adding to the other base-layout VMs.

(b) In `build_dashboard`, load the registry **while `conn` is open** (it closes at `dashboard.py:555`; `candidates_by_ticker` is built at `:528` inside the same try). Use a FUNCTION-LOCAL import of `cohort_hint_for` (a module-level `from swing.web.view_models.watchlist import cohort_hint_for` would complete the `dashboard → watchlist → dashboard` import cycle, since `watchlist.py:23` already imports from `dashboard.py` at module level — Codex R3-Major). Compute hints from the in-memory registry + `candidates_by_ticker` AFTER the close:

```python
    # INSIDE the try, before conn.close() at dashboard.py:555:
    from swing.data.repos.hypothesis import list_hypotheses
    _registry = list_hypotheses(conn)
    # ... existing close happens ...
    # AFTER close, compute the top-5 chips from the in-memory registry:
    from swing.web.view_models.watchlist import cohort_hint_for  # function-local: breaks the dashboard<->watchlist cycle
    cohort_hints = {}
    for w in watchlist_top5:                  # the dashboard's top-5 watchlist rows (DashboardVM.watchlist_top5)
        hint = cohort_hint_for(candidates_by_ticker.get(w.ticker), _registry)
        if hint:
            cohort_hints[w.ticker] = hint
```

and pass `cohort_hints=cohort_hints` into the `DashboardVM(...)`. (Confirm the top-5 list variable name in `build_dashboard` — the field is `DashboardVM.watchlist_top5`, `dashboard.py:328`; use whatever local feeds it.) **This does NOT make the dashboard a recommendation opt-in:** the hint is a read-only preview chip, it does not become a `prioritize_recommendations` row, and the dashboard's two `match_candidate_to_hypotheses` calls (`dashboard.py:540`, `:1061`) STAY `include_baseline=False` (untouched — verified by the containment test).

- [ ] **Step 6: Pass `cohort_hint` from the `/row` route**

In `swing/web/routes/watchlist.py`, the `/watchlist/{ticker}/row` collapse route — pass `cohort_hint=row_vm.cohort_hint` in the `TemplateResponse` context (so expand→collapse keeps the chip). Find the existing `TemplateResponse(request, "partials/watchlist_row.html.j2", {...})` and add the key.

- [ ] **Step 6b: Render the cohort-hint chip in the shared template (REQUIRED for the Step-3 three-site test to pass — Codex R2-Major)**

The three-site render test (Step 3) asserts the rendered `tag-cohort` chip, so the template work MUST land in THIS task, not Task 7 (Task 7 owns only the pin badge + pin form). In `swing/web/templates/partials/watchlist_row.html.j2`, in the **Tags cell**, after the existing `pattern_tag` guard, add the chip (same guard shape as `pattern_tag` — a guarded scalar, NOT `vm.cohort_hints`, so it stays scoped and needs no base-layout VM change):

```jinja
{% if cohort_hint is defined and cohort_hint %}<span class="tag tag-cohort">{{ cohort_hint }}</span>{% endif %}
```

The page templates set `cohort_hint` before the `{% include "partials/watchlist_row.html.j2" %}` — confirm `watchlist.html.j2` and `watchlist_top5_section.html.j2` do `{% set cohort_hint = vm.cohort_hints.get(w.ticker) %}` before the include (mirror the `pattern_tag` `{% set %}` already there; add it if absent). The `/row` route already passes `cohort_hint` directly (Step 6). This is the cohort feature end-to-end; Task 7's `watchlist_row.html.j2` edit touches a DIFFERENT cell (the Ticker cell badge) and a different commit.

- [ ] **Step 7: Write the dashboard containment regression (BEHAVIORAL — the real defense)**

Create `tests/web/view_models/test_dashboard_broad_watch_containment.py`:

```python
def test_no_broad_watch_rows_reach_hyp_recs_panel(harness):
    """Codex R1-Major BEHAVIORAL containment: with an ACTIVE Broad-watch
    registry row AND a pure-watch candidate (matches no narrow hypothesis),
    ZERO broad-watch rows appear in the dashboard hyp-recs panel /
    prioritize_recommendations output. Proves containment even if the call
    graph changes."""
    vm = harness.build_dashboard_with_active_broad_watch_and_watch_candidate("WCH")
    # The dashboard hyp-recs VM is HypothesisRecommendation; its label field is
    # `suggested_label` (dashboard.py:276), NOT `hypothesis_label` (Codex R4-Major).
    rec_labels = [r.suggested_label for r in harness.hyp_recs_rows(vm)]
    assert not any((lbl or "").startswith("Broad-watch baseline") for lbl in rec_labels)
    # the cohort-hint chip IS present (the preview), proving the hint path is live
    assert vm.cohort_hints.get("WCH") == "broad-watch"


def test_dashboard_matcher_calls_do_not_pass_include_baseline():
    """Companion kwargs assertion (localizes a regression to the call site).
    The two dashboard match_candidate_to_hypotheses calls must NOT pass
    include_baseline (default False)."""
    import ast
    from pathlib import Path
    src = Path("swing/web/view_models/dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(getattr(n, "func", None), "attr", None)) == "match_candidate_to_hypotheses"
    ]
    assert len(calls) == 2
    for c in calls:
        assert not any(k.arg == "include_baseline" for k in c.keywords), \
            "dashboard matcher call must stay include_baseline=False (R6 containment)"
```

(The `harness` fixture is a placeholder for the existing dashboard VM test setup to EXTEND — wire its methods to the real `build_dashboard` + the hyp-recs panel accessor. The behavioral half is the load-bearing one; the AST kwargs half is the localizer.)

- [ ] **Step 8: Run all Task-6 tests + the inventory guard (now green)**

Run: `python -m pytest tests/web/view_models/test_cohort_hint.py tests/web/view_models/test_dashboard_broad_watch_containment.py tests/integration/test_include_baseline_inventory_guard.py -v`
Expected: PASS — the inventory guard now sees exactly the 3 expected files.

- [ ] **Step 9: Run the web view-model suite (no circular-import regression)**

Run: `python -m pytest tests/web/ -q -k "watchlist or dashboard"`
Expected: PASS — and critically, no `ImportError`/circular-import at module load (the function-local import is what prevents it). If the suite errors on import, the import is at module level — move it inside `build_dashboard`.

- [ ] **Step 10: Commit**

```bash
git add swing/web/view_models/watchlist.py swing/web/view_models/dashboard.py swing/web/routes/watchlist.py swing/web/templates/partials/watchlist_row.html.j2 swing/web/templates/watchlist.html.j2 swing/web/templates/partials/watchlist_top5_section.html.j2 tests/web/view_models/test_cohort_hint.py tests/web/view_models/test_dashboard_broad_watch_containment.py tests/integration/test_include_baseline_inventory_guard.py
git commit -m "feat(web): per-row cohort-hint preview chip (opt-in site #2)

cohort_hint_for (the lone hint include_baseline=True) lives in
view_models/watchlist.py and feeds three read-only render sites — the
standalone watchlist page, the dashboard top-5 section (function-local
import breaks the dashboard<->watchlist cycle, Codex R3), and the /row
collapse route. Dashboard recommendation matcher calls stay
include_baseline=False (behavioral containment regression). An inventory
guard asserts exactly 3 literal opt-in sites."
```

---

### Task 7: HTMX pin UI (route + templates)

**Files:**
- Modify: `swing/web/routes/watchlist.py` (new `POST /watchlist/{ticker}/pin`)
- Modify: `swing/web/templates/partials/watchlist_row.html.j2` (pin badge in Ticker cell ONLY — the Tags-cell cohort chip landed in Task 6 Step 6b)
- Modify: `swing/web/templates/partials/watchlist_expanded.html.j2` (embedded pin form)
- Test: `tests/web/test_routes/test_watchlist_pin_route.py`, `tests/web/test_routes/test_watchlist_pin_render.py`

**Column-contract constraint (Codex R1-Major):** add NO new column. The pin badge renders inside the existing **Ticker cell** (and the Task-6 cohort chip inside the existing **Tags cell**). Header `<th>` count, compact `<td>` count, and the expanded `colspan` stay UNCHANGED. Do NOT "fix" the pre-existing 7-th/8-td/colspan-7 mismatch.

**Reference reading:** open `watchlist_row.html.j2` (the Ticker cell + Tags cell + the existing `{% set pattern_tag = ... %}` guard), `watchlist_expanded.html.j2` (the `colspan="7"` row + where forms live), and the existing `/watchlist/{ticker}/expand` route (the `build_watchlist_expanded` + JIT-chart pattern + the `TemplateResponse` shape) — the pin route returns the SAME re-rendered expanded-row partial.

- [ ] **Step 1: Write the failing route test**

Create `tests/web/test_routes/test_watchlist_pin_route.py` (use `with TestClient(app) as client:`):

```python
def test_pin_route_persists_and_server_stamps_pinned_at(client, seeded_watchlist_AAAA):
    with client:
        resp = client.post("/watchlist/AAAA/pin", data={"pinned": "on", "pin_note": "future breakout"})
    assert resp.status_code == 200
    e = get_watchlist_entry(conn(), "AAAA")
    assert e.pinned is True
    assert e.pin_note == "future breakout"
    assert e.pinned_at is not None          # server-stamped (no hidden input)


def test_unpin_clears_note_and_timestamp(client, seeded_pinned_AAAA):
    with client:
        resp = client.post("/watchlist/AAAA/pin", data={"pin_note": ""})  # checkbox absent → unpinned
    assert resp.status_code == 200
    e = get_watchlist_entry(conn(), "AAAA")
    assert (e.pinned, e.pin_note, e.pinned_at) == (False, None, None)


def test_empty_pin_note_persists_null_not_empty_string(client, seeded_watchlist_AAAA):
    with client:
        client.post("/watchlist/AAAA/pin", data={"pinned": "on", "pin_note": ""})
    assert get_watchlist_entry(conn(), "AAAA").pin_note is None   # `... or None`


def test_pin_route_404_for_absent_ticker(client):
    with client:
        resp = client.post("/watchlist/ZZZZ/pin", data={"pinned": "on"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/web/test_routes/test_watchlist_pin_route.py -v`
Expected: FAIL — route not registered (404 on a present ticker / 405).

- [ ] **Step 3: Implement the route**

In `swing/web/routes/watchlist.py`, add the route mirroring the EXISTING module patterns (Codex R1-Major: the module uses `apply_overrides` + `open_connection` + `HTTPException`, NOT `connect`/`app.state.db_path`/`PlainTextResponse`). Read `watchlist_expand` (`routes/watchlist.py:176`) — it does `cfg = apply_overrides(request.app.state.cfg)`, `open_connection(str(cfg.paths.db_path), busy_timeout_ms=cfg.web.db_busy_timeout_ms)`, raises `HTTPException(status_code=404, …)` for an absent ticker, builds the expanded VM + JIT chart, and returns an `HTMLResponse`. The pin route reuses that exact tail:

```python
from datetime import datetime  # add to the module imports if not present

@router.post("/watchlist/{ticker}/pin")
def watchlist_pin(request: Request, ticker: str):
    cfg = apply_overrides(request.app.state.cfg)
    pinned = ...        # parse the form (see note below — Starlette form access)
    pin_note = ...      # `(value or "").strip() or None`  → empty textarea persists NULL
    pinned_at = datetime.now().isoformat(timespec="seconds") if pinned else None
    conn = open_connection(str(cfg.paths.db_path), busy_timeout_ms=cfg.web.db_busy_timeout_ms)
    try:
        with conn:
            set_watchlist_pin(conn, ticker.upper(), pinned=pinned, pin_note=pin_note, pinned_at=pinned_at)
    except WatchlistEntryNotFoundError:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")
    finally:
        conn.close()
    # Re-render the expanded row exactly as `watchlist_expand` does (200, tr->tr
    # outerHTML swap). Factor `watchlist_expand`'s VM-build + JIT-chart + render
    # tail into a shared helper `_render_expanded_row(request, cfg, ticker)` and
    # call it from BOTH routes, OR inline the identical body here.
    return _render_expanded_row(request, cfg, ticker.upper())
```

**Form parsing note:** the module's POST routes are `def` (sync) — check whether sibling POST handlers use `async def … await request.form()` or a sync form helper, and match. If async, make this `async def` and `form = await request.form(); pinned = form.get("pinned") is not None; pin_note = (form.get("pin_note") or "").strip() or None`. Import `set_watchlist_pin` + `WatchlistEntryNotFoundError` from `swing.data.repos.watchlist` (the module already imports several names from there — extend the import). `HTTPException` + `apply_overrides` + `open_connection` are already imported (`routes/watchlist.py:6,9,10`).

- [ ] **Step 4: Run to verify the route tests pass**

Run: `python -m pytest tests/web/test_routes/test_watchlist_pin_route.py -v`
Expected: PASS.

- [ ] **Step 5: Write the template-render test (HTMX gotcha attributes)**

Create `tests/web/test_routes/test_watchlist_pin_render.py`:

```python
def test_expanded_pin_form_carries_htmx_attributes(client, seeded_watchlist_AAAA):
    with client:
        html = client.get("/watchlist/AAAA/expand").text
    assert 'hx-post="/watchlist/AAAA/pin"' in html
    assert 'hx-headers=' in html and '"HX-Request": "true"' in html.replace("'", '"')
    assert 'hx-target="#watchlist-row-AAAA"' in html      # explicit target — no ancestor inheritance
    assert 'name="pinned"' in html
    assert 'name="pin_note"' in html


def test_compact_row_shows_pin_badge_when_pinned(client, seeded_pinned_AAAA):
    with client:
        html = client.get("/watchlist").text
    assert "watchlist-pin-badge" in html                  # the 📌 badge class in the Ticker cell


def test_compact_row_no_badge_when_unpinned(client, seeded_watchlist_AAAA):
    with client:
        html = client.get("/watchlist").text
    assert "watchlist-pin-badge" not in html
```

- [ ] **Step 6: Implement the templates**

(a) `watchlist_row.html.j2` — in the **Ticker cell** ONLY, after the symbol, add the guarded pin badge (plain HTML/UTF-8 — no `print()`/matplotlib exposure). The cohort chip in the Tags cell already landed in Task 6 Step 6b — do NOT re-add it here; this task touches a DIFFERENT cell:

```jinja
{{ w.ticker }}{% if w.pinned %}<span class="watchlist-pin-badge" title="{{ (w.pin_note or '')|truncate(60) }}">📌</span>{% endif %}
```

(b) `watchlist_expanded.html.j2` — add the embedded pin form (inside the existing `colspan="7"` detail cell; the `<tr id="watchlist-row-{ticker}">` wrapper already exists for the expand/collapse swap — confirm the id):

```jinja
<form hx-post="/watchlist/{{ expanded.ticker }}/pin"
      hx-target="#watchlist-row-{{ expanded.ticker }}" hx-swap="outerHTML"
      hx-headers='{"HX-Request": "true"}'>
  <label><input type="checkbox" name="pinned" {% if expanded.entry.pinned %}checked{% endif %}> Pinned</label>
  <textarea name="pin_note" rows="2">{{ expanded.entry.pin_note or "" }}</textarea>
  <button type="submit">Save pin</button>
</form>
```

(Confirm the swap target id matches the compact row's `<tr id=...>` — read `watchlist_row.html.j2:15` / the expand route. The `outerHTML` swap onto a `<tr>` target is the SAME shape the existing expand/collapse uses, so the `<tr>`-fragment `makeFragment` hazard does NOT apply.)

- [ ] **Step 7: Run the render tests + the web suite**

Run: `python -m pytest tests/web/test_routes/test_watchlist_pin_render.py tests/web/test_routes/test_watchlist_pin_route.py -v`
Expected: PASS.
Run: `python -m pytest tests/web/ -q`
Expected: PASS (no base-layout VM `UndefinedError` — `cohort_hints` is scoped, not in `base.html.j2`).

- [ ] **Step 8: Commit**

```bash
git add swing/web/routes/watchlist.py swing/web/templates/partials/watchlist_row.html.j2 swing/web/templates/partials/watchlist_expanded.html.j2 tests/web/test_routes/test_watchlist_pin_route.py tests/web/test_routes/test_watchlist_pin_render.py
git commit -m "feat(web): expanded-row pin form + compact-row pin badge

POST /watchlist/{ticker}/pin server-stamps pinned_at (no hidden input),
persists via set_watchlist_pin (404 on absent), returns the re-rendered
expanded row (200, tr->tr outerHTML swap — the existing expand shape).
The form carries hx-headers HX-Request (OriginGuard) + an explicit
hx-target (no ancestor inheritance). Badge in the Ticker cell — no new
column (Codex R1-Major; the Tags-cell cohort chip landed in Task 6)."
```

---

### Task 8: 0026 §ADDENDUM + full suite + ruff

**Files:**
- Modify: `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md` (append the dated §ADDENDUM)
- Test: full fast suite + ruff (verification)

- [ ] **Step 1: Append the §ADDENDUM (verbatim from Arc-7 spec §13)**

Open the Arc-7 spec (`docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md`) §13 and copy the dated `### ADDENDUM 2026-06-10 — Arc 7 attribution-surface re-classification` block VERBATIM (from the `---` divider through the measurement-universe note) to the END of `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md`. This is a dated APPEND (the Arc-1 §5.3 precedent for editing a merged spec with a dated block) — do NOT rewrite §3.2/§5.1; the addendum amends the LETTER, not the spirit, and the frozen registry row + matcher gate stay untouched.

- [ ] **Step 2: Verify the addendum landed**

Run: `git diff --stat docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md`
Expected: the 0026 spec shows additions only (the dated block); no deletions.

- [ ] **Step 3: Run ruff**

Run: `ruff check swing/`
Expected: clean (zero findings). Fix any import-order / unused-import findings the new code introduced.

- [ ] **Step 4: Run the FULL fast suite on the branch HEAD**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS — green, with the new tests added (baseline ~7716 + the Arc-7 additions). READ the actual final count + status; do NOT carry a per-task pass-count forward ([[feedback_no_false_green_claim]]).

- [ ] **Step 5: Commit the addendum**

```bash
git add docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md
git commit -m "docs(spec): 0026 broad-watch addendum — Arc 7 attribution surfaces

Appends the dated 2026-06-10 §ADDENDUM re-classifying the entry prefill +
the cohort-hint helper as attribution surfaces (include_baseline=True),
enumerating the bounded 3-site opt-in set and the screen+pinned
measurement-universe note. Dated append (Arc-1 §5.3 precedent); the
frozen registry row + matcher gate are untouched."
```

---

## Operator-witnessed BROWSER gate (BINDING — HTMX discipline; part of the deliverable)

This is scripted for the executing-phase operator gate (NOT automatable — TestClient cannot detect the browser-only HTMX surfaces). Run `swing web`, open `127.0.0.1:8080`, and walk:

**A. Pin survival across a removing nightly**
1. On `/watchlist`, expand a watch-bucket row near aging-off (or seed one at `not_qualified_streak=2`). Confirm NO pin badge in the compact Ticker cell yet.
2. In the expanded row, check **Pinned**, type a `pin_note` ("future breakout"), click **Save pin**. Witness: the expanded row re-renders in place (200 swap), the checkbox stays checked, the note persists.
3. Collapse the row. Witness: the **📌 badge** now renders in the Ticker cell (with the note as the tooltip).
4. Run a nightly that WOULD have aged it off (`swing pipeline run`, or trigger the nightly): the ticker fails stable criteria, streak crosses the threshold. Witness: the row **survives** on `/watchlist` (not archived), shows a **fresh re-evaluated** bucket/criteria (it was fetched + evaluated, not stale), and `pipeline.log` / the run's `warnings_json` carries a `pin_suppressed_removal` line for it AND (if it was off-screen) a `pin_injection` line.
5. Expand the row, **uncheck Pinned**, Save. Collapse → badge gone.
6. Run the next nightly. Witness: the row now **ages off** (archived; accumulated streak took effect at the next run).

**B. Server-stamped broad-watch label on entry (no real trade needed)**
1. For a watch-bucket ticker (one the latest run bucketed `watch` with no narrow match), open the trade-entry form.
2. Witness: the `hypothesis_label` display span + hidden input render **`Broad-watch baseline (watch); failed: <criteria>`** — server-stamped, no manual action. (Form-render + the TestClient persist test in Task 5 suffice for the persistence half; the operator witnesses the render.)
3. (Optional, if the operator chooses to persist a test trade) submit through the soft-warn confirm + a `force=true` resubmit; witness the saved trade carries the broad-watch label (not `NULL`).

**C. Cohort-hint chip**
1. On `/watchlist` AND the dashboard top-5 section AND after expand→collapse, witness the **`broad-watch`** chip in the Tags cell for the watch ticker, and the narrow chip for a narrow-matching ticker — identical at all three sites.

Merge is BLOCKED until the operator confirms A + B (+ C) in a real browser ([[feedback_visual_gate_both_render_and_browser]]).

---

## Self-review (run against the spec)

**Spec coverage:** R1 → Tasks 1–2; R2 (amended, universe injection + veto) → Tasks 3–4; R3 (auto-label) → Task 5; R4 (cohort hint) → Task 6; R5 (round-trip) → Task 5 Step 5; R6 (locks) → containment + inventory guard (Task 6) + NOT-touched file list; the §10 contracts 1–10 → mapped (1 label-match T5; 2 dashboard containment T6; 3 inventory guard T6; 4 pin-preserved-upsert T2; 5 pin-veto T3; 6 universe injection T4; 7 delisted-pin F6 T3+T4; 8 held+error dedup T4; 9 three-site chip T6; 10 set_watchlist_pin 404 T2); §13 addendum → Task 8; browser gate → scripted above.

**Discriminating tests present:** pin-survival upsert (T2 Step 2 — FAILS under naive ON-CONFLICT including pin cols); veto (T3 Step 1 — FAILS under suppression-that-freezes-streaks, streak computed both ways); inventory guard (T6 Step 1 — exactly 3, FAILS on a 4th).

**Type consistency:** `pinned: bool`, `pin_note: str | None`, `pinned_at: str | None` consistent across model/repo/service/VM; `set_watchlist_pin(conn, ticker, *, pinned, pin_note, pinned_at)` signature identical at definition (T2) and call (T7); `cohort_hint_for(candidate, registry)` identical at definition (T6) and both callers; `suppressed_removes` is `list[WatchlistArchiveEntry]` at the lane (T3) and the iteration (T4).

**Open items flagged for executing** (verify-on-disk, do not block planning; the db.py/route/VM grounding errors from Codex round 1 are already FIXED inline above): (ii) the matched-object attribute (`.hypothesis_name` vs `.name`) returned by `match_candidate_to_hypotheses` — confirm in `hypothesis.py` and adjust `_hint_label`/the contract test; (v) the existing `_step_evaluate`/`_step_watchlist`/prefill/dashboard/route test-harness fixtures to EXTEND (do NOT build parallel harnesses — reuse the closest existing test module's setup); (vi) whether the watchlist POST routes are `def` or `async def` (form-parse style, Task 7); (vii) the `watchlist_expand` body to factor into the shared `_render_expanded_row(request, cfg, ticker)` helper.

**Codex round 1 (gpt-5.5): 0 critical, 4 major, 1 minor — all verified against source + FIXED** (migration test harness → the 0027 `_migrate(conn,…)` pattern; backup gate → real `WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES` + `_create_pre_watchlist_pin_migration_backup` + `_watchlist_pin_backup_gate`; Task-6 registry-before-close; Task-7 `apply_overrides`/`open_connection`/`HTTPException`/inline timestamp). Findings + dispositions persisted to `.copowers-findings.md`. Round 2 below confirms convergence.
