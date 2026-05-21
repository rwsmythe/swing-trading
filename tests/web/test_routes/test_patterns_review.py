"""Phase 13 T2.SB6b T-A.6.3 — ``/patterns/{candidate_id}/review`` web tests.

Per plan G.9 T-A.6.3 Step 1: 10+ discriminating tests covering the 8-item
v2 brief 9.2 checklist + 9.3 6-decision enum + label_source semantic
split + cross-column CHECK invariant #1 + L9 server-recompute + L12 HTMX
3-surface discipline + L11 BaseLayoutVM extension.

HTMX failure-surface coverage (CLAUDE.md gotcha family):
  - HX-Request propagation on embedded form (Phase 5 R1 M1).
  - HX-Redirect success path 204 + /patterns/queue (Phase 5 R1 M2).
  - HX-Redirect target /patterns/queue registered in app.routes (Phase 6 I3).

Server-recompute discipline (T3.SB3 R1 M#2 LOCK; L9 LOCK): POST handler
RECOMPUTES proposed_pattern_class from pattern_evaluations at POST time,
NOT operator-submitted hidden input. Discriminating test: tampered hidden
proposed_pattern_class='vcp' for a flat_base pattern_evaluation; assert
persisted row carries 'flat_base'.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.web.app import create_app
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.patterns.review_form import (
    PatternReviewFormVM,
    build_patterns_review_form_vm,
)

# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed_pipeline_run(conn) -> int:
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


def _make_evaluation(
    *,
    pipeline_run_id: int,
    ticker: str = "ABC",
    pattern_class: str = "vcp",
    geometric_score: float = 0.55,
    composite_score: float = 0.62,
    template_match_score: float | None = 0.40,
    template_match_nearest_exemplar_ids_json: str | None = None,
    structural_evidence_json: str | None = None,
    geometric_score_json: str | None = None,
) -> PatternEvaluation:
    return PatternEvaluation(
        id=None,
        pipeline_run_id=pipeline_run_id,
        ticker=ticker,
        pattern_class=pattern_class,
        detector_version="v1",
        geometric_score=geometric_score,
        geometric_score_json=geometric_score_json or json.dumps({
            "criteria": [
                {"name": "stage_2", "result": "pass", "score": 1.0},
                {"name": "contractions", "result": "pass", "score": 0.7},
                {"name": "volume_dryup", "result": "fail", "score": 0.2,
                 "note": "ratio 0.85 above 0.70 max"},
            ],
        }),
        composite_score=composite_score,
        structural_evidence_json=structural_evidence_json or json.dumps({
            "criteria_pass": {
                "stage_2": True,
                "contractions": True,
                "volume_dryup": False,
            },
            "pivot_price": 120.5,
            "contractions": [
                {"depth_pct": 22.0},
                {"depth_pct": 14.0},
                {"depth_pct": 8.0},
            ],
        }),
        feature_distribution_log_json="{}",
        window_start_date="2026-04-01",
        window_end_date="2026-05-15",
        created_at="2026-05-20T09:01:00",
        template_match_score=template_match_score,
        template_match_nearest_exemplar_ids_json=(
            template_match_nearest_exemplar_ids_json
        ),
    )


@pytest.fixture
def seeded_db_with_evaluation(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            ev = _make_evaluation(
                pipeline_run_id=run_id, ticker="ABC", pattern_class="vcp",
            )
            eval_id = evals_repo.insert_evaluation(conn, ev)
    finally:
        conn.close()
    return cfg, cfg_path, eval_id


@pytest.fixture
def seeded_db_with_flat_base(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            ev = _make_evaluation(
                pipeline_run_id=run_id, ticker="FBT",
                pattern_class="flat_base",
            )
            eval_id = evals_repo.insert_evaluation(conn, ev)
    finally:
        conn.close()
    return cfg, cfg_path, eval_id


# ---------------------------------------------------------------------------
# Test 1: 8-item checklist render
# ---------------------------------------------------------------------------


def test_get_patterns_review_renders_8_item_checklist_per_v2_brief_92(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    # 8 checklist items present (per spec lines 766-775).
    assert "proposed pattern class" in body.lower()
    assert "geometric score" in body.lower()
    assert "template" in body.lower()  # top-3 thumbnails section
    assert "trend template" in body.lower()  # state badge
    assert "rs rank" in body.lower()
    assert "volume profile" in body.lower()
    assert "uncertainty" in body.lower()  # reason from criteria_pass
    assert "outcome distribution" in body.lower()


def test_get_patterns_review_renders_geometric_score_breakdown_per_rule_component(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    # Per-criterion breakdown rows.
    assert "stage_2" in body
    assert "contractions" in body
    assert "volume_dryup" in body


def test_get_patterns_review_renders_top_3_template_match_thumbnails(
    seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            ev = _make_evaluation(
                pipeline_run_id=run_id,
                template_match_nearest_exemplar_ids_json=json.dumps(
                    [11, 12, 13],
                ),
            )
            eval_id = evals_repo.insert_evaluation(conn, ev)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    # Each of the 3 exemplar IDs surfaces in the rendered chrome.
    for ex_id in (11, 12, 13):
        assert str(ex_id) in body


def test_get_patterns_review_renders_trend_template_badge(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    assert "trend-template-badge" in body or "trend template" in body.lower()


def test_get_patterns_review_renders_rs_rank_badge(seeded_db_with_evaluation):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    assert "rs-rank" in r.text or "rs rank" in r.text.lower()


def test_get_patterns_review_renders_volume_profile_sparkline(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    assert "volume-profile" in r.text or "volume profile" in r.text.lower()


def test_get_patterns_review_renders_uncertainty_reason_per_criterion(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    # criteria_pass renders per-criterion uncertainty.
    assert "volume_dryup" in body
    # Failed criterion surfaces as "fail" or "uncertain".
    assert "fail" in body.lower() or "uncertain" in body.lower()


def test_get_patterns_review_renders_outcome_distribution_from_prior_similar_candidates(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    # Outcome distribution surfaces (n=0 expected for fresh db; section still
    # renders).
    assert "outcome distribution" in body.lower()


# ---------------------------------------------------------------------------
# Test 9-15: 6-decision enum behavior
# ---------------------------------------------------------------------------


def _open_trade_for(ticker: str, conn) -> None:
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    insert_trade_with_event(
        conn,
        Trade(
            id=None,
            ticker=ticker,
            entry_date="2026-05-18",
            entry_price=100.0,
            initial_shares=10,
            initial_stop=90.0,
            current_stop=90.0,
            state="entered",
            watchlist_entry_target=None,
            watchlist_initial_stop=None,
            notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-18T09:00:00",
            current_size=10.0,
        ),
        event_ts="2026-05-18T09:00:00",
    )


def test_post_patterns_review_decision_confirm_persists_closed_loop_review_even_if_unrelated_trade_exists(
    seeded_db_with_evaluation,
):
    """Codex R1 MAJOR #3 closure: V1 emits closed_loop_review
    unconditionally, even when an unrelated prior trade on the SAME
    ticker exists. The ticker-level proxy for organic_trade_history was
    rejected because it would mislabel a new candidate review as organic
    history just because an old ABC trade happens to share the ticker.

    V2 candidate banked: when trades carries a candidate_id backlink,
    confirm + trade-opened-on-THIS-candidate persists
    organic_trade_history per spec section 5.10 lines 787-788.
    """
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _open_trade_for("ABC", conn)
    finally:
        conn.close()
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/queue"
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    assert rows
    new = rows[-1]
    # V1 LOCK: closed_loop_review even with unrelated prior ticker trade.
    assert new.label_source == "closed_loop_review", (
        "Codex R1 MAJOR #3 regression: V1 must emit closed_loop_review "
        "unconditionally from this route since trades schema lacks a "
        "candidate-to-trade backlink (organic_trade_history is V2)."
    )
    assert new.final_decision == "confirmed"
    assert new.ticker == "ABC"
    assert new.proposed_pattern_class == "vcp"
    # Invariant #4 requires geometric_score_json non-NULL for
    # closed_loop_review source.
    assert new.geometric_score_json is not None


def test_post_patterns_review_decision_confirm_persists_closed_loop_review_if_no_trade_opened(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    assert rows
    new = rows[-1]
    assert new.label_source == "closed_loop_review"
    assert new.final_decision == "confirmed"


def test_post_patterns_review_decision_watch_persists_watch(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    assert rows
    new = rows[-1]
    assert new.final_decision == "watch"
    assert new.label_source == "closed_loop_review"


def test_post_patterns_review_decision_reject_persists_rejected(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "reject"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    assert rows
    new = rows[-1]
    assert new.final_decision == "rejected"
    assert new.label_source == "closed_loop_review"
    # gold_validated_at MUST be NULL for rejected per spec section 5.10.
    assert new.gold_validated_at is None


def test_post_patterns_review_decision_relabel_with_corrected_class_persists_relabeled(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "relabel",
                "corrected_pattern_class": "flat_base",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    assert rows
    new = rows[-1]
    # Invariant #1: relabeled requires final_pattern_class non-NULL +
    # distinct from proposed.
    assert new.final_decision == "relabeled"
    assert new.proposed_pattern_class == "vcp"
    assert new.final_pattern_class == "flat_base"


def test_post_patterns_review_decision_pattern_present_outside_window_emits_window_shift_row(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "pattern_present_outside_window",
                "corrected_window_start_date": "2026-03-01",
                "corrected_window_end_date": "2026-04-15",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    assert rows
    new = rows[-1]
    # Window-shift emit: operator-noted corrected window is persisted.
    assert new.start_date == "2026-03-01"
    assert new.end_date == "2026-04-15"
    assert new.label_source == "closed_loop_review"


def test_post_patterns_review_decision_multiple_overlapping_patterns_emits_multi_exemplar_rows(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "multiple_overlapping_patterns",
                "additional_pattern_classes": "flat_base,cup_with_handle",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    # At least 3 rows: original (vcp confirmed) + flat_base + cup_with_handle.
    closed_loop_rows = [
        r for r in rows if r.label_source == "closed_loop_review"
        and r.ticker == "ABC"
    ]
    classes = {r.proposed_pattern_class for r in closed_loop_rows}
    assert {"vcp", "flat_base", "cup_with_handle"} <= classes


# ---------------------------------------------------------------------------
# Test 16: VM extends BaseLayoutVM
# ---------------------------------------------------------------------------


def test_patterns_review_vm_extends_base_layout_vm(seeded_db_with_evaluation):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, candidate_id=eval_id, session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert isinstance(vm, PatternReviewFormVM)
    assert isinstance(vm, BaseLayoutVM)


def test_patterns_review_vm_populates_banner_fields(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, candidate_id=eval_id, session_date="2026-05-20",
        )
    finally:
        conn.close()
    # Banner fields exist and are integers / None per BaseLayoutVM contract.
    assert isinstance(vm.unresolved_material_discrepancies_count, int)
    assert isinstance(vm.recent_multi_leg_auto_correction_count, int)
    # banner_resolve_link is str|None.
    assert vm.banner_resolve_link is None or isinstance(
        vm.banner_resolve_link, str,
    )


# ---------------------------------------------------------------------------
# Test 18-20: HTMX trinity + server-recompute (L9 LOCK / T3.SB3 R1 M#2)
# ---------------------------------------------------------------------------


def test_post_patterns_review_returns_204_with_hx_redirect_to_queue_not_303(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/patterns/queue"


def test_post_patterns_review_hx_redirect_target_queue_registered_in_app_routes(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, _ = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    route_paths = {getattr(r, "path", None) for r in app.routes}
    assert "/patterns/queue" in route_paths


def test_get_patterns_review_embedded_form_carries_hx_request_propagation_header(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    body = r.text
    # HX-Request propagation per Phase 5 R1 M1 LOCK.
    assert "HX-Request" in body and "true" in body


def test_post_patterns_review_server_recomputes_proposed_pattern_class_from_evaluation_not_operator_hidden(
    seeded_db_with_flat_base,
):
    """L9 LOCK / T3.SB3 R1 M#2 — POST handler RECOMPUTES proposed_pattern_class
    from pattern_evaluations row, NOT from operator-submitted hidden input.

    Discriminating test: submit a tampered hidden `proposed_pattern_class=vcp`
    for a pattern_evaluation that is actually flat_base; assert persisted
    pattern_exemplar carries the RECOMPUTED 'flat_base', not the tampered
    'vcp'. Mirrors Phase 13 T3.SB3 R1 M#2 closure semantics.
    """
    cfg, cfg_path, eval_id = seeded_db_with_flat_base
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "confirm",
                # Tamper: operator submits the WRONG pattern class.
                "proposed_pattern_class": "vcp",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    conn = connect(cfg.paths.db_path)
    rows = exemplars_repo.list_exemplars(conn)
    conn.close()
    closed_loop = [r for r in rows if r.label_source == "closed_loop_review"]
    assert closed_loop
    new = closed_loop[-1]
    assert new.proposed_pattern_class == "flat_base", (
        "L9 LOCK regression: POST handler accepted tampered hidden "
        f"proposed_pattern_class='vcp' instead of server-recomputing "
        f"'flat_base' from pattern_evaluations row; got "
        f"{new.proposed_pattern_class!r}"
    )


def test_post_patterns_review_404_when_candidate_id_missing(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/patterns/99999/review",
            data={"decision": "watch"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404


def test_post_patterns_review_400_when_decision_invalid(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={"decision": "bogus"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400


def test_post_patterns_review_400_when_relabel_target_matches_proposed(
    seeded_db_with_evaluation,
):
    cfg, cfg_path, eval_id = seeded_db_with_evaluation
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/patterns/{eval_id}/review",
            data={
                "decision": "relabel",
                "corrected_pattern_class": "vcp",  # Same as proposed.
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
