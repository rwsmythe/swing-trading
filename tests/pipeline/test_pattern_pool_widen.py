from __future__ import annotations
import pytest
from tests.pipeline.conftest_temporal import (  # noqa
    tmp_db_v22, _build_bars, _StubOhlcvCache, _drive_detect,
    _seed_aplus_watch_skip_candidates_and_run)


def test_detect_pool_includes_watch_not_skip(tmp_db_v22, tmp_path):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(tmp_db_v22)
    bars = {t: _build_bars() for t in tickers}
    cache = _StubOhlcvCache(bars)
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM pattern_evaluations "
        "WHERE pipeline_run_id = 1").fetchall()
    got = {r[0] for r in rows}
    # aplus+watch enter the detect loop (1 aplus + 2 watch = 3); skip never
    # enters either path. Pre-widen (aplus-only) would yield {AAA} only.
    assert "AAA" in got and "WAT1" in got and "WAT2" in got
    assert "SKP" not in got
    assert len(got) == 3 and len(got) > 1   # > the aplus-only count of 1


def test_empty_pool_audit_uses_standardized_vocabulary(tmp_db_v22, tmp_path):
    # Skip-only pool: zero detect work on BOTH paths; the discriminator is the
    # audit SHAPE, not widen behavior.
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=(), watch=(), skip=("SKP1", "SKP2"))
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, _StubOhlcvCache({}), warnings)
    entry = next(w for w in warnings if w["step"] == "pattern_detect")
    assert entry["expected_pool"] == 2          # total candidate rows
    assert entry["expected_detect_pool"] == 0   # aplus+watch pre-cap
    assert entry["expected_pool_by_bucket"] == {"aplus": 0, "watch": 0}
    assert entry["actual_pool"] == 0
    assert entry["actual_pool_by_bucket"] == {"aplus": 0, "watch": 0}
    assert "actual_aplus_pool" not in entry     # the removed key


def test_watch_detection_tags_bucket_watch(tmp_db_v22, tmp_path):
    import json
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=(), watch=("WAT1",), skip=())
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    _drive_detect(conn, cfg, lease, eval_run_id, cache, [])
    rows = conn.execute(
        "SELECT finviz_screen_state FROM pattern_detection_events "
        "WHERE ticker='WAT1'").fetchall()
    assert rows, "widened path must emit a detection for the watch ticker"
    assert any(json.loads(r[0]).get("bucket") == "watch" for r in rows)
    # Pre-isolation discriminator: aplus-only path emits ZERO rows for WAT1.


def test_bucket_flip_first_detection_wins(tmp_db_v22, tmp_path):
    import json
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run)
    from swing.data.models import Candidate, EvaluationRun
    from tests.pipeline.conftest_temporal import _FakeLease, _cfg
    conn, db_path = tmp_db_v22
    cache = _StubOhlcvCache({"FLP": _build_bars()})
    asof, session = "2026-05-19", "2026-05-20"   # SHARED by both runs

    def _mk(bucket):
        return Candidate(
            ticker="FLP", bucket=bucket, close=15.0, pivot=15.1,
            initial_stop=13.5, adr_pct=2.5, tight_streak=3, pullback_pct=5.0,
            prior_trend_pct=40.0, rs_rank=85, rs_return_12w_vs_spy=12.0,
            rs_method="universe", pattern_tag=None, notes=None,
            criteria=tuple(), sector="", industry="")

    def _seed_run(run_id, bucket, aplus_n, watch_n):
        conn.execute(
            "INSERT INTO pipeline_runs (id, started_ts, trigger, "
            "data_asof_date, action_session_date, lease_token, state) VALUES "
            "(?, ?, 'manual', ?, ?, ?, 'running')",
            (run_id, f"2026-05-20T18:0{run_id}:00", asof, session,
             f"tok{run_id}"))
        er = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts=f"2026-05-20T18:0{run_id}:00", data_asof_date=asof,
            action_session_date=session, finviz_csv_path=None,
            tickers_evaluated=1, aplus_count=aplus_n, watch_count=watch_n,
            skip_count=0, excluded_count=0, error_count=0))
        insert_candidates(conn, er, [_mk(bucket)])
        conn.execute("UPDATE pipeline_runs SET evaluation_run_id=? WHERE id=?",
                     (er, run_id))
        conn.commit()
        return er

    cfg = _cfg(db_path.parent, db_path)
    # Run 1: FLP bucket=watch (the FIRST detection).
    er1 = _seed_run(1, "watch", 0, 1)
    _drive_detect(conn, cfg, _FakeLease(db_path, 1, asof), er1, cache, [])
    # _build_bars() triggers >=1 detector, so FLP yields one PDE per
    # pattern_class (the unique key includes pattern_class). Capture the count.
    n1 = conn.execute(
        "SELECT COUNT(*) FROM pattern_detection_events "
        "WHERE ticker='FLP'").fetchone()[0]
    assert n1 >= 1
    # Close run 1 (the partial unique index allows only one 'running' run).
    conn.execute(
        "UPDATE pipeline_runs SET state='complete', "
        "finished_ts='2026-05-20T18:30:00' WHERE id=1")
    conn.commit()
    # Run 2: FLP bucket=aplus, SAME detection_date (= action_session_date).
    er2 = _seed_run(2, "aplus", 1, 0)
    _drive_detect(conn, cfg, _FakeLease(db_path, 2, asof), er2, cache, [])
    rows = conn.execute(
        "SELECT finviz_screen_state FROM pattern_detection_events "
        "WHERE ticker='FLP'").fetchall()
    # First-detection-wins: run 2's aplus re-detection adds NO rows (the
    # bucket-agnostic unique index (source,ticker,detection_date,pattern_class)
    # + SELECT-then-skip), and EVERY locked detection keeps run 1's watch
    # bucket. Pre-widen, run 1 would skip FLP (non-aplus) and run 2 would
    # lock 'aplus'; the widened path locks 'watch'.
    assert len(rows) == n1                               # no duplicate rows
    assert all(json.loads(r[0])["bucket"] == "watch" for r in rows)
