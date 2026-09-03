"""22-A3 -- the CLI consumes `post_commit_warnings` and contains its own
post-durability close AND its output.

`post_commit_warnings` is a caveat ON a successful entry, so it goes to
stderr with the existing `WARN` prefix convention and **the exit code is not
touched**: the exit status is a statement about the ledger and the ledger has
the row.  A non-zero exit here would be the failure-conversion this arc
closes, reintroduced at the shell.

The CLI is the case where `KeyboardInterrupt` IS fully deliverable -- it is
the main thread -- so its containment is not symmetry with the web route, it
is necessity.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from tests.cli.test_cli_eval import _minimal_config
from tests.conftest import cli_entry_pre_trade_args

# What is INJECTED (an accented char, an em-dash and a LONE SURROGATE -- what
# `record_entry`'s raw `{exc!r}` can actually put in front of `click.echo`).
RAW = "22-A3 PROBE: delta é — \ud800"
# What `ascii_safe` EMITS. CONFIRMED BY RUNNING IT rather than by predicting
# the escape forms: `backslashreplace` renders a BMP char as \xNN or \uNNNN
# depending on width, and a hard-coded guess is exactly the kind of arithmetic
# this project requires to be computed.
EXPECTED = "22-A3 PROBE: delta \\xe9 \\u2014 \\ud800"


def _setup(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert result.exit_code == 0, result.output
    return runner, cfg


def _db_path(cfg_path: Path) -> Path:
    import tomllib
    return Path(tomllib.loads(cfg_path.read_text())["paths"]["db_path"])


def _trade_rows(cfg_path: Path):
    conn = connect(_db_path(cfg_path))
    try:
        return conn.execute("SELECT id, ticker FROM trades ORDER BY id").fetchall()
    finally:
        conn.close()


def _entry_argv(cfg, ticker="AAPL"):
    return [
        "--config", str(cfg), "trade", "entry",
        "--ticker", ticker, "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ]


def _inject_post_commit_warning(monkeypatch, warning: str):
    """Wrap the REAL service and add ONLY the field under test.

    The CLI imports `record_entry` function-locally, so the MODULE attribute
    is the binding one.
    """
    import dataclasses

    import swing.trades.entry as entry_mod
    real = entry_mod.record_entry

    def _wrapped(*a, **kw):
        result = real(*a, **kw)
        return dataclasses.replace(result, post_commit_warnings=(warning,))

    monkeypatch.setattr(entry_mod, "record_entry", _wrapped)


class _CloseRaises:
    """A forwarding proxy whose `close()` performs the real close and THEN
    raises.  The transaction still commits, so the trade is genuinely
    durable -- the whole premise of (c2)."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def __enter__(self):
        object.__getattribute__(self, "_real").__enter__()
        return self

    def __exit__(self, *a):
        return object.__getattribute__(self, "_real").__exit__(*a)

    def close(self):
        object.__getattribute__(self, "_real").close()
        raise sqlite3.OperationalError("22-A3 PROBE: close failed")


def _patch_connect_to_raise_on_close(monkeypatch):
    import swing.data.db as db_mod
    real_connect = db_mod.connect

    def _wrapped(*a, **kw):
        return _CloseRaises(real_connect(*a, **kw))

    monkeypatch.setattr(db_mod, "connect", _wrapped)


def _break_first_echo(monkeypatch):
    """Raise `BrokenPipeError` on the FIRST `click.echo` and delegate after.

    `swing trade entry | head` is the everyday shape of this failure, and an
    uncontained failure there leaves a durable entry exiting NON-ZERO with no
    confirmation -- this arc's own failure mode at the last statement.
    """
    import click

    real_echo = click.echo
    fired: list[bool] = []

    def _wrapped(*a, **kw):
        if not fired:
            fired.append(True)
            raise BrokenPipeError("22-A3 PROBE: output failed")
        return real_echo(*a, **kw)

    monkeypatch.setattr(click, "echo", _wrapped)
    return fired


# ===========================================================================
# (c) -- the warnings are printed, ASCII-coerced, and the exit stays 0.
# ===========================================================================


def test_c_the_cli_prints_post_commit_warnings_and_stays_at_exit_0(
        tmp_path, monkeypatch):
    """PRE-fix nothing is printed and the exit code is ALREADY 0 (the control
    -- and the point of the arc); POST-fix the warning is printed to stderr,
    ASCII-coerced, and the exit code is STILL 0.

    THE ASSERTION IS ON THE ESCAPED FORM, NOT THE RAW SENTINEL: an earlier
    draft asserted the raw non-ASCII sentinel AND `.isascii()`, which cannot
    both hold.
    """
    runner, cfg = _setup(tmp_path)
    _inject_post_commit_warning(monkeypatch, RAW)

    result = runner.invoke(main, _entry_argv(cfg))

    assert result.exit_code == 0, result.output   # CONTROL, both paths
    rows = _trade_rows(cfg)
    assert len(rows) == 1, rows
    trade_id = rows[0][0]

    assert EXPECTED in result.output
    assert EXPECTED in result.stderr, (
        "the warnings are a caveat ON a success, so they go to stderr")
    assert RAW not in result.output
    assert f"Trade id {trade_id}" in result.output, (
        "the success line is not displaced")
    # `.encode("cp1252")` is NOT used: cp1252 accepts a large non-ASCII range
    # and cannot establish the declared constraint.
    assert result.output.isascii()
    assert result.stderr.isascii()


# ===========================================================================
# (c4) -- a NON-ASCII TICKER reaches the success line.
# ===========================================================================


def test_c4_a_non_ascii_ticker_is_coerced_on_the_success_line(
        tmp_path, monkeypatch):
    """`--ticker` is unrestricted text and `.upper()` does not make it ASCII.

    A half-fix that coerces the warning lines and leaves the success and
    watchlist-archive lines raw passes (c), (c2) and (c3). A claim the plan
    makes must be a claim the plan tests.
    """
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.trades.entry import ascii_safe

    runner, cfg = _setup(tmp_path)
    ticker = "CAFÉ"

    conn = connect(_db_path(cfg))
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=ticker, added_date="2026-04-14",
                last_qualified_date="2026-04-14", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-13",
                entry_target=180.0, initial_stop_target=170.0,
                last_close=179.0, last_pivot=None, last_stop=None,
                last_adr_pct=2.0, missing_criteria=None, notes=None))
    finally:
        conn.close()

    result = runner.invoke(main, _entry_argv(cfg, ticker=ticker))

    assert result.exit_code == 0, result.output   # CONTROL, both paths
    assert len(_trade_rows(cfg)) == 1
    assert result.output.isascii(), (
        "the raw non-ASCII ticker reached stdout; Windows cp1252 raises on "
        "it and pytest's capsys hides that")
    assert ascii_safe(ticker) in result.output
    assert "archived" in result.output, (
        "the watchlist-archive line must fire too -- it is one of the lines "
        "a half-fix would leave uncoerced")


# ===========================================================================
# (c2) -- a `conn.close()` failure AFTER a durable entry.
# ===========================================================================


def test_c2_a_close_failure_after_a_durable_entry_keeps_exit_0(
        tmp_path, monkeypatch):
    """PRE-fix the `OperationalError` escapes `trade entry`: non-zero exit
    with the success line never printed, over one durable row.  POST-fix exit
    0, the success line printed, and the contained close REPORTED."""
    runner, cfg = _setup(tmp_path)
    _patch_connect_to_raise_on_close(monkeypatch)

    result = runner.invoke(main, _entry_argv(cfg))

    rows = _trade_rows(cfg)
    assert len(rows) == 1, rows          # under BOTH paths
    trade_id = rows[0][0]
    assert result.exit_code == 0, result.output
    assert f"Trade id {trade_id}" in result.output
    assert "close failed" in result.stderr


def test_c2_control_a_REFUSAL_propagates_the_EXACT_close_exception(
        tmp_path, monkeypatch):
    """THE CONTROL MUST ASSERT THE IDENTITY OF WHAT ESCAPES -- "still fails"
    does NOT discriminate on this surface.

    A duplicate-ticker invocation through the same proxy exits non-zero under
    BOTH a correct conditional containment (the close error replaces the
    duplicate error) AND an incorrect unconditional one (the duplicate
    `ClickException` reaches Click's own top-level handling and `CliRunner`
    surfaces a `SystemExit(1)`).  `SystemExit` is not
    `sqlite3.OperationalError`, so the exact-class assertion is what makes
    this control work.
    """
    runner, cfg = _setup(tmp_path)

    first = runner.invoke(main, _entry_argv(cfg))
    assert first.exit_code == 0, first.output

    _patch_connect_to_raise_on_close(monkeypatch)
    second = runner.invoke(main, _entry_argv(cfg))

    assert second.exit_code != 0
    assert type(second.exception) is sqlite3.OperationalError, (
        f"a refusal has no durable result to protect, so the close failure "
        f"must propagate UNCHANGED; got {second.exception!r}")
    assert "close failed" in str(second.exception)
    assert len(_trade_rows(cfg)) == 1


# ===========================================================================
# (c3) -- a failing `click.echo` after a durable entry.
# ===========================================================================


def test_c3_a_failing_echo_after_a_durable_entry_keeps_exit_0(
        tmp_path, monkeypatch):
    """An implementation that reads the warnings and contains the close but
    leaves the OUTPUT BLOCK unguarded passes (c) and (c2).

    PRE-fix the `BrokenPipeError` escapes and the exit code is non-zero over
    one durable row; POST-fix the exit code is 0 -- because there is nowhere
    left to write, so the exit code becomes the ONLY remaining signal, which
    is exactly why it must be the TRUE one.
    """
    runner, cfg = _setup(tmp_path)
    fired = _break_first_echo(monkeypatch)

    result = runner.invoke(main, _entry_argv(cfg))

    assert len(_trade_rows(cfg)) == 1     # under BOTH paths; the premise
    assert fired, "the echo probe never fired, so this row measures nothing"
    assert result.exit_code == 0, result.output


def test_c3_control_a_REFUSAL_with_a_failing_echo_still_exits_non_zero(
        tmp_path, monkeypatch):
    """`result is None` on a refusal, so nothing is contained there."""
    runner, cfg = _setup(tmp_path)

    first = runner.invoke(main, _entry_argv(cfg))
    assert first.exit_code == 0, first.output

    _break_first_echo(monkeypatch)
    second = runner.invoke(main, _entry_argv(cfg))

    assert second.exit_code != 0
    assert len(_trade_rows(cfg)) == 1
