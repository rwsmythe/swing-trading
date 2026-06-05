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
