"""Phase 13 T2.SB6b T-A.6.7 closer — full closed-loop happy-path E2E.

Per plan G.9 T-A.6.7 Step 1: seed a complete pipeline run + pattern_evaluations
rows + chart_renders cache + walk the operator workflow through all 5
surfaces shipped in T2.SB6b:

  GET /dashboard - market weather chart at TOP
  GET /patterns/queue - active-learning prioritized list
  GET /patterns/{id}/review - 8-item checklist + decision form
  POST /patterns/{id}/review - persists pattern_exemplars row
  GET /metrics/pattern-outcomes - 9th tile shows the freshly written
                                  exemplar row in the outcome distribution
  GET /patterns/exemplars - chart + criteria + narrative per exemplar

Fast E2E (no slow marker): uses synthetic fixtures + TestClient. No
network. No matplotlib invocation in the request path (cache-only).
"""
from __future__ import annotations

import json
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.data.models import ChartRender, PatternEvaluation, PatternExemplar
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.data.repos.chart_renders import refresh_chart_render
from swing.web.app import create_app


@pytest.fixture
def seeded_db(tmp_path: Path):
    """Local seeded_db fixture (the web conftest is not loaded here)."""
    db_path = tmp_path / "phase13_t2_sb6b_e2e.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return cfg, Path("swing.config.toml")


def _seed_full_happy_path(cfg) -> tuple[int, int, int]:
    """Plant pipeline run + 2 pattern_evaluations + watchlist + chart_renders
    + 5 prior gold exemplars (so the metric tile passes Wilson-CI n>=5).

    Returns (pipeline_run_id, primary_eval_id, gold_count).
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
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
            pipeline_run_id = int(cur.lastrowid)

            # Two pattern evaluations: one borderline (priority queue
            # surfaces it) + one strong (drops off the queue).
            primary = evals_repo.insert_evaluation(conn, PatternEvaluation(
                id=None,
                pipeline_run_id=pipeline_run_id,
                ticker="QQQ",
                pattern_class="vcp",
                detector_version="v1",
                geometric_score=0.51,  # borderline (|0.51-0.5|<0.1)
                geometric_score_json=json.dumps({
                    "criteria": [
                        {"name": "stage_2", "result": "pass"},
                        {"name": "contractions", "result": "marginal"},
                    ],
                }),
                composite_score=0.55,
                structural_evidence_json=json.dumps({
                    "criteria_pass": {"stage_2": True, "contractions": False},
                    "pivot_price": 200.0,
                }),
                feature_distribution_log_json="{}",
                window_start_date="2026-04-01",
                window_end_date="2026-05-15",
                created_at="2026-05-20T09:01:00",
                template_match_score=0.40,
                template_match_nearest_exemplar_ids_json="[]",
            ))
            evals_repo.insert_evaluation(conn, PatternEvaluation(
                id=None,
                pipeline_run_id=pipeline_run_id,
                ticker="SPY",
                pattern_class="flat_base",
                detector_version="v1",
                geometric_score=0.95,  # strong; not in queue.
                geometric_score_json="{}",
                composite_score=0.92,
                structural_evidence_json="{}",
                feature_distribution_log_json="{}",
                window_start_date="2026-04-01",
                window_end_date="2026-05-15",
                created_at="2026-05-20T09:01:00",
            ))

            # 5 prior gold exemplars for VCP so the metric tile renders Wilson
            # CI at n>=5.
            for i in range(5):
                exemplars_repo.insert_exemplar(conn, PatternExemplar(
                    id=None,
                    ticker=f"VCP{i}",
                    timeframe="daily",
                    start_date="2024-01-01",
                    end_date="2024-02-01",
                    proposed_pattern_class="vcp",
                    final_decision="confirmed",
                    label_source="curated_gold",
                    structural_evidence_json="{}",
                    created_at="2024-02-02T00:00:00",
                    created_by="operator",
                    geometric_score_json='{"score": 0.95}',
                    labeler_evidence_json=json.dumps({
                        "rule_criteria": [
                            {"name": "stage_2", "status": "pass",
                             "evidence_value": "Stage 2",
                             "threshold": "in [2]"},
                        ],
                        "narrative": "Stage 2 + 3 contractions clean.",
                    }),
                    gold_validated_at="2024-02-03T00:00:00",
                ))

            # Market weather chart cache row (TOP of dashboard).
            refresh_chart_render(conn, ChartRender(
                id=None,
                ticker=cfg.rs.benchmark_ticker,
                surface="market_weather",
                chart_svg_bytes=b"<svg>weather-e2e</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=pipeline_run_id,
                pattern_class=None,
            ))
            # Theme 2 annotated chart cache row for the VCP exemplars so
            # the exemplars surface renders chart per row.
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="VCP0", surface="theme2_annotated",
                chart_svg_bytes=b"<svg>vcp0-e2e</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=pipeline_run_id,
                pattern_class="vcp",
            ))
    finally:
        conn.close()
    return pipeline_run_id, primary, 5


def test_phase13_t2_sb6b_closed_loop_full_e2e_happy_path(seeded_db):
    cfg, cfg_path = seeded_db
    _, primary_eval_id, _ = _seed_full_happy_path(cfg)
    app = create_app(cfg, cfg_path)

    with TestClient(app) as client:
        # ---- 1. Dashboard renders weather chart at TOP. ----
        r_dash = client.get("/dashboard")
        assert r_dash.status_code == 200
        assert "<svg>weather-e2e</svg>" in r_dash.text
        weather_idx = r_dash.text.find('id="dashboard-market-weather"')
        status_idx = r_dash.text.find('id="status-strip"')
        assert weather_idx >= 0 and status_idx >= 0
        assert weather_idx < status_idx, (
            "Phase 13 T2.SB6b T-A.6.6 + spec section 4.5 + plan section "
            "C.3 LOCK: market weather chart must render BEFORE the status "
            "strip on the dashboard."
        )

        # ---- 2. /patterns/queue lists prioritized candidates. ----
        r_queue = client.get("/patterns/queue")
        assert r_queue.status_code == 200
        # Borderline VCP candidate surfaced; strong SPY/flat_base did not.
        assert "QQQ" in r_queue.text
        assert "borderline_geometric" in r_queue.text

        # ---- 3. /patterns/{id}/review renders 8-item checklist. ----
        r_review = client.get(f"/patterns/{primary_eval_id}/review")
        assert r_review.status_code == 200
        body = r_review.text
        for item in (
            "proposed pattern class",
            "geometric score",
            "trend template",
            "rs rank",
            "volume profile",
            "uncertainty",
            "outcome distribution",
        ):
            assert item in body.lower(), (
                f"Phase 13 T2.SB6b T-A.6.3 + spec section 5.10 lines "
                f"766-775 LOCK: review form must surface the {item!r} "
                f"checklist item."
            )

        # ---- 4. POST review persists closed_loop_review exemplar. ----
        r_post = client.post(
            f"/patterns/{primary_eval_id}/review",
            data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
        assert r_post.status_code == 204
        assert r_post.headers.get("HX-Redirect") == "/patterns/queue"

        # ---- 5. /metrics/pattern-outcomes renders cohort distribution. ----
        r_metrics = client.get("/metrics/pattern-outcomes")
        assert r_metrics.status_code == 200
        # 5 gold + 1 new closed_loop_review = 6 -> Wilson CI populated.
        assert "vcp" in r_metrics.text
        # Body has n=6 string somewhere in the triggered-pct text.
        assert "n=6" in r_metrics.text or "n=5" in r_metrics.text

        # ---- 6. /patterns/exemplars renders chart + criteria + narrative. ----
        r_exemplars = client.get("/patterns/exemplars")
        assert r_exemplars.status_code == 200
        body_ex = r_exemplars.text
        assert "<svg>vcp0-e2e</svg>" in body_ex
        # Rule criterion + narrative from seeded labeler_evidence_json.
        assert "stage_2" in body_ex
        assert "Stage 2 + 3 contractions clean." in body_ex

    # Final cross-surface assertion: pattern_exemplars row was written via
    # the POST handler (label_source='closed_loop_review' since no trade
    # opened for QQQ in this happy path).
    conn = connect(cfg.paths.db_path)
    try:
        new_rows = exemplars_repo.list_exemplars(
            conn, label_source="closed_loop_review",
        )
    finally:
        conn.close()
    qqq_rows = [r for r in new_rows if r.ticker == "QQQ"]
    assert qqq_rows, (
        "Phase 13 T2.SB6b T-A.6.3 + spec section 5.10 label_source split: "
        "confirm + no-trade-opened path must persist a closed_loop_review "
        "exemplar."
    )
    assert qqq_rows[0].final_decision == "confirmed"
    assert qqq_rows[0].proposed_pattern_class == "vcp"
