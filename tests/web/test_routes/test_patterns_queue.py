"""Phase 13 T2.SB6b T-A.6.4 — `/patterns/queue` active-learning surface tests.

Per plan G.9 T-A.6.4 Step 1: 6+ tests covering the 4-criterion ranking
per spec section 5.10 lines 796-801 VERBATIM + PatternQueueVM extends
BaseLayoutVM + banner fields.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.patterns.active_learning import (
    BORDERLINE_GEOMETRIC_BAND,
    CandidatePriority,
    FAILED_RULE_NEAR_MISS_HIGH,
    FAILED_RULE_NEAR_MISS_LOW,
    RULE_TEMPLATE_DISAGREEMENT_THRESHOLD,
    prioritize_candidates,
)
from swing.web.app import create_app
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.patterns.queue import (
    PatternQueueVM,
    build_patterns_queue_vm,
)


def _seed_complete_pipeline_run(conn) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token)
        VALUES ('2026-05-20T09:00:00', '2026-05-20T09:05:00',
                'manual', '2026-05-19', '2026-05-20',
                'complete', 't-x')
        """
    )
    return int(cur.lastrowid)


def _insert_eval(
    conn, *,
    pipeline_run_id: int,
    ticker: str,
    pattern_class: str = "vcp",
    geometric_score: float,
    template_match_score: float | None = None,
) -> int:
    ev = PatternEvaluation(
        id=None,
        pipeline_run_id=pipeline_run_id,
        ticker=ticker,
        pattern_class=pattern_class,
        detector_version="v1",
        geometric_score=geometric_score,
        geometric_score_json="{}",
        composite_score=geometric_score,
        structural_evidence_json="{}",
        feature_distribution_log_json="{}",
        window_start_date="2026-04-01",
        window_end_date="2026-05-15",
        created_at="2026-05-20T09:01:00",
        template_match_score=template_match_score,
        template_match_nearest_exemplar_ids_json=None,
    )
    return evals_repo.insert_evaluation(conn, ev)


@pytest.fixture
def seeded_db_with_run(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_pipeline_run(conn)
    finally:
        conn.close()
    return cfg, cfg_path, run_id


# ---------------------------------------------------------------------------
# Test 1: borderline geometric included (|score - 0.5| < 0.1).
# ---------------------------------------------------------------------------


def test_prioritize_candidates_includes_borderline_geometric(
    seeded_db_with_run,
):
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Borderline: |0.52 - 0.5| = 0.02 < 0.1 -> include.
            cid = _insert_eval(
                conn, pipeline_run_id=run_id, ticker="BDR",
                geometric_score=0.52,
            )
            # Far from borderline + no template + not failed-near-miss + not
            # underrepresented (we'll seed pattern_exemplars to push out).
            _insert_eval(
                conn, pipeline_run_id=run_id, ticker="FAR",
                geometric_score=0.90,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(conn, top_k=20)
    finally:
        conn.close()
    ids = {p.candidate_id for p in priorities}
    assert cid in ids
    by_id = {p.candidate_id: p for p in priorities}
    assert by_id[cid].priority_reason == "borderline_geometric"


# ---------------------------------------------------------------------------
# Test 2: rule/template disagreement included (|geo - template| > 0.3).
# ---------------------------------------------------------------------------


def test_prioritize_candidates_includes_rule_template_disagreement(
    seeded_db_with_run,
):
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # geo 0.85, template 0.30 -> disagreement 0.55 > 0.3 + NOT
            # borderline (0.85 - 0.5 = 0.35 > 0.1) -> falls through to
            # criterion 2.
            cid = _insert_eval(
                conn, pipeline_run_id=run_id, ticker="DSG",
                geometric_score=0.85,
                template_match_score=0.30,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(conn, top_k=20)
    finally:
        conn.close()
    by_id = {p.candidate_id: p for p in priorities}
    assert cid in by_id
    assert by_id[cid].priority_reason == "rule_template_disagreement"


# ---------------------------------------------------------------------------
# Test 3: failed-rule near-miss included (geo in [0.55, 0.70]).
# ---------------------------------------------------------------------------


def test_prioritize_candidates_includes_failed_rule_near_miss(
    seeded_db_with_run,
):
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Seed gold exemplars for all 5 classes so 'vcp' is NOT
            # underrepresented (else criterion 3 fires first).
            now_iso = "2026-05-20T09:00:00"
            for cls in (
                "vcp", "flat_base", "cup_with_handle",
                "high_tight_flag", "double_bottom_w",
            ):
                for i in range(6):
                    conn.execute(
                        """
                        INSERT INTO pattern_exemplars
                            (ticker, timeframe, start_date, end_date,
                             proposed_pattern_class, final_decision,
                             label_source, structural_evidence_json,
                             created_at, created_by,
                             labeler_evidence_json)
                        VALUES (?, 'daily', '2024-01-01', '2024-02-01',
                                ?, 'confirmed', 'curated_gold', '{}',
                                ?, 'operator', '{}')
                        """,
                        (f"T{cls[:3]}{i}", cls, now_iso),
                    )
            # geo 0.65 -> in failed-rule near-miss band [0.55, 0.70];
            # |0.65 - 0.5| = 0.15 > 0.1 (NOT borderline); no template
            # score (NOT disagreement); not underrepresented.
            cid = _insert_eval(
                conn, pipeline_run_id=run_id, ticker="FRM",
                geometric_score=0.65,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(conn, top_k=20)
    finally:
        conn.close()
    by_id = {p.candidate_id: p for p in priorities}
    assert cid in by_id
    assert by_id[cid].priority_reason == "failed_rule_near_miss"


# ---------------------------------------------------------------------------
# Test 4: underrepresented regime included (low exemplar count for class).
# ---------------------------------------------------------------------------


def test_prioritize_candidates_includes_underrepresented_regime(
    seeded_db_with_run,
):
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Empty pattern_exemplars => all 5 detector classes < threshold
            # of 5 => underrepresented. geo 0.80 -> NOT borderline; no
            # template -> NOT disagreement; NOT in failed-near-miss band.
            # Falls through to criterion 3.
            cid = _insert_eval(
                conn, pipeline_run_id=run_id, ticker="UND",
                pattern_class="high_tight_flag",
                geometric_score=0.80,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(conn, top_k=20)
    finally:
        conn.close()
    by_id = {p.candidate_id: p for p in priorities}
    assert cid in by_id
    assert by_id[cid].priority_reason == "underrepresented_regime"


# ---------------------------------------------------------------------------
# Test 5: ordering by priority_score DESC + top_k limit.
# ---------------------------------------------------------------------------


def test_prioritize_candidates_ordered_by_priority_score_desc(
    seeded_db_with_run,
):
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Two borderline candidates with different priorities. 0.50 is
            # the most borderline (priority_score ~ 1.0); 0.58 less so
            # (priority_score ~ 0.2 since 0.08 / 0.1 = 0.8 distance).
            cid_high = _insert_eval(
                conn, pipeline_run_id=run_id, ticker="HIG",
                geometric_score=0.50,
            )
            cid_low = _insert_eval(
                conn, pipeline_run_id=run_id, ticker="LOW",
                geometric_score=0.58,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(conn, top_k=20)
    finally:
        conn.close()
    # Both included, high before low.
    ids_ordered = [p.candidate_id for p in priorities]
    assert cid_high in ids_ordered
    assert cid_low in ids_ordered
    assert ids_ordered.index(cid_high) < ids_ordered.index(cid_low)


# ---------------------------------------------------------------------------
# Test 6: PatternQueueVM extends BaseLayoutVM + populates banner fields.
# ---------------------------------------------------------------------------


def test_patterns_queue_vm_extends_base_layout_vm_with_banner_fields(
    seeded_db_with_run,
):
    cfg, _, _ = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_queue_vm(
            conn, session_date="2026-05-20", top_k=20,
        )
    finally:
        conn.close()
    assert isinstance(vm, PatternQueueVM)
    assert isinstance(vm, BaseLayoutVM)
    assert isinstance(vm.unresolved_material_discrepancies_count, int)
    assert isinstance(vm.recent_multi_leg_auto_correction_count, int)
    assert vm.banner_resolve_link is None or isinstance(
        vm.banner_resolve_link, str,
    )


# ---------------------------------------------------------------------------
# Test 7: GET /patterns/queue route renders + 200 with empty advisory.
# ---------------------------------------------------------------------------


def test_get_patterns_queue_route_renders_empty_advisory_when_no_runs(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/queue")
    assert r.status_code == 200
    assert "No prioritized candidates" in r.text


def test_get_patterns_queue_route_renders_candidates_when_present(
    seeded_db_with_run,
):
    cfg, cfg_path, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _insert_eval(
                conn, pipeline_run_id=run_id, ticker="QQQ",
                geometric_score=0.51,  # borderline
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/patterns/queue")
    assert r.status_code == 200
    assert "QQQ" in r.text
    assert "borderline_geometric" in r.text


# ---------------------------------------------------------------------------
# Test 9: CandidatePriority.priority_reason runtime Literal validation.
# ---------------------------------------------------------------------------


def test_candidate_priority_rejects_invalid_priority_reason():
    """Per L6 LOCK / CLAUDE.md gotcha "Literal[...] not runtime-enforced"."""
    with pytest.raises(ValueError, match="priority_reason"):
        CandidatePriority(
            candidate_id=1,
            ticker="ABC",
            pattern_class="vcp",
            geometric_score=0.5,
            composite_score=0.5,
            template_match_score=None,
            priority_reason="bogus",  # type: ignore[arg-type]
            priority_score=0.5,
        )


# ---------------------------------------------------------------------------
# Test 10: spec ranking constants byte-for-byte vs spec section 5.10.
# ---------------------------------------------------------------------------


def test_active_learning_constants_match_spec_section_5_10_lines_796_801():
    """L1 + Expansion #2 LOCK — byte-fidelity vs spec source-of-truth.

    Spec section 5.10 lines 796-801 VERBATIM:
      1. abs(geometric_score - 0.5) < 0.1
      2. abs(geometric_score - template_match_score) > 0.3
      3. (low historical exemplar count for current weather state)
      4. geometric_score in [0.55, 0.70]
    """
    assert BORDERLINE_GEOMETRIC_BAND == 0.1
    assert RULE_TEMPLATE_DISAGREEMENT_THRESHOLD == 0.3
    assert FAILED_RULE_NEAR_MISS_LOW == 0.55
    assert FAILED_RULE_NEAR_MISS_HIGH == 0.70
