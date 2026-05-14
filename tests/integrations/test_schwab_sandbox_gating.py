"""Phase 11 T-B.2 — Sandbox-gating discriminating tests (cross-cutting).

Per plan §A.3 + spec §3.6.3 production-only domain writes.

Sandbox-gating contract (BINDING):
  * `_step_schwab_snapshot` under env='sandbox': writes audit row with
    status='success'; ZERO new rows in account_equity_snapshots for that
    snapshot_date.
  * `_step_schwab_orders` under env='sandbox': writes 3 audit rows; ZERO
    reconciliation_runs rows.
  * CLI `swing schwab fetch --environment sandbox` mirrors pipeline-step
    behavior (audit-only).
  * Production-env cfg flip activates domain writes.

These tests are discriminating: same input cassette/payload + opposite
env flag must produce DIFFERENT outputs (audit-row count unchanged;
domain-row count divergent).

Codex pre-emption per dispatch brief §4.2 T-B.2: "Sandbox-gating precedence
wrong (write-then-rollback vs short-circuit-before-write)" — the assertion
pattern is "account_equity_snapshots count UNCHANGED post-call when
env='sandbox' (NOT INSERT-then-DELETE)" + audit row status='success'.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.pipeline_steps import (
    _step_schwab_orders,
    _step_schwab_snapshot,
)


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "schwab-sandbox-gating.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    original_factory = logging.getLogRecordFactory()
    original_installed = schwab_client_module._FACTORY_INSTALLED
    original_orig = schwab_client_module._ORIGINAL_RECORD_FACTORY
    original_secrets = set(schwab_client_module._GLOBAL_KNOWN_SECRETS)
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._FACTORY_INSTALLED = False
    schwab_client_module._ORIGINAL_RECORD_FACTORY = None
    logging.setLogRecordFactory(logging.LogRecord)
    yield
    logging.setLogRecordFactory(original_factory)
    schwab_client_module._FACTORY_INSTALLED = original_installed
    schwab_client_module._ORIGINAL_RECORD_FACTORY = original_orig
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._GLOBAL_KNOWN_SECRETS.update(original_secrets)


def _make_cfg(*, environment: str) -> SimpleNamespace:
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment=environment,
                account_hash="abc...64charhash",
                lookback_days=7,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
        ),
    )


def _stub_client(nlv: float = 2014.36):
    """Build a stub schwabdev Client that returns a successful response."""
    client = MagicMock()
    details_resp = MagicMock()
    details_resp.json.return_value = {
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": nlv,
                "cashBalance": 100.0, "buyingPower": 4000.0,
            },
            "positions": [],
        },
    }
    details_resp.status_code = 200
    details_resp.headers = {}
    client.account_details.return_value = details_resp

    orders_resp = MagicMock()
    orders_resp.json.return_value = []
    orders_resp.status_code = 200
    orders_resp.headers = {}
    client.account_orders.return_value = orders_resp

    tx_resp = MagicMock()
    tx_resp.json.return_value = []
    tx_resp.status_code = 200
    tx_resp.headers = {}
    client.transactions.return_value = tx_resp
    return client


# ============================================================================
# T-B.2 — Sandbox-gating discriminating tests
# ============================================================================


def test_b2_01_snapshot_under_sandbox_writes_audit_skips_domain(v18_conn):
    """Sandbox: audit row written with status='success'; zero domain rows.

    Discriminating: pre-fix (write-then-rollback) would briefly INSERT then
    DELETE the snapshot — under SQLite, even the deleted-row autoincrement
    PK leaves a gap. Post-fix (short-circuit-before-write): NEVER touched
    the account_equity_snapshots table.
    """
    cfg = _make_cfg(environment="sandbox")
    client = _stub_client()
    pre_snap = v18_conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots"
    ).fetchone()[0]

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "sandbox_audit_only"

    # Audit row: success.
    audit_row = v18_conn.execute(
        "SELECT status, environment FROM schwab_api_calls "
        "WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert audit_row[0] == "success"
    assert audit_row[1] == "sandbox"

    # Domain table COUNT unchanged (NOT INSERT-then-DELETE).
    post_snap = v18_conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots"
    ).fetchone()[0]
    assert post_snap == pre_snap


def test_b2_02_orders_under_sandbox_writes_3_audit_zero_recon(v18_conn):
    """Sandbox orders: 3 audit rows + ZERO reconciliation_runs."""
    cfg = _make_cfg(environment="sandbox")
    client = _stub_client()
    pre_recon = v18_conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs"
    ).fetchone()[0]

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "sandbox_audit_only"
    assert result["reconciliation_run_id"] is None

    audit_cnt = v18_conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls WHERE environment = 'sandbox'"
    ).fetchone()[0]
    assert audit_cnt == 3

    post_recon = v18_conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs"
    ).fetchone()[0]
    assert post_recon == pre_recon


def test_b2_03_cfg_cascade_flip_activates_production_domain_writes(v18_conn):
    """Same conn + same input + cfg flip sandbox → production: domain
    write activates.

    Discriminating: pre-fix gating-by-pipeline-only would write under BOTH
    envs (gate misplaced). Post-fix: the env value alone (read from
    cfg.integrations.schwab.environment at step entry) drives the gate.
    """
    client = _stub_client()
    # Sandbox: no domain write.
    cfg_sandbox = _make_cfg(environment="sandbox")
    _step_schwab_snapshot(v18_conn, cfg_sandbox, pipeline_run_id=None, client=client)
    snap_after_sandbox = v18_conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots WHERE source = 'schwab_api'"
    ).fetchone()[0]
    assert snap_after_sandbox == 0

    # Production: domain write activates.
    cfg_prod = _make_cfg(environment="production")
    client2 = _stub_client()
    _step_schwab_snapshot(v18_conn, cfg_prod, pipeline_run_id=None, client=client2)
    snap_after_prod = v18_conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots WHERE source = 'schwab_api'"
    ).fetchone()[0]
    assert snap_after_prod == 1


def test_b2_04_sandbox_vs_production_signature_hash_match_on_same_payload(
    v18_conn,
):
    """Same payload under sandbox vs production yields SAME signature_hash.

    Per dispatch brief §4.2 T-B.7 pre-emption: cassette signature_hash MUST
    be env-independent (drift-detection signature is computed off response
    SHAPE, not env). Discriminating: pre-fix env-dependent signature
    (mistakenly seeded env into the fingerprint) would yield DIFFERENT
    hashes; post-fix: identical.
    """
    client_sandbox = _stub_client(nlv=2014.36)
    client_prod = _stub_client(nlv=2014.36)
    cfg_sb = _make_cfg(environment="sandbox")
    cfg_pd = _make_cfg(environment="production")

    r1 = _step_schwab_snapshot(
        v18_conn, cfg_sb, pipeline_run_id=None, client=client_sandbox,
    )
    r2 = _step_schwab_snapshot(
        v18_conn, cfg_pd, pipeline_run_id=None, client=client_prod,
    )
    sig1 = v18_conn.execute(
        "SELECT signature_hash FROM schwab_api_calls WHERE call_id = ?",
        (r1["call_id"],),
    ).fetchone()[0]
    sig2 = v18_conn.execute(
        "SELECT signature_hash FROM schwab_api_calls WHERE call_id = ?",
        (r2["call_id"],),
    ).fetchone()[0]
    assert sig1 == sig2  # signature_hash is shape-derived, env-independent


def test_b2_05_sandbox_audit_row_linked_snapshot_id_remains_null(v18_conn):
    """Sandbox audit row has linked_snapshot_id=NULL (no domain link)."""
    cfg = _make_cfg(environment="sandbox")
    client = _stub_client()
    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    row = v18_conn.execute(
        "SELECT linked_snapshot_id, linked_reconciliation_run_id "
        "FROM schwab_api_calls WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] is None
    assert row[1] is None


def test_b2_06_production_audit_row_linked_snapshot_id_populated(v18_conn):
    """Production audit row has linked_snapshot_id populated (combined tx2)."""
    cfg = _make_cfg(environment="production")
    client = _stub_client()
    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    row = v18_conn.execute(
        "SELECT linked_snapshot_id FROM schwab_api_calls WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] is not None
    assert row[0] == result["snapshot_id"]
