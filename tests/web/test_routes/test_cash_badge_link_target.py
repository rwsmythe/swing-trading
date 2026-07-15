"""Gate-run #100 witness fix — the cash-coherence badge's link target.

The operator's browser witness hit a 404: the badge hardcoded href="/reconcile",
a route that has never existed (only per-discrepancy resolve routes are
registered). The link-target-must-exist gotcha: the original badge test
asserted the VM flag, never the destination. These tests close it end-to-end.
"""
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.view_models.dashboard import _first_pending_cash_resolve_link_path


def _seed_pending_cash(cfg) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO reconciliation_runs (source, state, started_ts, "
                "finished_ts, period_start, period_end) VALUES ('schwab_api', "
                "'completed', '1', '2', '2026-05-01', '2026-05-31')")
            run_id = int(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO reconciliation_discrepancies (run_id, "
                "discrepancy_type, field_name, material_to_review, created_at, "
                "resolution, ambiguity_kind, expected_value_json, "
                "actual_value_json) VALUES (?, 'cash_movement_mismatch', "
                "'missing_journal_row', 1, '1', 'pending_ambiguity_resolution', "
                "'schwab_returned_no_match', "
                "'{\"transactionId\": \"T-LINK\", \"net_amount\": 100.0, "
                "\"date\": \"2026-05-28\", \"type\": \"ACH_RECEIPT\", "
                "\"description\": \"ACH deposit\", \"flag_reason\": "
                "\"no_journal_match_in_window\"}', "
                "'{\"matched\": null}')", (run_id,))
            disc_id = int(cur.lastrowid)
    finally:
        conn.close()
    return disc_id


def test_badge_link_target_renders_200_for_a_pending_cash_row(seeded_db):
    """The path the badge links to must be a real, rendering route — followed
    with a live GET (not just header-asserted), per the gotcha's prescription."""
    cfg, cfg_path = seeded_db
    disc_id = _seed_pending_cash(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        path = _first_pending_cash_resolve_link_path(conn)
    finally:
        conn.close()
    assert path == f"/reconcile/discrepancy/{disc_id}/resolve"
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get(path)
        assert resp.status_code == 200, resp.text[:300]


def _seed_equity_delta_only(cfg) -> None:
    """Seed a completed schwab_api run with an unresolved equity_delta and NO
    pending cash row -- the badge's clause-2 lit state (Arc 20-C D24)."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO reconciliation_runs (source, state, started_ts, "
                "finished_ts, period_start, period_end, equity_delta_dollars) "
                "VALUES ('schwab_api', 'completed', '1', '2', '2026-05-01', "
                "'2026-05-31', -12.34)")
            run_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO reconciliation_discrepancies (run_id, "
                "discrepancy_type, field_name, material_to_review, created_at, "
                "resolution, expected_value_json, actual_value_json) VALUES (?, "
                "'equity_delta', 'net_liquidating_value', 1, '1', 'unresolved', "
                "'{\"basis\": \"ledger\", \"equity_dollars\": 1000.0}', "
                "'{\"basis\": \"net_liq\", \"equity_dollars\": 1012.34}')",
                (run_id,))
    finally:
        conn.close()


def test_badge_link_target_renders_200_for_equity_delta_lit_state(seeded_db):
    """Arc 20-C (D24): the equity_delta-lit badge links to the diagnostic view
    -- a real, rendering route (the link-target-must-exist gotcha), NOT the old
    dead <span>. Followed with a live GET, not just a path assertion."""
    cfg, cfg_path = seeded_db
    _seed_equity_delta_only(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        path = _first_pending_cash_resolve_link_path(conn)
    finally:
        conn.close()
    assert path == "/reconcile/equity-delta"
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get(path)
        assert resp.status_code == 200, resp.text[:300]


def test_bare_reconcile_path_is_not_a_registered_route(seeded_db):
    """Documents the 404 the operator hit: any hardcoded /reconcile href is a
    bug — the badge must thread the per-discrepancy path from the VM."""
    cfg, cfg_path = seeded_db
    with TestClient(create_app(cfg, cfg_path)) as client:
        assert client.get("/reconcile").status_code == 404


def test_lock_error_predicate_distinguishes_contention_from_sql_defects():
    """Gate-run #100: 'no such column: net_amount' was mislabeled as
    'Database is busy' by the broad OperationalError catches. Only genuine
    contention may render the retry page; defects must surface as 500s."""
    import sqlite3 as s
    from swing.web.routes.reconcile import _is_transient_lock_error
    assert _is_transient_lock_error(s.OperationalError("database is locked"))
    assert _is_transient_lock_error(s.OperationalError("database is busy"))
    assert _is_transient_lock_error(
        s.OperationalError("unable to open database file"))
    assert not _is_transient_lock_error(
        s.OperationalError("no such column: net_amount"))
    assert not _is_transient_lock_error(s.OperationalError("syntax error"))
