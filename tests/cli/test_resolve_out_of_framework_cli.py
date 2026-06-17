"""SPCX carve-out — `swing schwab resolve-out-of-framework` CLI surface (Task 3).

The operator-driven one-shot clear: resolves the EXISTING declared-ticker SPCX
orphan rows via the scoped landing function. Invoked OUTSIDE any recon tx (the
clean post-COMMIT call site per the resolve_discrepancy BEGIN-IMMEDIATE
discipline).
"""
from __future__ import annotations

from types import SimpleNamespace

import swing.config_overrides as _config_overrides
from click.testing import CliRunner

from swing.cli import main as cli
from swing.data.db import ensure_schema


def _stub_cfg(db_path, *, tickers=("SPCX",)):
    return SimpleNamespace(
        paths=SimpleNamespace(db_path=db_path),
        reconciliation=SimpleNamespace(out_of_framework_tickers=tuple(tickers)),
    )


def _plant_orphan(conn, ticker="SPCX"):
    cur = conn.execute(
        "INSERT INTO reconciliation_runs "
        "(source, state, started_ts, finished_ts, "
        " unresolved_discrepancies_count) VALUES "
        "('schwab_api', 'completed', '2026-06-15T09:00:00.000', "
        "'2026-06-15T09:00:01.000', 1)"
    )
    run_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, ticker, "
        " expected_value_json, actual_value_json, delta_text, "
        " material_to_review, resolution, created_at) "
        "VALUES (?, 'untracked_broker_position', 'broker_position', ?, "
        " '{\"journal_qty\": 0}', '{\"qty\": 2.0, \"market_value\": 412.0}', "
        " 'x', 1, 'unresolved', '2026-06-15T09:00:00.000')",
        (run_id, ticker),
    )
    conn.commit()


def test_cli_resolve_out_of_framework_clears_declared_orphan(
    tmp_path, monkeypatch,
):
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    _plant_orphan(conn, "SPCX")
    conn.close()

    stub = _stub_cfg(db_path, tickers=("SPCX",))
    monkeypatch.setattr(_config_overrides, "apply_overrides", lambda _c: stub)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["schwab", "resolve-out-of-framework"]
    )
    assert result.exit_code == 0, result.output
    assert "1" in result.output

    conn = ensure_schema(db_path)
    resolution = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE ticker='SPCX'"
    ).fetchone()[0]
    conn.close()
    assert resolution == "acknowledged_immaterial"


def test_cli_resolve_out_of_framework_empty_set_noop(tmp_path, monkeypatch):
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    _plant_orphan(conn, "SPCX")
    conn.close()

    stub = _stub_cfg(db_path, tickers=())
    monkeypatch.setattr(_config_overrides, "apply_overrides", lambda _c: stub)

    runner = CliRunner()
    result = runner.invoke(cli, ["schwab", "resolve-out-of-framework"])
    assert result.exit_code == 0, result.output

    conn = ensure_schema(db_path)
    resolution = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE ticker='SPCX'"
    ).fetchone()[0]
    conn.close()
    assert resolution == "unresolved"  # untouched
