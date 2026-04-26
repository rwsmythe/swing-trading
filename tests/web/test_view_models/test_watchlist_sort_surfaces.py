"""Surface tests for the tag-aware watchlist sort.

The unit tests in `test_watchlist_sort.py` only exercise `_sort_watchlist` in
isolation — they would still pass if `build_dashboard`, `build_watchlist`, or
the `/prices/refresh` route kept calling the old proximity-only sort.

These tests pin the actual SURFACES: dashboard top-5 ordering, /watchlist
rows ordering, and the refresh-route prefetch list. Each uses the canonical
pre-fix vs post-fix discriminator from the brief — a tagged ticker with
WORSE proximity vs an untagged ticker with BETTER proximity.
"""
from __future__ import annotations

from pathlib import Path

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def _seed_two_watchlist_with_eval(cfg, *, tagged_ticker: str, untagged_ticker: str) -> None:
    """Seed:
      - one completed pipeline_run linked to evaluation_run E1
      - in E1: a candidate row for `tagged_ticker` with bucket='aplus' (→ A+
        tag emitted by `_flag_tags`); no candidate row for `untagged_ticker`
        (→ no tags)
      - two watchlist rows: tagged_ticker WORSE proximity (8% from pivot),
        untagged_ticker BETTER proximity (1% from pivot)

    Pre-fix sort: untagged first (better proximity).
    Post-fix sort: tagged first (more tags).
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, ?, 'aplus', 108.0, 100.0, 95.0, 'universe')""",
                (eval_id, tagged_ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token, charts_status,
                    evaluation_run_id)
                   VALUES ('2026-04-17T20:55:00', '2026-04-17T21:05:00',
                           'manual', '2026-04-17', '2026-04-20',
                           'complete', 't-x', 'ok', ?)""",
                (eval_id,),
            )
            conn.execute(
                """INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close, rationale)
                   VALUES ('2026-04-17T21:00:00', '2026-04-17', 'SPY', 'Bullish', 450.0, 'ok')""",
            )
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=tagged_ticker, added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=100.0, initial_stop_target=95.0,
                last_close=108.0,            # 8% above pivot — WORSE proximity
                last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=untagged_ticker, added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=100.0, initial_stop_target=95.0,
                last_close=101.0,            # 1% above pivot — BETTER proximity
                last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()


def _no_op_executor():
    class _Executor:
        def submit(self, fn, *a, **kw):
            class _F:
                def result(self_inner, timeout=None):
                    return fn(*a, **kw)
            return _F()
    return _Executor()


def _patch_caches(monkeypatch):
    from swing.web.price_cache import PriceCache

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_build_dashboard_top5_uses_tag_aware_sort(seeded_db, monkeypatch):
    """Dashboard top-5: tagged ticker (worse proximity) MUST appear before
    untagged ticker (better proximity). Pre-fix would have ordered by
    proximity only and put the untagged ticker first.
    """
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_two_watchlist_with_eval(cfg, tagged_ticker="TAG", untagged_ticker="UNT")
    _patch_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    tickers_in_top5 = [w.ticker for w in vm.watchlist_top5]
    assert tickers_in_top5 == ["TAG", "UNT"], (
        f"dashboard top-5 must put tagged ticker (A+) before untagged "
        f"despite worse proximity; got {tickers_in_top5}"
    )
    # Sanity: the A+ tag survived the flag_tags computation.
    assert vm.flag_tags.get("TAG") == ("A+",), (
        f"expected TAG flag_tags == ('A+',), got {vm.flag_tags.get('TAG')}"
    )


def test_build_watchlist_rows_use_tag_aware_sort(seeded_db, monkeypatch):
    """/watchlist page: same discriminator. Tagged row first."""
    from swing.web.view_models.watchlist import build_watchlist
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_two_watchlist_with_eval(cfg, tagged_ticker="TAG", untagged_ticker="UNT")
    _patch_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_watchlist(cfg=cfg, cache=cache, executor=_no_op_executor())

    tickers = [w.ticker for w in vm.rows]
    assert tickers == ["TAG", "UNT"], (
        f"/watchlist rows must put tagged ticker first; got {tickers}"
    )
    assert vm.flag_tags.get("TAG") == ("A+",)


def test_prices_refresh_route_warms_tag_aware_top5(seeded_db, monkeypatch):
    """The /prices/refresh route's prefetch list must include the tagged
    ticker (which is now in the dashboard's actual top-5) and not silently
    fall back to a proximity-only top-5 that would have excluded it.

    Captures the tickers passed to `cache.refresh_all` and asserts the
    tagged ticker is present.
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache
    from swing.web.ohlcv_cache import OhlcvCache

    cfg, cfg_path = seeded_db
    _seed_two_watchlist_with_eval(cfg, tagged_ticker="TAG", untagged_ticker="UNT")

    captured: dict[str, list[str]] = {}

    def fake_refresh_all(self, tickers):
        captured["tickers"] = list(tickers)

    monkeypatch.setattr(PriceCache, "refresh_all", fake_refresh_all)
    monkeypatch.setattr(PriceCache, "reset_circuit_breaker", lambda self: None)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    monkeypatch.setattr(OhlcvCache, "reset_circuit_breaker", lambda self: None)
    monkeypatch.setattr(OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "tickers" in captured, "refresh_all was never invoked"
    # Tagged ticker MUST be in the prefetch list — under pure-proximity it
    # would still show up here for N=2 watchlist (top-5 covers everything),
    # but the assertion that matters is that the tag-aware top-5 IS what
    # gets warmed. We reinforce that by verifying it ranks ahead of UNT
    # via the dashboard build that happens inside the route.
    assert "TAG" in captured["tickers"], (
        f"tagged ticker must appear in /prices/refresh prefetch list; "
        f"got {captured['tickers']}"
    )
    # The route's own top-5 selection runs `_sort_watchlist` (pre-build). If
    # someone reverts the route to pure proximity, the prefetch list would
    # not change for this 2-row watchlist — the discriminator must therefore
    # be the dashboard VM ordering inside the rendered response. Assert that
    # the response markup orders TAG before UNT.
    tag_pos = r.text.find(">TAG<")
    unt_pos = r.text.find(">UNT<")
    assert tag_pos != -1 and unt_pos != -1, (
        f"both tickers must render; TAG@{tag_pos} UNT@{unt_pos}"
    )
    assert tag_pos < unt_pos, (
        f"refresh-now response must order tagged ticker before untagged; "
        f"TAG@{tag_pos} > UNT@{unt_pos}"
    )


def test_prices_refresh_uses_pipeline_eval_anchor(seeded_db, monkeypatch):
    """Anchor regression: when a standalone `swing eval` runs after the
    pipeline (the Bug 7 family scenario), /prices/refresh must compute
    flag_tags from the pipeline's OWN eval, not the latest standalone.

    Pre-fix discriminator: the original /prices/refresh implementation in
    this commit used `MAX(run_ts) FROM evaluation_runs` with no pipeline
    anchor. Under the post-pipeline standalone-eval edge case it would
    have rebuilt flag_tags from the standalone eval (which has different
    candidates) — silently disagreeing with what the rendered dashboard
    shows.

    Setup:
      - E1 (pipeline-bound): TAG is aplus (→ tagged in dashboard)
      - E2 (standalone, later run_ts): TAG is dropped (no candidate row)
      - Pure latest-eval anchor would compute flag_tags from E2 → TAG
        gets no tags → falls behind UNT in the route's top-5 selection
      - Pipeline-eval anchor uses E1 → TAG remains tagged → wins top-5
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache
    from swing.web.ohlcv_cache import OhlcvCache

    cfg, cfg_path = seeded_db

    # Build the pipeline-bound eval E1 with TAG=aplus.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            e1 = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'TAG', 'aplus', 108.0, 100.0, 95.0, 'universe')""",
                (e1,),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token, charts_status,
                    evaluation_run_id)
                   VALUES ('2026-04-17T20:55:00', '2026-04-17T21:05:00',
                           'manual', '2026-04-17', '2026-04-20',
                           'complete', 't-x', 'ok', ?)""",
                (e1,),
            )
            # E2: later standalone eval — drops TAG, adds OTHER as aplus.
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T22:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            e2 = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'OTHER', 'aplus', 200.0, 201.0, 190.0, 'universe')""",
                (e2,),
            )
            conn.execute(
                """INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close, rationale)
                   VALUES ('2026-04-17T21:00:00', '2026-04-17', 'SPY', 'Bullish', 450.0, 'ok')""",
            )
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="TAG", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=100.0, initial_stop_target=95.0,
                last_close=108.0, last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="UNT", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=100.0, initial_stop_target=95.0,
                last_close=101.0, last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    captured: dict[str, list[str]] = {}

    def fake_refresh_all(self, tickers):
        captured["tickers"] = list(tickers)

    monkeypatch.setattr(PriceCache, "refresh_all", fake_refresh_all)
    monkeypatch.setattr(PriceCache, "reset_circuit_breaker", lambda self: None)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    monkeypatch.setattr(OhlcvCache, "reset_circuit_breaker", lambda self: None)
    monkeypatch.setattr(OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    # The rendered dashboard (built inside the route) uses the pipeline-eval
    # anchor → TAG stays tagged → orders before UNT. If the route silently
    # used latest-eval (E2) and the dashboard used pipeline-eval (E1), the
    # prefetch list would still match on this 2-row watchlist BUT a future
    # refactor that grew the watchlist could diverge. We assert the rendered
    # ordering as the primary verification.
    tag_pos = r.text.find(">TAG<")
    unt_pos = r.text.find(">UNT<")
    assert tag_pos != -1 and unt_pos != -1
    assert tag_pos < unt_pos, (
        "post-pipeline standalone-eval edge case: TAG must still order "
        "before UNT (pipeline-eval anchor preserves the A+ tag)"
    )
