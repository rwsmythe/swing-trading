"""22-F T-A5 web half (A5-e) -- a CONTROL, by the plan's READ.

READ of `POST /reconcile/discrepancy/{id}/resolve` (`swing/web/routes/
reconcile.py`, the step-5 service call's handler chain): neither
`ReservedJournalFieldError` nor `MultiRowCorrectionOverrideError` derives from
`ValueError`, so neither reaches the `except ValueError` 400 re-render; BOTH
are caught by the route's defense-in-depth `except Exception` clause
(`reconcile.py:1753`), which logs the class name and renders the
`service_error` fragment at 500. The type never reaches the app-wide handler,
so the web half is NOT in the escape set (census C1-05) and gets no fix here.

This test pins that clause as the catcher, on BOTH trees: the planted
reserved-field refusal is asserted to be the exception it logged (the class
name in the WARNING record), so the control cannot pass on some other
failure.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app
from tests.web.test_routes.test_22a4_corrector_refusal_delivery import _seed


def test_A5e_control_web_resolve_reserved_field_caught_by_defense_clause(
    seeded_db: tuple[Config, Path], caplog,
) -> None:
    cfg, cfg_path = seeded_db
    trade_id, disc_id = _seed(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with caplog.at_level(logging.WARNING, logger="swing.web.routes.reconcile"):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "operator_truth",
                    "custom_value": '{"entry_date": "2026-04-28"}',
                    "resolution_reason": "broker says a different entry date",
                    "ambiguity_kind_at_render": "unsupported",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 500, (r.status_code, r.text[:400])
    assert 'data-error-kind="service_error"' in r.text
    assert any(rec.getMessage() == "ReservedJournalFieldError"
               for rec in caplog.records
               if rec.name == "swing.web.routes.reconcile"), [
        (rec.name, rec.getMessage()) for rec in caplog.records]
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        assert conn.execute(
            "SELECT entry_date FROM trades WHERE id = ?", (trade_id,),
        ).fetchone()[0] == "2026-04-27"
        assert conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections",
        ).fetchone()[0] == 0
    finally:
        conn.close()
