"""Arc 20-C (D23) — the durable out-of-framework path on the untracked-position
resolve page.

The ``untracked_broker_position`` resolve page offered ONLY the one-shot
acknowledge; the durable fix (declare the ticker out-of-framework so it stops
re-emitting) was invisible (RKLB re-emitted 7x before the config path was
found). This adds a "recurring holding?" GUIDANCE block ABOVE the acknowledge:
the exact config stanza (ticker pre-filled), the exact
``swing schwab resolve-out-of-framework`` command, and when to choose it vs
journaling vs one-shot acknowledging.

V1 = GUIDANCE ONLY (no config write-path). The acknowledge flow is UNTOUCHED.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app


def _seed_orphan(db_path: Path, *, ticker: str = "RKLB") -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES ('schwab_api', '2026-07-01T12:00:00', 'completed')",
        )
        run_id = int(rcur.lastrowid)
        dcur = conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, trade_id, fill_id, cash_movement_id, ticker, "
            "field_name, expected_value_json, actual_value_json, delta_text, "
            "material_to_review, resolution, created_at) VALUES (?, "
            "'untracked_broker_position', NULL, NULL, NULL, ?, "
            "'broker_position', '{\"journal_qty\": 0}', "
            "'{\"market_value\": 411.9, \"qty\": 2.0}', ?, 1, 'unresolved', "
            "'2026-07-01T12:00:00')",
            (run_id, ticker,
             f"{ticker}: +2.00 sh @ $+411.90 held at broker, not in journal"),
        )
        disc_id = int(dcur.lastrowid)
        conn.commit()
        return disc_id
    finally:
        conn.close()


def test_orphan_page_surfaces_oof_guidance_with_ticker_interpolated(
    seeded_db: tuple[Config, Path],
):
    cfg, cfg_path = seeded_db
    did = _seed_orphan(cfg.paths.db_path, ticker="RKLB")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    body = r.text
    # The durable-path guidance block is present.
    assert 'data-oof-guidance="true"' in body
    # The exact config stanza, ticker pre-filled.
    assert "[reconciliation]" in body
    assert "out_of_framework_tickers" in body
    assert '"RKLB"' in body
    # The exact resolve command.
    assert "swing schwab resolve-out-of-framework" in body
    # The acknowledge form is UNTOUCHED (still present).
    assert 'data-orphan-acknowledge-form="true"' in body


def test_orphan_oof_guidance_appears_above_acknowledge_form(
    seeded_db: tuple[Config, Path],
):
    """The durable path must be surfaced ABOVE the one-shot acknowledge (so the
    operator sees the recurring-holding option first)."""
    cfg, cfg_path = seeded_db
    did = _seed_orphan(cfg.paths.db_path, ticker="RKLB")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    body = r.text
    assert body.index('data-oof-guidance="true"') < body.index(
        'data-orphan-acknowledge-form="true"'
    )
