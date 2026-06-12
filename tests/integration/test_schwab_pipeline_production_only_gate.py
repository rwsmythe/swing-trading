"""Phase 11 T-B.7 — Production-only domain writes integration test.

Per plan §K T-B.7 + spec §3.6.3. Cassette-driven integration test
mirroring Phase 9 Sub-bundle E E2E pattern (`tests/integration/
test_phase9_full_happy_path.py`). Exercises the full
_step_schwab_snapshot + _step_schwab_orders pipeline-step flow under
BOTH `environment='production'` AND `environment='sandbox'`; asserts:

  - Production produces domain rows (account_equity_snapshots +
    reconciliation_runs).
  - Sandbox produces audit rows ONLY + ZERO domain rows.
  - Same cassette under both envs yields IDENTICAL signature_hash on
    the schwab_api_calls audit rows (drift-detection is env-independent).
  - Lease status (audit-row status='success') transitions correctly.

T-B.0.b §4 deferred live-cassette recording to phase 2; this test uses
synthetic fixtures as the binding test surface until phase 2 lands.
"""
from __future__ import annotations

import logging
import sqlite3
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
        # Arc 4b Task 8: ledger-vs-NLV coherence reads cfg.account.starting_equity.
        account=SimpleNamespace(starting_equity=0.0),
    )


def _stub_client(nlv: float = 2014.36):
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

    list_resp = MagicMock()
    list_resp.json.return_value = []
    list_resp.status_code = 200
    list_resp.headers = {}
    client.account_orders.return_value = list_resp
    client.transactions.return_value = list_resp
    return client


def _new_db(tmp_path: Path, name: str) -> sqlite3.Connection:
    return ensure_schema(tmp_path / name)


# ============================================================================
# T-B.7 — 4 tests
# ============================================================================


def test_b7_01_production_produces_domain_rows(tmp_path):
    """Full snapshot+orders flow under production: domain rows present."""
    conn = _new_db(tmp_path, "schwab-prod.db")
    cfg = _make_cfg(environment="production")

    # Snapshot.
    r1 = _step_schwab_snapshot(conn, cfg, pipeline_run_id=None, client=_stub_client())
    assert r1["status"] == "completed"
    # Orders.
    r2 = _step_schwab_orders(conn, cfg, pipeline_run_id=None, client=_stub_client())
    assert r2["status"] == "completed"

    snap_cnt = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots WHERE source = 'schwab_api'"
    ).fetchone()[0]
    recon_cnt = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs WHERE source = 'schwab_api'"
    ).fetchone()[0]
    audit_cnt = conn.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0]
    assert snap_cnt == 1
    assert recon_cnt == 1
    # 1 audit for snapshot + 3 for orders = 4 total.
    assert audit_cnt == 4


def test_b7_02_sandbox_produces_audit_only_zero_domain_rows(tmp_path):
    """Full flow under sandbox: ZERO domain rows + audit rows present."""
    conn = _new_db(tmp_path, "schwab-sandbox.db")
    cfg = _make_cfg(environment="sandbox")

    r1 = _step_schwab_snapshot(conn, cfg, pipeline_run_id=None, client=_stub_client())
    assert r1["status"] == "sandbox_audit_only"
    r2 = _step_schwab_orders(conn, cfg, pipeline_run_id=None, client=_stub_client())
    assert r2["status"] == "sandbox_audit_only"

    snap_cnt = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots WHERE source = 'schwab_api'"
    ).fetchone()[0]
    recon_cnt = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs WHERE source = 'schwab_api'"
    ).fetchone()[0]
    audit_cnt = conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls WHERE environment = 'sandbox'"
    ).fetchone()[0]
    assert snap_cnt == 0
    assert recon_cnt == 0
    assert audit_cnt == 4  # 1 snapshot + 3 orders


def test_b7_03_signature_hash_env_independent_across_runs(tmp_path):
    """Same cassette under sandbox + production: identical signature_hash
    on the audit rows. Drift-detection is shape-derived, NOT env-derived.
    """
    sb_conn = _new_db(tmp_path, "schwab-sig-sb.db")
    pd_conn = _new_db(tmp_path, "schwab-sig-pd.db")
    _step_schwab_snapshot(
        sb_conn, _make_cfg(environment="sandbox"),
        pipeline_run_id=None, client=_stub_client(),
    )
    _step_schwab_snapshot(
        pd_conn, _make_cfg(environment="production"),
        pipeline_run_id=None, client=_stub_client(),
    )
    sb_sig = sb_conn.execute(
        "SELECT signature_hash FROM schwab_api_calls "
        "WHERE endpoint = 'accounts.details' ORDER BY call_id DESC LIMIT 1"
    ).fetchone()[0]
    pd_sig = pd_conn.execute(
        "SELECT signature_hash FROM schwab_api_calls "
        "WHERE endpoint = 'accounts.details' ORDER BY call_id DESC LIMIT 1"
    ).fetchone()[0]
    assert sb_sig is not None
    assert pd_sig is not None
    assert sb_sig == pd_sig


def test_b7_04_audit_lifecycle_success_transition_both_envs(tmp_path):
    """Audit row status transitions in_flight → success in BOTH envs."""
    for env in ("sandbox", "production"):
        conn = _new_db(tmp_path, f"schwab-lifecycle-{env}.db")
        result = _step_schwab_snapshot(
            conn, _make_cfg(environment=env),
            pipeline_run_id=None, client=_stub_client(),
        )
        # Final state is success (NOT in_flight — UPDATE fired).
        row = conn.execute(
            "SELECT status FROM schwab_api_calls WHERE call_id = ?",
            (result["call_id"],),
        ).fetchone()
        assert row[0] == "success", f"env={env}: status={row[0]}"
