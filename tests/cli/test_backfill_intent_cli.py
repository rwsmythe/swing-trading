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
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

import swing.cli as cli_mod
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


# D69 -- the per-row header echo (~cli.py:2103) printed the RAW ticker
# without `ascii_safe`. A CliRunner captures stdout through an internal
# UTF-8-charset buffer (never the real console encoder), so an
# UnicodeEncodeError at the header's own `click.echo` is INVISIBLE to a bare
# CliRunner invocation -- the same "capsys hides this failure" shape CLAUDE.md
# names for pytest capsys (gotcha, Windows/tooling section). The discriminator
# is therefore a POST-HOC strict `.encode("cp1252")` on the CAPTURED text
# (the established pattern in this suite: test_correct_entry_date_command.py,
# test_diagnose_subcommands.py) -- it simulates what the REAL cp1252 console
# would have done with that exact text, without needing a subprocess. U+2713
# (a checkmark) is chosen because it is OUTSIDE cp1252's 256-slot repertoire
# (unlike an em-dash or an accented letter, which cp1252 DOES encode) -- see
# ascii_safe's own docstring in swing/trades/entry.py.
_NON_CP1252_TICKER = "T✓K"  # "T[checkmark]K"


def test_backfill_header_ascii_coerced_for_non_ascii_ticker(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    _seed_trade(db_path, ticker=_NON_CP1252_TICKER)
    res = runner.invoke(
        main, ["--config", str(cfg), "trade", "backfill-intent"], input="skip\n"
    )
    assert res.exit_code == 0, res.output
    # Post-fix: ascii_safe's backslashreplace escape is pure ASCII (hence
    # pure cp1252-safe); pre-fix, the raw checkmark glyph in res.output
    # raises UnicodeEncodeError here -- the discriminator.
    res.output.encode("cp1252")
    assert _NON_CP1252_TICKER not in res.output
    assert "\\u2713" in res.output


class _CloseRaises:
    """Forwarding proxy whose `close()` performs the real close and THEN
    raises -- the transaction still commits, so a durable row stays durable.
    Mirrors tests/cli/test_cli_trade_entry_post_commit_warnings.py."""

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
        raise sqlite3.OperationalError("D69 PROBE: close failed")


def _patch_backfill_connect_to_raise_on_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch `swing.cli`'s OWN `connect` name.

    `trade_backfill_intent_cmd` resolves the bare name `connect` from
    `swing.cli`'s MODULE-LEVEL import (`cli.py:36`), unlike most other
    handlers in this file which locally re-import `connect` inside the
    function body for exactly this kind of test-patchability. Patching
    `swing.data.db.connect` (the target every other command's LOCAL import
    re-resolves at call time) would silently no-op here -- `swing.cli`'s own
    module-level binding was captured once, at `swing.cli`'s first import,
    and is untouched by a patch to a DIFFERENT module's attribute (the same
    "by-name import defeats a same-module-only patch" shape as D67, one
    level removed). Patching `swing.cli.connect` directly is correct
    regardless of import timing, because the bare `connect(...)` call inside
    `trade_backfill_intent_cmd` is a normal global-name lookup against
    `swing.cli`'s OWN `__dict__` at CALL time.
    """
    real_connect = cli_mod.connect

    def _wrapped(*a, **kw):
        return _CloseRaises(real_connect(*a, **kw))

    monkeypatch.setattr(cli_mod, "connect", _wrapped)


def test_backfill_close_raise_after_commit_warns_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """D69 (b)/(d): the durability boundary crossed (n_set=1) -- a close()
    failure is contained: WARN naming the count, logged, exit 0, row durable
    on a FRESH connection (not the writer's own, per the CLAUDE.md gotcha on
    reading a writer's own uncommitted-vs-committed connection)."""
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA")
    _patch_backfill_connect_to_raise_on_close(monkeypatch)
    with caplog.at_level("ERROR"):
        res = runner.invoke(
            main, ["--config", str(cfg), "trade", "backfill-intent"],
            input="standard\n",
        )
    assert res.exit_code == 0, res.output
    assert "WARN (post-commit):" in res.output
    assert "1 row(s)" in res.output
    assert "close failed" in res.output
    # Durable on a FRESH connection, not the (raised-on-close) writer's own.
    assert _read_intent(db_path, t1) == "standard"
    assert any("D69" in r.message for r in caplog.records)


def test_backfill_close_raise_zero_committed_raises_as_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D69 (c): before the boundary (n_set=0, every row skipped) every path
    is byte-unchanged -- a close() failure propagates exactly as a bare
    `conn.close()` always has, non-zero exit, no WARN line."""
    runner, cfg, db_path = _setup(tmp_path)
    _seed_trade(db_path, ticker="AAA")
    _patch_backfill_connect_to_raise_on_close(monkeypatch)
    res = runner.invoke(
        main, ["--config", str(cfg), "trade", "backfill-intent"], input="skip\n",
    )
    assert res.exit_code != 0
    assert isinstance(res.exception, sqlite3.OperationalError)
    assert "WARN (post-commit):" not in res.output


def test_backfill_close_raise_with_abort_in_flight_names_not_substitutes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """D69 (e), D39's template: an exception ALREADY in flight (here,
    click.Abort from a prompt hitting EOF after one row committed) MUST
    keep propagating UNCHANGED when close() ALSO raises -- the close
    failure is named (a durable log record), never substituted for the
    original.

    Click's OWN top-level handler converts an in-flight `Abort` to
    `SystemExit(1)` with "Aborted!" printed (unrelated to this fix -- that
    conversion happens in `click.BaseCommand.main`, one frame above
    `trade_backfill_intent_cmd`). What this test pins is that OUR close-
    failure containment does not touch that outcome at all: same exit code,
    same "Aborted!" text, no WARN line, and the close failure is recorded
    only via the durable log, never printed over the abort."""
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA", entry_date="2026-04-01")
    t2 = _seed_trade(db_path, ticker="BBB", entry_date="2026-04-02")
    _patch_backfill_connect_to_raise_on_close(monkeypatch)
    with caplog.at_level("ERROR"):
        res = runner.invoke(
            main, ["--config", str(cfg), "trade", "backfill-intent"],
            # Only ONE answer for TWO NULL rows: the second row's prompt
            # hits EOF and click.prompt raises click.Abort -- unforced,
            # not a monkeypatch of click.prompt itself.
            input="standard\n",
        )
    assert res.exit_code != 0
    assert isinstance(res.exception, SystemExit)
    assert "Aborted!" in res.output
    # The abort's own text, never overwritten by the close failure.
    assert "WARN (post-commit):" not in res.output
    # The first row's commit is durable regardless of the later abort.
    assert _read_intent(db_path, t1) == "standard"
    assert _read_intent(db_path, t2) is None
    assert any("D69" in r.message and "ALSO RAISED" in r.message
               for r in caplog.records)


# Codex R1 (round 1 of the D67+D69 review): two findings against the FIRST
# cut of the D69 fix, both IN ENVELOPE, adjudicated and fixed rather than
# banked. Each test below is a discriminator computed under both the
# pre-R1-fix and post-R1-fix code (see the return report for the recorded
# results); the fix commit references R1 Major 1 / R1 Major 2 by number.


def test_backfill_force_same_value_reanswer_does_not_cross_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R1 Major 2: `n_set` alone is NOT a durability boundary.
    `update_entry_intent` (swing/data/repos/trades.py) returns WITHOUT
    writing when the operator's --force re-answer EQUALS the row's current
    value -- no transaction opens, nothing commits. `n_set` still
    increments (the pre-existing, byte-unchanged summary count), but the
    NEW durability boundary (n_written) must NOT cross on this path: a
    subsequent close() failure with nothing else written must stay on the
    byte-unchanged raise-as-today path, not the WARN-and-swallow one."""
    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA", entry_intent="standard")
    _patch_backfill_connect_to_raise_on_close(monkeypatch)
    res = runner.invoke(
        main,
        ["--config", str(cfg), "trade", "backfill-intent", "--force"],
        # Re-answer with the SAME value already on the row -- a genuine
        # no-op at the DB layer even though the summary counts it "set".
        input="standard\n",
    )
    assert res.exit_code != 0
    assert isinstance(res.exception, sqlite3.OperationalError)
    assert "WARN (post-commit):" not in res.output
    assert _read_intent(db_path, t1) == "standard"  # unaffected either way


def test_backfill_post_boundary_output_failure_is_contained(
    tmp_path: Path,
) -> None:
    """Codex R1 Major 1: after the durability boundary is crossed, EVERY
    remaining output line (not just the close()-failure WARN lines) must go
    through the contained sink. A single seeded trade: the pre-write header
    prints via the byte-unchanged path (n_written == 0, real click.echo);
    the post-commit summary must survive BOTH stdout and stderr failing."""
    import click

    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA")
    real_echo = click.echo
    calls: list[int] = []

    def _hostile_echo(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            # The row's own header: BEFORE any write this invocation
            # (byte-unchanged path) -- let it through normally.
            return real_echo(*a, **kw)
        # Every later echo (chosen to land on/after the commit): both
        # stdout and stderr attempts must fail here to prove containment
        # (click.echo is the shared primitive for both).
        raise BrokenPipeError("R1 PROBE: sink gone")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(click, "echo", _hostile_echo)
        res = runner.invoke(
            main, ["--config", str(cfg), "trade", "backfill-intent"],
            input="standard\n",
        )
    assert res.exit_code == 0, res.output
    assert _read_intent(db_path, t1) == "standard"


def test_backfill_prompt_render_failure_after_commit_stops_gracefully(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """Codex R2 Major: click.prompt renders its own question text through
    click.termui's internal (same-module) echo, which this command's
    _emit/_echo_either_sink machinery cannot reach -- a broken sink there
    raises OSError, not click.exceptions.Abort. With TWO NULL rows and only
    the FIRST prompt answered before the sink breaks: the first row commits
    (n_written=1, crossing the boundary), the second row's prompt raises
    OSError, and the command must stop gracefully (not crash) -- the
    unanswered row is left for a future run, never silently skipped."""
    import click

    runner, cfg, db_path = _setup(tmp_path)
    t1 = _seed_trade(db_path, ticker="AAA", entry_date="2026-04-01")
    t2 = _seed_trade(db_path, ticker="BBB", entry_date="2026-04-02")
    real_prompt = click.prompt
    calls: list[int] = []

    def _hostile_prompt(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            return real_prompt(*a, **kw)
        raise OSError("R2 PROBE: prompt sink gone")

    with pytest.MonkeyPatch.context() as mp, caplog.at_level("ERROR"):
        mp.setattr(click, "prompt", _hostile_prompt)
        res = runner.invoke(
            main, ["--config", str(cfg), "trade", "backfill-intent"],
            input="standard\n",
        )
    assert res.exit_code == 0, res.output
    assert _read_intent(db_path, t1) == "standard"
    assert _read_intent(db_path, t2) is None  # never silently skipped/set
    assert any("D69" in r.message and "prompting for trade" in r.message
               for r in caplog.records)


def test_backfill_prompt_render_failure_zero_written_raises_as_today(
    tmp_path: Path,
) -> None:
    """Codex R2 Major, the byte-unchanged control: a prompt-render OSError
    with NOTHING written yet (n_written == 0) must still propagate exactly
    as it always has -- no swallow, no graceful stop."""
    import click

    runner, cfg, db_path = _setup(tmp_path)
    _seed_trade(db_path, ticker="AAA")

    def _hostile_prompt(*a, **kw):
        raise OSError("R2 PROBE: prompt sink gone before any write")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(click, "prompt", _hostile_prompt)
        res = runner.invoke(
            main, ["--config", str(cfg), "trade", "backfill-intent"],
            input="standard\n",
        )
    assert res.exit_code != 0
    assert isinstance(res.exception, OSError)
