"""Phase 10 Sub-bundle E Task T-E.6 — trade detail discrepancy indicator tests.

Per electives amendment §2 Task E.6 acceptance:
- (a) Trade with 0 discrepancies → no indicator section.
- (b) Trade with 1 unresolved material → indicator renders with type/
  field/expected/actual.
- (c) Trade with 1 RESOLVED material → no indicator (resolution clears).
- (d) Trade with 1 NON-material discrepancy → no indicator (material=0).
- Orphan-emit discrepancies (trade_id IS NULL) are EXCLUDED by
  ``list_unresolved_material_for_trade``.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _seed_closed_trade(db_path, *, trade_id: int = 1, ticker: str = "AAA") -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size, "
            "premortem_technical) "
            "VALUES (?, ?, '2026-04-01', 10.0, 100, 9.0, 9.0, 'closed', "
            "'S', 'I', 'manual_off_pipeline', '2026-04-01T09:30:00', 0, "
            "'tech risk')",
            (trade_id, ticker),
        )
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES "
            "(?, '2026-04-01T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
            (trade_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_reconciliation_run(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO reconciliation_runs "
            "(run_id, period_start, period_end, started_ts, finished_ts, "
            " state, source, source_artifact_path, source_artifact_sha256) "
            "VALUES (1, '2026-04-01', '2026-04-08', "
            "'2026-04-08T16:00:00.000', '2026-04-08T16:00:01.000', "
            "'completed', 'system_audit', 'gate-test', 'gate-test-sha')"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_discrepancy(
    db_path,
    *,
    discrepancy_id: int,
    trade_id: int | None,
    material: int = 1,
    resolution: str = "unresolved",
    discrepancy_type: str = "stop_mismatch",
    field_name: str = "current_stop",
    expected_json: str = '"9.00"',
    actual_json: str = '"8.50"',
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        resolved_at = "'2026-04-09T10:00:00'" if resolution != "unresolved" else "NULL"
        resolved_by = "'operator'" if resolution != "unresolved" else "NULL"
        reason = "'gate-test'" if resolution != "unresolved" else "NULL"
        trade_id_sql = "NULL" if trade_id is None else str(trade_id)
        conn.execute(
            f"INSERT INTO reconciliation_discrepancies "
            f"(discrepancy_id, run_id, discrepancy_type, trade_id, fill_id, "
            f" cash_movement_id, linked_daily_management_record_id, "
            f" ticker, field_name, expected_value_json, actual_value_json, "
            f" delta_text, material_to_review, resolution, "
            f" resolution_reason, resolved_at, resolved_by, "
            f" mistake_tag_assigned, created_at) VALUES "
            f"({discrepancy_id}, 1, ?, {trade_id_sql}, NULL, NULL, NULL, "
            f" 'AAA', ?, ?, ?, NULL, {material}, ?, "
            f" {reason}, {resolved_at}, {resolved_by}, NULL, "
            f" '2026-04-08T16:00:00.000')",
            (discrepancy_type, field_name, expected_json, actual_json, resolution),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4 acceptance branches per electives amendment §2 Task E.6
# ---------------------------------------------------------------------------

def test_trade_detail_no_indicator_when_zero_discrepancies(seeded_db):
    """(a) Trade with 0 discrepancies → no indicator section."""
    cfg, cfg_path = seeded_db
    _seed_closed_trade(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200
    assert 'data-indicator="unresolved-material-discrepancies"' not in r.text


def test_trade_detail_renders_indicator_for_unresolved_material(seeded_db):
    """(b) Trade with 1 unresolved material → indicator renders with
    type/field/expected/actual.
    """
    cfg, cfg_path = seeded_db
    _seed_closed_trade(cfg.paths.db_path)
    _seed_reconciliation_run(cfg.paths.db_path)
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=1, trade_id=1, material=1, resolution="unresolved",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200
    assert 'data-indicator="unresolved-material-discrepancies"' in r.text
    assert 'data-count="1"' in r.text
    assert "stop_mismatch" in r.text
    assert "current_stop" in r.text


def test_trade_detail_no_indicator_when_resolved(seeded_db):
    """(c) Trade with 1 RESOLVED material → no indicator (resolution
    NOT NULL clears it).
    """
    cfg, cfg_path = seeded_db
    _seed_closed_trade(cfg.paths.db_path)
    _seed_reconciliation_run(cfg.paths.db_path)
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=1, trade_id=1, material=1,
        resolution="acknowledged_immaterial",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200
    assert 'data-indicator="unresolved-material-discrepancies"' not in r.text


def test_trade_detail_no_indicator_when_non_material(seeded_db):
    """(d) Trade with 1 NON-material discrepancy → no indicator
    (material_to_review=0 clears).
    """
    cfg, cfg_path = seeded_db
    _seed_closed_trade(cfg.paths.db_path)
    _seed_reconciliation_run(cfg.paths.db_path)
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=1, trade_id=1, material=0, resolution="unresolved",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200
    assert 'data-indicator="unresolved-material-discrepancies"' not in r.text


# ---------------------------------------------------------------------------
# Orphan-discrepancy exclusion
# ---------------------------------------------------------------------------

def test_trade_detail_excludes_orphan_discrepancies(seeded_db):
    """Orphan-emit discrepancies (trade_id IS NULL) MUST NOT appear in the
    per-trade indicator — the helper's ``WHERE trade_id = ?`` predicate
    filters them out. Sum of per-trade indicator counts ≤ global banner
    count when orphans exist (electives amendment §2 watch item +
    return-report §7 V2 candidate).
    """
    cfg, cfg_path = seeded_db
    _seed_closed_trade(cfg.paths.db_path)
    _seed_reconciliation_run(cfg.paths.db_path)
    # Orphan discrepancy — no trade attribution.
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=1, trade_id=None, material=1, resolution="unresolved",
        discrepancy_type="sector_tamper",
        field_name="sector",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200
    # The per-trade indicator stays HIDDEN because the orphan has no
    # trade_id attribution.
    assert 'data-indicator="unresolved-material-discrepancies"' not in r.text


# ---------------------------------------------------------------------------
# Helper directness
# ---------------------------------------------------------------------------

def test_helper_filters_by_trade_id_and_unresolved_material(seeded_db):
    """Unit-level: ``list_unresolved_material_for_trade(conn, trade_id)``
    filters by trade_id AND material=1 AND resolution='unresolved'.
    """
    cfg, _ = seeded_db
    from swing.metrics.discrepancies import list_unresolved_material_for_trade
    _seed_closed_trade(cfg.paths.db_path, trade_id=1, ticker="AAA")
    _seed_closed_trade(cfg.paths.db_path, trade_id=2, ticker="BBB")
    _seed_reconciliation_run(cfg.paths.db_path)
    # trade 1: unresolved material — should match
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=1, trade_id=1, material=1, resolution="unresolved",
    )
    # trade 2: resolved — should NOT match
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=2, trade_id=2, material=1,
        resolution="acknowledged_immaterial",
    )
    # orphan: unresolved material but no trade_id — should NOT match
    _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_id=3, trade_id=None, material=1, resolution="unresolved",
        discrepancy_type="sector_tamper", field_name="sector",
    )
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        out_trade1 = list_unresolved_material_for_trade(conn, 1)
        out_trade2 = list_unresolved_material_for_trade(conn, 2)
    finally:
        conn.close()
    assert len(out_trade1) == 1
    assert out_trade1[0].discrepancy_id == 1
    assert out_trade2 == []


def test_discrepancy_display_post_init_rejects_invalid_inputs():
    import pytest

    from swing.web.view_models.trades import DiscrepancyDisplay

    with pytest.raises(ValueError, match="discrepancy_id must be > 0"):
        DiscrepancyDisplay(
            discrepancy_id=0, type="stop_mismatch", field_name="current_stop",
            expected="9.00", actual="8.50", period_end="2026-04-08",
        )
    with pytest.raises(ValueError, match="type must be non-empty"):
        DiscrepancyDisplay(
            discrepancy_id=1, type="", field_name="current_stop",
            expected="9.00", actual="8.50", period_end="2026-04-08",
        )
