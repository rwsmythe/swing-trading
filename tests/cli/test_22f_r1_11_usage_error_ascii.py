"""22-F R1-11 (Reviewer A round 1, minor) -- the three `click.UsageError(
str(e))` translations in `swing/cli.py` pass raw service text to Click.  A
service `ValueError` can embed an operator payload value verbatim, so
non-ASCII text reached stderr unchanged.  POST-FIX the text goes through
`ascii_safe` (the arc's S-ASCII shape); the exit code stays click's usage 2.

The three sites (READ in `swing/cli.py`): `discrepancy resolve-ambiguity`'s
FK-orphan branch (`resolve_discrepancy`), its tier-2 path
(`apply_tier2_resolution`), and `discrepancy override-correction`
(`apply_tier3_override`).  Each service is imported INSIDE the command, so the
patch lands on the module attribute the command resolves at call time; each
case asserts the planted raise fired (did-it-fire).
"""
from __future__ import annotations

import sqlite3

from swing.cli import main
from tests._22f_proxies import raising
from tests.cli.test_22f_cli_typed_refusals import _recon_world, _seed_head

_NON_ASCII = "bad payload value 交易"


def _assert_usage_ascii(result, planted) -> None:
    assert planted.calls == 1
    assert result.exit_code == 2, (result.output, result.exception)
    assert "bad payload value" in result.output
    assert result.output.isascii(), result.output


def test_r1_11_orphan_branch_usage_error_is_ascii(tmp_path, monkeypatch):
    from tests.cli.test_discrepancy_resolve_ambiguity_cli import (
        _seed_reconciliation_run,
    )
    from tests.cli.test_discrepancy_resolve_ambiguity_orphan_cli import (
        _plant_fk_orphan,
    )
    runner, cfg, db_path, _world = _recon_world(tmp_path, tier2=True)
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_fk_orphan(conn, run_id=run_id, cash_movement_id=9999)
        conn.commit()
    finally:
        conn.close()
    planted = raising(ValueError(_NON_ASCII))
    monkeypatch.setattr("swing.trades.reconciliation.resolve_discrepancy",
                        planted)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve-ambiguity",
        str(did), "--reason", "subject row gone",
    ])
    _assert_usage_ascii(result, planted)


def test_r1_11_tier2_usage_error_is_ascii(tmp_path, monkeypatch):
    runner, cfg, _db_path, world = _recon_world(tmp_path, tier2=True)
    planted = raising(ValueError(_NON_ASCII))
    monkeypatch.setattr(
        "swing.trades.reconciliation_auto_correct.apply_tier2_resolution",
        planted)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve-ambiguity",
        str(world["discrepancy_id"]), "--choice", "operator_truth",
        "--custom-value", '{"current_stop": 4.6}',
        "--reason", "broker says so",
    ])
    _assert_usage_ascii(result, planted)


def test_r1_11_override_correction_usage_error_is_ascii(tmp_path,
                                                        monkeypatch):
    runner, cfg, db_path, world = _recon_world(tmp_path, tier2=False)
    head_id = _seed_head(db_path, world)
    planted = raising(ValueError(_NON_ASCII))
    monkeypatch.setattr(
        "swing.trades.reconciliation_auto_correct.apply_tier3_override",
        planted)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "override-correction",
        str(head_id), "--truth-value", '{"current_stop": 4.6}',
        "--reason", "override", "--force",
    ])
    _assert_usage_ascii(result, planted)


def test_r1_11_source_has_no_raw_usage_error_text():
    """Closure (static): no `click.UsageError(str(` remains in the CLI
    modules; the three sites are the whole family by the grep that found
    them (`grep -n 'UsageError(str(' swing/cli*.py`)."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "swing"
    for path in sorted(root.glob("cli*.py")):
        text = path.read_text(encoding="utf-8")
        assert "UsageError(str(" not in text, path.name
