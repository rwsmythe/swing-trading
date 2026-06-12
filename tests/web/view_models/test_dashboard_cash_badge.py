"""Arc 4b Task 9 — the §6.2 cash-coherence badge predicate."""
from swing.data.db import ensure_schema
from swing.web.view_models.dashboard import _compute_cash_coherence_badge


def _seed_run(conn, *, state="completed", finished_ts="2"):
    cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, state, started_ts, finished_ts, "
        "period_start, period_end) VALUES ('schwab_api', ?, '1', ?, "
        "'2026-05-01', '2026-05-31')", (state, finished_ts))
    return int(cur.lastrowid)


def test_badge_lights_on_pending_source_direction_row(tmp_path):
    conn = ensure_schema(tmp_path / "b.db")
    run_id = _seed_run(conn)
    # A source-direction pending (all FK NULL) — the trade-joined banner would
    # miss it; the direct-count badge must light.
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "field_name, material_to_review, created_at, resolution, ambiguity_kind, "
        "expected_value_json, actual_value_json) VALUES (?, "
        "'cash_movement_mismatch', 'missing_journal_row', 1, '1', "
        "'pending_ambiguity_resolution', 'schwab_returned_no_match', "
        "'{\"transactionId\": \"T9\"}', '{\"matched\": null}')", (run_id,))
    conn.commit()
    assert _compute_cash_coherence_badge(conn) is True


def test_badge_lights_on_unresolved_equity_delta_latest_run(tmp_path):
    conn = ensure_schema(tmp_path / "b.db")
    run_id = _seed_run(conn)
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "field_name, material_to_review, created_at, resolution) VALUES (?, "
        "'equity_delta', 'net_liquidating_value', 1, '1', 'unresolved')", (run_id,))
    conn.commit()
    assert _compute_cash_coherence_badge(conn) is True


def test_badge_dark_when_no_pendings_and_no_unresolved_equity_delta(tmp_path):
    conn = ensure_schema(tmp_path / "b.db")
    _seed_run(conn)
    conn.commit()
    assert _compute_cash_coherence_badge(conn) is False
