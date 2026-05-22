"""Phase 13 T2.SB6c T-A.6c.3 — review-form data completeness tests.

Gap B.1 (trend_template_state via current_stage) + Gap B.2 (volume_profile
via OHLCV archive). Per plan §G.3 Step 1a + spec §5.10.

Per CLAUDE.md NEW gotcha #12 (`date.fromisoformat()` cross-type-boundary):
malformed `window_end_date` (TEXT in pattern_evaluations) must NOT 500
the review form — VM falls back to 'undefined' + WARN logs.

Per CLAUDE.md NEW gotcha #11 (template-rendering surface audit): VM
fields must be SURFACED in the rendered template, not just populated.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import PatternEvaluation
from swing.data.repos import pattern_evaluations as evals_repo
from swing.web.app import create_app
from swing.web.view_models.patterns.review_form import (
    PatternReviewFormVM,
    VolumeProfileRow,
    build_patterns_review_form_vm,
)


# ---------------------------------------------------------------------------
# Seed helpers.
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


def _seed_eval(
    conn, *, pipeline_run_id: int, ticker: str = "AAA",
    pattern_class: str = "vcp",
    window_end_date: str = "2026-05-15",
) -> int:
    ev = PatternEvaluation(
        id=None,
        pipeline_run_id=pipeline_run_id,
        ticker=ticker,
        pattern_class=pattern_class,
        detector_version="v1",
        geometric_score=0.62,
        geometric_score_json="{}",
        composite_score=0.62,
        structural_evidence_json="{}",
        feature_distribution_log_json="{}",
        window_start_date="2026-04-01",
        window_end_date=window_end_date,
        created_at="2026-05-20T09:01:00",
        template_match_score=None,
        template_match_nearest_exemplar_ids_json=None,
    )
    return evals_repo.insert_evaluation(conn, ev)


def _seed_evaluation_run(conn, *, action_session_date: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs
            (run_ts, data_asof_date, action_session_date, finviz_csv_path,
             tickers_evaluated, aplus_count, watch_count, skip_count,
             excluded_count, error_count)
        VALUES (?, ?, ?, '/dev/null', 1, 1, 0, 0, 0, 0)
        """,
        (
            f"{action_session_date}T09:00:00",
            action_session_date,
            action_session_date,
        ),
    )
    return int(cur.lastrowid)


def _seed_candidate(
    conn, *, evaluation_run_id: int, ticker: str,
    bucket: str = "aplus",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO candidates
            (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
             adr_pct, rs_rank, rs_method)
        VALUES (?, ?, ?, 100.0, 105.0, 95.0, 2.0, 95, 'universe')
        """,
        (evaluation_run_id, ticker, bucket),
    )
    return int(cur.lastrowid)


def _seed_candidate_criteria_all_tt_pass(
    conn, *, candidate_id: int, count: int = 8,
):
    # Seed `count` rows of layer='trend_template', result='pass'.
    names = [
        "tt1_above_sma150", "tt2_above_sma200", "tt3_sma150_above_sma200",
        "tt4_sma200_up_at_least_1mo", "tt5_sma50_above_sma150_and_sma200",
        "tt6_above_sma50", "tt7_30pct_above_52w_low",
        "tt8_within_25pct_52w_high",
    ]
    for i in range(min(count, 8)):
        conn.execute(
            """
            INSERT INTO candidate_criteria
                (candidate_id, criterion_name, layer, result, value, rule)
            VALUES (?, ?, 'trend_template', 'pass', '1', '1')
            """,
            (candidate_id, names[i]),
        )


# ---------------------------------------------------------------------------
# Test 1 — Gap B.1: trend_template_state populated 'stage_2' when all 8 pass.
# ---------------------------------------------------------------------------


def test_pattern_review_form_vm_populates_trend_template_state_stage_2(
    seeded_db,
):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="ABC",
                window_end_date="2026-05-15",
            )
            eval_run_id = _seed_evaluation_run(
                conn, action_session_date="2026-05-15",
            )
            cid = _seed_candidate(
                conn, evaluation_run_id=eval_run_id, ticker="ABC",
            )
            _seed_candidate_criteria_all_tt_pass(conn, candidate_id=cid)
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, cfg=cfg, candidate_id=eval_id,
            session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert vm is not None
    assert vm.trend_template_state == "stage_2"


# ---------------------------------------------------------------------------
# Test 2 — Gap B.1: 'undefined' when fewer than 8 TT criteria pass.
# ---------------------------------------------------------------------------


def test_pattern_review_form_vm_trend_template_state_undefined_when_partial(
    seeded_db,
):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="ABC",
                window_end_date="2026-05-15",
            )
            eval_run_id = _seed_evaluation_run(
                conn, action_session_date="2026-05-15",
            )
            cid = _seed_candidate(
                conn, evaluation_run_id=eval_run_id, ticker="ABC",
            )
            _seed_candidate_criteria_all_tt_pass(
                conn, candidate_id=cid, count=7,
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, cfg=cfg, candidate_id=eval_id,
            session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert vm is not None
    assert vm.trend_template_state == "undefined"


# ---------------------------------------------------------------------------
# Test 3 — Gap B.1: malformed window_end_date falls back to 'undefined' +
# does NOT raise (graceful per CLAUDE.md NEW gotcha #12).
# ---------------------------------------------------------------------------


def test_pattern_review_form_vm_malformed_window_end_date_undefined_no_500(
    seeded_db, caplog,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="ABC",
                window_end_date="not-a-date",
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        with caplog.at_level("WARNING"):
            vm = build_patterns_review_form_vm(
                conn, cfg=cfg, candidate_id=eval_id,
                session_date="2026-05-20",
            )
    finally:
        conn.close()
    assert vm is not None
    assert vm.trend_template_state == "undefined"

    # Route renders 200 (defense in depth).
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Test 4 — Gap B.1: template renders trend_template_state value.
# ---------------------------------------------------------------------------


def test_get_patterns_review_template_renders_trend_template_state(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="ABC",
                window_end_date="2026-05-15",
            )
            eval_run_id = _seed_evaluation_run(
                conn, action_session_date="2026-05-15",
            )
            cid = _seed_candidate(
                conn, evaluation_run_id=eval_run_id, ticker="ABC",
            )
            _seed_candidate_criteria_all_tt_pass(conn, candidate_id=cid)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    # The template surfaces the trend_template_state value.
    assert "stage_2" in r.text


# ---------------------------------------------------------------------------
# Test 5 — Gap B.2: VolumeProfileRow dataclass validator rejects negatives.
# ---------------------------------------------------------------------------


def test_volume_profile_row_validates_non_negative():
    # OK row.
    row = VolumeProfileRow(
        recent_30session_volume_sum=100,
        prior_50day_avg_volume=10.0,
        ratio_pct=100.0,
    )
    assert row.recent_30session_volume_sum == 100
    # Negative recent volume.
    with pytest.raises(ValueError, match="recent_30session_volume_sum"):
        VolumeProfileRow(
            recent_30session_volume_sum=-1,
            prior_50day_avg_volume=10.0,
            ratio_pct=100.0,
        )
    # Negative prior avg.
    with pytest.raises(ValueError, match="prior_50day_avg_volume"):
        VolumeProfileRow(
            recent_30session_volume_sum=100,
            prior_50day_avg_volume=-1.0,
            ratio_pct=100.0,
        )


# ---------------------------------------------------------------------------
# Test 6 — Gap B.2: volume_profile computed correctly from archive.
# Test 7 — Gap B.2: ratio_pct math.
# ---------------------------------------------------------------------------


def _write_archive_with_known_volume(
    cache_dir: Path, ticker: str, recent_vol: int, prior_vol: int,
) -> None:
    """Plant a parquet archive for `ticker` with known volumes.

    50 prior bars of ``prior_vol`` then 30 recent bars of ``recent_vol``.
    Anchored at today's last-completed-session so ``read_or_fetch_archive``
    does NOT trigger a yfinance full-refresh (which would fail in the
    network-free test env).
    """
    from datetime import datetime as _dt
    from swing.evaluation.dates import last_completed_session

    cache_dir.mkdir(parents=True, exist_ok=True)
    today = last_completed_session(_dt.now())
    dates = pd.bdate_range(end=pd.Timestamp(today), periods=80)
    volumes = [prior_vol] * 50 + [recent_vol] * 30
    closes = [100.0] * 80
    df = pd.DataFrame({
        "Open": closes,
        "High": closes,
        "Low": closes,
        "Close": closes,
        "Volume": volumes,
    }, index=dates)
    df.index.name = "Date"
    parquet_path = cache_dir / f"{ticker.upper()}.parquet"
    df.to_parquet(parquet_path)
    # Write a meta with today's refresh anchor so the 7-day weekly-refresh
    # gate does NOT fire (which would try to hit yfinance).
    import json as _json
    meta_path = cache_dir / f"{ticker.upper()}.meta.json"
    meta_path.write_text(_json.dumps({
        "last_full_refresh_date": today.isoformat(),
        "last_session_in_archive": today.isoformat(),
    }))


def test_pattern_review_form_vm_populates_volume_profile_from_archive(
    seeded_db, tmp_path,
):
    cfg, _ = seeded_db
    # Plant a known archive at cfg.paths.prices_cache_dir.
    _write_archive_with_known_volume(
        cfg.paths.prices_cache_dir, ticker="ABC",
        recent_vol=2_000_000, prior_vol=1_000_000,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="ABC",
                window_end_date="2026-05-15",
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, cfg=cfg, candidate_id=eval_id,
            session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert vm is not None
    assert vm.volume_profile is not None
    vp = vm.volume_profile
    # 30 bars at 2_000_000 each → sum = 60_000_000.
    assert vp.recent_30session_volume_sum == 60_000_000
    # 50 prior bars at 1_000_000 each → avg = 1_000_000.
    assert abs(vp.prior_50day_avg_volume - 1_000_000.0) < 1e-3


def test_pattern_review_form_vm_volume_profile_ratio_pct_math(
    seeded_db,
):
    """30 recent bars sum 60_000_000; 50 prior avg 1_000_000 (=> total
    50_000_000 prior). Ratio_pct = 100 * (60_000_000 / 30) / 1_000_000
    = 100 * 2_000_000 / 1_000_000 = 200.0 (recent avg / prior avg) OR
    per-session 100 * sum/avg/30. Spec/plan defines ratio_pct = 100 *
    recent / prior; here recent=30-day SUM, prior=50d AVG (single
    average value per day) — so ratio_pct = 100 * (sum/30) / avg =
    100 * recent_avg_per_day / prior_avg_per_day. Plant 2x recent →
    ratio_pct == 200.0.
    """
    cfg, _ = seeded_db
    _write_archive_with_known_volume(
        cfg.paths.prices_cache_dir, ticker="RTI",
        recent_vol=2_000_000, prior_vol=1_000_000,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="RTI",
                window_end_date="2026-05-15",
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, cfg=cfg, candidate_id=eval_id,
            session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert vm is not None
    assert vm.volume_profile is not None
    # Plant 2x recent vs prior — ratio_pct = 200.0.
    assert abs(vm.volume_profile.ratio_pct - 200.0) < 0.1


# ---------------------------------------------------------------------------
# Test 8 — Gap B.2: VM exposes volume_profile field on PatternReviewFormVM.
# ---------------------------------------------------------------------------


def test_pattern_review_form_vm_exposes_volume_profile_field(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="EXP",
            )
    finally:
        conn.close()
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, cfg=cfg, candidate_id=eval_id,
            session_date="2026-05-20",
        )
    finally:
        conn.close()
    assert vm is not None
    # field present on the dataclass; may be None if archive empty.
    assert hasattr(vm, "volume_profile")
    assert vm.volume_profile is None or isinstance(
        vm.volume_profile, VolumeProfileRow,
    )


# ---------------------------------------------------------------------------
# Test 9 — Gap B.2: template renders volume profile values (sparkline +
# numeric).
# ---------------------------------------------------------------------------


def test_get_patterns_review_template_renders_volume_profile(seeded_db):
    cfg, cfg_path = seeded_db
    _write_archive_with_known_volume(
        cfg.paths.prices_cache_dir, ticker="VRP",
        recent_vol=3_000_000, prior_vol=1_000_000,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = _seed_eval(
                conn, pipeline_run_id=run_id, ticker="VRP",
                window_end_date="2026-05-15",
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/patterns/{eval_id}/review")
    assert r.status_code == 200
    # Template surfaces the volume_profile values when populated.
    # Plant 3x — ratio_pct = 300.0 — render contains "300" string
    # (NEW gotcha #11 template-rendering surface audit).
    assert "300" in r.text
