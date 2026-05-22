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
            # Per T-A.6c.3 Gap B.6: criterion 3 is now weather-state-aware;
            # plant an EARLY Bullish weather_runs row so the same-status
            # JOIN matches all the gold exemplars seeded below.
            conn.execute(
                """
                INSERT INTO weather_runs
                    (run_ts, asof_date, ticker, status, close)
                VALUES ('2024-01-01T09:00:00', '2024-01-01', 'QQQ',
                        'Bullish', 400.0)
                """
            )
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
            # Per T-A.6c.3 Gap B.6: criterion 3 is now weather-state-aware;
            # plant a current Bullish weather_runs row so the conservative
            # no-op-when-no-weather guard doesn't fire.
            conn.execute(
                """
                INSERT INTO weather_runs
                    (run_ts, asof_date, ticker, status, close)
                VALUES ('2026-05-20T09:00:00', '2026-05-19', 'QQQ',
                        'Bullish', 400.0)
                """
            )
            # Empty pattern_exemplars => all 5 detector classes < threshold
            # of 5 same-status confirmed exemplars => underrepresented.
            # geo 0.80 -> NOT borderline; no template -> NOT disagreement;
            # NOT in failed-near-miss band. Falls through to criterion 3.
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


# ===========================================================================
# Phase 13 T2.SB6c T-A.6c.3 — Gap B.6 weather-state-aware criterion 3 tests.
#
# Per spec §5.10 line 799: "low historical exemplar count for current weather
# state". V1 prior implementation used min_count_threshold proxy without
# weather; T-A.6c.3 extends to read the current weather status (via
# weather_runs) + count confirmed exemplars whose labeling-time weather
# status (at-or-before JOIN on weather_runs) matches.
# ===========================================================================


def _seed_weather_run(
    conn, *, run_ts: str, asof_date: str, status: str, ticker: str = "QQQ",
):
    conn.execute(
        """
        INSERT INTO weather_runs
            (run_ts, asof_date, ticker, status, close)
        VALUES (?, ?, ?, ?, 400.0)
        """,
        (run_ts, asof_date, ticker, status),
    )


def _seed_exemplar(
    conn,
    *,
    pattern_class: str,
    final_decision: str = "confirmed",
    label_source: str = "curated_gold",
    created_at: str,
    ticker: str = "AAA",
):
    conn.execute(
        """
        INSERT INTO pattern_exemplars
            (ticker, timeframe, start_date, end_date,
             proposed_pattern_class, final_decision, label_source,
             structural_evidence_json, created_at, created_by,
             final_pattern_class,
             labeler_evidence_json)
        VALUES (?, 'daily', '2024-01-01', '2024-02-01', ?, ?, ?,
                '{}', ?, 'operator', NULL, '{}')
        """,
        (ticker, pattern_class, final_decision, label_source, created_at),
    )


def test_prioritize_candidates_weather_state_aware_underrepresented(
    seeded_db_with_run,
):
    """Gap B.6 — when current weather is Bullish and class X has 0 confirmed
    Bullish-labeled exemplars (while other classes have many), class X gets
    underrepresented_regime priority.
    """
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Current weather: Bullish (most recent run).
            _seed_weather_run(
                conn, run_ts="2026-05-20T09:00:00",
                asof_date="2026-05-19", status="Bullish",
            )
            # Earlier weather: Caution.
            _seed_weather_run(
                conn, run_ts="2024-01-01T09:00:00",
                asof_date="2024-01-01", status="Caution",
            )
            # 5+ Caution-labeled vcp confirmed exemplars (Bullish count = 0
            # for vcp). Created_at AFTER the earlier Caution weather run +
            # BEFORE the new Bullish run.
            for i in range(7):
                _seed_exemplar(
                    conn, pattern_class="vcp",
                    created_at="2024-02-01T09:00:00",
                    ticker=f"V{i}",
                )
            # Seed 5+ Caution-labeled exemplars for all OTHER classes too
            # so they aren't underrepresented under non-weather count.
            for cls in (
                "flat_base", "cup_with_handle",
                "high_tight_flag", "double_bottom_w",
            ):
                for i in range(7):
                    _seed_exemplar(
                        conn, pattern_class=cls,
                        created_at="2024-02-01T09:00:00",
                        ticker=f"{cls[:2].upper()}{i}",
                    )
            # Insert one Bullish-confirmed exemplar for flat_base AFTER the
            # Bullish weather run, so flat_base is NOT underrepresented for
            # current Bullish status.
            with conn:
                pass
            conn.execute(
                """
                INSERT INTO weather_runs
                    (run_ts, asof_date, ticker, status, close)
                VALUES ('2026-05-21T09:00:00', '2026-05-21', 'QQQ',
                        'Bullish', 401.0)
                """
            )
            for i in range(7):
                _seed_exemplar(
                    conn, pattern_class="flat_base",
                    created_at="2026-05-22T09:00:00",
                    ticker=f"FB{i}",
                )
            # Candidate: vcp, geometric 0.80 (not borderline, no template,
            # not failed-near-miss).
            _insert_eval(
                conn, pipeline_run_id=run_id, ticker="UND",
                pattern_class="vcp",
                geometric_score=0.80,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(
            conn, top_k=20, benchmark_ticker="QQQ",
        )
    finally:
        conn.close()
    by_ticker = {p.ticker: p for p in priorities}
    assert "UND" in by_ticker
    assert by_ticker["UND"].priority_reason == "underrepresented_regime"


def test_prioritize_candidates_weather_state_aware_not_underrepresented(
    seeded_db_with_run,
):
    """Gap B.6 — when current weather is Bullish and class X has 5+ confirmed
    Bullish-labeled exemplars, class X is NOT underrepresented_regime.

    Discriminating partner to the above: same setup minus the vcp/flat_base
    asymmetry — vcp has many Bullish-labeled confirmed exemplars.
    """
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Current weather: Bullish.
            _seed_weather_run(
                conn, run_ts="2026-05-20T09:00:00",
                asof_date="2026-05-19", status="Bullish",
            )
            # 7 Bullish-labeled vcp confirmed exemplars (created AFTER the
            # Bullish weather run).
            for i in range(7):
                _seed_exemplar(
                    conn, pattern_class="vcp",
                    created_at="2026-05-22T09:00:00",
                    ticker=f"V{i}",
                )
            # Seed 0 confirmed for all OTHER classes (so they ARE
            # underrepresented for current Bullish — but the test asserts
            # vcp specifically is NOT). The candidate has high enough
            # geometric_score to avoid criteria 1, 2, 4.
            _insert_eval(
                conn, pipeline_run_id=run_id, ticker="OK0",
                pattern_class="vcp",
                geometric_score=0.85,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(
            conn, top_k=20, benchmark_ticker="QQQ",
        )
    finally:
        conn.close()
    by_ticker = {p.ticker: p for p in priorities}
    # vcp NOT underrepresented for current Bullish weather; the candidate
    # falls through all 4 criteria (NOT borderline, no template, no
    # near-miss, not underrepresented) => dropped.
    assert "OK0" not in by_ticker


def test_build_patterns_queue_vm_threads_benchmark_ticker_from_cfg(
    seeded_db_with_run,
):
    """Gap B.6 — `build_patterns_queue_vm(conn, cfg, ...)` reads
    `cfg.rs.benchmark_ticker` + plumbs into `prioritize_candidates`.

    Discriminating test: cfg specifies a non-default benchmark_ticker. The
    weather_runs row with that ticker drives the weather-aware criterion 3;
    a different weather_runs row with ticker='QQQ' does NOT.
    """
    cfg, _, run_id = seeded_db_with_run
    # Patch cfg.rs.benchmark_ticker to a non-default ticker using
    # dataclasses.replace (Config is frozen).
    import dataclasses
    new_rs = dataclasses.replace(cfg.rs, benchmark_ticker="SPY")
    cfg = dataclasses.replace(cfg, rs=new_rs)

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # SPY weather: Bearish (current).
            _seed_weather_run(
                conn, run_ts="2026-05-20T09:00:00",
                asof_date="2026-05-19", status="Bearish",
                ticker="SPY",
            )
            # QQQ weather: Bullish (current). Should be IGNORED because
            # benchmark_ticker=SPY.
            _seed_weather_run(
                conn, run_ts="2026-05-20T09:00:00",
                asof_date="2026-05-19", status="Bullish",
                ticker="QQQ",
            )
            # 7 SPY-Bearish-labeled vcp confirmed exemplars; 0
            # SPY-Bearish-labeled exemplars for flat_base.
            for i in range(7):
                _seed_exemplar(
                    conn, pattern_class="vcp",
                    created_at="2026-05-22T09:00:00",
                    ticker=f"V{i}",
                )
            # Candidate in flat_base (underrepresented under SPY-Bearish).
            _insert_eval(
                conn, pipeline_run_id=run_id, ticker="FLB",
                pattern_class="flat_base",
                geometric_score=0.85,
            )
    finally:
        conn.close()

    from swing.web.view_models.patterns.queue import (
        build_patterns_queue_vm,
    )
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_queue_vm(
            conn, cfg=cfg, session_date="2026-05-20", top_k=20,
        )
    finally:
        conn.close()
    by_ticker = {p.ticker: p for p in vm.candidates}
    assert "FLB" in by_ticker
    assert by_ticker["FLB"].priority_reason == "underrepresented_regime"


def test_prioritize_candidates_no_weather_row_falls_back_no_op(
    seeded_db_with_run,
):
    """Gap B.6 — when NO weather row exists, criterion 3 emits zero hits
    (conservative); the candidate falls through to other criteria or is
    dropped.

    Discriminating: NO weather_runs at all. A vcp candidate at geometric
    0.85 (no template) — would have been underrepresented_regime under
    the V1 proxy, but with weather-aware criterion 3 + no weather row,
    criterion 3 returns no hits => candidate is dropped.
    """
    cfg, _, run_id = seeded_db_with_run
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # NO weather_runs at all.
            _insert_eval(
                conn, pipeline_run_id=run_id, ticker="NWX",
                pattern_class="vcp",
                geometric_score=0.85,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        priorities = prioritize_candidates(
            conn, top_k=20, benchmark_ticker="QQQ",
        )
    finally:
        conn.close()
    by_ticker = {p.ticker: p for p in priorities}
    # No weather => criterion 3 emits zero hits => candidate dropped
    # (not borderline, no template, not near-miss).
    assert "NWX" not in by_ticker
