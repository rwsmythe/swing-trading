"""D79 T8 -- ``swing trade exit``: ``--confirm-duplicate`` and the pinned
typed-refusal wrap.

RD K5c (the CLI is operator-typed only, so only the anonymous (c) value-tuple
match applies there); orchestrator K5 (the confirm binds to the printed fill
IDS); CHARC K1 (v). Plan T8; AL-8 says why (v) is planted at the service
seam: the CLI carries no Schwab envelope, so it cannot submit an id at all.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from swing.cli import main
from swing.trades import exit as exit_mod
from tests.cli.test_22f_cli_typed_refusals import _db
from tests.cli.test_cli_trade import _PRE_TRADE_OK_FLAGS, _setup

_REPO = Path(__file__).resolve().parents[2]


def _entry(runner, cfg) -> None:
    """A 10-share entry on trade 1. (Cell 1's draft reused the 22-F 5-share
    helper; after the planted 3-share fill only 2 remained, so the 3-share
    exit under test was refused as "exceeds" before any question.)"""
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "10",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert r.exit_code == 0, r.output


def _plant_anonymous_exit(db: Path, trade_id: int = 1) -> int:
    """RAW insert of an operator-typed exit (no envelope) at 2026-05-21 /
    131.00 x 3 -- the anonymous row a hand-typed duplicate would match."""
    from swing.data.repos.fills import _recompute_aggregates
    c = sqlite3.connect(str(db))
    try:
        with c:
            cur = c.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, fill_origin) VALUES (?, ?, 'trim', 3, 131.0, "
                "'operator_typed')", (trade_id, "2026-05-21T16:00:00"))
            _recompute_aggregates(c, trade_id)
        return int(cur.lastrowid)
    finally:
        c.close()


def _exit_fill_count(db: Path) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(
            "SELECT COUNT(*) FROM fills WHERE action != 'entry'").fetchone()[0]
    finally:
        c.close()


def _args(cfg, *extra: str) -> list[str]:
    return ["--config", str(cfg), "trade", "exit", "--trade-id", "1",
            "--exit-date", "2026-05-21", "--exit-price", "131",
            "--shares", "3", "--reason", "target", *extra]


def test_t8a_cli_value_tuple_match_asks_and_records_nothing(tmp_path):
    """Cell list 13. PRE-FIX: exit 0 and a duplicate is recorded."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    fid = _plant_anonymous_exit(_db(tmp_path))
    result = runner.invoke(main, _args(cfg))
    assert result.exit_code == 1, result.output
    assert f"#{fid}" in result.output
    assert "--confirm-duplicate" in result.output
    assert "Traceback" not in result.output
    assert _exit_fill_count(_db(tmp_path)) == 1


def test_t8b_cli_confirm_is_bound_to_the_printed_fill_ids(tmp_path):
    """Orchestrator K5 (CLI form). NULL killed: a boolean flag."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    fid = _plant_anonymous_exit(_db(tmp_path))
    wrong = runner.invoke(main, _args(cfg, "--confirm-duplicate", str(fid + 99)))
    assert wrong.exit_code == 1, wrong.output
    assert _exit_fill_count(_db(tmp_path)) == 1
    ok = runner.invoke(main, _args(cfg, "--confirm-duplicate", str(fid)))
    assert ok.exit_code == 0, ok.output
    assert _exit_fill_count(_db(tmp_path)) == 2


def test_t8_control_no_match_records_without_a_flag(tmp_path):
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    result = runner.invoke(main, _args(cfg))
    assert result.exit_code == 0, result.output
    assert _exit_fill_count(_db(tmp_path)) == 1


def test_t8c_cli_typed_refusal_is_a_click_exception_not_a_traceback(
        tmp_path, monkeypatch):
    """CHARC K1 (v) -- a PIN: the ``ValueError -> ClickException`` wrap exists
    at ``cli.py``'s ``trade exit``; green once T2 defines the class."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)

    def refuse(conn, req):
        raise exit_mod.ExitOrderAlreadyRecordedError(
            "Order o2 is already recorded as fill(s) #7 on trade #1; it "
            "cannot be recorded again.")

    monkeypatch.setattr(exit_mod, "record_exit", refuse)
    result = runner.invoke(main, _args(cfg))
    assert result.exit_code == 1, result.output
    assert "already recorded as fill(s) #7" in result.output
    assert "Traceback" not in result.output


def test_t8d_cli_flag_output_survives_the_real_cp1252_encoder(tmp_path):
    """The CLAUDE.md cp1252 encode gotcha: ``capsys``/``CliRunner`` bypass the
    OS encoder, so the flagged case is run as a REAL subprocess under
    ``PYTHONIOENCODING=cp1252``."""
    runner, cfg = _setup(tmp_path)
    _entry(runner, cfg)
    fid = _plant_anonymous_exit(_db(tmp_path))
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=str(_REPO))
    proc = subprocess.run(
        [sys.executable, "-m", "swing.cli", *_args(cfg)],
        capture_output=True, cwd=str(_REPO), env=env, timeout=120)
    out = proc.stdout.decode("cp1252", "replace")
    err = proc.stderr.decode("cp1252", "replace")
    assert "UnicodeEncodeError" not in err, err
    assert proc.returncode == 1, (out, err)
    assert f"#{fid}" in out + err
