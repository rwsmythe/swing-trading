"""22-A4 Task 1b -- (m8c) WEB half: DELIVERY through the UNCHANGED caller.

`POST /reconcile/discrepancy/{id}/resolve` maps a service `ValueError` to a
400 re-render with the message in the error band and the operator's submission
preserved (`swing/web/routes/reconcile.py`, the `except ValueError` clause ->
`_render_form_with_error`, which returns `status_code=400`).

**Pre-fix:** the refusal is `sqlite3.IntegrityError` from
`trg_trades_attempt_id_immutable`, which falls through to the route's blanket
`except Exception` -> **500**. A refusal deriving from a bare `Exception`
lands in exactly the same place. The assertion is the EXACT status, not merely
"not 204": a weak delivery row would pass on any non-success result and would
certify nothing about legibility.

NO PRODUCTION CALLER WAS EDITED for this row -- that is the point of it.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app

MINTED_TOKEN = "11111111-2222-4333-8444-555555555555"
OTHER_TOKEN = "99999999-8888-4777-8666-555555555555"


def _seed(db_path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        trade_id = int(conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at, attempt_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("CVGI", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
             "manual_off_pipeline", "2026-04-27T16:00:00", MINTED_TOKEN),
        ).lastrowid)
        run_id = int(conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES (?,?,?)",
            ("schwab_api", "2026-09-07T12:00:00", "running"),
        ).lastrowid)
        disc_id = int(conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, trade_id, fill_id, ticker, field_name, "
            "expected_value_json, actual_value_json, material_to_review, "
            "resolution, ambiguity_kind, resolution_reason, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "stop_mismatch", trade_id, None, "CVGI", "current_stop",
             '{"current_stop": 4.0}', '{"current_stop": 4.5}', 1,
             "pending_ambiguity_resolution", "unsupported",
             "classifier did not recognize the shape", "2026-09-07T12:00:00"),
        ).lastrowid)
        conn.commit()
        return trade_id, disc_id
    finally:
        conn.close()


def test_m8c_web_refusal_is_status_400_through_the_unchanged_route(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    trade_id, disc_id = _seed(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "operator_truth",
                "custom_value": '{"attempt_id": "' + OTHER_TOKEN + '"}',
                "resolution_reason": "broker named a different attempt token",
                "ambiguity_kind_at_render": "unsupported",
            },
            headers={"HX-Request": "true"},
        )

    assert r.status_code == 400, (r.status_code, r.text[:400])
    assert "WRITE-ONCE" in r.text
    # The operator's submission is preserved in the re-rendered form.
    assert OTHER_TOKEN in r.text

    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?", (trade_id,),
        ).fetchone()[0] == MINTED_TOKEN
        assert conn.execute(
            "SELECT resolution FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?", (disc_id,),
        ).fetchone()[0] == "pending_ambiguity_resolution"
        assert conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections",
        ).fetchone()[0] == 0
    finally:
        conn.close()
