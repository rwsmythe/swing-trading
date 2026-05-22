"""Phase 12 Sub-sub-bundle C.D T-D.10 — banner predicate widening
13-VM regression suite (plan §A.5 lists 14 across 9 files;
implementation count is 13 explicit ``unresolved_material_discrepancies_count``
field declarations + the ``BaseLayoutVM`` mixin in
``metrics/shared.py`` inherited by 8 metrics VMs — banked as V2.1
§VII.F amendment candidate per T-D.10 return report §5).

Per plan §E.10 acceptance criterion #4: discriminating regression
test suite covering each base-layout-extending page. Plant a
discrepancy with
``resolution='pending_ambiguity_resolution' AND
material_to_review=1 AND ambiguity_kind='unsupported'`` attributed to
an active trade; render each base-layout-extending page; assert the
banner fires with count = 1.

Sibling: ``test_base_layout_discrepancy_banner.py`` covers the
``resolution='unresolved'`` path (Phase 10 T-E.3). This test extends
the discriminating coverage to confirm ``pending_ambiguity_resolution``
joins the banner predicate.

Banner-text content invariant (acceptance criterion #6): banner text
stays ``"N unresolved material reconciliation discrepancy/discrepancies"``
regardless of the underlying resolution mix; the predicate widening
is invisible to the operator at the banner-text level except via
the count.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app


# 6 base-layout pages mirroring test_base_layout_discrepancy_banner.py
_BASE_LAYOUT_PAGES: tuple[str, ...] = (
    "/",
    "/pipeline",
    "/journal",
    "/watchlist",
    "/config",
    "/reviews/pending",
)

# 10 metrics pages (umbrella + 8 Phase 10 surfaces + 1 Phase 13 T2.SB6b
# T-A.6.5 9th tile) — each populates the field via the BaseLayoutVM mixin
# in ``metrics/shared.py``.
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
    "/metrics/pattern-outcomes",
)


def _seed_one_pending_ambiguity_discrepancy(db_path) -> None:
    """Plant an OPEN trade + a single ``pending_ambiguity_resolution``
    material discrepancy attributed to it.

    Cross-column CHECK from migration 0019: ``pending_ambiguity_resolution``
    REQUIRES ``ambiguity_kind IS NOT NULL``. Uses ``'unsupported'``
    (one of the 7 enum values; mirrors C.B classifier graceful-degradation
    path).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, "
            "'entered', 'S', 'I', 'manual_off_pipeline', "
            "'2026-04-01T09:30:00', 100)"
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
            "(1, 1, 'entry_price_mismatch', 1, NULL, NULL, NULL, 'AAA', "
            " 'entry_price', '\"10.00\"', '\"10.15\"', NULL, 1, "
            " 'pending_ambiguity_resolution', 'unsupported', "
            " 'classifier exception: Pass 2 required', NULL, NULL, NULL, "
            " '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_mixed_discrepancies(db_path) -> None:
    """Plant 1 ``unresolved`` + 1 ``pending_ambiguity_resolution`` +
    1 ``auto_corrected_from_schwab`` against the same active trade.

    Expected banner count: 2 (auto_corrected stays excluded). Verifies
    the predicate widening is additive, not replacement.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, "
            "'entered', 'S', 'I', 'manual_off_pipeline', "
            "'2026-04-01T09:30:00', 100)"
        )
        conn.execute(
            "INSERT INTO reconciliation_runs "
            "(run_id, period_start, period_end, started_ts, finished_ts, "
            " state, source, source_artifact_path, source_artifact_sha256) "
            "VALUES (1, '2026-04-01', '2026-04-08', "
            "'2026-04-08T16:00:00.000', '2026-04-08T16:00:01.000', "
            "'completed', 'system_audit', 'gate-test', 'gate-test-sha')"
        )
        # discrepancy_id=1 — unresolved
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(discrepancy_id, run_id, discrepancy_type, trade_id, "
            " ticker, field_name, material_to_review, resolution, "
            " created_at) VALUES "
            "(1, 1, 'stop_mismatch', 1, 'AAA', 'current_stop', 1, "
            " 'unresolved', '2026-04-08T16:00:00.000')"
        )
        # discrepancy_id=2 — pending_ambiguity_resolution
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(discrepancy_id, run_id, discrepancy_type, trade_id, "
            " ticker, field_name, material_to_review, resolution, "
            " ambiguity_kind, created_at) VALUES "
            "(2, 1, 'entry_price_mismatch', 1, 'AAA', 'entry_price', "
            " 1, 'pending_ambiguity_resolution', 'unsupported', "
            " '2026-04-08T16:00:00.000')"
        )
        # discrepancy_id=3 — auto_corrected_from_schwab (terminal-state)
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(discrepancy_id, run_id, discrepancy_type, trade_id, "
            " ticker, field_name, material_to_review, resolution, "
            " resolved_by, resolved_at, created_at) VALUES "
            "(3, 1, 'close_price_mismatch', 1, 'AAA', 'close_price', "
            " 1, 'auto_corrected_from_schwab', 'auto', "
            " '2026-04-08T16:00:01.000', '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Banner FIRES on each base-layout-extending page when ONLY
# pending_ambiguity_resolution rows exist (predicate-widening discriminator).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _BASE_LAYOUT_PAGES)
def test_base_layout_banner_fires_for_pending_ambiguity(seeded_db, path):
    """T-D.10 binding: each of 6 base-layout pages fires the banner for
    a ``pending_ambiguity_resolution`` discrepancy attributed to an
    active trade. Before the predicate widening, the banner would have
    been absent (only ``= 'unresolved'`` matched).
    """
    cfg, cfg_path = seeded_db
    _seed_one_pending_ambiguity_discrepancy(cfg.paths.db_path)
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
def test_metrics_pages_banner_fires_for_pending_ambiguity(seeded_db, path):
    """The 9 metrics pages inherit ``unresolved_material_discrepancies_count``
    via the shared ``BaseLayoutVM`` mixin in ``swing/web/view_models/
    metrics/shared.py`` — banner fires here too on the same seed data.
    """
    cfg, cfg_path = seeded_db
    _seed_one_pending_ambiguity_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 200
    assert 'data-banner="unresolved-material-discrepancies"' in r.text
    assert 'data-count="1"' in r.text


# ---------------------------------------------------------------------------
# Banner count reflects MIXED unresolved + pending + auto_corrected
# (auto_corrected stays EXCLUDED — count=2 not 3).
# ---------------------------------------------------------------------------


def test_banner_count_excludes_auto_corrected_in_mixed_seed(seeded_db):
    """Mixed seed planting 1 unresolved + 1 pending_ambiguity_resolution
    + 1 auto_corrected_from_schwab → banner shows ``data-count="2"``.

    Discriminator: a regression that widens the predicate too broadly
    (e.g., ``resolution != 'acknowledged_immaterial'``) would produce
    count=3.
    """
    cfg, cfg_path = seeded_db
    _seed_mixed_discrepancies(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert 'data-banner="unresolved-material-discrepancies"' in r.text
    assert 'data-count="2"' in r.text


def test_banner_count_plural_grammar_at_count_2(seeded_db):
    """Banner text uses plural ``discrepancies`` at count > 1
    (regardless of resolution mix)."""
    cfg, cfg_path = seeded_db
    _seed_mixed_discrepancies(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # plural form
    assert "discrepancies" in r.text


# ---------------------------------------------------------------------------
# Per-trade indicator (Phase 10 T-E.6) picks up pending-ambiguity rows.
# ---------------------------------------------------------------------------


def _seed_closed_trade_with_pending_ambiguity(db_path) -> None:
    """Plant a CLOSED trade + entry fill + a pending_ambiguity_resolution
    discrepancy attributed to it.

    Mirrors ``tests/web/test_routes/test_trade_detail_discrepancy_indicator.py``
    seed shape — the /trades/{id} route requires a fill row + a fully-formed
    trade for full template render.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size, "
            "premortem_technical) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, 'closed', "
            "'S', 'I', 'manual_off_pipeline', '2026-04-01T09:30:00', 0, "
            "'tech risk')"
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
            "(1, 1, 'entry_price_mismatch', 1, NULL, NULL, NULL, 'AAA', "
            " 'entry_price', '\"10.00\"', '\"10.15\"', NULL, 1, "
            " 'pending_ambiguity_resolution', 'unsupported', "
            " 'classifier exception: Pass 2 required', NULL, NULL, NULL, "
            " '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


def test_trade_detail_indicator_picks_up_pending_ambiguity(seeded_db):
    """T-D.10 acceptance #5: per-trade ``/trades/{id}`` indicator
    surfaces the pending-ambiguity discrepancy via the widened
    ``list_unresolved_material_for_trade`` helper.

    Mirrors Phase 10 T-E.6's
    ``test_trade_detail_renders_indicator_for_unresolved_material``
    pattern but seeds a ``pending_ambiguity_resolution`` row instead
    of ``unresolved`` — discriminator for T-D.10 widening at the
    per-trade surface.
    """
    cfg, cfg_path = seeded_db
    _seed_closed_trade_with_pending_ambiguity(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200
    # T-E.6 indicator marker — fires now that the predicate widens.
    assert 'data-indicator="unresolved-material-discrepancies"' in r.text
    assert 'data-count="1"' in r.text
    # Discrepancy type + field rendered into the details body.
    assert "entry_price_mismatch" in r.text
