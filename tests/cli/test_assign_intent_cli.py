"""Arc 22-B Task 6 -- `swing trade assign-intent` (the ONE writer of the value).

The CLI opens the DB exactly as `trade review` does (the group's config +
`swing.data.db.connect`), prints the three predicates WITH their values, and
turns a typed refusal into a ClickException (exit 1). The service never
prints; stdout is this command's. The subprocess test drives the REAL cp1252
encoder (capsys bypasses it; gotcha #16).
"""
from __future__ import annotations

import ast
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests._22b_fixtures import seed_amn_row5, seed_trade20
from tests.cli.test_cli_eval import _minimal_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def _setup(tmp_path: Path, **trade):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    res = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert res.exit_code == 0, res.output
    db_path = Path(tomllib.loads(cfg.read_text())["paths"]["db_path"])
    c = sqlite3.connect(db_path)
    try:
        seed_amn_row5(c)
        seed_trade20(c, **trade)
        c.commit()
    finally:
        c.close()
    return runner, cfg, db_path


def _args(cfg: Path, *extra: str) -> list[str]:
    return ["--config", str(cfg), "trade", "assign-intent", "20",
            "--value", "unintended_execution", "--cite", "why_now,notes",
            "--reason", "Stale A+ latch order fired after the mandate died", *extra]


def _state(db_path: Path) -> tuple:
    c = sqlite3.connect(db_path)
    try:
        return (c.execute("SELECT COUNT(*) FROM entry_intent_attestations").fetchone()[0],
                c.execute("SELECT entry_intent FROM trades WHERE id = 20").fetchone()[0])
    finally:
        c.close()


def test_dry_run_prints_predicates_and_writes_nothing_b22_110(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    res = runner.invoke(main, _args(cfg, "--dry-run"))
    assert res.exit_code == 0, res.output
    out = res.output
    assert "ADMIT" in out and "dry run" in out and "nothing written" in out
    assert "tier: contemporaneous_record" in out
    assert "P1" in out and "leg deployment" in out
    assert '"deployment_session": "2026-08-03"' in out
    assert '"placement_session": "2026-08-01"' in out
    assert ("P2" in out and "corrections 0/0 over reconciliation_corrections, "
            "provenance_corrections" in out)
    assert "P3" in out and "outcome 2026-08-11T16:00:00" in out
    assert "attestation" not in out.split("P3", 1)[1]  # no id on a dry run
    assert _state(db_path) == (0, None)


def test_open_trade_prints_outcome_open_b22_110(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path, with_outcome=False)
    res = runner.invoke(main, _args(cfg, "--dry-run"))
    assert res.exit_code == 0, res.output
    assert "outcome open" in res.output


def test_write_prints_attestation_id_b22_111(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    res = runner.invoke(main, _args(cfg))
    assert res.exit_code == 0, res.output
    c = sqlite3.connect(db_path)
    try:
        att_id = c.execute("SELECT attestation_id FROM entry_intent_attestations "
                           "WHERE trade_id = 20").fetchone()[0]
    finally:
        c.close()
    assert f"attestation_id: {att_id}" in res.output
    assert "dry run" not in res.output
    assert _state(db_path) == (1, "unintended_execution")


def test_refusal_exits_nonzero_with_the_typed_message_b22_112(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path, entry_intent="standard")
    res = runner.invoke(main, _args(cfg))
    assert res.exit_code == 1, res.output
    assert "Error:" in res.output and "already_set" in res.output
    assert "no relabel path" in res.output
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert _state(db_path) == (0, "standard")


def test_value_choice_names_only_the_evidence_bearing_value_b22_112(
        tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    args = _args(cfg)
    args[args.index("unintended_execution")] = "standard"
    res = runner.invoke(main, args)
    assert res.exit_code == 2  # click usage error: not a choice
    assert _state(db_path) == (0, None)


@pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="cp1252 stdout footgun is Windows/PowerShell-specific",
)
def test_stdout_is_ascii_b22_113(tmp_path: Path) -> None:
    """Trade 20's shape through the REAL console encoder, run from THIS
    checkout (cwd = the worktree root, so `-m swing.cli` resolves here)."""
    _, cfg, _ = _setup(tmp_path)
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f'& "{sys.executable}" -m swing.cli --config "{cfg}" trade assign-intent 20 '
         f'--value unintended_execution --cite why_now,notes '
         f'--reason "stale order fired" --dry-run'],
        capture_output=True, cwd=REPO_ROOT)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert b"ADMIT" in completed.stdout
    completed.stdout.decode("ascii")  # raises on any non-ASCII byte


# ---------------------------------------------------------------------------
# F4: the callers of `assign` are pinned (the AST walk over swing/)
# ---------------------------------------------------------------------------
_SERVICE = "swing.trades.entry_intent_assignment"


def _assign_call_sites(source: str) -> set[str]:
    """Names of the functions containing a call to the service's `assign`,
    by every import spelling (`from ... import assign [as x]`, the module
    imported under any alias)."""
    tree = ast.parse(source)
    fn_names: set[str] = set()
    mod_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == _SERVICE:
            fn_names |= {a.asname or a.name for a in node.names if a.name == "assign"}
        elif isinstance(node, ast.ImportFrom) and node.module == "swing.trades":
            mod_names |= {a.asname or a.name for a in node.names
                          if a.name == "entry_intent_assignment"}
        elif isinstance(node, ast.Import):
            mod_names |= {a.asname for a in node.names
                          if a.name == _SERVICE and a.asname}
    sites: set[str] = set()

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call):
                f = child.func
                if ((isinstance(f, ast.Name) and f.id in fn_names)
                        or (isinstance(f, ast.Attribute) and f.attr == "assign"
                            and isinstance(f.value, ast.Name)
                            and f.value.id in mod_names)
                        or (isinstance(f, ast.Attribute) and f.attr == "assign"
                            and ast.unparse(f.value) == _SERVICE)):
                    sites.add(owner)
            visit(child, owner)

    visit(tree, "<module>")
    return sites


def test_the_walker_finds_every_spelling() -> None:
    for src in (
        "from swing.trades.entry_intent_assignment import assign\ndef f():\n    assign(1)",
        "from swing.trades.entry_intent_assignment import assign as a\ndef f():\n    a(1)",
        "from swing.trades import entry_intent_assignment as m\ndef f():\n    m.assign(1)",
        "import swing.trades.entry_intent_assignment as m\ndef f():\n    m.assign(1)",
        "import swing.trades.entry_intent_assignment\n"
        "def f():\n    swing.trades.entry_intent_assignment.assign(1)",
    ):
        assert _assign_call_sites(src) == {"f"}, src
    assert _assign_call_sites("def f():\n    x.assign(1)") == set()


def test_assign_intent_is_the_only_caller_of_assign_b22_114() -> None:
    found: set[tuple[str, str]] = set()
    for path in sorted((REPO_ROOT / "swing").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for owner in _assign_call_sites(path.read_text(encoding="utf-8")):
            found.add((rel, owner))
    assert found == {("swing/cli.py", "trade_assign_intent")}, found


# ---------------------------------------------------------------------------
# Codex R7-1: once `assign` has COMMITTED, an output failure must not turn the
# durable assignment into a nonzero exit (a retry would then read
# `already_set` for an assignment the operator was told failed). Every
# admission line goes through the 22-A3 per-line, per-sink containment
# (`_echo_either_sink(ascii_safe(...))`), the idiom RULING R4-1-TEXT names.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sink", ["stdout_broken", "stderr_broken",
                                  "every_sink_broken"])
def test_an_output_failure_after_the_commit_keeps_the_success_exit_b22_249(
        tmp_path: Path, monkeypatch, sink: str) -> None:
    """``stdout_broken`` and ``every_sink_broken`` are the discriminators
    (pre-fix: the first echo raised and Click exited 1 over a durable row);
    ``stderr_broken`` is the control (the lines prefer stdout)."""
    import click as click_mod

    runner, cfg, db_path = _setup(tmp_path)
    real_echo = click_mod.echo

    def _sink(message=None, file=None, nl=True, err=False, color=None):
        broken = (sink == "every_sink_broken"
                  or (sink == "stdout_broken" and not err)
                  or (sink == "stderr_broken" and err))
        if broken:
            raise OSError(32, "Broken pipe")
        return real_echo(message, file=file, nl=nl, err=err, color=color)

    monkeypatch.setattr(click_mod, "echo", _sink)
    res = runner.invoke(main, _args(cfg))
    assert res.exit_code == 0, (res.output, res.exception)
    assert _state(db_path) == (1, "unintended_execution")
    if sink != "every_sink_broken":
        # the confirmation still reached the operator on the other sink
        assert "ADMIT unintended_execution" in res.output, res.output
        assert "attestation_id: 1" in res.output, res.output
