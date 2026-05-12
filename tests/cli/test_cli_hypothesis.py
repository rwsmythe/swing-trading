"""CLI: swing hypothesis list / status / update.

Per backend brief §4.6 + §5 watch items.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_hypothesis_list_shows_all_seeded(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    assert r.exit_code == 0, r.output
    out = r.output
    for name in [
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
    ]:
        assert name in out
    # Each row shows the n/N progress against the seeded targets.
    assert "0/20" in out or "0 / 20" in out
    assert "0/5" in out or "0 / 5" in out


def test_hypothesis_list_shows_status(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    assert r.exit_code == 0, r.output
    # All 4 are seeded as active — output mentions `active` for each.
    assert r.output.lower().count("active") >= 4


def test_hypothesis_status_command_dumps_one_hypothesis_detail(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    # First, get a valid id from the list output.
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    assert list_r.exit_code == 0
    # Find the id of "Sub-A+ VCP-not-formed" by scanning lines.
    line = next(
        ln for ln in list_r.output.splitlines() if "Sub-A+ VCP-not-formed" in ln
    )
    hid = next(tok for tok in line.split() if tok.isdigit())

    r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "status", hid])
    assert r.exit_code == 0, r.output
    out = r.output
    assert "Sub-A+ VCP-not-formed" in out
    # Detail dump includes statement, decision criteria, tripwire thresholds.
    assert "Watch-bucket candidates" in out
    assert "Confirm negative mean R-multiple" in out
    assert "5" in out  # consecutive_loss_tripwire = 3 OR target = 5; both match


def test_hypothesis_status_command_unknown_id_errors(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "status", "999"])
    assert r.exit_code != 0
    assert "999" in r.output


def test_hypothesis_update_status_records_reason(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    line = next(
        ln for ln in list_r.output.splitlines() if "Sub-A+ VCP-not-formed" in ln
    )
    hid = next(tok for tok in line.split() if tok.isdigit())

    r = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "paused", "--reason", "Operator review pending",
    ])
    assert r.exit_code == 0, r.output

    # status command now shows paused + reason.
    s = runner.invoke(main, ["--config", str(cfg), "hypothesis", "status", hid])
    assert s.exit_code == 0, s.output
    assert "paused" in s.output
    assert "Operator review pending" in s.output


def test_hypothesis_update_requires_reason(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    line = next(ln for ln in list_r.output.splitlines() if "A+ baseline" in ln)
    hid = next(tok for tok in line.split() if tok.isdigit())

    # No --reason
    r = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid, "--status", "paused",
    ])
    assert r.exit_code != 0


def test_hypothesis_update_rejects_invalid_status(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    line = next(ln for ln in list_r.output.splitlines() if "A+ baseline" in ln)
    hid = next(tok for tok in line.split() if tok.isdigit())

    r = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "exploded", "--reason", "x",
    ])
    assert r.exit_code != 0


def test_hypothesis_update_rejects_invalid_transition(tmp_path: Path):
    """closed-target-met is terminal — operator cannot reopen via CLI."""
    runner, cfg = _setup(tmp_path)
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    line = next(ln for ln in list_r.output.splitlines() if "A+ baseline" in ln)
    hid = next(tok for tok in line.split() if tok.isdigit())

    r1 = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "closed-target-met", "--reason", "hit 20",
    ])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "active", "--reason", "reopen",
    ])
    assert r2.exit_code != 0
    assert "transition" in r2.output.lower() or "not allowed" in r2.output.lower()


def test_hypothesis_update_does_not_expose_frozen_field_mutators(tmp_path: Path):
    """Anti-rationalization watch (brief §5): the CLI exposes ONLY a
    `--status` mutator. There is no flag to change target_sample_size,
    consecutive_loss_tripwire, etc."""
    runner, cfg = _setup(tmp_path)
    help_r = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", "--help",
    ])
    assert help_r.exit_code == 0
    out = help_r.output.lower()
    assert "--status" in out
    assert "--reason" in out
    # Forbidden flags must not be present.
    for forbidden in [
        "--target", "--target-sample", "--target-sample-size",
        "--consecutive-loss", "--tripwire", "--decision-criteria",
        "--statement", "--name",
    ]:
        assert forbidden not in out, f"forbidden mutator {forbidden} surfaced in help"


def test_hypothesis_paused_to_active_round_trip(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    line = next(ln for ln in list_r.output.splitlines() if "A+ baseline" in ln)
    hid = next(tok for tok in line.split() if tok.isdigit())

    p = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "paused", "--reason", "p",
    ])
    assert p.exit_code == 0
    a = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "active", "--reason", "resume",
    ])
    assert a.exit_code == 0


def test_hypothesis_update_identity_returns_info_not_error(tmp_path: Path):
    """Phase 9 T-C.4: identity transition (current == new) returns INFO,
    NOT a transition error.

    Per spec §3.4.1 R3 Minor #1 + plan §A.1 step 4: the legacy repo
    function REJECTED identity transitions with a transition error; the
    new service helper treats them as NoOpIdentityTransition, returns
    sentinel, CLI prints an INFO line + exits 0.
    """
    runner, cfg = _setup(tmp_path)
    list_r = runner.invoke(main, ["--config", str(cfg), "hypothesis", "list"])
    line = next(ln for ln in list_r.output.splitlines() if "A+ baseline" in ln)
    hid = next(tok for tok in line.split() if tok.isdigit())

    # All seeded hypotheses start as `active`. Identity transition.
    r = runner.invoke(main, [
        "--config", str(cfg), "hypothesis", "update", hid,
        "--status", "active", "--reason", "redundant",
    ])
    assert r.exit_code == 0, r.output
    assert "already active" in r.output
    assert "info:" in r.output
