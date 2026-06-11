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


def _mk(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fresh(tmp_path: Path, *, target: int) -> sqlite3.Connection:
    # foreign_keys at sqlite default (OFF) so synthetic backlink UPDATEs in the
    # v21-v23 era fixture don't need a real candidates parent row.
    conn = sqlite3.connect(str(tmp_path / "swing.db"))
    run_migrations(conn, target_version=target, backup_dir=tmp_path)
    return conn


def _cols(conn: sqlite3.Connection) -> set[str]:
    return {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}


def test_expected_schema_version_is_24() -> None:
    assert EXPECTED_SCHEMA_VERSION == 28


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


def test_read_mapper_three_eras(tmp_path: Path) -> None:
    # --- v24 era: failure_mode round-trips ---
    conn24 = _fresh(_mk(tmp_path, "v24"), target=24)
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


def test_complete_trade_review_threads_failure_mode(tmp_path: Path) -> None:
    from swing.data.models import Fill
    from swing.data.repos.fills import insert_fill_with_event
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
