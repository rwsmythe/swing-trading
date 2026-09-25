"""22-F Part B -- the WIDENED rows of the F-F2 three-state list (plan 3.1).

`SchwabSchemaParityError` is a `_RedactedMessageError`, NOT a
`SchwabApiError` (the classes are disjoint; F-F2 refused a re-base), so a
tuple naming only `SchwabApiError` lets a parity failure through.

T-B2 -- rows 5, 6 (`cli_schwab.py` `schwab fetch`'s snapshot / orders belts)
and 13 (`pipeline_steps.py` `_step_schwab_snapshot`).

Every planted failure goes through a counting wrapper asserted called (the
did-it-fire rule); each patch target is the name the code resolves at call
time, read from its source.
"""
from __future__ import annotations

from types import SimpleNamespace

from swing.integrations.schwab.client import SchwabSchemaParityError
from tests._22f_proxies import raising
from tests.integrations.test_schwab_fetch_cli import (  # noqa: F401
    _make_cfg,
    _stub_schwabdev_client,
    invoke_cli,
    isolated_db,
    isolated_home,
)

_PARITY = "<accounts.details: missing required key 'x'>"


def _plant_details(monkeypatch):
    """`pipeline_steps` binds `get_account_details` by its module-level
    import, so the module attribute is what `_step_schwab_snapshot`
    resolves per call."""
    planted = raising(SchwabSchemaParityError(_PARITY))
    monkeypatch.setattr(
        "swing.integrations.schwab.pipeline_steps.get_account_details",
        planted)
    return planted


def test_B2a_snapshot_step_contains_parity_as_failed(
        isolated_db, monkeypatch):
    """B2-a (row 13). PRE-FIX: the parity error escapes
    `_step_schwab_snapshot`'s `except SchwabApiError`.  POST-FIX:
    ``status="failed"``, ``error`` starts ``SchwabSchemaParityError:``."""
    from swing.data.db import connect
    from swing.integrations.schwab.pipeline_steps import _step_schwab_snapshot
    planted = _plant_details(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    conn = connect(isolated_db)
    try:
        r = _step_schwab_snapshot(conn, cfg, pipeline_run_id=None,
                                  client=SimpleNamespace(), surface="cli")
    finally:
        conn.close()
    assert planted.calls == 1  # did-it-fire
    assert r["status"] == "failed"
    assert r["error"].startswith("SchwabSchemaParityError:"), r


def test_B2b_fetch_snapshot_parity_is_contained_by_the_step(
        isolated_db, invoke_cli, monkeypatch):
    """B2-b. PRE-FIX: traceback (exit 1, the parity error as
    `result.exception`).  POST-FIX: exit 0, the snapshot step reported
    `failed` (row 13 contains it; row 5 is the belt)."""
    _stub_schwabdev_client(monkeypatch)
    planted = _plant_details(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert planted.calls == 1  # did-it-fire
    assert result.exit_code == 0, (repr(result.exception), result.output)
    assert "failed" in result.output


def _plant_step(monkeypatch, name: str):
    """`schwab_fetch` imports the steps FUNCTION-LOCALLY, so the
    `pipeline_steps` module attribute is read per call."""
    planted = raising(SchwabSchemaParityError(_PARITY))
    monkeypatch.setattr(
        f"swing.integrations.schwab.pipeline_steps.{name}", planted)
    return planted


def test_B2c_fetch_snapshot_belt_types_a_parity_escape(
        isolated_db, invoke_cli, monkeypatch):
    """B2-c (row 5, the belt). PRE-FIX: traceback.  POST-FIX: exit 1,
    `Error: Snapshot step failed: ...`, no traceback."""
    _stub_schwabdev_client(monkeypatch)
    planted = _plant_step(monkeypatch, "_step_schwab_snapshot")
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert planted.calls == 1  # did-it-fire
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1
    assert "Error: Snapshot step failed:" in result.output
    assert "Traceback" not in result.output


def test_B2d_fetch_orders_belt_types_a_parity_escape(
        isolated_db, invoke_cli, monkeypatch):
    """B2-d (row 6). PRE-FIX: traceback.  POST-FIX: exit 1,
    `Error: Orders step failed: ...`."""
    _stub_schwabdev_client(monkeypatch)
    planted = _plant_step(monkeypatch, "_step_schwab_orders")
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--orders")
    assert planted.calls == 1  # did-it-fire
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1
    assert "Error: Orders step failed:" in result.output
    assert "Traceback" not in result.output
