# B-7 Operator Failure-Mode Classification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a capture-only, nullable, CHECK-constrained `trades.failure_mode` column and thread it through the existing CR.1 post-trade review surface (web form + CLI + chronology read-back) so the operator can record *why a closed trade failed* for later outcome-attribution analysis.

**Architecture:** One new column of state (`trades.failure_mode`), the **first v24 migration** since the schwabdev arc, plus thin wiring on the established Phase-6/Phase-7 review path. No new table, route, or service module. The load-bearing design idea is the **orthogonality contract** (L2): `failure_mode` is computationally independent of `process_grade` and `mistake_tags`. Two slices: **A** = the gotcha-#11 atomic schema/model/persistence task (indivisible); **B** = the capture surfaces (form, POST, VM, chronology, CLI). B depends on A.

**Tech Stack:** Python 3.14, SQLite (migration runner in `swing/data/db.py`), dataclasses, FastAPI + HTMX (Starlette 1.0), Jinja2, click, pytest (`-m "not slow"`).

**Authoritative spec:** [`docs/superpowers/specs/2026-06-03-b7-operator-failure-mode-design.md`](../specs/2026-06-03-b7-operator-failure-mode-design.md) (619 lines, Codex-converged). **Dispatch brief:** [`docs/b7-operator-failure-mode-writing-plans-dispatch-brief.md`](../../b7-operator-failure-mode-writing-plans-dispatch-brief.md).

**Worker note (Windows):** use `python -m swing.cli` in the worktree (NOT bare `swing`). Prefix git/test with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. Commits: conventional, **ZERO `Co-Authored-By`**, **no `--no-verify`**, final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]` before any push.

---

## LOCKed OQ resolutions (operator 2026-06-03; BINDING — do NOT re-litigate)

| OQ | Resolution baked into this plan |
|----|---------------------------------|
| OQ-1 schema | New nullable CHECK `failure_mode` column → migration **0024 / v24**; strict `_b7_backup_gate` (`current==23 AND target>=24`); `EXPECTED_SCHEMA_VERSION` 23→24; gotcha-#11 atomic (Task A1). |
| OQ-2/OQ-7 | Always-shown, OPTIONAL, nullable, **NO sentinel**. `NULL` = winner OR unclassified-loss (disambiguated by realized-R at analysis time, not this column). |
| OQ-3 | Single-select (one column). |
| OQ-4 | The **7-value vocab** (locked): `thesis_invalidated`, `normal_volatility_stop`, `market_regime_shift`, `adverse_event_shock`, `execution_error`, `failed_to_advance`, `other`. `NULL` = no failure attributed (NOT a token). |
| OQ-5 | Capture-only V1; analysis surface is the NEXT arc (out of scope). |
| OQ-6 | Forward-only; existing reviewed trades stay `NULL`. |
| OQ-8 | **Include** the CLI `--failure-mode` option (Task B6). |

**Inherited locks:** L1 capture-only · L2 orthogonal to grade+tags (Task B7 guard) · L3 explicit carve-out into `swing/trades/review.py` + `swing/data/` + `swing/cli.py` + web · L4 schema is the #11 atomic task · L5 `... or None` for the nullable CHECK column · L6 every review-form gotcha preserved + operator browser gate (incl. unseeded-blank witness).

---

## Production anchors (re-grepped against live tree at HEAD `f9ca06ca`; STEP 0 done)

The spec cites earlier HEADs; these are the **current** line numbers:

- `swing/data/db.py:51` — `EXPECTED_SCHEMA_VERSION = 23`.
- `swing/data/db.py:166-169` — `PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES` (the v22/v23 table set; reuse for B7 — 0024 adds **no table**).
- `swing/data/db.py:322` — `_verify_backup_integrity(backup_path, *, expected_tables)`.
- `swing/data/db.py:556-580` — `_create_pre_phase14_sb3_migration_backup` (the backup-helper template to mirror).
- `swing/data/db.py:909-950` — `_phase14_sb3_backup_gate` (the gate template to mirror; STRICT `current_version != 22` guard).
- `swing/data/db.py:953` — `run_migrations`; gate calls `977-1024`; the SB3 gate call is `1019-1024`; `apply_ceiling = min(target_version, EXPECTED_SCHEMA_VERSION)` at `1026`.
- `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql` — the latest migration; next file is `0024_phase15_b7_failure_mode.sql`.
- `swing/data/models.py:179-265` — `Trade` dataclass; **it currently has NO `__post_init__`** (the first `__post_init__` at `:307` belongs to `Fill`). Task A1 ADDS one. The trailing fields are `candidate_id` (`:264`) / `pattern_evaluation_id` (`:265`). Top-of-file CHECK-mirror block: `:8-21`.
- `swing/data/repos/trades.py:57-77` — `_TRADE_SELECT_COLS` (54 cols; ends `candidate_id, pattern_evaluation_id`); `:82-102` `_TRADE_SELECT_COLS_PRE_V21`; `:105-119` `_trade_select_cols(conn)`; `:155-302` `insert_trade_with_event` (SVAI two-branch); `:478-550` `_row_to_trade` (positional, indices 0..53); `:553-595` `update_trade_review_fields`.
- `swing/trades/review.py:23-26` imports; `:37-66` `MISTAKE_TAGS` + `ALL_MISTAKE_TAGS`; `:102-138` `compute_process_grade` (`(*, entry, management, exit_, disqualifying)` — no failure_mode param); `:550-619` `complete_trade_review`.
- `swing/web/routes/trades.py:2669-2799` — `review_post` (empty-tags 400+re-render ladder `:2706-2739`; `complete_trade_review` call `:2778-2792`; success `:2799` = `204` + `HX-Redirect`).
- `swing/web/view_models/trades.py:1139-1178` — `ReviewVM`; `:1224-1390` `build_review_vm` (return `:1370-1390`).
- `swing/web/templates/partials/review_form.html.j2` — Mistake-tags fieldset `:92-106`; Counterfactual fieldset `:108-125`.
- `swing/web/view_models/trade_chronology.py:157-187` — `_review_entry` (explicit-column SELECT, NOT via `_trade_select_cols`).
- `swing/cli.py:1330-1357` — `trade_review_cmd` options; `:1359-1483` body; `complete_trade_review` call `:1460-1476`; echo `:1480-1483`.
- `tests/trades/test_review.py:31-36` — `_seed_v14` runs `run_migrations(target_version=16)` (pre-v21 AND pre-v24). These callers pass `failure_mode=None` by default and **must stay green** — the binding constraint on the PRAGMA-aware UPDATE.

---

## Slice / task map

| Slice | Task | What | Commit |
|-------|------|------|--------|
| **A** | A1 | The #11 ATOMIC schema/model/persistence task: migration 0024 + backup-gate + `EXPECTED_SCHEMA_VERSION=24` + `FAILURE_MODES` + `Trade.failure_mode` + `__post_init__` + three-era read + `update_trade_review_fields` PRAGMA-aware + `complete_trade_review` param. | ONE commit (gotcha #11). |
| **B** | B1 | `FAILURE_MODE_DISPLAY` ordered tuple + `failure_mode_display_choices()` + `failure_mode_label()` helpers in `review.py`. | 1 |
| | B2 | `ReviewVM.failure_mode_choices` + `build_review_vm` populates it; base-layout no-deref check. | 1 |
| | B3 | Review-form `<select>` fieldset (after Mistake-tags, before Counterfactual); ASCII. | 1 |
| | B4 | `review_post` POST handler: `Form(None)` + `... or None` + validate→400+re-render + thread. | 1 |
| | B5 | `_review_entry` PRAGMA-aware chronology read-back + fold label into detail. | 1 |
| | B6 | CLI `--failure-mode` option: validate → `click.ClickException`; ASCII. | 1 |
| | B7 | L2 orthogonality guard test (no impl). | 1 |
| | — | Operator-witnessed browser gate (manual; not a code task). | — |

**Why Slice A is one task:** gotcha #11 ("Schema-CHECK + Python-constant + dataclass-validator MUST land in ONE task … Read-path `_row_to_*` mappers MUST be widened in the SAME task as the write-path") + L4 + Codex watch item #1 ("no partial landing leaves a schema/model mismatch"). The migration cannot even be *exercised* without the `EXPECTED_SCHEMA_VERSION` bump (`apply_ceiling = min(target, EXPECTED_SCHEMA_VERSION)`), so the bump, the column, the constant, the validator, the read mapper, and the write path are inseparable. Slice A is therefore presented as a single task with many TDD steps and **one** commit.

---

## Slice A — schema + model + persistence (the #11 atomic task)

### Task A1: migration 0024 / v24 + FAILURE_MODES + Trade.failure_mode + three-era read + both write paths + backup-gate

**Files:**
- Create: `swing/data/migrations/0024_phase15_b7_failure_mode.sql`
- Modify: `swing/data/db.py:51` (`EXPECTED_SCHEMA_VERSION`), `db.py:166-169` (expected-tables snapshot), add `_b7_backup_gate` after `db.py:950`, wire it into `run_migrations` after `db.py:1024`, add `_create_pre_b7_migration_backup` near `db.py:580`
- Modify: `swing/data/models.py` — add `FAILURE_MODES` above `class Trade` (`:179`), add `failure_mode` field after `:265`, add `Trade.__post_init__`
- Modify: `swing/data/repos/trades.py` — `_TRADE_SELECT_COLS` (`:57-77`), add `_TRADE_SELECT_COLS_V21_TO_V23`, extend `_TRADE_SELECT_COLS_PRE_V21` (`:82-102`), `_trade_select_cols` (`:105-119`), `_row_to_trade` (`:478-550`), `update_trade_review_fields` (`:553-595`)
- Modify: `swing/trades/review.py` — `complete_trade_review` (`:550-619`) gains `failure_mode` keyword-only param + threads it
- Test: `tests/data/test_b7_failure_mode_schema.py` (new), plus an assertion added to `tests/trades/test_review.py`

> **NOTE on `insert_trade_with_event`:** it requires **NO column-list change**. `failure_mode` is a review-time field, always `NULL` at entry, so the entry INSERT simply omits the column (SQLite defaults `NULL`) — already era-tolerant across pre-v21 / v21–v23 / v24. Task A1 adds a *guard test* confirming a v24 insert yields `failure_mode=NULL` and pre-v24 inserts still succeed; it does not modify the INSERT SQL. This is the spec §4.3 #5 "the legacy INSERT path simply omits the column" point.

---

- [ ] **Step 1: Write the failing migration round-trip + strict-backup-gate test**

Create `tests/data/test_b7_failure_mode_schema.py`:

```python
"""B-7 (Phase 15) — failure_mode column: migration 0024 / v24, the #11 atomic
schema/model/read/write consistency, the three-era read, both write paths, and
the strict v23->v24 backup gate."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    run_migrations,
)
from swing.data.models import FAILURE_MODES, Trade
from swing.data.repos.trades import (
    _row_to_trade,
    _trade_select_cols,
    get_trade,
    insert_trade_with_event,
    update_trade_review_fields,
)


def _fresh(tmp_path: Path, *, target: int) -> sqlite3.Connection:
    # foreign_keys at sqlite default (OFF) so synthetic backlink UPDATEs in the
    # v21-v23 era fixture don't need a real candidates parent row.
    conn = sqlite3.connect(str(tmp_path / "swing.db"))
    run_migrations(conn, target_version=target, backup_dir=tmp_path)
    return conn


def _cols(conn: sqlite3.Connection) -> set[str]:
    return {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}


def test_expected_schema_version_is_24() -> None:
    assert EXPECTED_SCHEMA_VERSION == 24


def test_migration_0024_adds_failure_mode_column(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, target=24)
    try:
        # PRE-FIX value: "failure_mode" NOT in cols (column never added) -> False.
        # POST-FIX value: present -> True.
        assert "failure_mode" in _cols(conn)
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 24
    finally:
        conn.close()


def test_run_migrate_twice_is_noop(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, target=24)
    try:
        run_migrations(conn, target_version=24, backup_dir=tmp_path)  # no raise
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 24
    finally:
        conn.close()


def test_b7_backup_gate_fires_on_v23_to_v24(tmp_path: Path) -> None:
    # Build to v23 first (apply_ceiling stops there), then migrate v23->v24 with a
    # backup_dir -> the strict gate fires and writes a backup file.
    conn = _fresh(tmp_path, target=23)
    try:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 23
        run_migrations(conn, target_version=24, backup_dir=tmp_path)
        backups = list(tmp_path.glob("swing-pre-b7-migration-*.db"))
        # PRE-FIX: gate does not exist -> zero backup files. POST-FIX: exactly one.
        assert len(backups) == 1
    finally:
        conn.close()


def test_b7_backup_gate_bypassed_from_pre_v23_baseline(tmp_path: Path) -> None:
    # A multi-version walk from scratch (current=0) never equals 23 at 0024 -> gate
    # bypassed by design (no b7 backup file written for the fresh-build path).
    conn = _fresh(tmp_path, target=24)
    try:
        assert list(tmp_path.glob("swing-pre-b7-migration-*.db")) == []
    finally:
        conn.close()
```

- [ ] **Step 2: Write the failing CHECK + frozenset + validator consistency test (#11)**

Append to `tests/data/test_b7_failure_mode_schema.py`:

```python
def test_vocabulary_is_the_locked_seven() -> None:
    assert FAILURE_MODES == frozenset({
        "thesis_invalidated", "normal_volatility_stop", "market_regime_shift",
        "adverse_event_shock", "execution_error", "failed_to_advance", "other",
    })


def test_migration_check_tokens_equal_frozenset() -> None:
    # Spec §7.1 #2 + gotcha #11: the SQL CHECK enum and the Python frozenset must
    # be IDENTICAL sets, not merely "all 7 insert + one bogus rejects" (that weaker
    # check passes even if the CHECK accidentally allows an 8th token). Parse the
    # migration's `failure_mode IN ( ... )` list and assert exact set equality.
    import re
    from pathlib import Path
    sql = Path(
        "swing/data/migrations/0024_phase15_b7_failure_mode.sql"
    ).read_text(encoding="utf-8")
    m = re.search(r"failure_mode\s+IN\s*\((.*?)\)", sql, re.IGNORECASE | re.DOTALL)
    assert m, "could not locate the failure_mode IN (...) CHECK clause"
    check_tokens = set(re.findall(r"'([^']+)'", m.group(1)))
    # PRE-FIX: the migration file does not exist -> FileNotFoundError. POST-FIX:
    # the CHECK token set equals FAILURE_MODES exactly (drift in EITHER direction
    # fails). This is the binding #11 vocabulary-identity assertion.
    assert check_tokens == set(FAILURE_MODES)


def test_all_tokens_insert_and_non_member_rejected_by_check(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, target=24)
    try:
        with conn:
            for i, token in enumerate(sorted(FAILURE_MODES)):
                conn.execute(
                    "INSERT INTO trades (ticker, entry_date, entry_price, "
                    "initial_shares, initial_stop, current_stop, state, "
                    "trade_origin, pre_trade_locked_at, current_size, "
                    "failure_mode) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (f"T{i}", "2026-05-01", 10.0, 1, 9.0, 9.0, "closed",
                     "manual_off_pipeline", "2026-05-01T09:30:00", 1.0, token),
                )
        # PRE-FIX: the INSERT raises OperationalError("no such column: failure_mode").
        # POST-FIX: all 7 insert cleanly; a non-member trips the CHECK.
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    "INSERT INTO trades (ticker, entry_date, entry_price, "
                    "initial_shares, initial_stop, current_stop, state, "
                    "trade_origin, pre_trade_locked_at, current_size, "
                    "failure_mode) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("BOGUS", "2026-05-01", 10.0, 1, 9.0, 9.0, "closed",
                     "manual_off_pipeline", "2026-05-01T09:30:00", 1.0, "not_a_token"),
                )
    finally:
        conn.close()


def test_trade_post_init_rejects_bad_failure_mode() -> None:
    # PRE-FIX: Trade had no __post_init__ -> Trade(failure_mode="bogus") returns an
    # object (no raise). POST-FIX: __post_init__ validates -> ValueError.
    with pytest.raises(ValueError):
        Trade(
            id=None, ticker="AAPL", entry_date="2026-05-01", entry_price=10.0,
            initial_shares=1, initial_stop=9.0, current_stop=9.0, state="closed",
            watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
            failure_mode="bogus",
        )
    # A valid token AND None both construct cleanly.
    Trade(
        id=None, ticker="AAPL", entry_date="2026-05-01", entry_price=10.0,
        initial_shares=1, initial_stop=9.0, current_stop=9.0, state="closed",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        failure_mode="thesis_invalidated",
    )
```

- [ ] **Step 3: Write the failing three-era read-mapper test**

Append:

```python
def test_read_mapper_three_eras(tmp_path: Path) -> None:
    # --- v24 era: failure_mode round-trips ---
    conn24 = _fresh(tmp_path / "a", target=24) if False else _fresh(
        _mk(tmp_path, "v24"), target=24)
    try:
        with conn24:
            conn24.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, trade_origin, "
                "pre_trade_locked_at, current_size, candidate_id, "
                "pattern_evaluation_id, failure_mode) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("V24", "2026-05-01", 10.0, 1, 9.0, 9.0, "closed",
                 "manual_off_pipeline", "2026-05-01T09:30:00", 1.0, 42, 43,
                 "execution_error"),
            )
        sql = f"SELECT {_trade_select_cols(conn24)} FROM trades WHERE ticker='V24'"
        t = _row_to_trade(conn24.execute(sql).fetchone())
        assert t.failure_mode == "execution_error"
        assert t.candidate_id == 42 and t.pattern_evaluation_id == 43
    finally:
        conn24.close()

    # --- v21-v23 era: failure_mode reads None AND real backlinks SURVIVE ---
    conn23 = _fresh(_mk(tmp_path, "v23"), target=23)
    try:
        with conn23:
            conn23.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, trade_origin, "
                "pre_trade_locked_at, current_size, candidate_id, "
                "pattern_evaluation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                ("V23", "2026-05-01", 10.0, 1, 9.0, 9.0, "closed",
                 "manual_off_pipeline", "2026-05-01T09:30:00", 1.0, 77, 88),
            )
        sql = f"SELECT {_trade_select_cols(conn23)} FROM trades WHERE ticker='V23'"
        t = _row_to_trade(conn23.execute(sql).fetchone())
        # PRE-FIX (naive two-era: full vs PRE_V21): a v23 DB lacks failure_mode, so a
        # naive impl that routes "no failure_mode" -> PRE_V21 would null the backlinks
        # -> candidate_id would read None. POST-FIX (three-era): backlinks survive.
        assert t.candidate_id == 77 and t.pattern_evaluation_id == 88
        assert t.failure_mode is None
    finally:
        conn23.close()

    # --- pre-v21 era: all three read None ---
    conn16 = _fresh(_mk(tmp_path, "v16"), target=16)
    try:
        with conn16:
            conn16.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, trade_origin, "
                "pre_trade_locked_at, current_size) VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("V16", "2026-05-01", 10.0, 1, 9.0, 9.0, "closed",
                 "manual_off_pipeline", "2026-05-01T09:30:00", 1.0),
            )
        sql = f"SELECT {_trade_select_cols(conn16)} FROM trades WHERE ticker='V16'"
        t = _row_to_trade(conn16.execute(sql).fetchone())
        assert t.candidate_id is None and t.pattern_evaluation_id is None
        assert t.failure_mode is None
    finally:
        conn16.close()


def _mk(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d
```

> Place the `_mk` helper near the top of the file (above the tests) when implementing; it is shown here inline for readability. (Self-review note: hoist `_mk` above first use.)

- [ ] **Step 4: Write the failing write-path tests (SVAI guard + PRAGMA-aware UPDATE + service param)**

Append:

```python
def test_insert_omits_failure_mode_and_defaults_null(tmp_path: Path) -> None:
    # The entry INSERT never references failure_mode -> default NULL at v24, and the
    # pre-v21 / v21-v23 inserts still succeed (era-tolerant; no column reference).
    for target in (16, 23, 24):
        conn = _fresh(_mk(tmp_path, f"ins{target}"), target=target)
        try:
            tr = Trade(
                id=None, ticker="INS", entry_date="2026-05-01", entry_price=10.0,
                initial_shares=1, initial_stop=9.0, current_stop=9.0,
                state="entered", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-05-01T09:30:00",
            )
            with conn:
                tid = insert_trade_with_event(conn, tr, event_ts="2026-05-01T09:30:00")
            got = get_trade(conn, tid)
            assert got is not None
            assert got.failure_mode is None  # POST-FIX attr exists + is None
        finally:
            conn.close()


def test_update_review_fields_pragma_aware(tmp_path: Path) -> None:
    base = dict(
        reviewed_at="2026-05-05T16:00:00", mistake_tags_json="[\"none_observed\"]",
        entry_grade="A", management_grade="A", exit_grade="A", process_grade="A",
        disqualifying_process_violation=False, realized_R_if_plan_followed=None,
        mistake_cost_confidence=None, lesson_learned="ok",
    )

    # v24: a valid token persists.
    conn24 = _fresh(_mk(tmp_path, "u24"), target=24)
    try:
        with conn24:
            conn24.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,"
                " initial_stop, current_stop, state, trade_origin, pre_trade_locked_at,"
                " current_size) VALUES ('U',?,?,?,?,?,?,?,?,?)",
                ("2026-05-01", 10.0, 1, 9.0, 9.0, "closed", "manual_off_pipeline",
                 "2026-05-01T09:30:00", 1.0))
            tid = conn24.execute("SELECT id FROM trades WHERE ticker='U'").fetchone()[0]
        with conn24:
            update_trade_review_fields(
                conn24, trade_id=tid, failure_mode="thesis_invalidated", **base)
        stored = conn24.execute(
            "SELECT failure_mode FROM trades WHERE id=?", (tid,)).fetchone()[0]
        assert stored == "thesis_invalidated"
    finally:
        conn24.close()

    # pre-v24 + failure_mode=None: no-op assignment, completes cleanly (legacy green).
    conn16 = _fresh(_mk(tmp_path, "u16"), target=16)
    try:
        with conn16:
            conn16.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,"
                " initial_stop, current_stop, state, trade_origin, pre_trade_locked_at,"
                " current_size) VALUES ('U',?,?,?,?,?,?,?,?,?)",
                ("2026-05-01", 10.0, 1, 9.0, 9.0, "closed", "manual_off_pipeline",
                 "2026-05-01T09:30:00", 1.0))
            tid = conn16.execute("SELECT id FROM trades WHERE ticker='U'").fetchone()[0]
        with conn16:
            update_trade_review_fields(conn16, trade_id=tid, failure_mode=None, **base)
        # PRE-FIX: an unconditional "failure_mode = ?" assignment raises
        # OperationalError("no such column"). POST-FIX: omitted -> clean completion.
        assert conn16.execute(
            "SELECT reviewed_at FROM trades WHERE id=?", (tid,)).fetchone()[0] is not None
    finally:
        conn16.close()

    # pre-v24 + non-None failure_mode: clean ValueError (NOT a leaked OperationalError).
    conn16b = _fresh(_mk(tmp_path, "u16b"), target=16)
    try:
        with conn16b:
            conn16b.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,"
                " initial_stop, current_stop, state, trade_origin, pre_trade_locked_at,"
                " current_size) VALUES ('U',?,?,?,?,?,?,?,?,?)",
                ("2026-05-01", 10.0, 1, 9.0, 9.0, "closed", "manual_off_pipeline",
                 "2026-05-01T09:30:00", 1.0))
            tid = conn16b.execute("SELECT id FROM trades WHERE ticker='U'").fetchone()[0]
        with pytest.raises(ValueError):
            with conn16b:
                update_trade_review_fields(
                    conn16b, trade_id=tid, failure_mode="execution_error", **base)
    finally:
        conn16b.close()
```

Append a `complete_trade_review` signature + threading assertion to `tests/trades/test_review.py` (reuse its `_seed_v14` is pre-v24, so use a v24 seed here — add a small v24 helper at the top of the new schema-test file instead, to avoid touching the legacy file's pre-v24 assumption). In `tests/data/test_b7_failure_mode_schema.py` append:

```python
def test_complete_trade_review_threads_failure_mode(tmp_path: Path) -> None:
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.models import Fill
    from swing.trades.review import complete_trade_review

    conn = _fresh(_mk(tmp_path, "ctr"), target=24)
    try:
        tr = Trade(
            id=None, ticker="CTR", entry_date="2026-05-01", entry_price=10.0,
            initial_shares=1, initial_stop=9.0, current_stop=9.0, state="entered",
            watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-01T09:30:00")
        with conn:
            tid = insert_trade_with_event(conn, tr, event_ts="2026-05-01T09:30:00")
            insert_fill_with_event(conn, Fill(
                fill_id=None, trade_id=tid, fill_datetime="2026-05-01T09:30:00",
                action="entry", quantity=1.0, price=10.0),
                event_ts="2026-05-01T09:30:00")
            conn.execute("UPDATE trades SET state='closed' WHERE id=?", (tid,))
        complete_trade_review(
            conn, tid, reviewed_at="2026-05-05T16:00:00",
            mistake_tags_json="[\"none_observed\"]", entry_grade="A",
            management_grade="A", exit_grade="A", process_grade="A",
            disqualifying_process_violation=False, realized_R_if_plan_followed=None,
            mistake_cost_confidence=None, lesson_learned="clean",
            failure_mode="thesis_invalidated", event_ts="2026-05-05T16:00:00")
        got = get_trade(conn, tid)
        assert got is not None and got.state == "reviewed"
        assert got.failure_mode == "thesis_invalidated"
    finally:
        conn.close()
```

- [ ] **Step 5: Run all the new tests to verify they FAIL**

Run: `cd <worktree> && python -m pytest tests/data/test_b7_failure_mode_schema.py -q`
Expected: FAIL — `ImportError: cannot import name 'FAILURE_MODES'` / `AssertionError: EXPECTED_SCHEMA_VERSION == 23` / `no such column: failure_mode`.

- [ ] **Step 6: Implement — the migration file**

Create `swing/data/migrations/0024_phase15_b7_failure_mode.sql` (gotcha #9 — explicit `BEGIN;…COMMIT;`):

```sql
-- Phase 15 B-7 (operator failure-mode classification) migration 0024 / v24:
-- add the nullable, CHECK-constrained failure_mode TEXT column to trades.
-- A nullable ADD COLUMN whose CHECK references only the new column is a cheap,
-- NON-rebuild migration (contrast 0023's chart_renders rebuild, forced by an
-- enum-VALUE rename of an existing column). Existing rows backfill implicitly to
-- NULL (OQ-6 forward-only). NULL = "no failure attributed" (winner or
-- unclassified loss) -- NOT a vocabulary token.
--
-- gotcha #9: explicit BEGIN; ... COMMIT; (executescript implicit-COMMIT
-- discipline). The runner's _apply_migration wraps this in try/except with
-- rollback on any mid-script failure.
BEGIN;
ALTER TABLE trades ADD COLUMN failure_mode TEXT
    CHECK (failure_mode IS NULL OR failure_mode IN (
        'thesis_invalidated', 'normal_volatility_stop', 'market_regime_shift',
        'adverse_event_shock', 'execution_error', 'failed_to_advance', 'other'
    ));
UPDATE schema_version SET version = 24;
COMMIT;
```

- [ ] **Step 7: Implement — `db.py`: version bump, expected-tables, backup helper, gate, wiring**

In `swing/data/db.py`:

1. Line `:51` — `EXPECTED_SCHEMA_VERSION = 24`.
2. After `:169` add the expected-tables snapshot (0024 adds **no** table → same set as v23):

```python
# B-7 (Phase 15) backup gate: migrating v23 -> v24 snapshots the live v23 DB.
# Migration 0024 only ADDs the nullable failure_mode column -- NO new tables --
# so the table set present at v23 equals the post-SB3 set. Derived from the SB3
# set so provenance stays auditable.
B7_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES
)
```

3. After `_create_pre_phase14_sb3_migration_backup` (`:580`) add the B7 backup helper (mirror it verbatim, only the filename prefix differs):

```python
def _create_pre_b7_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """B-7 (Phase 15) mirror with the b7 filename prefix.

    SQLite-native Connection.backup() snapshot before the 0024 migration.
    Backup file pattern ``swing-pre-b7-migration-<ISO>.db``.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-b7-migration-{timestamp}.db"
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
```

4. After `_phase14_sb3_backup_gate` (`:950`) add `_b7_backup_gate` (mirror; STRICT `current_version != 23`):

```python
def _b7_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """B-7 (Phase 15) backup-before-migrate gate (spec §4.4).

    Fires ONLY when ``current_version == 23 AND target_version >= 24`` -- a real
    production v23 DB about to receive migration 0024 (failure_mode column).
    STRICT EQUALITY on pre_version per the ``pre_version == (target - 1)`` gotcha
    (NOT ``<=``). Multi-step walks from pre-v23 baselines bypass this gate by
    design (Phase 9 / 12 / 13 / 14 precedent).

    Filename: ``swing-pre-b7-migration-<ISO>.db``.
    """
    if target_version < 24 or current_version != 23:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-B7 backup gate requires a file-backed source DB; in-memory "
            "connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_b7_migration_backup(src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=B7_PRE_MIGRATION_EXPECTED_TABLES)
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-B7 backup failed: {exc}") from exc
```

5. In `run_migrations`, after the `_phase14_sb3_backup_gate(...)` call (`:1019-1024`) add:

```python
    _b7_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
```

- [ ] **Step 8: Implement — `models.py`: FAILURE_MODES + field + `__post_init__`**

In `swing/data/models.py`, immediately above `class Trade:` (`:179`):

```python
# B-7 (Phase 15, migration 0024 / v24) — operator failure-mode vocabulary.
# Co-located with the Trade dataclass + the Phase-6 CHECK mirrors per the
# schema-CHECK + Python-constant + dataclass-validator paired discipline. Placed
# HERE (NOT swing/trades/review.py) to avoid the review.py -> models.py import
# cycle: review.py already imports Trade FROM models.py, so the constant must
# live upstream. The migration 0024 CHECK list and this frozenset are asserted
# identical by tests/data/test_b7_failure_mode_schema.py. NULL = "no failure
# attributed" (NOT a token).
FAILURE_MODES: frozenset[str] = frozenset({
    "thesis_invalidated",
    "normal_volatility_stop",
    "market_regime_shift",
    "adverse_event_shock",
    "execution_error",
    "failed_to_advance",
    "other",
})
```

After `pattern_evaluation_id: int | None = None` (`:265`) add the field:

```python
    # B-7 (Phase 15, migration 0024 / v24) — operator failure-mode attribution.
    # Review-time field; always NULL at entry. Nullable: a winning trade has no
    # failure mode, and an unclassified loss stays NULL. Validated against
    # FAILURE_MODES in __post_init__ (Literal[...] is NOT runtime-enforced).
    failure_mode: str | None = None
```

Add a `__post_init__` to `Trade` (the class currently has none — append it as the last method of the dataclass, after the field block, before `class Fill`):

```python
    def __post_init__(self) -> None:
        # B-7 (#11 paired-atomic-landing validator): the failure_mode value, when
        # set, MUST be a member of FAILURE_MODES. Mirrors the migration 0024 CHECK
        # so the model rejects exactly what the schema rejects.
        if self.failure_mode is not None and self.failure_mode not in FAILURE_MODES:
            raise ValueError(
                f"failure_mode must be one of {sorted(FAILURE_MODES)} or None, "
                f"got {self.failure_mode!r}")
```

> The dataclass is `@dataclass(frozen=True)`? Check the decorator above `:179`. If frozen, `__post_init__` may only read `self`, which is the case here (read-only validation) — fine. If NOT frozen, also fine.

- [ ] **Step 9: Implement — `repos/trades.py`: three-era read + PRAGMA-aware UPDATE**

Extend `_TRADE_SELECT_COLS` (`:57-77`) — append `, failure_mode` as the LAST column:

```python
    planned_target_R,
    candidate_id, pattern_evaluation_id, failure_mode
"""
```

Add a new v21–v23 projection (real backlinks + `NULL AS failure_mode`) directly after `_TRADE_SELECT_COLS` and before `_TRADE_SELECT_COLS_PRE_V21`:

```python
# v21-v23 era (candidate_id/pattern_evaluation_id present, failure_mode absent):
# real backlink values + NULL AS failure_mode. MUST NOT null the v21 backlinks
# (the three-era trap a naive single-PRE projection would fall into).
_TRADE_SELECT_COLS_V21_TO_V23 = """
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
    candidate_id, pattern_evaluation_id, NULL AS failure_mode
"""
```

Extend `_TRADE_SELECT_COLS_PRE_V21` (`:82-102`) — change its last line to add the third NULL:

```python
    planned_target_R,
    NULL AS candidate_id, NULL AS pattern_evaluation_id, NULL AS failure_mode
"""
```

Rewrite `_trade_select_cols` (`:105-119`) to branch across THREE eras (detect `failure_mode` and the v21 columns independently):

```python
def _trade_select_cols(conn: sqlite3.Connection) -> str:
    """Return the schema-era-appropriate SELECT-cols projection.

    THREE eras (B-7 migration 0024 added a third):
      * v24+ (failure_mode present)  -> full projection incl. failure_mode.
      * v21-v23 (candidate_id present, failure_mode absent) -> real backlinks +
        NULL AS failure_mode. MUST preserve the real backlinks (the era trap).
      * pre-v21 (none present) -> NULL backlinks + NULL failure_mode.
    Detect failure_mode AND the v21 columns INDEPENDENTLY, then compose. Keeps
    _row_to_trade positional + agnostic across all eras (~140 pre-v21 fixtures).
    """
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    has_v21 = "candidate_id" in cols and "pattern_evaluation_id" in cols
    if "failure_mode" in cols:  # v24 implies v21 columns exist
        return _TRADE_SELECT_COLS
    if has_v21:
        return _TRADE_SELECT_COLS_V21_TO_V23
    return _TRADE_SELECT_COLS_PRE_V21
```

Extend `_row_to_trade` (`:478-550`) — add to the docstring index map `54:failure_mode (B-7 / migration 0024)` and add the kwarg in the `return Trade(...)` after `pattern_evaluation_id=row[53],`:

```python
        candidate_id=row[52],
        pattern_evaluation_id=row[53],
        failure_mode=row[54],
    )
```

Rewrite `update_trade_review_fields` (`:553-595`) PRAGMA-aware. Add a keyword-only `failure_mode: str | None = None` param and build the SET clause conditionally:

```python
def update_trade_review_fields(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    reviewed_at: str,
    mistake_tags_json: str,
    entry_grade: str,
    management_grade: str,
    exit_grade: str,
    process_grade: str,
    disqualifying_process_violation: bool | None,
    realized_R_if_plan_followed: float | None,  # noqa: N803
    mistake_cost_confidence: str,
    lesson_learned: str,
    failure_mode: str | None = None,
) -> None:
    """UPDATE the review fields atomically. Caller wraps in `with conn:`.

    B-7 (migration 0024): ``failure_mode`` is PRAGMA-aware. The assignment is
    included ONLY when the column exists (v24+). On a pre-v24 schema a non-None
    ``failure_mode`` raises a clean ValueError (NOT a leaked OperationalError);
    ``failure_mode=None`` against pre-v24 is a no-op (keeps the legacy
    run_migrations(target_version=16) review fixtures green).
    """
    from swing.data.models import FAILURE_MODES

    if failure_mode is not None and failure_mode not in FAILURE_MODES:
        raise ValueError(
            f"failure_mode must be one of {sorted(FAILURE_MODES)} or None, "
            f"got {failure_mode!r}")
    has_fm = "failure_mode" in {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    if failure_mode is not None and not has_fm:
        raise ValueError(
            "failure_mode requires schema v24+ (the trades.failure_mode column "
            "is absent on this DB)")
    set_clauses = [
        "reviewed_at = ?", "mistake_tags = ?", "entry_grade = ?",
        "management_grade = ?", "exit_grade = ?", "process_grade = ?",
        "disqualifying_process_violation = ?", "realized_R_if_plan_followed = ?",
        "mistake_cost_confidence = ?", "lesson_learned = ?",
    ]
    params: list = [
        reviewed_at, mistake_tags_json, entry_grade, management_grade,
        exit_grade, process_grade,
        (None if disqualifying_process_violation is None
         else (1 if disqualifying_process_violation else 0)),
        realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned,
    ]
    if has_fm:
        set_clauses.append("failure_mode = ?")
        params.append(failure_mode)
    params.append(trade_id)
    cur = conn.execute(
        f"UPDATE trades SET {', '.join(set_clauses)} WHERE id = ?", params)
    if cur.rowcount == 0:
        raise ValueError(f"trade {trade_id} not found")
```

- [ ] **Step 10: Implement — `review.py`: `complete_trade_review` gains the param**

In `swing/trades/review.py`, add `failure_mode: str | None = None` as a keyword-only param to `complete_trade_review` and thread it into the `update_trade_review_fields(...)` call (after `lesson_learned=lesson_learned,` at `:610`). Place the new param **after** `event_ts` and **before** `rationale`:

```python
    lesson_learned: str,
    event_ts: str,
    failure_mode: str | None = None,
    rationale: str | None = None,
) -> None:
```

```python
            lesson_learned=lesson_learned,
            failure_mode=failure_mode,
        )
```

> **Technical note (Codex R1 finding #1).** `complete_trade_review` declares all review fields keyword-only (`def complete_trade_review(conn, trade_id, *, reviewed_at, …, event_ts, rationale=None)`). For **keyword-only** params Python *does* permit a defaulted param before a required one (`def f(*, a=1, b)` is valid — the "non-default after default" rule applies only to *positional* params), so placing `failure_mode=None` before `event_ts` would also be valid. We nonetheless place it **after** `event_ts` (before `rationale`) for clarity and to avoid the foot-gun. All callers pass `event_ts=` / `rationale=` by keyword (verified `routes/trades.py:2790`, `cli.py:1474`), so the reorder is caller-safe.

- [ ] **Step 11: Run the full new suite + the legacy review suite to verify GREEN**

Run: `cd <worktree> && python -m pytest tests/data/test_b7_failure_mode_schema.py tests/trades/test_review.py -q`
Expected: PASS (incl. every pre-v24 legacy review fixture in `test_review.py`).

Then a focused regression sweep of the repos + migration consumers:

Run: `python -m pytest tests/data/ tests/trades/ -q`
Expected: PASS.

- [ ] **Step 12: ruff + commit (ONE commit — gotcha #11 atomic)**

Run: `ruff check swing/`
Expected: clean.

```bash
cd <worktree>
git branch --show-current   # must be b7-operator-failure-mode-writing-plans... (exec branch at run time)
git add swing/data/migrations/0024_phase15_b7_failure_mode.sql swing/data/db.py \
        swing/data/models.py swing/data/repos/trades.py swing/trades/review.py \
        tests/data/test_b7_failure_mode_schema.py
git commit -m "feat(data): add nullable failure_mode column (migration 0024 / v24)

The #11 atomic task: migration 0024 CHECK enum, FAILURE_MODES frozenset,
Trade.failure_mode field plus __post_init__ validator, the three-era read
projection, the PRAGMA-aware review UPDATE, complete_trade_review threading,
and the strict v23 to v24 backup gate land together so no partial state leaves
the schema and the model disagreeing."
git log -1 --format='%(trailers)'   # MUST print [] (no Co-Authored-By / trailer)
```

---

## Slice B — the capture surfaces

Slice B depends on Slice A (the column must exist before the form persists into it). TDD per task.

### Task B1: ordered display tuple + helpers in `review.py`

**Files:**
- Modify: `swing/trades/review.py` (add helpers near `MISTAKE_TAGS`, `:62`)
- Test: `tests/trades/test_failure_mode_display.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/trades/test_failure_mode_display.py`:

```python
from swing.data.models import FAILURE_MODES
from swing.trades.review import (
    FAILURE_MODE_DISPLAY,
    failure_mode_display_choices,
    failure_mode_label,
)


def test_display_values_match_vocabulary_exactly() -> None:
    # The display set and the validation set must never drift.
    assert {v for v, _ in FAILURE_MODE_DISPLAY} == FAILURE_MODES


def test_display_order_is_deterministic_and_complete() -> None:
    choices = failure_mode_display_choices()
    assert isinstance(choices, tuple) and len(choices) == 7
    assert choices[0] == ("thesis_invalidated", "Thesis invalidated")
    # Every label is plain ASCII (the form is rendered; the CLI echo is cp1252).
    for value, label in choices:
        assert label.isascii(), f"non-ASCII label for {value!r}: {label!r}"


def test_label_lookup() -> None:
    assert failure_mode_label("execution_error") == "Execution error"
    assert failure_mode_label(None) is None
    assert failure_mode_label("unknown_token") == "unknown_token"  # passthrough
```

- [ ] **Step 2: Run to verify FAIL**

Run: `python -m pytest tests/trades/test_failure_mode_display.py -q`
Expected: FAIL — `ImportError: cannot import name 'FAILURE_MODE_DISPLAY'`.

- [ ] **Step 3: Implement**

In `swing/trades/review.py`, after `ALL_MISTAKE_TAGS` (`:66`) add (importing `FAILURE_MODES` from models — `review.py` already imports `Trade` from `swing.data.models` at `:23`):

```python
from swing.data.models import FAILURE_MODES, Trade  # extend the existing import

# B-7 (Phase 15) — ordered (value, label) display tuple for the failure-mode
# <select>. A frozenset has NO iteration-order guarantee, so the form/labels MUST
# iterate THIS tuple, never FAILURE_MODES directly. Labels are plain-ASCII title-
# case prose (hyphens, NOT em-dashes -- the CLI echo is a cp1252 stdout path and
# the form snippet keeps parity). A test asserts {v for v, _ in DISPLAY} ==
# FAILURE_MODES so the two never drift.
FAILURE_MODE_DISPLAY: tuple[tuple[str, str], ...] = (
    ("thesis_invalidated", "Thesis invalidated"),
    ("normal_volatility_stop", "Normal-volatility stop"),
    ("market_regime_shift", "Market / sector regime shift"),
    ("adverse_event_shock", "Adverse event shock"),
    ("execution_error", "Execution error"),
    ("failed_to_advance", "Failed to advance (dead money)"),
    ("other", "Other"),
)

_FAILURE_MODE_LABELS: dict[str, str] = dict(FAILURE_MODE_DISPLAY)


def failure_mode_display_choices() -> tuple[tuple[str, str], ...]:
    """Ordered (value, label) pairs for the review-form <select> + VM."""
    return FAILURE_MODE_DISPLAY


def failure_mode_label(value: str | None) -> str | None:
    """Map a stored token to its display label; None -> None; unknown -> itself."""
    if value is None:
        return None
    return _FAILURE_MODE_LABELS.get(value, value)
```

> Update the existing `from swing.data.models import Trade` at `:23` to `from swing.data.models import FAILURE_MODES, Trade`.

- [ ] **Step 4: Run to verify PASS**

Run: `python -m pytest tests/trades/test_failure_mode_display.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/review.py tests/trades/test_failure_mode_display.py
git commit -m "feat(trades): add ordered failure-mode display tuple and label helpers

The form and chronology consume an explicit ordered (value, label) tuple rather
than iterating the unordered FAILURE_MODES frozenset so option order is stable."
```

### Task B2: `ReviewVM.failure_mode_choices` + `build_review_vm` populates it

**Files:**
- Modify: `swing/web/view_models/trades.py` (`ReviewVM` `:1139-1178`; `build_review_vm` return `:1370-1390`)
- Test: `tests/web/test_review_vm_failure_mode.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_review_vm_failure_mode.py`:

```python
from swing.web.view_models.trades import ReviewVM


def test_review_vm_has_failure_mode_choices_default() -> None:
    # Safe default so a VM constructed without the field still renders.
    import inspect
    sig = inspect.signature(ReviewVM)
    assert "failure_mode_choices" in sig.parameters


def test_base_layout_does_not_dereference_failure_mode_choices() -> None:
    # 5-VM rule: failure_mode_choices is referenced ONLY in review_form.html.j2,
    # so a safe default on ReviewVM suffices; base.html.j2 must not deref it.
    from pathlib import Path
    base = Path("swing/web/templates/base.html.j2").read_text(encoding="utf-8")
    assert "failure_mode_choices" not in base
```

- [ ] **Step 2: Run to verify FAIL**

Run: `python -m pytest tests/web/test_review_vm_failure_mode.py -q`
Expected: FAIL — `assert "failure_mode_choices" in sig.parameters`.

- [ ] **Step 3: Implement**

In `swing/web/view_models/trades.py`, add a field to `ReviewVM` with a safe default (place beside the other defaulted fields, e.g. after `grade_choices` `:1150`):

```python
    # B-7 (Phase 15) — ordered (value, label) pairs for the failure-mode <select>.
    # Safe default () keeps the VM constructible without the field; referenced
    # ONLY in review_form.html.j2 (no base-layout deref -> the 5-VM rule needs no
    # other base-layout VM change).
    failure_mode_choices: tuple[tuple[str, str], ...] = ()
```

In `build_review_vm`, import the helper (extend the existing `from swing.trades.review import (...)` block `:1247-1254`) and pass it in the `return ReviewVM(...)` (`:1370-1390`):

```python
    from swing.trades.review import (
        DISQUALIFYING_VIOLATIONS,
        MISTAKE_TAGS,
        compute_actual_realized_R_effective,
        compute_lucky_violation_R,
        compute_mistake_cost_R,
        failure_mode_display_choices,
        get_priors_for_ticker,
    )
```

```python
        review_chart_url=f"/trades/{trade_id}/review/chart",
        failure_mode_choices=failure_mode_display_choices(),
    )
```

- [ ] **Step 4: Run to verify PASS**

Run: `python -m pytest tests/web/test_review_vm_failure_mode.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/trades.py tests/web/test_review_vm_failure_mode.py
git commit -m "feat(web): surface ordered failure-mode choices on ReviewVM"
```

### Task B3: review-form `<select>` fieldset

**Files:**
- Modify: `swing/web/templates/partials/review_form.html.j2` (insert between `:106` and `:108`)
- Test: `tests/web/test_review_form_failure_mode.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_review_form_failure_mode.py`:

```python
from pathlib import Path


def test_form_has_failure_mode_select_with_blank_default() -> None:
    src = Path(
        "swing/web/templates/partials/review_form.html.j2").read_text(encoding="utf-8")
    assert 'name="failure_mode"' in src
    # Default blank option persists NULL on an unattributed submit.
    assert '<option value="">' in src
    assert "vm.failure_mode_choices" in src


def test_form_failure_mode_strings_are_ascii() -> None:
    src = Path(
        "swing/web/templates/partials/review_form.html.j2").read_text(encoding="utf-8")
    # The new fieldset's legend + blank-option text use plain hyphens (spec §7.1 #8).
    legend = "Why did this trade fail? (outcome attribution - optional)"
    blank = "- not a loss / not attributed -"
    assert legend in src and blank in src
    assert legend.isascii() and blank.isascii()
```

- [ ] **Step 2: Run to verify FAIL**

Run: `python -m pytest tests/web/test_review_form_failure_mode.py -q`
Expected: FAIL — `assert 'name="failure_mode"' in src`.

- [ ] **Step 3: Implement**

In `swing/web/templates/partials/review_form.html.j2`, insert AFTER the Mistake-tags `</fieldset>` (`:106`) and BEFORE the Counterfactual `<fieldset>` (`:108`):

```html
  <fieldset>
    <legend>Why did this trade fail? (outcome attribution - optional)</legend>
    <label>
      Primary failure mode
      <select name="failure_mode">
        <option value="">- not a loss / not attributed -</option>
        {% for value, label in vm.failure_mode_choices %}
          <option value="{{ value }}">{{ label }}</option>
        {% endfor %}
      </select>
    </label>
    <p><small>Records the proximate cause of the loss for later attribution
       analysis. Separate from process grade (how well you executed) and mistake
       tags (what you did wrong): a clean "good loss" can be an A-grade trade with
       zero mistakes.</small></p>
  </fieldset>
```

> ASCII discipline: plain hyphens only in the new strings (the existing form has em-dashes elsewhere — out of scope, do not touch).

- [ ] **Step 4: Run to verify PASS**

Run: `python -m pytest tests/web/test_review_form_failure_mode.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/partials/review_form.html.j2 \
        tests/web/test_review_form_failure_mode.py
git commit -m "feat(web): add failure-mode select to the review form"
```

### Task B4: `review_post` parses, validates, threads

**Files:**
- Modify: `swing/web/routes/trades.py:2669-2799`
- Test: **append** to `tests/web/test_review_route.py` (reuse its `test_app_closed_trade` fixture `:16-68` — `ensure_schema` migrates the DB to HEAD = v24; the existing happy-path POST test is at `:203-221`, the 400-re-render test at `:224-240`)

- [ ] **Step 1: Write the failing tests (concrete; appended to `tests/web/test_review_route.py`)**

These use the real `test_app_closed_trade` fixture (closed VIR trade id=1) already in that module. `app.state.cfg.paths.db_path` is the DB path; read it back with `swing.data.db.connect`. The success cases assert BOTH `204` AND the L6 `HX-Redirect` invariant (Codex R2 finding #2):

```python
def test_post_review_blank_failure_mode_persists_null(test_app_closed_trade) -> None:
    app = test_app_closed_trade
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "failure_mode": ""},
            headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204                                   # success unchanged
    assert r.headers.get("HX-Redirect") == "/reviews/pending"     # L6 invariant
    from swing.data.db import connect
    val = connect(app.state.cfg.paths.db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=1").fetchone()[0]
    # PRE-FIX: 422 (unknown Form field) OR column never written. POST-FIX: the
    # ... or None gotcha persists NULL on a blank submit.
    assert val is None


def test_post_review_valid_failure_mode_persists(test_app_closed_trade) -> None:
    app = test_app_closed_trade
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "failure_mode": "thesis_invalidated"},
            headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/reviews/pending"     # L6 invariant
    from swing.data.db import connect
    val = connect(app.state.cfg.paths.db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=1").fetchone()[0]
    assert val == "thesis_invalidated"


def test_post_review_invalid_failure_mode_is_400_not_500(test_app_closed_trade) -> None:
    app = test_app_closed_trade
    with TestClient(app) as client:
        r = client.post(
            "/trades/1/review",
            data={"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                  "lesson_learned": "clean", "mistake_tags": ["none_observed"],
                  "failure_mode": "not_a_token"},
            headers={"HX-Request": "true"})
    # PRE-FIX: the value reaches the CHECK -> 500 IntegrityError. POST-FIX:
    # validated against FAILURE_MODES BEFORE the DB -> a clean 400 + re-render.
    assert r.status_code == 400
    assert 'name="lesson_learned"' in r.text                      # form re-rendered
    assert "failure_mode" in r.text.lower() or "failure mode" in r.text.lower()
```

> `ensure_schema` (used by `test_app_closed_trade`) migrates to `EXPECTED_SCHEMA_VERSION` = 24, so the `failure_mode` column exists in the fixture DB. `TestClient`, `pytest`, and the fixture are already imported at the top of `test_review_route.py`.

- [ ] **Step 2: Run to verify FAIL**

Run: `python -m pytest tests/web/test_review_route.py -k failure_mode -q`
Expected: FAIL (422 from the unknown Form field, or 500 on the invalid token).

- [ ] **Step 3: Implement**

In `swing/web/routes/trades.py` `review_post`:

1. Add to the signature (after `mistake_tags` `:2679`): `failure_mode: str | None = Form(None),`.
2. After the grade-compute block (after `:2751`, before `conn = connect(...)` `:2753`), normalize + validate:

```python
    from swing.data.models import FAILURE_MODES
    fm = failure_mode or None  # ... or None: empty string -> NULL (nullable CHECK)
    if fm is not None and fm not in FAILURE_MODES:
        from swing.web.view_models.trades import build_review_vm
        vm = build_review_vm(trade_id=trade_id, cfg=cfg)
        fm_err = f"Invalid failure_mode {fm!r}"
        if vm is None:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": fm_err}, status_code=400)
        return templates.TemplateResponse(
            request, "partials/review_form.html.j2",
            {"vm": vm, "error_message": fm_err}, status_code=400)
```

3. Thread into the `complete_trade_review(...)` call (after `lesson_learned=lesson_learned,` `:2789`): `failure_mode=fm,`.

- [ ] **Step 4: Run to verify PASS**

Run: `python -m pytest tests/web/test_review_route.py -k failure_mode -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_review_route.py
git commit -m "feat(web): validate and persist failure_mode on review POST"
```

### Task B5: PRAGMA-aware chronology read-back

**Files:**
- Modify: `swing/web/view_models/trade_chronology.py:157-187`
- Test: `tests/web/test_trade_chronology_failure_mode.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_trade_chronology_failure_mode.py`:

```python
import sqlite3
from pathlib import Path

from swing.data.db import run_migrations
from swing.web.view_models.trade_chronology import _review_entry


def _seed_reviewed(conn, *, failure_mode_sql: str, fm_value):
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        f"current_size, reviewed_at, process_grade, lesson_learned, mistake_tags"
        f"{failure_mode_sql}) VALUES ('CH','2026-05-01',10.0,1,9.0,9.0,'reviewed',"
        "'manual_off_pipeline','2026-05-01T09:30:00',1.0,'2026-05-05T16:00:00',"
        f"'A','learned','[]'{', ?' if fm_value is not None else ''})",
        ((fm_value,) if fm_value is not None else ()))
    return conn.execute("SELECT id FROM trades WHERE ticker='CH'").fetchone()[0]


def test_v24_reviewed_trade_shows_failure_mode_label(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "swing.db"))
    run_migrations(conn, target_version=24, backup_dir=tmp_path)
    tid = _seed_reviewed(conn, failure_mode_sql=", failure_mode",
                         fm_value="execution_error")
    entries = _review_entry(conn, tid)
    assert entries and "Execution error" in (entries[0].detail or "")


def test_pre_v24_chronology_renders_without_no_such_column(tmp_path):
    # PRE-FIX: a literal "SELECT ... failure_mode" raises OperationalError on a
    # pre-v24 DB. POST-FIX: PRAGMA fallback selects NULL AS failure_mode -> renders.
    conn = sqlite3.connect(str(tmp_path / "swing.db"))
    run_migrations(conn, target_version=16, backup_dir=tmp_path)
    tid = _seed_reviewed(conn, failure_mode_sql="", fm_value=None)
    entries = _review_entry(conn, tid)  # must NOT raise
    assert entries  # the review entry still renders
```

- [ ] **Step 2: Run to verify FAIL**

Run: `python -m pytest tests/web/test_trade_chronology_failure_mode.py -q`
Expected: FAIL — the v24 label is absent (the SELECT doesn't read `failure_mode`).

- [ ] **Step 3: Implement**

Rewrite `_review_entry` (`:157-187`) PRAGMA-aware:

```python
def _review_entry(conn, trade_id) -> list[ChronologyEntry]:
    # Verified trades review columns (models.py): reviewed_at, process_grade,
    # lesson_learned, mistake_tags. B-7: failure_mode is PRAGMA-aware so a pre-v24
    # DB / chronology fixture renders without `no such column: failure_mode`.
    from swing.trades.review import failure_mode_label
    has_fm = "failure_mode" in {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    fm_select = "failure_mode" if has_fm else "NULL AS failure_mode"
    row = conn.execute(
        f"SELECT reviewed_at, process_grade, lesson_learned, mistake_tags, "
        f"{fm_select} FROM trades WHERE id = ? AND reviewed_at IS NOT NULL",
        (trade_id,)).fetchone()
    if not row:
        return []
    reviewed_at, grade, lesson, tags, failure_mode = row
    ts_key, malformed = _normalize_ts(reviewed_at, precision="datetime")
    tag_display: str | None = None
    if tags:
        try:
            parsed = json.loads(tags)
            tag_display = (", ".join(str(t) for t in parsed)
                           if isinstance(parsed, list) else str(tags))
        except (ValueError, TypeError):
            tag_display = str(tags)
    fm_label = failure_mode_label(failure_mode)
    detail = "; ".join(b for b in (fm_label, lesson, tag_display) if b)
    return [ChronologyEntry(
        ts=ts_key, source="review", kind="review",
        summary=(str(grade) if grade else ""),
        detail=(detail or None), ts_malformed=malformed)]
```

- [ ] **Step 4: Run to verify PASS**

Run: `python -m pytest tests/web/test_trade_chronology_failure_mode.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/trade_chronology.py \
        tests/web/test_trade_chronology_failure_mode.py
git commit -m "feat(web): fold failure-mode label into the chronology review entry"
```

### Task B6: CLI `--failure-mode` option

**Files:**
- Modify: `swing/cli.py:1330-1483`
- Test: **append** to `tests/cli/test_trade_review_cli.py` (reuse its `_setup(tmp_path) -> (runner, cfg, db_path)` `:28-39` and `_seed_closed_trade(db_path) -> trade_id` `:42-95`; `ensure_schema` migrates to HEAD = v24; `main` is imported at `:20`)

- [ ] **Step 1: Write the failing tests (concrete; appended to `tests/cli/test_trade_review_cli.py`)**

These reuse the module's existing `_setup` + `_seed_closed_trade` helpers and the `["--config", str(cfg), "trade", "review", …]` invocation shape (verified against `:102-114`):

```python
def test_cli_valid_failure_mode_persists(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--failure-mode", "thesis_invalidated"])
    assert res.exit_code == 0, res.output
    from swing.data.db import connect
    assert connect(db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] == "thesis_invalidated"


def test_cli_omitted_failure_mode_persists_null(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean"])
    assert res.exit_code == 0, res.output
    from swing.data.db import connect
    assert connect(db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] is None


def test_cli_invalid_failure_mode_is_clean_clickexception(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--failure-mode", "not_a_token"])
    # PRE-FIX: "No such option: --failure-mode" (exit 2). POST-FIX: a clean
    # ClickException message (exit 1), NOT a traceback (no leaked ValueError).
    assert res.exit_code != 0
    assert not isinstance(res.exception, (KeyError, AttributeError, TypeError, ValueError))
    assert "failure" in res.output.lower()
```

- [ ] **Step 2: Run to verify FAIL**

Run: `python -m pytest tests/cli/test_trade_review_cli.py -k failure_mode -q`
Expected: FAIL — `No such option: --failure-mode`.

- [ ] **Step 3: Implement**

Add the option decorator after `--lesson-learned` (`:1356`):

```python
@click.option("--failure-mode", "failure_mode", default=None,
              help="Optional outcome attribution for a losing trade. One of: "
                   "thesis_invalidated, normal_volatility_stop, "
                   "market_regime_shift, adverse_event_shock, execution_error, "
                   "failed_to_advance, other. Omit for a winner / unattributed.")
```

Add `failure_mode` to the `trade_review_cmd(...)` parameter list (`:1359-1364`). Inside the command, validate + wrap (after the `validate_mistake_tags` block, before `compute_process_grade` `:1450`):

```python
        from swing.data.models import FAILURE_MODES
        if failure_mode is not None and failure_mode not in FAILURE_MODES:
            raise click.ClickException(
                f"Invalid --failure-mode {failure_mode!r}; choose one of "
                f"{sorted(FAILURE_MODES)} or omit.")
```

Thread it into the `complete_trade_review(...)` call (after `lesson_learned=lesson_learned,` `:1473`): `failure_mode=failure_mode,`. Wrap the call in a `ValueError -> ClickException` guard so the repo-layer pre-v24 ValueError surfaces cleanly (defense-in-depth; production is v24):

```python
        try:
            complete_trade_review(
                conn, trade_id,
                reviewed_at=reviewed_at,
                mistake_tags_json=json.dumps(canonical_tags),
                entry_grade=entry_grade,
                management_grade=management_grade,
                exit_grade=exit_grade,
                process_grade=process_grade,
                disqualifying_process_violation=disqualifying_process_violation,
                realized_R_if_plan_followed=realized_r_if_plan_followed,
                mistake_cost_confidence=mistake_cost_confidence or None,
                lesson_learned=lesson_learned,
                failure_mode=failure_mode,
                event_ts=reviewed_at,
                rationale=None,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
```

Optionally extend the success echo (`:1480-1483`) with an ASCII suffix (plain hyphen, no glyph):

```python
    click.echo(
        f"Review recorded for trade #{trade_id} ({trade.ticker}). "
        f"Process grade: {process_grade}."
        + (f" Failure mode: {failure_mode}." if failure_mode else ""))
```

- [ ] **Step 4: Run to verify PASS**

Run: `python -m pytest tests/cli/test_trade_review_cli.py -k failure_mode -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_trade_review_cli.py
git commit -m "feat(cli): add --failure-mode option to the trade review command"
```

### Task B7: L2 orthogonality guard test (no implementation)

**Files:**
- Test: `tests/trades/test_failure_mode_orthogonality.py` (new) — the static guards
- Test: `tests/metrics/test_process.py` (append) — the metric-level guard (Codex R1 finding #3)

These are **standing guards** (they pass on first run because the code already keeps the surfaces separate). They document the L2 contract and fail only if a future change wires `failure_mode` into the grade or the mistake-tag vocabulary/metric. They assert COMPUTATIONAL separation, NOT statistical independence (an `execution_error` outcome may legitimately co-occur with execution mistake tags — that is fine).

- [ ] **Step 1: Write the static guard tests**

Create `tests/trades/test_failure_mode_orthogonality.py`:

```python
import inspect

from swing.data.models import FAILURE_MODES
from swing.trades.review import (
    ALL_MISTAKE_TAGS,
    MISTAKE_TAGS,
    compute_process_grade,
)


def test_failure_mode_does_not_feed_process_grade() -> None:
    # The grade measures execution quality; the failure mode measures outcome
    # cause. They are deliberately decoupled -- no failure_mode parameter.
    assert "failure_mode" not in inspect.signature(compute_process_grade).parameters


def test_failure_mode_vocabulary_is_disjoint_from_mistake_tags() -> None:
    # failure_mode is NOT a mistake tag. Disjoint token sets prove the
    # computational separation at the vocabulary level.
    assert FAILURE_MODES.isdisjoint(ALL_MISTAKE_TAGS)
    flat = {t for tags in MISTAKE_TAGS.values() for t in tags}
    assert FAILURE_MODES.isdisjoint(flat)
```

- [ ] **Step 2: Write the metric-level guard (Codex R1 finding #3)**

The vocabulary-disjointness check above is necessary but not sufficient — spec §6/§7.1 #5 requires `failure_mode` be **excluded from the mistake-tag frequency metric** itself. Verified faithful: `compute_trade_process_metrics` (`swing/metrics/process.py:747-768`) builds `mistake_tag_frequency` purely from `x.trade.mistake_tags` (JSON) and never references `failure_mode`. Append to `tests/metrics/test_process.py` (reuse its `conn` fixture + `_seed_full_trade` helper + the `hypothesis_label="A+ baseline"` filter; the helper defaults that label):

```python
def test_failure_mode_excluded_from_mistake_tag_frequency_metric(
    conn: sqlite3.Connection,
) -> None:
    # A reviewed trade carrying BOTH a mistake tag AND a failure_mode must NOT
    # leak the failure_mode token into mistake_tag_frequency.
    from swing.data.models import FAILURE_MODES
    _seed_full_trade(
        conn, trade_id=1, ticker="ORTH",
        entry_price=10.0, initial_stop=9.0, initial_shares=100, exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        mistake_tags=json.dumps(["SOLD_TOO_EARLY"]),
    )
    # The metric runs against v24 here (the test DB is migrated to HEAD), so the
    # failure_mode column exists; stamp it directly on the seeded reviewed row.
    conn.execute(
        "UPDATE trades SET failure_mode = 'execution_error' WHERE id = 1")
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    freq = result.mistake_tag_frequency
    # PRE-FIX (hypothetical leak): "execution_error" would appear as a key.
    # POST-FIX: the metric only sees mistake_tags -> the failure_mode token is absent.
    assert "execution_error" in FAILURE_MODES  # sanity: it IS a failure-mode token
    assert "execution_error" not in freq
    assert set(freq.keys()).isdisjoint(FAILURE_MODES)
    assert "SOLD_TOO_EARLY" in freq  # the real mistake tag still counts
```

> If `_seed_full_trade` is module-private and the metrics test file already migrates the fixture DB to HEAD (`EXPECTED_SCHEMA_VERSION == 24`), the `UPDATE … failure_mode` succeeds. If the metrics `conn` fixture pins an older `target_version`, bump it to default (HEAD) for this test or guard the UPDATE with the PRAGMA check (mirror Task B5). Confirm against the fixture at execution time.

- [ ] **Step 3: Run to verify both guards PASS**

Run: `python -m pytest tests/trades/test_failure_mode_orthogonality.py tests/metrics/test_process.py::test_failure_mode_excluded_from_mistake_tag_frequency_metric -q`
Expected: PASS (the surfaces are already separate; the static guard would FAIL if a later change adds a `failure_mode` param to `compute_process_grade` or folds a token into `MISTAKE_TAGS`; the metric guard would FAIL if the frequency metric ever consumed `failure_mode`).

- [ ] **Step 4: Commit**

```bash
git add tests/trades/test_failure_mode_orthogonality.py tests/metrics/test_process.py
git commit -m "test: guard the failure-mode orthogonality contract at vocabulary and metric level"
```

### Slice B final: full fast-suite sanity + ruff

- [ ] Run: `cd <worktree> && python -m pytest -m "not slow" -q` — Expected: GREEN (baseline ~7053 + the B-7 deltas; READ the actual count, do not carry a stale number — memory `feedback_no_false_green_claim`).
- [ ] Run: `ruff check swing/` — Expected: clean.

---

## The operator-witnessed browser gate (BINDING — L6; spec §7.2)

TestClient cannot catch the HTMX browser-only surfaces (`hx-headers` OriginGuard 403; `204`+`HX-Redirect` vs `303` swallow). The binding acceptance gate is an **operator-driven real-browser submit** on a real closed-but-unreviewed trade. Enumerate for the operator at executing-plans close:

1. Open a real closed-but-unreviewed trade's `/trades/{id}/review` page in a browser.
2. **Attributed path:** select a failure mode (e.g. `thesis_invalidated`), fill the required fields, submit. Confirm the browser navigates to `/reviews/pending` (the `HX-Redirect` fired — NOT a swap, NOT a stuck form). Confirm `SELECT failure_mode FROM trades WHERE id=...` shows the token. Confirm the chronology read-back displays the label.
3. **Unseeded-blank path (memory `feedback_seeded_gate_masks_default_state`):** on another closed trade, LEAVE the failure-mode control blank and submit. Confirm `NULL` persists AND the chronology shows NO failure-mode line. The blank/winner path is the common case and MUST be witnessed too.

---

## Self-review (run against the spec; fix inline)

**Spec coverage check:**
- §3.4 `FAILURE_MODES` in `models.py` (import-cycle fix) → Task A1 Step 8. ✅
- §4.1 migration 0024 nullable CHECK → A1 Step 6. ✅
- §4.3 #1-5 the #11 atomic set (CHECK + frozenset + validator + three-era read + both write paths) → A1 Steps 6-10. ✅ (insert path: documented no-op + guard test.)
- §4.4 strict `_b7_backup_gate` + `EXPECTED_SCHEMA_VERSION` 24 → A1 Step 7. ✅
- §5.1 form fieldset placement (after Mistake-tags, before Counterfactual) → B3. ✅
- §5.4 POST `... or None` + 400+re-render + thread → B4. ✅
- §5.5 `ReviewVM.failure_mode_choices` + ordered `FAILURE_MODE_DISPLAY` + base-layout no-deref → B1/B2. ✅
- §5.6 PRAGMA-aware `_review_entry` → B5. ✅
- §5.7 CLI `--failure-mode` + `click.ClickException` + ASCII → B6. ✅
- §6 orthogonality (computational, not zero-correlation) → B7. ✅
- §7.1 #1-8 tests → A1 (#1-3,7), B3/B6/B1 (#8 ASCII), B4 (#4), B7 (#5), B5 (#6). ✅
- §7.2 browser gate incl. unseeded-blank → the gate section. ✅

**Placeholder scan:** no "TBD"/"handle edge cases". The web (B4) and CLI (B6) tests are now CONCRETE — they append to the real harness files (`tests/web/test_review_route.py`'s `test_app_closed_trade` fixture; `tests/cli/test_trade_review_cli.py`'s `_setup` + `_seed_closed_trade`) with real fixtures, not undefined `client`/`runner` params (resolved per Codex R2). The `_mk` helper in A1 Step 3 is flagged to hoist above first use.

**Type consistency:** `failure_mode: str | None` everywhere (model field, `update_trade_review_fields` param, `complete_trade_review` param, POST `Form(None)`, CLI option, `failure_mode_label` arg). `FAILURE_MODE_DISPLAY: tuple[tuple[str, str], ...]`; `ReviewVM.failure_mode_choices: tuple[tuple[str, str], ...]`. `_TRADE_SELECT_COLS_V21_TO_V23` matches the naming family. `failure_mode` is column index **54** in all three projections (0-53 unchanged).

**Regression-test arithmetic (memory `feedback_regression_test_arithmetic`):** each test documents the PRE-FIX vs POST-FIX value so it distinguishes (e.g. the three-era test: a naive two-era impl returns `candidate_id is None` for a v23 row, the correct three-era impl returns `42/77`; the validator test: pre-fix `Trade(failure_mode="bogus")` returns an object, post-fix raises).

---

## Schema verdict

- **v23 → v24** — the FIRST migration since the schwabdev arc (which made no swing-DB change; last bump v22→v23 at SB3 `edd098d`).
- **Migration 0024** — a single nullable CHECK `ADD COLUMN` (NO table rebuild).
- **The #11 atomic task** (Slice A, ONE commit): migration CHECK + `FAILURE_MODES` + `Trade.failure_mode` + `__post_init__` + three-era read mapper + both write paths land together.
- **Strict backup-gate** — `_b7_backup_gate`, `current_version == 23 AND target_version >= 24` (STRICT, NOT `<=`); run-migrate-twice no-op; `EXPECTED_SCHEMA_VERSION == 24` asserted.
- **Operator live-DB** migrates v23→v24 at ship; existing rows get `failure_mode = NULL` (forward-only, OQ-6).

---

## Task count + line estimate

- **Slice A:** 1 task (A1), 12 steps, 1 commit (~6 production files + 1 new test file).
- **Slice B:** 7 tasks (B1-B7), 6 commits + the final sanity sweep (~6 production files + 5 new test files).
- **Total:** 8 tasks, 7 commits, 1 manual browser gate. Plan length ~ this document.

---

## Execution handoff

Plan complete. **Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.
2. **Inline Execution** — `superpowers:executing-plans`, batch with checkpoints.

**Slice sequencing is fixed: A before B** (the column must exist before the form/CLI/chronology persist into it). The operator browser gate (incl. the unseeded-blank witness) is the binding acceptance gate after Slice B.
