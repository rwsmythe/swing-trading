from __future__ import annotations
import pytest
from tests.pipeline.conftest_temporal import (  # noqa
    tmp_db_v22, _build_bars, _StubOhlcvCache, _drive_detect,
    _seed_aplus_watch_skip_candidates_and_run)


def test_lever1_dormant_default_no_cap_no_audit(tmp_db_v22):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=("AAA",), watch=("W1", "W2", "W3"), skip=())
    assert cfg.pipeline.detect_watch_pool_cap is None     # dormant default
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    got = {r[0] for r in conn.execute(
        "SELECT DISTINCT ticker FROM pattern_evaluations").fetchall()}
    assert got == {"AAA", "W1", "W2", "W3"}               # uncapped
    assert not [w for w in warnings if w.get("dropped_count")]  # no cap audit


def test_lever1_active_cap_audit_accuracy(tmp_db_v22):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=("AAA",), watch=("W1", "W2", "W3"), skip=())
    cfg.pipeline.detect_watch_pool_cap = 1                 # cap watch to 1
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    audit = next(w for w in warnings
                 if w["step"] == "pattern_detect" and "dropped_count" in w)
    assert audit["expected_detect_pool"] == 4             # 1 aplus + 3 watch
    assert audit["actual_pool"] == 2                      # 1 aplus + 1 watch
    assert audit["dropped_count"] == 2                    # 4 - 2
    assert audit["dropped_bucket"] == "watch"
    assert audit["expected_pool_by_bucket"] == {"aplus": 1, "watch": 3}
    assert audit["actual_pool_by_bucket"] == {"aplus": 1, "watch": 1}


def test_lever1_cap_must_be_positive():
    # Codex R2 MAJOR: cap=0 is rejected by the real frozen PipelineConfig
    # (None = uncapped; >=1 = a real cap). Prevents the cap from colliding with
    # the empty-pool audit.
    from swing.config import PipelineConfig
    with pytest.raises(ValueError):
        PipelineConfig(detect_watch_pool_cap=0)
    assert PipelineConfig(detect_watch_pool_cap=1).detect_watch_pool_cap == 1
    assert PipelineConfig().detect_watch_pool_cap is None
