"""Discriminating tests for ``swing diagnose backfill-trades-sector-industry``
(Phase 14 Sub-bundle 1 V2.G3 backfill CLI subcommand).

Tests cover spec section 4.3 + 4.5 discriminating-example walkthroughs
plus restore-SQL artifact emission (R1.M3 LOCK) + AND-empty WHERE clause
(R2.M3 LOCK) + idempotency + ASCII discipline.

Production-shape note (orchestrator brief): the plan code blocks reference
``insert_trade`` + ``fetch_trade_by_id`` which DO NOT exist in
``swing/data/repos/trades.py``. The canonical insert helper is
``insert_trade_with_event(conn, trade, *, event_ts, rationale=None)`` per
``swing/data/repos/trades.py:155``; tests read back via raw SQL because
there is no ``fetch_trade_by_id`` repo function.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from swing.cli import main as swing_cli
from swing.data.db import ensure_schema
from swing.data.models import Candidate, EvaluationRun, Trade
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.data.repos.trades import insert_trade_with_event


def _build_candidate_fixture(ticker: str) -> dict[str, Any]:
    """Return Candidate kwargs minus ticker/sector/industry (T-1.1 precedent
    at tests/data/repos/test_candidates_sector_industry_helper.py:25)."""
    return {
        "bucket": "watch",
        "close": 25.0,
        "pivot": 26.0,
        "initial_stop": 24.0,
        "adr_pct": 3.5,
        "tight_streak": 5,
        "pullback_pct": 4.0,
        "prior_trend_pct": 40.0,
        "rs_rank": 80,
        "rs_return_12w_vs_spy": 0.15,
        "rs_method": "universe",
        "pattern_tag": None,
        "notes": None,
        "criteria": (),
    }


def _build_trade_fixture(ticker: str) -> dict[str, Any]:
    """Return Trade kwargs minus id/ticker/state/sector/industry.

    Mirrors the minimal production-shape Trade construction used at
    ``tests/web/test_view_models/test_trades.py:70-76``. ``insert_trade_with_event``
    enforces ``state='entered'`` at insert time regardless of input; tests
    that need a different state (e.g. 'closed' for --include-closed test)
    post-UPDATE the state directly via SQL.
    """
    return {
        "entry_date": "2026-05-01",
        "entry_price": 100.0,
        "initial_shares": 10,
        "initial_stop": 95.0,
        "current_stop": 95.0,
        "watchlist_entry_target": None,
        "watchlist_initial_stop": None,
        "notes": None,
    }


def _insert_trade(
    db_path: Path,
    *,
    ticker: str,
    sector: str,
    industry: str,
    state: str = "entered",
) -> int:
    """Insert a Trade row via ``insert_trade_with_event`` + post-UPDATE
    the state if not 'entered' (the helper imposes 'entered' on insert).

    Owns its own connection so call sites can chain multiple inserts on
    the same ``db_path`` without leaking connection handles (matters on
    Windows where a held connection blocks subsequent ``CliRunner.invoke``
    file access on the same db file).
    """
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker=ticker, state="entered",
                    sector=sector, industry=industry,
                    **_build_trade_fixture(ticker),
                ),
                event_ts="2026-05-01T09:30:00",
            )
            if state != "entered":
                conn.execute(
                    "UPDATE trades SET state=? WHERE id=?",
                    (state, trade_id),
                )
    finally:
        conn.close()
    return trade_id


def _read_back_sector_industry(
    db_path: Path, trade_id: int,
) -> tuple[str, str]:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT sector, industry FROM trades WHERE id=?",
            (trade_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, f"trade {trade_id} not found"
    return row[0], row[1]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_subcommand_registered_in_diagnose_group():
    """CLI registration smoke -- subcommand visible in --help."""
    runner = CliRunner()
    result = runner.invoke(swing_cli, ["diagnose", "--help"])
    assert result.exit_code == 0
    assert "backfill-trades-sector-industry" in result.output


def test_dry_run_emits_table_and_restore_sql_artifact(tmp_path):
    """Dry-run prints table + writes restore-SQL artifact at deterministic
    path (R1.M3 LOCK; gotcha #27 audit emission)."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "exports" / "diagnostics"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    _insert_trade(
        db_path, ticker="VSAT", sector="", industry="",
    )

    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "UPDATE" in result.output
    assert "VSAT" in result.output
    artifacts = list(output_dir.glob(
        "backfill-trades-sector-industry-restore-*.sql"
    ))
    assert len(artifacts) == 1
    restore_sql = artifacts[0].read_text(encoding="ascii")
    assert "UPDATE trades SET sector='', industry=''" in restore_sql


def test_partial_empty_row_emits_skip_partial_empty_action(tmp_path):
    """Partial-empty (sector='Tech', industry='') row falls through to
    SKIP_PARTIAL_EMPTY (V1 STRICT all-or-nothing per R2.M3 LOCK)."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT", sector="Tech", industry="Comms",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    # Plant a partial-empty trade row.
    _insert_trade(
        db_path,
        ticker="VSAT", sector="Tech", industry="",
    )

    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    assert "SKIP_PARTIAL_EMPTY" in result.output
    # The partial-empty row was NOT scheduled for UPDATE.
    assert "UPDATE                 : 0" in result.output
    assert "SKIP_PARTIAL_EMPTY     : 1" in result.output


def test_dha_legacy_no_candidates_row_emits_skip_no_candidates(tmp_path):
    """Acknowledged-legacy DHA with no candidates row emits
    SKIP_NO_CANDIDATES_ROW (spec section 4.5 example #3)."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    _insert_trade(
        db_path, ticker="DHA", sector="", industry="",
    )

    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    assert "SKIP_NO_CANDIDATES_ROW : 1" in result.output
    assert "UPDATE                 : 0" in result.output


def test_apply_commits_atomic_update_and_emits_restore_before_update(tmp_path):
    """--apply commits UPDATE under with conn: and emits restore-SQL
    BEFORE the UPDATE fires (spec section 4.3 R1.M3 LOCK)."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    trade_id = _insert_trade(
        db_path, ticker="VSAT", sector="", industry="",
    )

    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--apply",
    ])
    assert result.exit_code == 0, result.output
    assert "APPLY" in result.output
    # Restore-SQL artifact emitted BEFORE the UPDATE (defense-in-depth).
    artifacts = list(output_dir.glob(
        "backfill-trades-sector-industry-restore-*.sql"
    ))
    assert len(artifacts) == 1
    restore_sql = artifacts[0].read_text(encoding="ascii")
    assert f"WHERE id={trade_id}" in restore_sql
    # Post-apply: trade row has the new values.
    sector, industry = _read_back_sector_industry(db_path, trade_id)
    assert sector == "Technology"
    assert industry == "Communications Equipment"


def test_apply_twice_is_idempotent(tmp_path):
    """Re-running --apply emits zero UPDATEs (the WHERE clause filters
    rows already populated)."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    _insert_trade(
        db_path, ticker="VSAT", sector="", industry="",
    )

    runner = CliRunner()
    # First apply.
    result1 = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--apply",
    ])
    assert result1.exit_code == 0, result1.output
    assert "UPDATE                 : 1" in result1.output
    # Second apply -- no-op (row already populated; AND-empty SELECT
    # returns zero rows).
    result2 = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--apply",
    ])
    assert result2.exit_code == 0, result2.output
    assert "UPDATE                 : 0" in result2.output


def test_include_closed_widens_to_all_states(tmp_path):
    """Default excludes closed trades; --include-closed widens."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    # Plant a CLOSED trade with empty sector/industry (post-UPDATE state).
    _insert_trade(
        db_path,
        ticker="VSAT", sector="", industry="", state="closed",
    )

    runner = CliRunner()
    # Default (no --include-closed): closed trade is filtered out.
    result_default = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result_default.exit_code == 0, result_default.output
    assert "UPDATE                 : 0" in result_default.output
    # --include-closed: closed trade is included.
    result_widened = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--include-closed",
    ])
    assert result_widened.exit_code == 0, result_widened.output
    assert "UPDATE                 : 1" in result_widened.output


def test_allowlist_restricts_to_specified_tickers(tmp_path):
    """--allowlist VSAT restricts UPDATEs to that opt-in set."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=2,
                aplus_count=0, watch_count=2, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
                Candidate(
                    ticker="DHC",
                    sector="Communication",
                    industry="Diversified",
                    **_build_candidate_fixture("DHC"),
                ),
            ])
    finally:
        conn.close()
    _insert_trade(
        db_path, ticker="VSAT", sector="", industry="",
    )
    _insert_trade(
        db_path, ticker="DHC", sector="", industry="",
    )

    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--allowlist", "VSAT",
    ])
    assert result.exit_code == 0, result.output
    assert "VSAT" in result.output
    # DHC was excluded by allowlist (not present in any output row).
    assert "DHC" not in result.output


def test_missing_db_path_raises_click_exception(tmp_path):
    """_validate_diagnose_db_path raises ClickException on missing --db."""
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(tmp_path / "does-not-exist.db"),
    ])
    assert result.exit_code != 0
    assert "DB not found" in result.output


def test_dry_run_table_renders_source_candidate_and_run_id_columns(tmp_path):
    """The dry-run table cites source_candidate_id +
    source_evaluation_run_id per spec section 4.3 column list (Codex R1.M#6
    LOCK -- provenance auditability so operators can re-trace which
    candidates row supplied each backfill)."""
    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    _insert_trade(
        db_path, ticker="VSAT", sector="", industry="",
    )

    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    # Column header includes provenance columns.
    assert "source_cand_id" in result.output
    assert "source_eval_run_id" in result.output
    # The UPDATE row cites the actual run_id (not the '-' placeholder
    # used for SKIP rows). run_id is 1 in this fixture.
    assert str(run_id) in result.output


class _ExecuteSpyConn:
    """Proxy that wraps a sqlite3.Connection so ``conn.execute`` calls
    are recorded for assertion. sqlite3.Connection's ``execute``
    attribute is read-only so we cannot monkey-patch in place; the
    proxy delegates everything else and records SQL on each execute
    invocation (per Codex round 1 Major #1 lock verification).
    """

    def __init__(self, underlying, sink: list[str]) -> None:
        self._underlying = underlying
        self._sink = sink

    def execute(self, sql, *args, **kwargs):
        if isinstance(sql, str):
            self._sink.append(sql.strip())
        else:
            self._sink.append(str(sql))
        return self._underlying.execute(sql, *args, **kwargs)

    def __enter__(self):
        return self._underlying.__enter__()

    def __exit__(self, *args, **kwargs):
        return self._underlying.__exit__(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._underlying, name)


def test_apply_path_uses_begin_immediate_lock_for_toctou_safety(tmp_path):
    """Per Codex round 1 Major #1: the apply path MUST acquire a write
    lock via ``BEGIN IMMEDIATE`` so the row set captured in the
    restore-SQL artifact matches the row set actually UPDATEd. Without
    the lock, a concurrent writer could fill an AND-empty trades row
    between the SELECT and UPDATE; the UPDATE no-ops via the
    WHERE-clause guard, but the restore-SQL would still contain
    ``UPDATE trades SET sector='', industry='' WHERE id=N`` -- applying
    restore later would clobber the concurrent writer's valid data.

    This test asserts the discipline by spying on ``conn.execute``
    calls to verify ``BEGIN IMMEDIATE`` is issued on the apply path.
    """
    from unittest.mock import patch

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = ensure_schema(db_path)
    try:
        with conn:
            run_id = insert_evaluation_run(conn, EvaluationRun(
                id=None, run_ts="2026-05-27T20:00:00",
                data_asof_date="2026-05-26",
                action_session_date="2026-05-27",
                finviz_csv_path=None, tickers_evaluated=1,
                aplus_count=0, watch_count=1, skip_count=0,
                excluded_count=0, error_count=0,
            ))
            insert_candidates(conn, run_id, [
                Candidate(
                    ticker="VSAT",
                    sector="Technology",
                    industry="Communications Equipment",
                    **_build_candidate_fixture("VSAT"),
                ),
            ])
    finally:
        conn.close()
    _insert_trade(db_path, ticker="VSAT", sector="", industry="")

    # Spy on every conn.execute call by patching connect to return a
    # wrapper that records the SQL statement of each invocation.
    executed_statements: list[str] = []
    from swing.diagnostics import backfill_trades_sector_industry as mod
    real_connect = mod.connect

    def _spy_connect(path):
        underlying = real_connect(path)
        return _ExecuteSpyConn(underlying, executed_statements)

    runner = CliRunner()
    with patch.object(mod, "connect", _spy_connect):
        result = runner.invoke(swing_cli, [
            "diagnose", "backfill-trades-sector-industry",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
            "--apply",
        ])
    assert result.exit_code == 0, result.output

    # The apply path MUST issue BEGIN IMMEDIATE before the UPDATE +
    # COMMIT after. The dry-run path would NOT do so.
    begin_immediate_count = sum(
        1 for s in executed_statements if s.upper() == "BEGIN IMMEDIATE"
    )
    commit_count = sum(
        1 for s in executed_statements if s.upper() == "COMMIT"
    )
    assert begin_immediate_count == 1, (
        f"expected exactly 1 BEGIN IMMEDIATE in apply path; got "
        f"{begin_immediate_count} (statements={executed_statements!r})"
    )
    assert commit_count == 1, (
        f"expected exactly 1 COMMIT in apply path; got {commit_count}"
    )


def test_dry_run_does_not_acquire_write_lock(tmp_path):
    """Per Codex round 1 Major #1 (companion): dry-run MUST NOT issue
    BEGIN IMMEDIATE (no writes fire; lock acquisition is unnecessary
    overhead and would serialize against other readers/writers)."""
    from unittest.mock import patch

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    ensure_schema(db_path).close()
    _insert_trade(db_path, ticker="VSAT", sector="", industry="")

    executed_statements: list[str] = []
    from swing.diagnostics import backfill_trades_sector_industry as mod
    real_connect = mod.connect

    def _spy_connect(path):
        underlying = real_connect(path)
        return _ExecuteSpyConn(underlying, executed_statements)

    runner = CliRunner()
    with patch.object(mod, "connect", _spy_connect):
        result = runner.invoke(swing_cli, [
            "diagnose", "backfill-trades-sector-industry",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
        ])
    assert result.exit_code == 0, result.output
    assert not any(
        s.upper() == "BEGIN IMMEDIATE" for s in executed_statements
    ), f"dry-run should NOT issue BEGIN IMMEDIATE; statements={executed_statements!r}"


def test_cli_subcommand_module_ascii_only():
    """CLI emit + helper module are ASCII-only per gotcha #32 + #16.

    Scope per gotcha #16 (ASCII discipline scope clarity): asserts on
    (a) the new helper module in full; (b) the new test module in full;
    (c) only the NEW ``backfill-trades-sector-industry`` subcommand
    region added to swing/cli.py (pre-existing non-ASCII chars elsewhere
    in cli.py are out of scope -- they belong to other features).
    """
    import swing.cli as cli_mod
    import swing.diagnostics.backfill_trades_sector_industry as helper_mod

    # Full ASCII check on the new helper module.
    Path(helper_mod.__file__).read_text(encoding="utf-8").encode("ascii")
    # Full ASCII check on this test module.
    Path(__file__).read_text(encoding="utf-8").encode("ascii")
    # Scoped check on cli.py: extract only the new subcommand region
    # (anchor = the @diagnose_group.command decorator for backfill-trades-
    # sector-industry; end = the ``if __name__ == "__main__":`` tail).
    src = Path(cli_mod.__file__).read_text(encoding="utf-8")
    pre = src.find(
        '@diagnose_group.command("backfill-trades-sector-industry")'
    )
    assert pre != -1, "new subcommand decorator not found in cli.py"
    post = src.find('if __name__ == "__main__":', pre)
    assert post != -1, "tail anchor not found in cli.py"
    new_region = src[pre:post]
    new_region.encode("ascii")
