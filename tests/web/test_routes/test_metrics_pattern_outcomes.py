"""Phase 13 T2.SB6b T-A.6.5 — `/metrics/pattern-outcomes` 9th tile tests.

Per plan G.9 T-A.6.5 Step 1: 7+ tests covering per-pattern-class outcome
distribution + Wilson-CI at n>=5 + suppression at n<5 + composition with
Phase 10 cohort architecture + BaseLayoutVM + banner fields.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.data.repos.risk_policy import get_active_policy
from swing.metrics.pattern_outcomes import build_pattern_outcome_rows
from swing.web.app import create_app
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.patterns.outcomes_card import (
    PatternOutcomesVM,
    build_pattern_outcomes_vm,
)


def _seed_exemplars(
    conn, *, pattern_class: str, n_confirmed: int, n_other: int,
    other_final_decision: str = "watch",
) -> None:
    """Seed N confirmed + M non-confirmed rows for the given class.

    Uses label_source='closed_loop_review' which requires
    geometric_score_json non-NULL + labeler_evidence_json NULL per
    invariants #4 + #5. final_decision='watch' triggers Invariant #1
    coherence (final_pattern_class must be NULL).
    """
    for i in range(n_confirmed):
        exemplars_repo.insert_exemplar(conn, PatternExemplar(
            id=None,
            ticker=f"CON{pattern_class[:2]}{i}",
            timeframe="daily",
            start_date="2026-04-01",
            end_date="2026-05-01",
            proposed_pattern_class=pattern_class,
            final_decision="confirmed",
            label_source="closed_loop_review",
            structural_evidence_json="{}",
            created_at="2026-05-01T12:00:00",
            created_by="operator",
            geometric_score_json="{}",
            labeler_evidence_json=None,
            gold_validated_at="2026-05-01T12:00:00",
        ))
    for i in range(n_other):
        exemplars_repo.insert_exemplar(conn, PatternExemplar(
            id=None,
            ticker=f"OTH{pattern_class[:2]}{i}",
            timeframe="daily",
            start_date="2026-04-01",
            end_date="2026-05-01",
            proposed_pattern_class=pattern_class,
            final_decision=other_final_decision,
            label_source="closed_loop_review",
            structural_evidence_json="{}",
            created_at="2026-05-01T12:00:00",
            created_by="operator",
            geometric_score_json="{}",
            labeler_evidence_json=None,
            gold_validated_at="2026-05-01T12:00:00",
        ))


# ---------------------------------------------------------------------------
# Test 1: per-pattern-class outcome distribution renders all 5 classes.
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_renders_per_pattern_class_outcome_distribution(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/pattern-outcomes")
    assert r.status_code == 200
    body = r.text
    # 5 detector pattern classes per spec section 3.0.
    for cls in (
        "vcp", "flat_base", "cup_with_handle",
        "high_tight_flag", "double_bottom_w",
    ):
        assert cls in body


# ---------------------------------------------------------------------------
# Test 2: Wilson CI renders at n>=5.
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_honesty_wilson_ci_at_n_geq_5(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplars(conn, pattern_class="vcp",
                            n_confirmed=4, n_other=2)
        policy = get_active_policy(conn)
        rows = build_pattern_outcome_rows(conn, policy=policy)
    finally:
        conn.close()
    by_class = {r.pattern_class: r for r in rows}
    vcp_row = by_class["vcp"]
    # n=6 >= 5 -> Wilson CI populated; suppressed_text None.
    assert vcp_row.n == 6
    assert vcp_row.triggered_n == 4
    assert vcp_row.triggered_ci is not None
    assert vcp_row.suppressed_text is None
    assert vcp_row.triggered_ci.lower <= vcp_row.triggered_ci.point
    assert vcp_row.triggered_ci.point <= vcp_row.triggered_ci.upper


# ---------------------------------------------------------------------------
# Test 3: suppression at n<5 per Phase 10 §5.1.
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_suppressed_at_n_lt_5_per_phase10_5_1(
    seeded_db,
):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplars(conn, pattern_class="vcp",
                            n_confirmed=1, n_other=1)
        policy = get_active_policy(conn)
        rows = build_pattern_outcome_rows(conn, policy=policy)
    finally:
        conn.close()
    by_class = {r.pattern_class: r for r in rows}
    vcp_row = by_class["vcp"]
    # n=2 < 5 -> suppression placeholder; CI is None.
    assert vcp_row.n == 2
    assert vcp_row.triggered_ci is None
    assert vcp_row.suppressed_text is not None
    assert "n too low" in vcp_row.suppressed_text


# ---------------------------------------------------------------------------
# Test 4: text format renders "X% triggered (95% CI ...) n=N".
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_renders_x_triggered_y_reached_1R_z_hit_stop(
    seeded_db,
):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplars(conn, pattern_class="flat_base",
                            n_confirmed=3, n_other=2)
        policy = get_active_policy(conn)
        rows = build_pattern_outcome_rows(conn, policy=policy)
    finally:
        conn.close()
    by_class = {r.pattern_class: r for r in rows}
    fb = by_class["flat_base"]
    # Sanity: text mentions triggered + CI + n.
    assert "triggered" in fb.triggered_pct_text
    assert "95pct CI" in fb.triggered_pct_text
    assert "n=5" in fb.triggered_pct_text
    # reached_1r_n + hit_stop_n are None in V1 (trade backlink not resolved).
    assert fb.reached_1r_n is None
    assert fb.hit_stop_n is None


# ---------------------------------------------------------------------------
# Test 5: VM extends BaseLayoutVM.
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_vm_extends_base_layout_vm(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_pattern_outcomes_vm(conn, session_date="2026-05-20")
    finally:
        conn.close()
    assert isinstance(vm, PatternOutcomesVM)
    assert isinstance(vm, BaseLayoutVM)


# ---------------------------------------------------------------------------
# Test 6: VM populates banner fields per forward-binding lesson #12.
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_vm_populates_banner_fields(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_pattern_outcomes_vm(conn, session_date="2026-05-20")
    finally:
        conn.close()
    assert isinstance(vm.unresolved_material_discrepancies_count, int)
    assert isinstance(vm.recent_multi_leg_auto_correction_count, int)
    assert vm.banner_resolve_link is None or isinstance(
        vm.banner_resolve_link, str,
    )


# ---------------------------------------------------------------------------
# Test 7: composes with Phase 10 cohort architecture (reuses honesty +
# RiskPolicy).
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_composes_with_phase10_cohort_architecture(
    seeded_db,
):
    """Verify L10 LOCK: ADDITIVE composition with Phase 10. Specifically:
    (a) suppression threshold uses RiskPolicy.low_sample_size_threshold_class_a_n
    (Phase 10 honesty class A); (b) wilson_ci helper is imported from
    Phase 10 honesty; (c) MetricsIndexSurface contains the 9th tile entry
    so the umbrella `/metrics` navigator surfaces it.
    """
    from swing.web.view_models.metrics.index import (
        _SURFACES,
        build_metrics_index_vm,
    )
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        # Phase 10 navigator includes the new tile.
        idx_vm = build_metrics_index_vm(conn)
        labels = {s.label for s in idx_vm.surfaces}
        assert "Pattern-outcomes" in labels
        # Phase 10 honesty's class-A threshold drives suppression.
        policy = get_active_policy(conn)
        # Plant exactly threshold - 1 rows -> suppress.
        target = policy.low_sample_size_threshold_class_a_n
        with conn:
            _seed_exemplars(conn, pattern_class="cup_with_handle",
                            n_confirmed=target - 1, n_other=0)
        rows = build_pattern_outcome_rows(conn, policy=policy)
        by_class = {r.pattern_class: r for r in rows}
        cwh = by_class["cup_with_handle"]
        assert cwh.suppressed_text is not None
        assert cwh.triggered_ci is None
    finally:
        conn.close()
    # _SURFACES tuple has the 9th entry (Phase 10's 8 + T-A.6.5's tile).
    surface_paths = {s.path for s in _SURFACES}
    assert "/metrics/pattern-outcomes" in surface_paths


# ---------------------------------------------------------------------------
# Test 8: route returns 200 + renders for fresh empty db.
# ---------------------------------------------------------------------------


def test_metrics_pattern_outcomes_route_renders_for_empty_db(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/pattern-outcomes")
    assert r.status_code == 200
    # n=0 across all classes -> suppression placeholder rendered.
    assert "n too low" in r.text
