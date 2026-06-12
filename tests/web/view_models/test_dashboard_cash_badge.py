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


# --- Gate-run #100 witness fix: the badge's link target (the operator hit a
# 404 on the hardcoded /reconcile href — a route that never existed; the
# link-target-must-exist gotcha). The link helper mirrors the badge
# predicate's pending clause so count and target cannot disagree. ---
from swing.web.view_models.dashboard import (  # noqa: E402
    _first_pending_cash_resolve_link_path,
)


def _seed_pending_cash(conn, run_id, tx_id):
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "field_name, material_to_review, created_at, resolution, ambiguity_kind, "
        "expected_value_json, actual_value_json) VALUES (?, "
        "'cash_movement_mismatch', 'missing_journal_row', 1, '1', "
        "'pending_ambiguity_resolution', 'schwab_returned_no_match', "
        "'{\"transactionId\": \"" + tx_id + "\"}', '{\"matched\": null}')",
        (run_id,))


def test_first_pending_cash_link_path_targets_oldest(tmp_path):
    conn = ensure_schema(tmp_path / "b.db")
    run_id = _seed_run(conn)
    _seed_pending_cash(conn, run_id, "T-OLD")
    _seed_pending_cash(conn, run_id, "T-NEW")
    conn.commit()
    oldest = conn.execute(
        "SELECT MIN(discrepancy_id) FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='cash_movement_mismatch'").fetchone()[0]
    path = _first_pending_cash_resolve_link_path(conn)
    assert path == f"/reconcile/discrepancy/{oldest}/resolve"


def test_first_pending_cash_link_path_none_without_pending(tmp_path):
    # An equity_delta-only badge (clause 2) has no pending row to link to:
    # the badge may light, but the link helper returns None -> unlinked render.
    conn = ensure_schema(tmp_path / "b.db")
    run_id = _seed_run(conn)
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "field_name, material_to_review, created_at, resolution) VALUES (?, "
        "'equity_delta', 'net_liquidating_value', 1, '1', 'unresolved')", (run_id,))
    conn.commit()
    assert _first_pending_cash_resolve_link_path(conn) is None
