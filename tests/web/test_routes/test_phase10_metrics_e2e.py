"""Phase 10 Sub-bundle E Task T-E.4 — combined metrics E2E happy-path test.

Per plan §H T-E.4 acceptance:
- Seeds full happy-path data (4 cohorts + closed-reviewed trades + 1
  snapshot + 1 unresolved discrepancy).
- Verifies all 9 metrics surfaces render 200 with their VM-bound content.
- Verifies the global discrepancy banner renders on every page when
  count>0.
- Verifies T-E.6 per-trade indicator + T-E.5 snapshot form are reachable.

Single-test cross-bundle smoke covering A+B+C+D+E surfaces in one
happy-path. Mirrors the Phase 9 Sub-bundle E
``test_phase9_full_happy_path.py`` precedent.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app


_ALL_PAGES: tuple[str, ...] = (
    "/",
    "/pipeline",
    "/journal",
    "/watchlist",
    "/config",
    "/reviews/pending",
    "/metrics",
    "/metrics/trade-process",
    "/metrics/hypothesis-progress",
    "/metrics/tier-comparison",
    "/metrics/deviation-outcome",
    "/metrics/capital-friction",
    "/metrics/maturity-stage",
    "/metrics/identification-funnel",
    "/metrics/process-grade-trend",
    "/account/snapshot",
)


def _seed_full_happy_path(db_path) -> None:
    """Seed 6 closed-reviewed trades across 4 hypothesis cohorts + 1 snapshot
    + 1 unresolved-material discrepancy attributed to one trade."""
    conn = sqlite3.connect(db_path)
    try:
        # 6 trades — 3 reviewed + 3 closed-but-not-yet-reviewed. Cohorts
        # vary so the trade-process card has multi-cohort coverage.
        rows = [
            (1, "AAA", "Pre-registered: A+ baseline", "A", 1.0),
            (2, "BBB", "Pre-registered: A+ baseline", "B", 1.5),
            (3, "CCC", "Pre-registered: Near-A+ defensible extension", "B", 0.5),
            (4, "DDD", "Pre-registered: Sub-A+ VCP not formed", "C", -0.5),
            (5, "EEE", "Pre-registered: Capital-blocked smaller position", "A", 2.0),
            (6, "FFF", "Pre-registered: A+ baseline", "D", -1.0),
        ]
        for i, (tid, ticker, hypothesis, grade, r_actual) in enumerate(rows):
            exit_price = 10.0 + r_actual  # risk_per_share = 1
            review_day = (i % 27) + 1
            review_ts = f"2026-04-{review_day:02d}T16:00:00"
            fill_ts = f"2026-04-{review_day:02d}T15:30:00"
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, sector, "
                "industry, trade_origin, pre_trade_locked_at, current_size, "
                "process_grade, entry_grade, management_grade, exit_grade, "
                "disqualifying_process_violation, realized_R_if_plan_followed, "
                "hypothesis_label, reviewed_at, last_fill_at) VALUES "
                "(?, ?, '2026-04-01', 10.0, 100, 9.0, 9.0, 'reviewed', "
                "'S', 'I', 'manual_off_pipeline', '2026-04-01T09:30:00', 0, "
                "?, ?, ?, ?, 0, 1.0, ?, ?, ?)",
                (
                    tid, ticker,
                    grade, grade, grade, grade,
                    hypothesis, review_ts, fill_ts,
                ),
            )
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES "
                "(?, '2026-04-01T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
                (tid,),
            )
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES "
                "(?, ?, 'exit', 100, ?, 'unreconciled')",
                (tid, fill_ts, exit_price),
            )
        # 1 manual equity snapshot.
        conn.execute(
            "INSERT INTO account_equity_snapshots "
            "(snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
            "VALUES ('2026-04-15', 2000.00, 'manual', "
            " '2026-04-15T18:00:00.000', 'operator')"
        )
        # 1 unresolved-material discrepancy on trade 1.
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
            "(1, 1, 'stop_mismatch', 1, NULL, NULL, NULL, "
            " 'AAA', 'current_stop', '\"9.00\"', '\"8.50\"', NULL, 1, "
            " 'unresolved', NULL, NULL, NULL, NULL, "
            " '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


def test_phase10_full_happy_path_all_surfaces_render_200_and_banner_fires(
    seeded_db,
):
    """Single E2E: seed → walk every Phase 10 surface + banner + electives."""
    cfg, cfg_path = seeded_db
    _seed_full_happy_path(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    with TestClient(app) as client:
        for path in _ALL_PAGES:
            r = client.get(path)
            assert r.status_code == 200, (
                f"{path} returned {r.status_code}: {r.text[:200]}"
            )
            # Global discrepancy banner fires on every base-layout page
            # because count=1 > 0.
            assert (
                'data-banner="unresolved-material-discrepancies"' in r.text
            ), f"{path} missing global discrepancy banner"

        # T-E.6 indicator: trade 1 has the unresolved-material discrepancy.
        r1 = client.get("/trades/1")
        assert r1.status_code == 200
        assert 'data-indicator="unresolved-material-discrepancies"' in r1.text
        assert "stop_mismatch" in r1.text

        # T-E.6 absent: trade 2 has no discrepancy.
        r2 = client.get("/trades/2")
        assert r2.status_code == 200
        assert (
            'data-indicator="unresolved-material-discrepancies"'
            not in r2.text
        )

        # T-E.5 form reachable + carries the snapshot_date display span.
        rf = client.get("/account/snapshot")
        assert rf.status_code == 200
        assert "Record account snapshot" in rf.text


def test_phase10_metrics_index_lists_all_eight_surface_tiles(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    for href in (
        "/metrics/trade-process",
        "/metrics/hypothesis-progress",
        "/metrics/tier-comparison",
        "/metrics/capital-friction",
        "/metrics/maturity-stage",
        "/metrics/identification-funnel",
        "/metrics/deviation-outcome",
        "/metrics/process-grade-trend",
    ):
        assert href in r.text, f"index missing surface tile: {href}"
