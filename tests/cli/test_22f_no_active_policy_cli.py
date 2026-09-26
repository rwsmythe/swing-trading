"""22-F T-D5 (CLI half) -- `NoActivePolicyError` CONVERTED (CHARC F-F4 (3)),
as RULED at STOP-2 (items 1-3 + the `risk_policy.py:139-141` retype) with the
STOP-3 supersession of item 4's discriminator (exec ledger, "Rulings
relayed").

* The two SUPERSEDE-ONLY writers (`config policy set`, `config policy
  import-from-toml`) and the three READ roots (`config policy show`,
  `discrepancy resolve-ambiguity`, `discrepancy override-correction`): a
  typed refusal (exit 1, `Error: <the ruled text>`), nothing written, ZERO
  active rows afterwards (no branch auto-seeds).
* The two CASCADE writers (`config set`, `config reset`): order and
  containment KEPT (exit 0; the override IS written / deleted -- observed on
  a fresh read); the WARNING states, in order, (a) the override was written /
  deleted, (b) the cascade did NOT fire because no policy row is active,
  (c) the ruled recovery; ZERO active rows afterwards.
* CONTROL: with an active row each cascade writer's happy path is
  byte-unchanged.
* The D35 pin (encoding TAKEN by CHARC at STOP-3): no `swing <N>` for any
  registered top-level command/group name N of `swing.cli.main`, and
  `command` is not a registered name -- the ruled sentence "No swing command
  creates a policy." stays.

Every world is a temp DB zeroed by a RAW `UPDATE risk_policy SET is_active =
0` (the state no `swing` command produces).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_22f_cli_typed_refusals import (
    _correction_count,
    _recon_world,
    _seed_head,
)

#: STOP-2 item 1, verbatim (the spec; the production constant must equal it).
RULED_TEXT = (
    "No active risk_policy row: the policy table is corrupted or unseeded. "
    "Recover by restoring ~/swing-data/swing.db from a gate image in "
    "~/swing-data/backups/ (see the migration ledger), or by a hand repair "
    "under the operator's own sitting. No swing command creates a policy."
)


def assert_names_no_swing_command(message: str) -> None:
    """The D35 pin: a refusal must not name an action that fails.  By
    REGISTERED names, not by the substring (the ruled text itself contains
    `swing ` + `command`)."""
    assert "command" not in main.commands
    named = [n for n in main.commands if f"swing {n}" in message]
    assert named == [], (named, message)


def test_d35_pin_discriminates():
    """The pin fails on the plan's old text and on the pre-fix cascade
    WARNING hint, and passes on the ruled text."""
    assert_names_no_swing_command(RULED_TEXT)
    for old in ("Run: swing config policy import-from-toml",
                "Run `swing config policy import-from-toml --field x`"):
        with pytest.raises(AssertionError):
            assert_names_no_swing_command(old)


# ---------------------------------------------------------------------------
# worlds
# ---------------------------------------------------------------------------

@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert r.exit_code == 0, r.output
    db = home / "swing-data" / "swing.db"
    return runner, cfg_path, db, home / "swing-data" / "user-config.toml"


def _zero(db: Path) -> None:
    c = sqlite3.connect(str(db))
    try:
        c.execute("UPDATE risk_policy SET is_active = 0")
        c.commit()
    finally:
        c.close()


def _policy(db: Path) -> tuple[int, int]:
    """(rows, active rows) on a FRESH connection."""
    c = sqlite3.connect(str(db))
    try:
        return c.execute(
            "SELECT COUNT(*), COALESCE(SUM(is_active), 0) FROM risk_policy"
        ).fetchone()
    finally:
        c.close()


def _override(user_cfg: Path) -> str | None:
    return user_cfg.read_text(encoding="utf-8") if user_cfg.exists() else None


def _assert_refused(result) -> None:
    assert isinstance(result.exception, SystemExit), (
        type(result.exception), result.output)
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.output == f"Error: {RULED_TEXT}\n", result.output
    assert_names_no_swing_command(result.output)


# ---------------------------------------------------------------------------
# the retype (STOP-2 item 4, standing)
# ---------------------------------------------------------------------------

def test_retype_supersede_raises_no_active_policy_error_ascii(world):
    """PRE-FIX: a plain `RuntimeError` with an em-dash.  POST-FIX:
    `NoActivePolicyError` (still a `RuntimeError`), ASCII text, and the
    rollback leaves the table untouched."""
    from swing.data.db import connect
    from swing.data.repos.risk_policy import NoActivePolicyError
    from swing.trades.risk_policy import supersede_active_policy
    _runner, _cfg, db, _uc = world
    _zero(db)
    before = _policy(db)
    conn = connect(db)
    try:
        with pytest.raises(NoActivePolicyError) as info:
            supersede_active_policy(
                conn, field_updates={"max_concurrent_positions": 5})
    finally:
        conn.close()
    assert isinstance(info.value, RuntimeError)
    str(info.value).encode("ascii")
    assert _policy(db) == before == (1, 0)


# ---------------------------------------------------------------------------
# the supersede-only writers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [
    ["config", "policy", "set", "--field", "max_concurrent_positions",
     "--value", "5"],
    ["config", "policy", "import-from-toml", "--field",
     "capital_floor_constant_dollars"],
], ids=["policy-set", "import-from-toml"])
def test_supersede_only_writer_refuses_typed_writes_nothing(world, argv):
    """PRE-FIX: exit 1 on an UNCAUGHT `RuntimeError` (empty output -- a
    traceback).  POST-FIX: the ruled refusal; the table unchanged; zero
    active rows."""
    runner, cfg, db, _uc = world
    _zero(db)
    result = runner.invoke(main, ["--config", str(cfg), *argv])
    _assert_refused(result)
    assert _policy(db) == (1, 0)


# ---------------------------------------------------------------------------
# the read roots
# ---------------------------------------------------------------------------

def test_D5i_policy_show_refuses_typed(world):
    runner, cfg, db, _uc = world
    _zero(db)
    result = runner.invoke(main, ["--config", str(cfg), "config", "policy",
                                  "show"])
    _assert_refused(result)
    assert _policy(db) == (1, 0)


def test_D5j_resolve_ambiguity_refuses_typed(tmp_path):
    """The command reaches its `read_active_policy` (`cli.py`, before the
    tier-2 service call) only after the discrepancy and the choice validate:
    22-A4's world (the T-A5 drive), zeroed."""
    runner, cfg, db_path, w = _recon_world(tmp_path, tier2=True)
    _zero(db_path)
    before = _correction_count(db_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve-ambiguity",
        str(w["discrepancy_id"]), "--choice", "operator_truth",
        "--custom-value", '{"current_stop": 4.6}', "--reason", "r",
    ])
    _assert_refused(result)
    assert _correction_count(db_path) == before
    assert _policy(db_path)[1] == 0


def test_D5j_override_correction_refuses_typed(tmp_path):
    runner, cfg, db_path, w = _recon_world(tmp_path, tier2=False)
    head_id = _seed_head(db_path, w)
    _zero(db_path)
    before = _correction_count(db_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "override-correction",
        str(head_id), "--truth-value", '{"current_stop": 4.6}',
        "--reason", "r", "--force",
    ])
    _assert_refused(result)
    assert _correction_count(db_path) == before
    assert _policy(db_path)[1] == 0


# ---------------------------------------------------------------------------
# the cascade writers: order + containment kept, cause-specific WARNING
# ---------------------------------------------------------------------------

def _assert_ordered_warning(output: str, verb: str) -> None:
    """(a) the override was <verb>, (b) the cascade did NOT fire because no
    policy row is active, (c) the ruled recovery -- in that order."""
    a = output.index(f"override {verb}")
    b = output.index("the risk_policy cascade did NOT fire because no "
                     "policy row is active")
    c = output.index(RULED_TEXT)
    assert a < b < c, output
    assert_names_no_swing_command(output)


def test_config_set_cascade_no_active_policy_is_contained_and_true(world):
    """PRE-FIX: exit 0 and a WARNING naming `swing config policy
    import-from-toml` (a command that FAILS in this state -- D35).
    POST-FIX: exit 0; the override written (fresh read); the ordered,
    cause-specific WARNING; zero active rows."""
    runner, cfg, db, uc = world
    _zero(db)
    result = runner.invoke(main, ["--config", str(cfg), "config", "set",
                                  "account.risk_equity_floor", "8500.0",
                                  "--force"])
    assert result.exit_code == 0, result.output
    assert "risk_equity_floor = 8500.0" in (_override(uc) or "")
    _assert_ordered_warning(result.output, "written")
    assert _policy(db) == (1, 0)


def test_config_reset_cascade_no_active_policy_is_contained_and_true(world):
    runner, cfg, db, uc = world
    r = runner.invoke(main, ["--config", str(cfg), "config", "set",
                             "account.risk_equity_floor", "8500.0", "--force"])
    assert r.exit_code == 0, r.output
    assert _policy(db) == (2, 1)
    _zero(db)
    result = runner.invoke(main, ["--config", str(cfg), "config", "reset",
                                  "account.risk_equity_floor"])
    assert result.exit_code == 0, result.output
    assert "risk_equity_floor" not in (_override(uc) or "")
    _assert_ordered_warning(result.output, "deleted")
    assert _policy(db) == (2, 0)


def test_cascade_other_cause_keeps_todays_hint(world, monkeypatch):
    """CONTROL: a cascade failure of any OTHER cause keeps today's text
    (an active row exists to supersede, so the hint is true).  The planted
    `ValueError` replaces `supersede_active_policy` in its home module (the
    command imports it function-locally, so the name resolves per call)."""
    from tests._22f_proxies import raising
    runner, cfg, db, _uc = world
    planted = raising(ValueError("planted other cause"))
    monkeypatch.setattr("swing.trades.risk_policy.supersede_active_policy",
                        planted)
    result = runner.invoke(main, ["--config", str(cfg), "config", "set",
                                  "account.risk_equity_floor", "8500.0",
                                  "--force"])
    assert planted.calls >= 1  # did-it-fire
    assert result.exit_code == 0, result.output
    assert ("WARNING: risk_policy cascade failed (planted other cause); "
            "override written but risk_policy NOT updated. Run `swing config "
            "policy import-from-toml --field capital_floor_constant_dollars` "
            "to reconcile.") in result.output
    assert RULED_TEXT not in result.output


def test_cascade_writers_happy_path_byte_unchanged(world):
    """CONTROL (STOP-3): with an active row each cascade writer supersedes
    exactly as before -- the output is byte-for-byte today's."""
    runner, cfg, db, _uc = world
    r = runner.invoke(main, ["--config", str(cfg), "config", "set",
                             "account.risk_equity_floor", "8500.0", "--force"])
    assert r.exit_code == 0
    assert r.output == (
        "Set account.risk_equity_floor = 8500.0\n"
        "Cascaded to risk_policy: new policy_id=2 with "
        "capital_floor_constant_dollars=8500.0\n"), r.output
    assert _policy(db) == (2, 1)
    r = runner.invoke(main, ["--config", str(cfg), "config", "reset",
                             "account.risk_equity_floor"])
    assert r.exit_code == 0
    # The startup divergence NOTE is today's output too (the tracked TOML
    # still reads 7500 while policy 2 holds 8500).
    assert r.output == (
        "NOTE: TOML diverges from risk_policy: cfg.account.risk_equity_floor="
        "7500.0 vs risk_policy.capital_floor_constant_dollars=8500.0; "
        "risk_policy is authoritative. To make TOML canonical, run: swing "
        "config policy import-from-toml --field capital_floor_constant_dollars"
        "\n"
        "Reset account.risk_equity_floor (now reads from default/tracked).\n"
        "Cascaded reset to risk_policy: new policy_id=3 with "
        "capital_floor_constant_dollars=7500.0\n"), r.output
    assert _policy(db) == (3, 1)
