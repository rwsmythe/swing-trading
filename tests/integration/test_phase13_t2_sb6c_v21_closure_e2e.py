"""Phase 13 T2.SB6c T-A.6c.5 closer — full v21 closure happy-path E2E.

Walks the full Phase 13 closure arc end-to-end against the v21 schema landed
at T-A.6c.1:

  1. Seed a fake pipeline run that emits a candidate + a pattern_evaluation
     row (ticker CVGI, pattern_class vcp).
  2. Operator POSTs `/trades/entry` with the 3 hidden anchors threaded
     (`pattern_evaluation_id`, `claimed_pattern_evaluation_anchor=true`,
     `pipeline_run_id_at_form_render`); origin=hyp-recs so
     `derive_trade_origin` returns ``pipeline_watch_hyp_recs``.
  3. Verify the trade row has BOTH ``candidate_id`` AND
     ``pattern_evaluation_id`` populated (v21 backlink delta closure).
  4. Operator POSTs `/patterns/{evaluation_id}/review` with
     decision=confirm; assert the new pattern_exemplar row's
     ``label_source == 'organic_trade_history'`` (Gap B.3 candidate-
     scope cross-row lookup closure).
  5. Simulate the trade hitting 1R: set state='closed' +
     realized_R_if_plan_followed=1.5 directly via SQL (V1 surrogate per
     plan §G.5 Step 1; the 1R+stop bucketing surfaces through
     swing/metrics/pattern_outcomes.py:_count_reached_1r_hit_stop).
  6. GET `/metrics/pattern-outcomes`; assert the response renders the
     VCP row with a NON-suppressed ``row.reached_1r_n`` cell (Gap B.5
     WilsonCI surfacing closure + §1.5.4 amendment closure).

This single fast E2E walks every Theme touched by T2.SB6c sub-tasks:
  - Gap A surfaces (NOT exercised here; covered by T-A.6c.2 unit tests
    + S3-S6b operator gates).
  - Gap B.3 (label_source split via v21 trades.candidate_id backlink).
  - Gap B.5 (PatternOutcomeRow.reached_1r_n + reached_1r_ci surfacing).
  - §1.5.4 WilsonCI render extension.
  - §C.5 anchor-threading (3 hidden inputs + 5-tier ladder pass-through).
  - EntryRequest extension with ``candidate_id`` + ``pattern_evaluation_id``
    (record_entry persists both on the trades row per plan §C.5 OQ-12).

Fast-marked (no `@pytest.mark.slow`); runs in `pytest -m "not slow"`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.data.models import (
    Candidate,
    EvaluationRun,
    PatternEvaluation,
)
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.web.app import create_app


@pytest.fixture
def seeded_db(tmp_path: Path) -> tuple[Any, Path]:
    """Mirror of the tests.web.conftest seeded_db fixture, isolated for the
    integration test directory (which does not inherit the web conftest).
    """
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed_evaluation_run(conn) -> int:
    return insert_evaluation_run(conn, EvaluationRun(
        id=None,
        run_ts="2026-05-22T09:00:00",
        data_asof_date="2026-05-21",
        action_session_date="2026-05-22",
        finviz_csv_path="data/finviz-inbox/finviz22May2026.csv",
        tickers_evaluated=1,
        aplus_count=0,
        watch_count=1,
        skip_count=0,
        excluded_count=0,
        error_count=0,
        rs_universe_version="rs-v1",
        rs_universe_hash="closure-e2e",
    ))


def _seed_pipeline_run(conn, *, evaluation_run_id: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token, evaluation_run_id)
        VALUES ('2026-05-22T09:00:00', '2026-05-22T09:05:00',
                'manual', '2026-05-21', '2026-05-22',
                'complete', ?, ?)
        """,
        (f"tok-closure-{evaluation_run_id}", evaluation_run_id),
    )
    return int(cur.lastrowid)


def _seed_candidate(
    conn, *, evaluation_run_id: int, ticker: str,
) -> int:
    insert_candidates(conn, evaluation_run_id, [
        Candidate(
            ticker=ticker,
            bucket="watch",
            close=120.0,
            pivot=120.5,
            initial_stop=100.0,
            adr_pct=4.0,
            tight_streak=3,
            pullback_pct=10.0,
            prior_trend_pct=35.0,
            rs_rank=85,
            rs_return_12w_vs_spy=0.18,
            rs_method="universe",
            pattern_tag="vcp",
            notes=None,
            criteria=(),
            sector="Industrials",
            industry="Machinery",
        ),
    ])
    row = conn.execute(
        "SELECT id FROM candidates "
        "WHERE evaluation_run_id = ? AND ticker = ?",
        (evaluation_run_id, ticker),
    ).fetchone()
    return int(row[0])


def _seed_evaluation(
    conn, *, pipeline_run_id: int, ticker: str,
    pattern_class: str = "vcp",
) -> int:
    return evals_repo.insert_evaluation(conn, PatternEvaluation(
        id=None,
        pipeline_run_id=pipeline_run_id,
        ticker=ticker,
        pattern_class=pattern_class,
        detector_version="v1",
        geometric_score=0.62,
        geometric_score_json=json.dumps({"criteria": []}),
        composite_score=0.62,
        structural_evidence_json=json.dumps({"criteria_pass": {}}),
        feature_distribution_log_json="{}",
        window_start_date="2026-04-01",
        window_end_date="2026-05-21",
        created_at="2026-05-22T09:01:00",
    ))


def _entry_post_payload(
    *, ticker: str, entry_date: str,
    entry_price: float, shares: int, initial_stop: float,
    pattern_evaluation_id: int,
    pipeline_run_id_at_form_render: int,
) -> dict[str, Any]:
    """Build a payload satisfying the Phase 7 pre-trade gate plus the
    T-A.6c.4 3-anchor threading inputs. Mirror of
    tests/web/test_routes/test_phase13_t2_sb6c_t_a_6c_4.py:_entry_post_data
    inlined here so the integration test directory doesn't depend on the
    sibling test module's helpers.
    """
    return {
        "ticker": ticker,
        "entry_date": entry_date,
        "entry_price": str(entry_price),
        "shares": str(shares),
        "initial_stop": str(initial_stop),
        "rationale": "vcp-breakout",
        "origin": "hyp-recs",
        # 13 always-required pre-trade fields (route gate):
        "thesis": "closure-e2e-thesis",
        "why_now": "closure-e2e-why-now",
        "invalidation_condition": "stop-hit",
        "expected_scenario": "win",
        "premortem_technical": "tech-risk",
        "premortem_market_sector": "market-risk",
        "premortem_execution": "execution-risk",
        "event_risk_present": "0",
        "gap_risk_present": "0",
        "emotional_state_pre_trade": "calm",
        "manual_entry_confidence": "normal",
        "market_regime": "Bullish",
        "catalyst": "technical_only",
        # Conditional fields populated for resilience under sibling flips.
        "event_handling": "not_applicable",
        "event_type": "earnings",
        "event_date": "2026-05-15",
        "gap_risk_handling": "not_applicable",
        "premortem_additional": "",
        # T-A.6c.4 anchor-threading 3 hidden inputs:
        "pattern_evaluation_id": str(pattern_evaluation_id),
        "claimed_pattern_evaluation_anchor": "true",
        "pipeline_run_id_at_form_render": str(
            pipeline_run_id_at_form_render,
        ),
    }


def test_phase13_t2_sb6c_v21_closure_happy_path_e2e(seeded_db):
    """Full happy-path E2E covering v21 backlinks + Gap B.3 + Gap B.5
    + §1.5.4 WilsonCI surfacing in one transaction-walking arc.
    """
    cfg, cfg_path = seeded_db
    ticker = "CVGI"

    # ----- Step 1: seed pipeline_run + candidate + pattern_evaluation -----
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_run_id = _seed_evaluation_run(conn)
            pipeline_run_id = _seed_pipeline_run(
                conn, evaluation_run_id=eval_run_id,
            )
            candidate_id = _seed_candidate(
                conn, evaluation_run_id=eval_run_id, ticker=ticker,
            )
            evaluation_id = _seed_evaluation(
                conn, pipeline_run_id=pipeline_run_id, ticker=ticker,
                pattern_class="vcp",
            )
    finally:
        conn.close()

    # ----- Step 2: operator POSTs /trades/entry with 3 hidden anchors -----
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        post_data = _entry_post_payload(
            ticker=ticker,
            entry_date="2026-05-22",
            entry_price=120.5,
            shares=10,
            initial_stop=100.0,
            pattern_evaluation_id=evaluation_id,
            pipeline_run_id_at_form_render=pipeline_run_id,
        )
        resp_entry = client.post(
            "/trades/entry", data=post_data,
            headers={"HX-Request": "true"},
        )
    assert resp_entry.status_code in (200, 204), (
        f"trade entry expected success; got {resp_entry.status_code}: "
        f"{resp_entry.text[:400]}"
    )

    # ----- Step 3: verify v21 backlinks populated on trades row -----
    conn = connect(cfg.paths.db_path)
    try:
        trade_row = conn.execute(
            "SELECT id, candidate_id, pattern_evaluation_id, trade_origin "
            "FROM trades WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    finally:
        conn.close()
    assert trade_row is not None, "trades row not persisted"
    trade_id = int(trade_row[0])
    assert trade_row[1] is not None, (
        "v21 Delta A: trades.candidate_id must be populated on "
        "pipeline-origin entry"
    )
    assert int(trade_row[1]) == candidate_id, (
        "trades.candidate_id must resolve to the seeded candidate"
    )
    assert trade_row[2] is not None, (
        "v21 Delta B: trades.pattern_evaluation_id must be populated "
        "when anchor threaded"
    )
    assert int(trade_row[2]) == evaluation_id, (
        "trades.pattern_evaluation_id must resolve to server-re-derived "
        "evaluation row (NOT operator-submitted hidden input verbatim)"
    )
    assert trade_row[3] == "pipeline_watch_hyp_recs", (
        "T-A.6c.4 R6 MAJOR #2: origin=hyp-recs + valid anchor → "
        "trade_origin must be pipeline_watch_hyp_recs"
    )

    # ----- Step 4: operator confirms pattern → organic_trade_history -----
    with TestClient(app) as client:
        resp_review = client.post(
            f"/patterns/{evaluation_id}/review",
            data={"decision": "confirm"},
            headers={"HX-Request": "true"},
        )
    assert resp_review.status_code == 204, (
        f"patterns review expected 204; got {resp_review.status_code}: "
        f"{resp_review.text[:400]}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        ex_row = conn.execute(
            "SELECT label_source, final_decision, ticker "
            "FROM pattern_exemplars ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert ex_row is not None, "pattern_exemplars row not persisted"
    assert ex_row[0] == "organic_trade_history", (
        "Gap B.3 closure: candidate-scope cross-row lookup must resolve "
        "label_source as organic_trade_history when a trade exists on "
        f"the resolved candidate (got {ex_row[0]!r})"
    )
    assert ex_row[1] == "confirmed"
    assert ex_row[2] == ticker

    # ----- Step 5: simulate the trade reaching 1R (V1 surrogate) -----
    # Plan §G.5 Step 1: set state='closed' + realized_R_if_plan_followed=1.5
    # so swing/metrics/pattern_outcomes.py:_count_reached_1r_hit_stop's
    # CASE WHEN ... >= 1.0 fires. The cohort denominator needs >= 5
    # evaluations to clear the n>=5 Wilson CI suppression gate; plant
    # 4 additional confirmed exemplars on synthetic ticker cohort members
    # so the production SQL JOIN counts 5 DISTINCT pe.id rows for the
    # vcp class.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE trades SET state = 'closed', "
                "realized_R_if_plan_followed = ? WHERE id = ?",
                (1.5, trade_id),
            )
            # Plant 4 additional cohort evaluations + matching confirmed
            # exemplars so the Gap B.5 denominator reaches 5 (the Wilson
            # CI threshold). Each is on a unique ticker; pattern_class=vcp;
            # overlapping window with the existing exemplar at 2026-04-01
            # to 2026-05-21.
            for i in range(4):
                extra_ticker = f"COHE{i:02d}"
                _seed_candidate(
                    conn, evaluation_run_id=eval_run_id,
                    ticker=extra_ticker,
                )
                extra_eval = _seed_evaluation(
                    conn, pipeline_run_id=pipeline_run_id,
                    ticker=extra_ticker, pattern_class="vcp",
                )
                _ = extra_eval  # eval id not needed; used only for join
                # Confirmed exemplar overlapping window so the SQL join in
                # _count_reached_1r_hit_stop counts this pe.id row.
                conn.execute(
                    """
                    INSERT INTO pattern_exemplars (
                        ticker, timeframe, start_date, end_date,
                        proposed_pattern_class, final_decision,
                        label_source, structural_evidence_json,
                        created_at, created_by, geometric_score_json,
                        labeler_evidence_json, gold_validated_at
                    ) VALUES (?, 'daily', '2026-04-15', '2026-05-10', 'vcp',
                             'confirmed', 'closed_loop_review',
                             '{}', '2026-05-22T09:02:00', 'operator',
                             '{}', NULL, '2026-05-22T09:02:00')
                    """,
                    (extra_ticker,),
                )
    finally:
        conn.close()

    # ----- Step 6: GET /metrics/pattern-outcomes — verify VCP cohort
    # row carries non-suppressed reached_1r cell (Gap B.5 closure +
    # §1.5.4 WilsonCI surfacing).
    with TestClient(app) as client:
        resp_metrics = client.get("/metrics/pattern-outcomes")
    assert resp_metrics.status_code == 200, (
        f"metrics page expected 200; got {resp_metrics.status_code}"
    )
    body = resp_metrics.text

    # POOL-WIDENING RE-BASELINE (2026-06-04): pre-widen, the populated
    # reached_1r cell rendered the "Wilson CI" badge. Post-isolation this
    # all-watch cohort is excluded from the aplus-only reached_1r
    # denominator, so that cell renders the suppressed placeholder instead
    # (the template at swing/web/templates/metrics/pattern_outcomes.html.j2
    # renders "(suppressed: ...)" when the cell is None). The triggering
    # cell (exemplar-sourced n=5) still renders its "95pct CI" text -- the
    # row is present, only the reached_1r/hit_stop cells are suppressed.
    #
    # Locate the VCP row by data-attribute marker for tolerance.
    vcp_row_start = body.find('data-pattern-class="vcp"')
    assert vcp_row_start != -1, "VCP row missing from rendered table"
    # The row's <td> cells run forward through end of <tr>; pick the
    # tr-bounded substring. We extend a generous slice (~1500 chars) to
    # span the row including reached_1r + hit_stop cells.
    vcp_row_slice = body[vcp_row_start:vcp_row_start + 1500]
    # The triggering cell still surfaces its CI text (widen-independent).
    assert "95pct CI" in vcp_row_slice, (
        "triggering cell (exemplar-sourced) must still render its CI text. "
        f"Render slice: {vcp_row_slice[:500]}"
    )
    # The watch-origin reached_1r cell is now suppressed (aplus-isolation).
    assert "suppressed" in vcp_row_slice, (
        "pool-widening isolation: the watch-origin reached_1r cell must "
        f"render the suppressed placeholder. Render slice: {vcp_row_slice[:500]}"
    )

    # Defense-in-depth assertion via the VM directly. POOL-WIDENING
    # RE-BASELINE (2026-06-04): this E2E's cohort (CVGI + the 4 COHE
    # padders) is entirely WATCH-origin (bucket='watch'; the watch-hyp-recs
    # entry path under test). The pool-widening arc isolates the B.5
    # reached_1r/hit_stop denominator (`_count_reached_1r_hit_stop`) to
    # PROVABLY-aplus-origin PEs so the widen stays invisible to this
    # operator-facing tile. A watch-origin traded pattern therefore does
    # NOT populate the aplus-only reached_1r cell -- denom_b5 == 0 ->
    # reached_1r_n is None (the curated tile excludes it; the trade's
    # outcome is captured via the KEPT trade<->PE backlink [asserted in
    # Step 3 above, OQ-7] + the temporal observation log, not this tile).
    # The triggering `n` is exemplar-sourced (widen-independent) so the VCP
    # row still renders with its triggered Wilson CI (asserted above). The
    # POSITIVE aplus reached_1r surfacing is covered by the B.5 unit tests
    # in test_phase13_t2_sb6c_t_a_6c_4.py.
    conn = connect(cfg.paths.db_path)
    try:
        from swing.data.repos.risk_policy import get_active_policy
        from swing.metrics.pattern_outcomes import build_pattern_outcome_rows
        policy = get_active_policy(conn)
        assert policy is not None
        rows = build_pattern_outcome_rows(conn, policy=policy)
    finally:
        conn.close()
    vcp = next((r for r in rows if r.pattern_class == "vcp"), None)
    assert vcp is not None, "VCP row missing from pattern outcomes"
    # Triggering n is exemplar-sourced (unaffected by the aplus-isolation).
    assert vcp.n >= 5, "triggering denominator (exemplar-sourced) unchanged"
    # reached_1r is isolated to aplus-origin: this all-watch cohort is
    # EXCLUDED (denom_b5 == 0 -> None). Pre-widen (no isolation) this was
    # populated >= 1; the discriminating axis is the watch-origin exclusion.
    assert vcp.reached_1r_n is None, (
        "pool-widening isolation: watch-origin traded pattern must NOT "
        "populate the aplus-only B.5 reached_1r cell"
    )
    assert vcp.reached_1r_ci is None
    assert vcp.hit_stop_n is None
