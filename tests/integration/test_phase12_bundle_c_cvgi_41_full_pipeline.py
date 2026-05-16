"""T-C.11 — End-to-end CVGI 41 tier-1 auto-correct through the
``run_schwab_reconciliation`` pivot + briefing-render service composition.

Per plan §D.11 + dispatch brief §0.5 — service-composition shape,
not CLI-driven (mirrors Sub-bundle D E2E test scope LOCKED at R1 M#4
ACCEPT-WITH-RATIONALE).

Plants the CVGI 41 fixture; runs ``run_schwab_reconciliation`` with a
mocked Schwab orders response carrying the divergent price; asserts:
  - fills.price updated end-to-end to the Schwab-canonical value.
  - reconciliation_corrections + trade_events + review_log + discrepancy
    state all transitioned per the spec §10.1 walkthrough.
  - The briefing.md ``Reconciliation status`` section emits with the
    Tier-1 auto-corrected count >= 1.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.briefing_md import render_briefing_md
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


def test_phase12_bundle_c_cvgi_41_end_to_end(tmp_path: Path) -> None:
    """Service-composition E2E: plant + reconcile + render briefing.md."""
    db_path = tmp_path / "test.db"
    conn = ensure_schema(db_path)
    try:
        world = _seed_cvgi_world(conn)
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
        # 7. Briefing.md renders the Reconciliation status section (we
        # exercise the T-C.10 counter-read SQL directly to keep this
        # test free of the pipeline-orchestrator lease/staging setup).
        from datetime import timedelta as _td
        cutoff_iso = (
            datetime.utcnow().replace(microsecond=0) - _td(days=7)
        ).isoformat(timespec="seconds")
        pending = int(conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE resolution = 'pending_ambiguity_resolution' "
            "AND material_to_review = 1"
        ).fetchone()[0])
        tier1_recent = int(conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections "
            "WHERE correction_action = 'auto_applied' "
            "AND applied_at >= ?",
            (cutoff_iso,),
        ).fetchone()[0])
        assert pending == 0
        assert tier1_recent == 1
    finally:
        conn.close()

    # 8. Construct a minimal BriefingInputs + render briefing.md.
    inputs = BriefingInputs(
        action_session_date="2026-05-16",
        data_asof_date="2026-05-15",
        generated_at="2026-05-16T08:00:00",
        weather=None,
        weather_is_stale=True,
        equity=2000.0,
        open_count=1,
        soft_warn=4,
        hard_cap=6,
        last_pipeline_ts="never",
        pipeline_is_stale=True,
        current_session_match=False,
        recommendations=[],
        open_trades=[],
        reconciliation_pending_count=pending,
        reconciliation_tier1_recent_count=tier1_recent,
    )
    vm = build_briefing_view_model(inputs)
    md = render_briefing_md(vm)
    assert "## Reconciliation status" in md
    assert "Tier-1 auto-corrected (last 7 days): 1" in md
    assert "Tier-2 pending operator review: 0" in md
