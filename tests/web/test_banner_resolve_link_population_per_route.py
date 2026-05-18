"""Phase 12.5 #2 T-2.9 — Pass-B retrofit per-route population tests.

Every base-layout-extending page populates ``banner_resolve_link`` via
:func:`swing.metrics.discrepancies.fetch_first_pending_ambiguity_resolve_link_path`
so the global banner becomes a clickable link to
``/reconcile/discrepancy/{first_pending_ambiguity.id}/resolve``.

The base-layout rendering predicate is ``vm.banner_resolve_link`` being
truthy. The banner-link is OMITTED (plain text banner only) when
no ``pending_ambiguity_resolution`` discrepancies exist in the banner
set — even if ``unresolved`` rows fire the banner count.

This test seeds a single pending-ambiguity discrepancy attributed to an
active trade, then asserts the link substring shows up on each route's
rendered HTML.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app


# Representative subset of base-layout + metrics + reconcile routes
# covering Pattern A (conn-shape) sites + the reconcile route family.
_PARAMETRIZED_PATHS: tuple[str, ...] = (
    "/",
    "/pipeline",
    "/journal",
    "/watchlist",
    "/config",
    "/reviews/pending",
    "/metrics",
    "/metrics/capital-friction",
    "/metrics/identification-funnel",
    "/metrics/trade-process",
    "/metrics/hypothesis-progress",
    "/metrics/tier-comparison",
    "/metrics/deviation-outcome",
    "/metrics/maturity-stage",
    "/metrics/process-grade-trend",
    "/account/snapshot",
    "/trades/1",
)


def _seed_pending_ambiguity_with_id(db_path, discrepancy_id: int) -> None:
    """Seed an active trade + one ``pending_ambiguity_resolution``
    material discrepancy with the supplied id.

    Mirrors ``tests/web/test_routes/test_base_layout_vm_banner_with_pending_ambiguity.py``
    seed shape but lets the caller pin the row's primary key so the
    expected resolve link path is deterministic.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size, "
            "premortem_technical) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, "
            "'entered', 'S', 'I', 'manual_off_pipeline', "
            "'2026-04-01T09:30:00', 100, 'tech risk')"
        )
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES "
            "(1, '2026-04-01T09:30:00', 'entry', 100, 10.0, 'unreconciled')"
        )
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
            " delta_text, material_to_review, resolution, ambiguity_kind, "
            " resolution_reason, resolved_at, resolved_by, "
            " mistake_tag_assigned, created_at) VALUES "
            "(?, 1, 'entry_price_mismatch', 1, NULL, NULL, NULL, 'AAA', "
            " 'entry_price', '\"10.00\"', '\"10.15\"', NULL, 1, "
            " 'pending_ambiguity_resolution', 'unsupported', "
            " 'classifier exception: Pass 2 required', NULL, NULL, NULL, "
            " '2026-04-08T16:00:00.000')",
            (discrepancy_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_unresolved_only(db_path) -> None:
    """Seed an active trade + a single ``unresolved`` material discrepancy
    (NO pending_ambiguity_resolution rows). Banner FIRES count=1 but
    ``banner_resolve_link`` should stay None.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size, "
            "premortem_technical) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, "
            "'entered', 'S', 'I', 'manual_off_pipeline', "
            "'2026-04-01T09:30:00', 100, 'tech risk')"
        )
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES "
            "(1, '2026-04-01T09:30:00', 'entry', 100, 10.0, 'unreconciled')"
        )
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
            "(discrepancy_id, run_id, discrepancy_type, trade_id, ticker, "
            " field_name, material_to_review, resolution, created_at) "
            "VALUES (1, 1, 'stop_mismatch', 1, 'AAA', 'current_stop', 1, "
            " 'unresolved', '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("path", _PARAMETRIZED_PATHS)
def test_banner_resolve_link_populated_per_route(seeded_db, path):
    """Pass-B retrofit binding: each parametrized route surfaces the
    ``data-banner-resolve-link="true"`` marker pointing at the seeded
    discrepancy's resolve form.
    """
    cfg, cfg_path = seeded_db
    _seed_pending_ambiguity_with_id(cfg.paths.db_path, 42)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 200, (
        f"{path} returned {r.status_code}: {r.text[:300]}"
    )
    assert 'data-banner-resolve-link="true"' in r.text, (
        f"{path} missing banner_resolve_link marker"
    )
    assert "/reconcile/discrepancy/42/resolve" in r.text, (
        f"{path} missing resolve form href"
    )


def test_banner_resolve_link_omitted_when_only_unresolved_seed(seeded_db):
    """Banner FIRES (count=1) but link is OMITTED when no
    pending_ambiguity_resolution rows exist."""
    cfg, cfg_path = seeded_db
    _seed_unresolved_only(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert 'data-banner="unresolved-material-discrepancies"' in r.text
    assert 'data-count="1"' in r.text
    # Link MUST be absent — no pending_ambiguity_resolution row exists.
    assert 'data-banner-resolve-link="true"' not in r.text


def test_banner_resolve_link_omitted_when_no_discrepancies(seeded_db):
    """Banner absent + link absent on empty DB."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert 'data-banner="unresolved-material-discrepancies"' not in r.text
    assert 'data-banner-resolve-link="true"' not in r.text


def test_banner_resolve_link_on_reconcile_resolve_form_page(seeded_db):
    """The ``/reconcile/discrepancy/{id}/resolve`` GET handler itself
    builds via ``build_reconcile_discrepancy_resolve_vm`` and consumes
    ``fetch_first_pending_ambiguity_resolve_link_path``. The form page
    SHOULD show the banner-link (possibly self-referential — the
    discrepancy the operator is viewing may also be the oldest-pending).
    """
    cfg, cfg_path = seeded_db
    _seed_pending_ambiguity_with_id(cfg.paths.db_path, 42)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/reconcile/discrepancy/42/resolve")
    assert r.status_code == 200
    assert 'data-banner-resolve-link="true"' in r.text
    assert "/reconcile/discrepancy/42/resolve" in r.text


def test_banner_resolve_link_on_schwab_status_page(seeded_db):
    """Pattern-B (db_path-shape) coverage on the ``/schwab/status``
    route. Sibling helper ``_fetch_banner_resolve_link`` opens a
    short-lived connection like ``_fetch_unresolved_material_count``.
    """
    cfg, cfg_path = seeded_db
    _seed_pending_ambiguity_with_id(cfg.paths.db_path, 42)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200, r.text[:300]
    assert 'data-banner-resolve-link="true"' in r.text
    assert "/reconcile/discrepancy/42/resolve" in r.text
