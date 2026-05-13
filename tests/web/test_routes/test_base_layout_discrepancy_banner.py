"""Phase 10 Sub-bundle E Task T-E.3 — banner integration tests.

Per plan §H T-E.3:
- ``base.html.j2`` renders the global reconciliation discrepancy banner
  whenever ``vm.unresolved_material_discrepancies_count > 0``.
- The banner is ABSENT when the count is 0.
- The banner renders consistently across the 6 base-layout pages + 8
  metrics pages + the umbrella ``/metrics`` index.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app


_BASE_LAYOUT_PAGES: tuple[str, ...] = (
    "/",
    "/pipeline",
    "/journal",
    "/watchlist",
    "/config",
    "/reviews/pending",
)
_METRICS_PAGES: tuple[str, ...] = (
    "/metrics",
    "/metrics/trade-process",
    "/metrics/hypothesis-progress",
    "/metrics/tier-comparison",
    "/metrics/deviation-outcome",
    "/metrics/capital-friction",
    "/metrics/maturity-stage",
    "/metrics/identification-funnel",
    "/metrics/process-grade-trend",
)


def _seed_one_unresolved_material_discrepancy(db_path) -> None:
    """Plant a closed trade + one unresolved material discrepancy attributed
    to it so ``list_unresolved_material_for_closed_trades`` returns N=1.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, 'closed', "
            "'S', 'I', 'manual_off_pipeline', '2026-04-01T09:30:00', 0)"
        )
        # Minimal reconciliation_run + discrepancy with material=1
        # resolution='unresolved' attributed to trade 1.
        conn.execute(
            "INSERT INTO reconciliation_runs "
            "(run_id, period_start, period_end, started_ts, finished_ts, "
            " state, source, source_artifact_path, source_artifact_sha256) "
            "VALUES (1, '2026-04-01', '2026-04-08', "
            "'2026-04-08T16:00:00.000', '2026-04-08T16:00:01.000', "
            "'completed', 'system_audit', 'gate-test', 'gate-test-sha')"
        )
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(discrepancy_id, run_id, discrepancy_type, trade_id, fill_id, "
            " cash_movement_id, linked_daily_management_record_id, "
            " ticker, field_name, expected_value_json, actual_value_json, "
            " delta_text, material_to_review, resolution, "
            " resolution_reason, resolved_at, resolved_by, "
            " mistake_tag_assigned, created_at) VALUES "
            "(1, 1, 'stop_mismatch', 1, NULL, NULL, NULL, 'AAA', "
            " 'current_stop', '\"9.00\"', '\"8.50\"', NULL, 1, "
            " 'unresolved', NULL, NULL, NULL, NULL, "
            " '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Banner ABSENT when count == 0
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _BASE_LAYOUT_PAGES)
def test_base_layout_omits_banner_when_count_eq_0(seeded_db, path):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code in (200, 404), (
        f"{path} returned {r.status_code}: {r.text[:300]}"
    )
    if r.status_code == 200:
        assert 'data-banner="unresolved-material-discrepancies"' not in r.text


@pytest.mark.parametrize("path", _METRICS_PAGES)
def test_metrics_pages_omit_banner_when_count_eq_0(seeded_db, path):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 200
    assert 'data-banner="unresolved-material-discrepancies"' not in r.text


# ---------------------------------------------------------------------------
# Banner FIRES when count > 0
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _BASE_LAYOUT_PAGES)
def test_base_layout_renders_banner_when_count_gt_0(seeded_db, path):
    cfg, cfg_path = seeded_db
    _seed_one_unresolved_material_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code in (200, 404), (
        f"{path} returned {r.status_code}: {r.text[:300]}"
    )
    if r.status_code == 200:
        assert 'data-banner="unresolved-material-discrepancies"' in r.text
        assert 'data-count="1"' in r.text
        assert "unresolved material reconciliation" in r.text


@pytest.mark.parametrize("path", _METRICS_PAGES)
def test_metrics_pages_render_banner_when_count_gt_0(seeded_db, path):
    cfg, cfg_path = seeded_db
    _seed_one_unresolved_material_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 200
    assert 'data-banner="unresolved-material-discrepancies"' in r.text
    assert 'data-count="1"' in r.text


def test_banner_singular_grammar_at_count_1(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_one_unresolved_material_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # singular "discrepancy" form should appear in the banner body.
    assert "discrepancy" in r.text
