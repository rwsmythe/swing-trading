"""Phase 11 T-B.6 — SchwabPipelineActiveError cross-surface exclusion tests.

Per plan §H.10 corrected disposition + dispatch brief §4.2 T-B.6:
  * 5 protected CLI subcommands (check + raise unless --force):
    setup-without-force, logout-without-force, fetch --snapshot,
    fetch --orders, fetch --all.
  * 2 with --force override (setup --force, logout --force): bypass + run.
  * 3 safe CLI subcommands (NO check; refresh has no --force flag at all):
    status, refresh, fetch --verify-marketdata.

Sub-bundle B owns the 3 fetch subcommands (--snapshot/--orders/--all);
Sub-bundle A already shipped setup/logout/refresh/status with their own
SchwabPipelineActiveError behavior. T-B.6 covers all 8 surfaces in one
file so the contract is verified end-to-end.

NOTE: `fetch --verify-marketdata` is the Market-Data verification surface
in Sub-bundle C (T-C.5). For Sub-bundle B, that command does NOT exist
yet — so the "3 safe" group reduces to 2 for Sub-bundle B's gate-budget.
The discriminating-test pattern stays correct for the 2 reachable safe
surfaces (status + refresh); T-C.5 will add the third.

10 tests total: 5 protected + 2 force-override + 3 safe (the
fetch --verify-marketdata test is SKIPPED with reason naming T-C.5 un-skip
point — preserves the +10 acceptance count per dispatch brief §4.2 T-B.6).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from swing.data.db import ensure_schema


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def isolated_db(isolated_home):
    db_path = isolated_home / "swing-data" / "swing.db"
    ensure_schema(db_path).close()
    return db_path


def _plant_running_pipeline(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES (?,?,?,?,?,?)",
        ("2026-05-14T08:00:00", "manual", "2026-05-13", "2026-05-14",
         "running", "test-token"),
    )
    conn.commit()
    conn.close()


def _make_cfg(*, db_path: Path) -> SimpleNamespace:
    """Minimal SimpleNamespace cfg stub used to exercise pipeline-active
    rejection. ``apply_overrides`` (called at CLI entry points per Codex
    R1 Critical #1 fix) short-circuits on non-dataclass cfgs (defensive
    contract documented in ``swing/config_overrides.py``), so this stub
    remains usable without web/pipeline/account namespaces.
    """
    return SimpleNamespace(
        paths=SimpleNamespace(db_path=Path(db_path)),
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                account_hash="abc...64charhash",
                lookback_days=7,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
            finviz=SimpleNamespace(token="", screen_query="", timeout_seconds=30),
        ),
    )


def _stub_schwabdev(monkeypatch):
    """Patch schwabdev.Client to return a usable mock."""
    mock_client = MagicMock()
    mock_client.tokens.access_token = "stub_access_token"
    mock_client.tokens.refresh_token = "stub_refresh_token"
    details_resp = MagicMock()
    details_resp.json.return_value = {
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": 2000.0,
                "cashBalance": 100.0, "buyingPower": 4000.0,
            },
            "positions": [],
        },
    }
    details_resp.status_code = 200
    details_resp.headers = {}
    mock_client.account_details.return_value = details_resp

    list_resp = MagicMock()
    list_resp.json.return_value = []
    list_resp.status_code = 200
    list_resp.headers = {}
    mock_client.account_orders.return_value = list_resp
    mock_client.transactions.return_value = list_resp

    # linked_accounts: list of one dict.
    linked_resp = MagicMock()
    linked_resp.json.return_value = [
        {"accountNumber": "12345678", "hashValue": "abc...64charhash"},
    ]
    linked_resp.status_code = 200
    linked_resp.headers = {}
    mock_client.linked_accounts.return_value = linked_resp

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", MagicMock(return_value=mock_client))
    return mock_client


@pytest.fixture
def invoke_cli():
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
# 5 PROTECTED (check + raise unless --force)
# ============================================================================


def test_b6_01_setup_without_force_raises(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab setup` without --force while pipeline running → error."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "setup")
    assert result.exit_code != 0
    assert "Pipeline" in result.output or "pipeline" in result.output


def test_b6_02_logout_without_force_raises(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab logout` without --force while pipeline running → error."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "logout")
    assert result.exit_code != 0
    assert "Pipeline" in result.output or "pipeline" in result.output


def test_b6_03_fetch_snapshot_raises(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab fetch --snapshot` while pipeline running → error (NO --force)."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert result.exit_code != 0


def test_b6_04_fetch_orders_raises(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab fetch --orders` while pipeline running → error."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--orders")
    assert result.exit_code != 0


def test_b6_05_fetch_all_raises(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab fetch --all` while pipeline running → error."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "fetch", "--all")
    assert result.exit_code != 0


# ============================================================================
# 2 FORCE-OVERRIDE (setup --force, logout --force bypass)
# ============================================================================


def test_b6_06_setup_force_bypasses(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab setup --force` while pipeline running: NO pipeline-active error.

    Discriminating: setup may still fail on other grounds (account_linked
    empty, etc.) — but it MUST NOT fail with SchwabPipelineActiveError.
    Verify by absence of "in flight" / "Pipeline run" substring AND that
    the exit code is non-pipeline-active.
    """
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "setup", "--force")
    # Pipeline-active error MUST NOT be the failure mode.
    assert "Pipeline run" not in result.output


def test_b6_07_logout_force_bypasses(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab logout --force` while pipeline running: bypasses gate."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    # Plant a token file so the revoke path has something to read.
    tokens_path = isolated_db.parent / "schwab-tokens.production.db"
    tokens_path.write_text('{"token_dictionary": {}}', encoding="utf-8")
    result = invoke_cli(cfg, "logout", "--force")
    assert "Pipeline run" not in result.output


# ============================================================================
# 3 SAFE (NO check)
# ============================================================================


def test_b6_08_status_NOT_protected(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab status` while pipeline running: SUCCEEDS (no gate)."""
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "status")
    # Status is read-only — must NOT emit pipeline-active error.
    assert "Pipeline run" not in result.output


def test_b6_09_refresh_NOT_protected(isolated_db, invoke_cli, monkeypatch):
    """`swing schwab refresh` while pipeline running: bypasses gate.

    Per plan §H.10 corrected disposition: refresh has NO --force flag at
    all + is concurrent-safe (schwabdev's RLock + SQLite file lock handle
    the inner race). Therefore the CLI MUST NOT gate on pipeline-active.
    """
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    _stub_schwabdev(monkeypatch)
    result = invoke_cli(cfg, "refresh")
    # Refresh may fail on other grounds (e.g., no tokens file) — but MUST
    # NOT raise pipeline-active error.
    assert "Pipeline run" not in result.output


def test_b6_10_fetch_verify_marketdata_NOT_protected(
    isolated_db, invoke_cli, monkeypatch,
):
    """`swing schwab fetch --verify-marketdata` while pipeline running:
    SUCCEEDS (verification-only, cache writes skipped regardless of env).

    Un-skipped at T-C.5 per dispatch brief: --verify-marketdata is in the
    3-safe-subcommands list (plan §H.10) + does NOT enforce the pipeline-
    active exclusion. Operator must be able to run market-data verification
    against a stuck/running pipeline lease.

    Discriminating: with a planted `state='running'` pipeline_runs row,
    the CLI invocation MUST NOT emit "Pipeline run" / "in flight"
    substring. quotes + price_history stubs are pre-wired to return
    success shapes so the test verifies the GATE BYPASS, not network
    reachability.
    """
    _plant_running_pipeline(isolated_db)
    cfg = _make_cfg(db_path=isolated_db)
    mock_client = _stub_schwabdev(monkeypatch)
    # Add quotes + price_history stubs (T-C.5 surface).
    quotes_resp = MagicMock()
    quotes_resp.json.return_value = {
        "AAPL": {
            "quote": {
                "lastPrice": 100.0, "bidPrice": 99.0, "askPrice": 101.0,
                "mark": 100.0, "quoteTime": "2026-05-14T15:30:00Z",
                "delayed": False,
            },
        },
    }
    quotes_resp.status_code = 200
    quotes_resp.headers = {}
    mock_client.quotes.return_value = quotes_resp

    ph_resp = MagicMock()
    ph_resp.json.return_value = {
        "empty": False,
        "symbol": "AAPL",
        "candles": [
            {
                "datetime": 1747094400000,
                "open": 100.0, "high": 101.0, "low": 99.0,
                "close": 100.5, "volume": 1_000_000,
            },
            {
                "datetime": 1747180800000,
                "open": 100.5, "high": 102.0, "low": 100.0,
                "close": 101.5, "volume": 1_100_000,
            },
        ],
    }
    ph_resp.status_code = 200
    ph_resp.headers = {}
    mock_client.price_history.return_value = ph_resp

    result = invoke_cli(cfg, "fetch", "--verify-marketdata")
    # Pipeline-active gate MUST NOT fire.
    assert "Pipeline run" not in result.output
    assert "in flight" not in result.output
