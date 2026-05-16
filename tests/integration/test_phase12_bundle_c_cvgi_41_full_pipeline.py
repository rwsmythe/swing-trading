"""T-C.11 — End-to-end CVGI 41 tier-1 auto-correct through the
``run_schwab_reconciliation`` pivot + ``_step_export`` briefing emission.

Per plan §D.11 + dispatch brief §0.5 — service-composition shape,
not CLI-driven (mirrors Sub-bundle D E2E test scope LOCKED at R1 M#4
ACCEPT-WITH-RATIONALE).

Plan §D.11 step 1 calls for full pipeline subprocess invocation
(``--no-finviz-fetch``); this test invokes service composition +
``_step_export`` directly to discriminate T-C.10's wiring point
(``BriefingInputs.reconciliation_*`` counters → briefing.md
``## Reconciliation status`` section) without requiring finviz inbox
setup or subprocess plumbing. The T-C.10 SQL is the same code-path
either way; the on-disk briefing.md assertion below is the binding
discriminator for T-C.10 + T-C.9 + T-C.8 wiring as a chain.

Plants the CVGI 41 fixture; runs ``run_schwab_reconciliation`` with a
mocked Schwab orders response carrying the divergent price; then runs
``_step_export`` against the same DB; asserts:
  - fills.price updated end-to-end to the Schwab-canonical value.
  - reconciliation_corrections + trade_events + review_log + discrepancy
    state all transitioned per the spec §10.1 walkthrough.
  - ``_step_export``'s emitted briefing.md carries the
    ``## Reconciliation status`` section with the
    ``Tier-1 auto-corrected (last 7 days): 1`` literal substring.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import run_schwab_reconciliation


pytestmark = pytest.mark.slow


@dataclass
class _SchwabOrder:
    status: str
    price: float
    quantity: float
    instrument_symbol: str
    order_type: str = "MARKET"
    instruction: str = "BUY"


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


def _seed_cvgi_world(conn: sqlite3.Connection) -> dict[str, Any]:
    """Plant CVGI 41: trade + entry-fill at price=5.23 with no Schwab match
    yet."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("CVGI", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 5.23,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return {"trade_id": trade_id, "fill_id": fill_id}


def _seed_pipeline_run_running(conn: sqlite3.Connection) -> tuple[int, str]:
    """A 'running' pipeline_runs row that satisfies _step_export's
    lease.verify_held(). Mirrors
    tests/pipeline/test_runner_export_eval_scoping.py pattern."""
    token = str(uuid.uuid4())
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, trigger, data_asof_date, action_session_date,
            state, lease_token, lease_heartbeat_ts)
           VALUES ('2026-04-27T20:55:00', 'manual', '2026-04-27',
                   '2026-04-28', 'running', ?, '2026-04-27T20:55:00')""",
        (token,),
    )
    return int(cur.lastrowid), token


def _seed_empty_evaluation_run(conn: sqlite3.Connection) -> int:
    """Minimal evaluation_runs row so _step_export's candidates/recs
    SELECTs return empty without raising. ZERO candidates + ZERO recs
    is fine — the T-C.10 wiring under test reads
    reconciliation_corrections + reconciliation_discrepancies, not
    candidates/recs."""
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES ('2026-04-27T21:00:00', '2026-04-27', '2026-04-28', NULL,
                   0, 0, 0, 0, 0, 0, 'v1', 'd')""",
    )
    return int(cur.lastrowid)


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def test_phase12_bundle_c_cvgi_41_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service-composition E2E: plant + reconcile + invoke _step_export
    + assert on-disk briefing.md carries the T-C.9/T-C.10 Reconciliation
    status section with Tier-1 count = 1.

    Plan §D.11 step 1 calls for full pipeline subprocess invocation;
    this test invokes service composition + ``_step_export`` directly
    to discriminate T-C.10 wiring without finviz inbox setup. Mirrors
    Phase 11 D R1 M#4 ACCEPT-WITH-RATIONALE precedent.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        world = _seed_cvgi_world(conn)
        with conn:
            eval_run_id = _seed_empty_evaluation_run(conn)
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    # Re-open for reconciliation + assertions.
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        schwab_orders = [
            _SchwabOrder(
                status="FILLED", price=5.30, quantity=100.0,
                instrument_symbol="CVGI",
            ),
        ]
        schwab_account = _SchwabAccount(
            net_liquidating_value=2000.0, positions=[],
        )
        run = run_schwab_reconciliation(
            conn,
            account_hash="<acct>",
            period_start="2026-04-27",
            period_end="2026-04-27",
            schwab_orders=schwab_orders,
            schwab_transactions=[],
            schwab_account=schwab_account,
        )
        # 1. Discrepancy emitted + auto-corrected.
        d = conn.execute(
            "SELECT resolution, discrepancy_id FROM reconciliation_discrepancies "
            "WHERE run_id = ? AND discrepancy_type = 'entry_price_mismatch'",
            (run.run_id,),
        ).fetchone()
        assert d[0] == "auto_corrected_from_schwab"
        discrepancy_id = d[1]
        # 2. fills.price updated.
        fp = conn.execute(
            "SELECT price FROM fills WHERE fill_id = ?",
            (world["fill_id"],),
        ).fetchone()
        assert fp[0] == 5.30
        # 3. reconciliation_corrections row written.
        rc = conn.execute(
            "SELECT correction_action, applied_value_json, applied_by "
            "FROM reconciliation_corrections "
            "WHERE discrepancy_id = ?",
            (discrepancy_id,),
        ).fetchone()
        assert rc[0] == "auto_applied"
        assert json.loads(rc[1]) == {"price": 5.30}
        assert rc[2] == "auto"
        # 4. trade_events emitted.
        te = conn.execute(
            "SELECT event_type FROM trade_events "
            "WHERE trade_id = ? ORDER BY id DESC LIMIT 1",
            (world["trade_id"],),
        ).fetchone()
        assert te[0] == "reconciliation_auto_correct"
        # 5. fills.reconciliation_status flipped.
        rs = conn.execute(
            "SELECT reconciliation_status FROM fills WHERE fill_id = ?",
            (world["fill_id"],),
        ).fetchone()
        assert rs[0] == "reconciled_discrepancy_resolved"
        # 6. summary_json carries pivot counters.
        summary = json.loads(run.summary_json)
        assert summary["tier1_applied_count"] == 1
        assert summary["tier2_pending_count"] == 0
    finally:
        conn.close()

    # 7. Invoke _step_export. This exercises T-C.10's BriefingInputs.
    # reconciliation_* wiring + emits briefing.md to the staging→target
    # path discipline. Stub the chart side-effect path; we only assert
    # on the on-disk briefing.md content.
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    action_session = _date(2026, 4, 28)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id,
        action_session=action_session,
        data_asof="2026-04-27",
        chart_paths={},
        fetcher=None,
    )

    # 8. Assert briefing.md was written + carries T-C.10 wiring.
    target_dir = cfg.paths.exports_dir / action_session.isoformat()
    md_path = target_dir / "briefing.md"
    assert md_path.exists(), (
        f"_step_export did not emit briefing.md at {md_path}"
    )
    md = md_path.read_text(encoding="utf-8")
    assert "## Reconciliation status" in md, (
        "briefing.md missing T-C.9 Reconciliation status section "
        "(T-C.8 + T-C.9 + T-C.10 wiring chain)"
    )
    assert "Tier-1 auto-corrected (last 7 days): 1" in md, (
        "briefing.md does NOT carry T-C.10 tier1_recent_count=1 "
        "rendered substring — T-C.10 BriefingInputs.reconciliation_* "
        "wiring or T-C.9 render is broken"
    )
    assert "Tier-2 pending operator review: 0" in md, (
        "briefing.md does NOT carry T-C.10 pending_count=0 rendered "
        "substring"
    )
