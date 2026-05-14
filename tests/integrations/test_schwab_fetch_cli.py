"""Phase 11 T-B.5 — `swing schwab fetch [--snapshot|--orders|--all]` CLI tests.

Per plan §3.5 + §H.10.

Tests cover:
  - Per-subcommand flag dispatch (--snapshot / --orders / --all).
  - Mutual-exclusion of --snapshot + --orders WITHOUT --all (error).
  - Empty-flag invocation (error).
  - Happy path: production env writes domain rows.
  - Sandbox env: audit row + no domain write.
  - Exit code 0 on success; non-zero on schwabdev failure.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from swing.data.db import ensure_schema


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch):
    """Isolate USERPROFILE + HOME per CLAUDE.md gotcha for write_user_overrides."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def isolated_db(isolated_home, monkeypatch):
    """Initialise a v18 DB at the isolated USERPROFILE."""
    db_path = isolated_home / "swing-data" / "swing.db"
    ensure_schema(db_path).close()
    return db_path


def _make_cfg(*, db_path: Path, environment: str = "production",
              account_hash: str | None = "abc...64charhash") -> SimpleNamespace:
    """Build a cfg namespace satisfying the CLI's ctx.obj['config'] consumer."""
    return SimpleNamespace(
        paths=SimpleNamespace(db_path=Path(db_path)),
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment=environment,
                account_hash=account_hash,
                lookback_days=7,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
            finviz=SimpleNamespace(token="", screen_query="", timeout_seconds=30),
        ),
    )


def _stub_schwabdev_client(monkeypatch, *, nlv: float = 2014.36):
    """Patch schwabdev.Client to return a MagicMock with tokens.access_token set."""
    mock_client = MagicMock()
    mock_client.tokens.access_token = "stub_access_token_12345"
    mock_client.tokens.refresh_token = "stub_refresh_token_12345"
    # account_details returns an HTTP-200 response with NLV.
    details_resp = MagicMock()
    details_resp.json.return_value = {
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": nlv,
                "cashBalance": 100.0,
                "buyingPower": 4000.0,
            },
            "positions": [],
        },
    }
    details_resp.status_code = 200
    details_resp.headers = {}
    mock_client.account_details.return_value = details_resp

    # orders: empty list.
    orders_resp = MagicMock()
    orders_resp.json.return_value = []
    orders_resp.status_code = 200
    orders_resp.headers = {}
    mock_client.account_orders.return_value = orders_resp

    # transactions: empty list.
    tx_resp = MagicMock()
    tx_resp.json.return_value = []
    tx_resp.status_code = 200
    tx_resp.headers = {}
    mock_client.transactions.return_value = tx_resp

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", MagicMock(return_value=mock_client))
    return mock_client


@pytest.fixture
def invoke_cli():
    """Helper: return (result, db_conn) for a CLI invocation with the schwab group."""
    runner = CliRunner()

    def _invoke(cfg, *args, input_str: str = "cid\ncsecret\n"):
        from swing.cli_schwab import schwab_group

        @click.group()
        @click.pass_context
        def root(ctx):
            ctx.obj = {"config": cfg}

        root.add_command(schwab_group)
        return runner.invoke(root, ["schwab", *args], input=input_str)
    return _invoke


# ============================================================================
# T-B.5 Tests
# ============================================================================


def test_b5_01_fetch_requires_one_flag(isolated_db, invoke_cli, monkeypatch):
    """Empty `swing schwab fetch` → error: must choose one of the 3 flags."""
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch")
    assert result.exit_code != 0
    assert "Choose one" in result.output


def test_b5_02_fetch_rejects_mutually_exclusive_snapshot_and_orders(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--snapshot --orders` without `--all` is rejected."""
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--snapshot", "--orders")
    assert result.exit_code != 0
    assert "Choose only one" in result.output


def test_b5_03_fetch_snapshot_happy_path_production(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--snapshot` under production: audit row + snapshot + linkage."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    mc = _stub_schwabdev_client(monkeypatch, nlv=2014.36)
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert result.exit_code == 0, result.output
    assert "snapshot" in result.output
    assert "completed" in result.output
    # Verify domain rows landed.
    conn = sqlite3.connect(isolated_db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM account_equity_snapshots "
            "WHERE source = 'schwab_api'"
        ).fetchone()[0]
        assert cnt == 1
        # Audit row carries surface='cli'.
        row = conn.execute(
            "SELECT surface, environment, status FROM schwab_api_calls "
            "WHERE endpoint = 'accounts.details' ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
        assert row[0] == "cli"
        assert row[1] == "production"
        assert row[2] == "success"
    finally:
        conn.close()


def test_b5_04_fetch_orders_happy_path_production(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--orders` under production: 3 audit rows + 1 reconciliation_run."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--orders")
    assert result.exit_code == 0, result.output
    assert "orders" in result.output
    conn = sqlite3.connect(isolated_db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs WHERE source = 'schwab_api'"
        ).fetchone()[0]
        assert cnt == 1
        # 3 audit rows for the 3 schwabdev calls.
        cnt = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE surface = 'cli'"
        ).fetchone()[0]
        assert cnt == 3
    finally:
        conn.close()


def test_b5_05_fetch_all_runs_both_steps(isolated_db, invoke_cli, monkeypatch):
    """`--all` runs snapshot + orders sequentially."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--all")
    assert result.exit_code == 0, result.output
    assert "snapshot" in result.output
    assert "orders" in result.output
    conn = sqlite3.connect(isolated_db)
    try:
        snap_cnt = conn.execute(
            "SELECT COUNT(*) FROM account_equity_snapshots WHERE source = 'schwab_api'"
        ).fetchone()[0]
        recon_cnt = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs WHERE source = 'schwab_api'"
        ).fetchone()[0]
        assert snap_cnt == 1
        assert recon_cnt == 1
    finally:
        conn.close()


def test_b5_06_fetch_snapshot_sandbox_skips_domain_write(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--snapshot --environment sandbox`: audit row written, ZERO snapshot rows."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--snapshot", "--environment", "sandbox")
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(isolated_db)
    try:
        snap_cnt = conn.execute(
            "SELECT COUNT(*) FROM account_equity_snapshots WHERE source = 'schwab_api'"
        ).fetchone()[0]
        audit_cnt = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE environment = 'sandbox'"
        ).fetchone()[0]
        assert snap_cnt == 0
        assert audit_cnt >= 1
    finally:
        conn.close()


def test_b5_07_fetch_orders_sandbox_skips_reconciliation(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--orders --environment sandbox`: audit rows written, ZERO reconciliation runs."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--orders", "--environment", "sandbox")
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(isolated_db)
    try:
        recon_cnt = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs WHERE source = 'schwab_api'"
        ).fetchone()[0]
        sandbox_audit_cnt = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE environment = 'sandbox'"
        ).fetchone()[0]
        assert recon_cnt == 0
        assert sandbox_audit_cnt == 3
    finally:
        conn.close()


def test_b5_08_fetch_pipeline_active_hard_exclusion(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--snapshot` while pipeline state='running' → exits non-zero (NO --force)."""
    # Plant a running pipeline row.
    conn = sqlite3.connect(isolated_db)
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES (?,?,?,?,?,?)",
        ("2026-05-14T08:00:00", "manual", "2026-05-13", "2026-05-14",
         "running", "test-token"),
    )
    conn.commit()
    conn.close()

    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert result.exit_code != 0
    assert "Pipeline run" in result.output or "in flight" in result.output


def test_b5_09_fetch_orders_pipeline_active_hard_exclusion(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--orders` while pipeline running → exits non-zero."""
    conn = sqlite3.connect(isolated_db)
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES (?,?,?,?,?,?)",
        ("2026-05-14T08:00:00", "manual", "2026-05-13", "2026-05-14",
         "running", "test-token"),
    )
    conn.commit()
    conn.close()

    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--orders")
    assert result.exit_code != 0


def test_b5_10_fetch_all_pipeline_active_hard_exclusion(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--all` while pipeline running → exits non-zero (mirror of --snapshot/--orders)."""
    conn = sqlite3.connect(isolated_db)
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES (?,?,?,?,?,?)",
        ("2026-05-14T08:00:00", "manual", "2026-05-13", "2026-05-14",
         "running", "test-token"),
    )
    conn.commit()
    conn.close()

    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--all")
    assert result.exit_code != 0
