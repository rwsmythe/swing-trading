"""Task 4.3 — `build_watchlist` + `build_dashboard` load classifications by
`pipeline_run_id` (Bug-7-family anchor discipline).

Spec §3.5 + Bug-7-family: classification reads MUST bind to
`pipeline_runs.evaluation_run_id → pipeline_run_id`. NO `MAX(run_ts)`
patterns; NO 'latest by computed_at' fallback. Otherwise a post-pipeline
standalone `swing eval` could silently win the latest-X race and the
operator sees pattern_tags from a pipeline that didn't chart that ticker.

These tests reuse the project's `seeded_db` fixture (which provides cfg
+ schema-applied DB) and the shared `seed_pipeline_with_classification`
helper from `_pattern_classification_seed.py`.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from swing.data.db import connect

from ._pattern_classification_seed import (
    delete_all_classifications,
    seed_pipeline_with_classification,
)


def test_build_watchlist_surfaces_pattern_tag_from_pipeline_run(seeded_db):
    """Discriminating: pre-fix, vm.pattern_tags is the empty default {};
    post-fix it carries 'AAPL': 'flag (0.78)' loaded via the
    pipeline_run_id anchor."""
    from swing.web.view_models.watchlist import build_watchlist
    cfg, _ = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False
    vm = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    assert vm.pattern_tags.get("AAPL") == "flag (0.78)"


def test_build_watchlist_pattern_tags_empty_when_classification_deleted(
    seeded_db,
):
    """Compounding-confound (anchor edition): with the cache row deleted,
    pattern_tags is empty even if a NEWER evaluation_runs row exists.
    Proves the read binds to pipeline_run_id, NOT 'latest classification
    anywhere' nor 'latest eval'."""
    from swing.web.view_models.watchlist import build_watchlist
    cfg, _ = seeded_db
    run_id, _eval_id = seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    # Wipe the classification rows; seed a NEWER eval (no pipeline) — the
    # pre-fix bug surface would re-bind to the newer eval.
    conn = connect(cfg.paths.db_path)
    try:
        conn.execute(
            "DELETE FROM pipeline_pattern_classifications "
            "WHERE pipeline_run_id = ?",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO evaluation_runs (run_ts, data_asof_date, "
            "action_session_date, finviz_csv_path, tickers_evaluated, "
            "aplus_count, watch_count, skip_count, excluded_count, "
            "error_count) VALUES ('2026-04-27T00:00:00','2026-04-26',"
            "'2026-04-27', NULL, 1,1,0,0,0,0)"
        )
        conn.commit()
    finally:
        conn.close()
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False
    vm = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    assert vm.pattern_tags == {}


def test_build_watchlist_filters_below_threshold(seeded_db):
    """The display-threshold gate from spec §3.8 actually fires through
    the build path. Discriminator: with threshold=0.50, the 0.10
    classification yields no tag; with default 0.0 the same row would
    render."""
    import dataclasses
    from swing.web.view_models.watchlist import build_watchlist
    cfg, _ = seeded_db
    # Web is a frozen dataclass; replace() returns a new copy with the
    # bumped threshold. Then clone the Config with the new web.
    bumped_web = dataclasses.replace(
        cfg.web, flag_pattern_display_threshold=0.50,
    )
    cfg = dataclasses.replace(cfg, web=bumped_web)
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL", pattern="flag", confidence=0.10,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False
    vm = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    assert vm.pattern_tags == {}


def test_build_watchlist_pattern_tags_empty_when_no_pipeline_run(seeded_db):
    """Fresh-install / no-pipeline-yet path: build_watchlist must NOT crash
    when there's no completed pipeline_run; pattern_tags is the default
    empty dict."""
    from swing.web.view_models.watchlist import build_watchlist
    cfg, _ = seeded_db
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False
    vm = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    assert vm.pattern_tags == {}


def test_build_dashboard_surfaces_pattern_tag_from_pipeline_run(seeded_db):
    """Spec §1.1(4) display surface includes the dashboard, not just
    /watchlist. build_dashboard's pattern_tags must surface from the
    pipeline_run_id anchor like build_watchlist's does."""
    from swing.web.view_models.dashboard import build_dashboard
    cfg, _ = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False
    vm = build_dashboard(
        cfg=cfg, cache=cache, executor=MagicMock(), ohlcv_cache=None,
    )
    assert vm.pattern_tags.get("AAPL") == "flag (0.78)"


def test_build_dashboard_pattern_tags_empty_when_classification_deleted(
    seeded_db,
):
    """Same compounding-confound check as build_watchlist's: with no
    classification row for the anchor, pattern_tags is empty regardless
    of any newer eval row."""
    from swing.web.view_models.dashboard import build_dashboard
    cfg, _ = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path,
        ticker="AAPL", pattern="flag", confidence=0.78,
    )
    delete_all_classifications(cfg.paths.db_path)
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False
    vm = build_dashboard(
        cfg=cfg, cache=cache, executor=MagicMock(), ohlcv_cache=None,
    )
    assert vm.pattern_tags == {}
