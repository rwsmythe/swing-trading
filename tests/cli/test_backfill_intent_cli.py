"""Task 5 (tuition-vs-error): `swing trade backfill-intent` walk.

Walks trades with ``entry_intent IS NULL`` (every state, incl. closed-not-
reviewed); idempotent; ``--trade-id``/``--force`` re-target; per-trade prompt
seeds the suggestion as the default; ``skip`` leaves the row NULL (re-runnable);
writes via the dedicated ``update_entry_intent`` writer; the re-runnable command
plus its summary ARE the audit (spec §6, D3).

The subprocess-through-PowerShell test exercises the REAL OS encoder (capsys
bypasses it): gotcha #16 cp1252 stdout footgun. Mirrors
tests/cli/test_logs_cleanup_cmd.py::test_cleanup_stdout_is_ascii_through_powershell.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect, ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    # db-migrate migrates to EXPECTED_SCHEMA_VERSION (v27 -> trades.entry_intent).
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    return runner, cfg, db_path


def _seed_trade(
    db_path: Path,
    *,
    ticker: str,
    entry_date: str = "2026-04-20",
    hypothesis_label: str | None = None,
    entry_intent: str | None = None,
) -> int:
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None,
                    ticker=ticker,
                    entry_date=entry_date,
                    entry_price=10.0,
                    initial_shares=10,
                    initial_stop=9.0,
                    current_stop=9.0,
                    state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                    trade_origin="manual_off_pipeline",
                    pre_trade_locked_at=f"{entry_date}T09:30:00",
                    hypothesis_label=hypothesis_label,
                    entry_intent=entry_intent,
                ),
                event_ts=f"{entry_date}T09:30:00",
            )
    finally:
        conn.close()
    return trade_id


def _read_intent(db_path: Path, trade_id: int) -> str | None:
    conn = connect(db_path)
    try:
        return conn.execute(
            "SELECT entry_intent FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_backfill_sets_null_rows_idempotently(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA")
    t2 = _seed_trade(db_path, ticker="BBB")
    # First run: two NULL rows -> operator types a choice for each.
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent"],
        input="standard\nhypothesis_test_by_design\n",
    )
    assert res.exit_code == 0, res.output
    assert _read_intent(db_path, t1) == "standard"
    assert _read_intent(db_path, t2) == "hypothesis_test_by_design"
    assert "2 set, 0 skipped-already-set, 0 skipped-by-operator" in res.output
    # Second run: no NULL rows remain -> "0 set" (idempotent).
    res2 = runner.invoke(
        main, ["--config", str(cfg), "trade", "backfill-intent"], input=""
    )
    assert res2.exit_code == 0, res2.output
    assert "0 set, 2 skipped-already-set, 0 skipped-by-operator" in res2.output


def test_backfill_skip_leaves_null(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA")
    # Answer 'skip' -> entry_intent stays NULL.
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent"],
        input="skip\n",
    )
    assert res.exit_code == 0, res.output
    assert _read_intent(db_path, t1) is None
    assert "0 set, 0 skipped-already-set, 1 skipped-by-operator" in res.output
    # Re-runnable: the still-NULL row re-appears on a later run.
    res2 = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent"],
        input="standard\n",
    )
    assert res2.exit_code == 0, res2.output
    assert _read_intent(db_path, t1) == "standard"


def test_backfill_trade_id_retargets_single(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA", entry_intent="standard")
    t2 = _seed_trade(db_path, ticker="BBB", entry_intent="standard")
    # --trade-id re-prompts ONLY trade t1 even though it is already set.
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent", "--trade-id", str(t1)],
        input="hypothesis_test_by_design\n",
    )
    assert res.exit_code == 0, res.output
    assert _read_intent(db_path, t1) == "hypothesis_test_by_design"
    assert _read_intent(db_path, t2) == "standard"  # untouched
    assert f"#{t2} BBB" not in res.output


def test_backfill_force_reprompts_set_rows(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA", entry_intent="standard")
    # --force re-prompts the already-set row (the correction path).
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent", "--force"],
        input="hypothesis_test_by_design\n",
    )
    assert res.exit_code == 0, res.output
    assert _read_intent(db_path, t1) == "hypothesis_test_by_design"
    assert "1 set, 0 skipped-already-set, 0 skipped-by-operator" in res.output


def test_backfill_summary_counts(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    # One NULL row (set), one already-set row (skipped-already-set), one NULL
    # row the operator skips (skipped-by-operator).
    _seed_trade(db_path, ticker="AAA", entry_date="2026-04-01")  # set
    _seed_trade(
        db_path, ticker="BBB", entry_date="2026-04-02", entry_intent="standard"
    )  # skipped-already-set
    _seed_trade(db_path, ticker="CCC", entry_date="2026-04-03")  # skipped-by-op
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent"],
        # Rows are ordered by entry_date: AAA (set), CCC (skip). BBB never prompts.
        input="standard\nskip\n",
    )
    assert res.exit_code == 0, res.output
    assert "1 set, 1 skipped-already-set, 1 skipped-by-operator" in res.output


def test_backfill_bad_input_raises_clickexception(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA")
    # A free-typed choice not in ENTRY_INTENTS -> update_entry_intent raises
    # ValueError -> wrapped as ClickException (non-zero exit), never a traceback.
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent"],
        input="not_a_real_intent\n",
    )
    assert res.exit_code != 0
    # A ClickException renders "Error: ..."; a leaked traceback would not.
    assert "Error" in res.output
    assert res.exc_info is None or not isinstance(res.exception, ValueError)
    assert _read_intent(db_path, t1) is None  # nothing persisted


@pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="cp1252 stdout footgun is Windows/PowerShell-specific",
)
def test_backfill_subprocess_ascii_stdout(tmp_path: Path) -> None:
    # cp1252 footgun (gotcha #16): the command's stdout must be ASCII so
    # PowerShell's default cp1252 encoder never raises UnicodeEncodeError in
    # production. capsys bypasses the OS encoder, so drive the REAL one via a
    # subprocess. Mirrors test_logs_cleanup_cmd.py's PowerShell encoding test.
    runner, cfg, db_path = _setup(tmp_path)
    _seed_trade(db_path, ticker="AAA")
    completed = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f'& "{sys.executable}" -m swing.cli --config "{cfg}" '
            f'trade backfill-intent',
        ],
        input="skip\n",
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    completed.stdout.encode("ascii")  # raises if any non-ASCII glyph slipped in
