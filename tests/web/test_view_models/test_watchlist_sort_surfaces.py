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


def _seed_seven_watchlist_with_eval(
    cfg, *, tagged_at_worst_proximity: str, untagged_close: list[str],
) -> None:
    """Seed a 7-row watchlist where the SOLE tagged ticker has the WORST
    proximity. Pre-fix top-5 (pure proximity) excludes the tagged ticker;
    post-fix top-5 (tag-aware) includes it as the first slot.

    Untagged tickers are placed at proximities 1%, 2%, 3%, 4%, 5%, 6%
    (closest to farthest). Tagged ticker sits at 10%.
    """
    assert len(untagged_close) == 6, "expected 6 untagged tickers"
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
                           NULL, 7, 1, 6, 0, 0, 0, 'v1', 'd')""",
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, ?, 'aplus', 110.0, 100.0, 95.0, 'universe')""",
                (eval_id, tagged_at_worst_proximity),
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
                ticker=tagged_at_worst_proximity, added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=100.0, initial_stop_target=95.0,
                last_close=110.0,           # 10% — WORST proximity
                last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            for i, ticker in enumerate(untagged_close, start=1):
                close = 100.0 + float(i)    # 101..106 → 1%..6% proximity
                upsert_watchlist_entry(conn, WatchlistEntry(
                    ticker=ticker, added_date="2026-04-10",
                    last_qualified_date="2026-04-17", status="watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date="2026-04-17",
                    entry_target=100.0, initial_stop_target=95.0,
                    last_close=close, last_pivot=100.0, last_stop=95.0,
                    last_adr_pct=2.5, missing_criteria=None, notes=None,
                ))
    finally:
        conn.close()


def _patch_route_caches(monkeypatch, *, captured: dict):
    from swing.web.price_cache import PriceCache
    from swing.web.ohlcv_cache import OhlcvCache

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


def test_build_dashboard_top5_tagged_vs_tagged_count_differential(
    seeded_db, monkeypatch,
):
    """Surface-level discriminator for the tag-COUNT primary key under
    realistic conditions: two tagged tickers at identical proximity differ
    on tag count. The 2-tag ticker (TT✓ + A+) must rank above the 1-tag
    ticker (A+ only).

    A future bug that bypasses `_sort_watchlist` and substitutes a simpler
    "has any tag" sort at the VM level would still pass the
    tagged-vs-untagged tests above. This test pins the count axis.
    """
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
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
                           NULL, 2, 2, 0, 0, 0, 0, 'v1', 'd')""",
            )
            eval_id = int(cur.lastrowid)
            # T2: bucket=aplus AND 7 trend_template passes → ("TT✓", "A+"),
            # tag count 2.
            cur = conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'T2', 'aplus', 105.0, 100.0, 95.0, 'universe')""",
                (eval_id,),
            )
            t2_cid = int(cur.lastrowid)
            for i in range(7):
                conn.execute(
                    """INSERT INTO candidate_criteria
                       (candidate_id, criterion_name, layer, result)
                       VALUES (?, ?, 'trend_template', 'pass')""",
                    (t2_cid, f"TT{i}"),
                )
            # T1: bucket=aplus only, no criteria → ("A+",), tag count 1.
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'T1', 'aplus', 105.0, 100.0, 95.0, 'universe')""",
                (eval_id,),
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
            # Both watchlist rows at identical 5% proximity.
            for ticker in ("T1", "T2"):
                upsert_watchlist_entry(conn, WatchlistEntry(
                    ticker=ticker, added_date="2026-04-10",
                    last_qualified_date="2026-04-17", status="watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date="2026-04-17",
                    entry_target=100.0, initial_stop_target=95.0,
                    last_close=105.0, last_pivot=100.0, last_stop=95.0,
                    last_adr_pct=2.5, missing_criteria=None, notes=None,
                ))
    finally:
        conn.close()

    _patch_caches(monkeypatch)
    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    # Sanity on flag_tags shape — confirms the seed produced the expected tags.
    assert vm.flag_tags.get("T2") == ("TT✓", "A+"), (
        f"T2 should have 2 tags from criteria + bucket; got {vm.flag_tags.get('T2')}"
    )
    assert vm.flag_tags.get("T1") == ("A+",), (
        f"T1 should have 1 tag (A+ only); got {vm.flag_tags.get('T1')}"
    )

    tickers = [w.ticker for w in vm.watchlist_top5]
    assert tickers == ["T2", "T1"], (
        f"2-tag ticker (T2) must rank above 1-tag ticker (T1) at equal "
        f"proximity; got {tickers}"
    )


def test_prices_refresh_route_warms_tag_aware_top5(seeded_db, monkeypatch):
    """7-row watchlist where the tagged ticker has the WORST proximity (10%)
    and 6 untagged tickers fill ranks 1–6 by proximity (1%..6%).

    Pre-fix discriminator: pure-proximity top-5 = the 5 closest untagged
    tickers; tagged ticker is RANK 7 → NOT prefetched.
    Post-fix: tag-aware top-5 = [TAG, then 4 closest untagged] → tagged IS
    prefetched. Asserting `"TAG" in captured["tickers"]` therefore strictly
    discriminates the route's own top-5 logic, independent of what the
    dashboard render does afterward.
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app

    cfg, cfg_path = seeded_db
    _seed_seven_watchlist_with_eval(
        cfg, tagged_at_worst_proximity="TAG",
        untagged_close=["U01", "U02", "U03", "U04", "U05", "U06"],
    )

    captured: dict[str, list[str]] = {}
    _patch_route_caches(monkeypatch, captured=captured)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "tickers" in captured, "refresh_all was never invoked"
    # Pre-fix: TAG (rank 7 by proximity) NOT in top-5; post-fix: TAG first.
    assert "TAG" in captured["tickers"], (
        f"tagged ticker (worst proximity, rank 7) must appear in the "
        f"/prices/refresh prefetch list under tag-aware sort; "
        f"got {captured['tickers']}"
    )
    # Sanity: the closest-by-proximity untagged tickers (U01, U02, U03, U04)
    # also appear — the prewarm picks the top-5 by tag-aware sort, which is
    # [TAG, U01, U02, U03, U04]. U05/U06 should NOT be in the warmed set
    # (other than via the open_trade union or the SPY benchmark).
    warmed = set(captured["tickers"])
    assert "U05" not in warmed and "U06" not in warmed, (
        f"tag-aware top-5 must exclude the worst-proximity untagged "
        f"tickers (U05, U06); got warmed set {warmed}"
    )


def test_prices_refresh_uses_pipeline_eval_anchor(seeded_db, monkeypatch):
    """Anchor regression: when a standalone `swing eval` runs after the
    pipeline (Bug 7 family), /prices/refresh must compute flag_tags from
    the pipeline's OWN eval, not the latest standalone.

    Setup:
      - E1 (pipeline-bound, earlier run_ts): TAG is aplus
      - E2 (standalone, later run_ts): TAG is dropped (NO candidate row)
      - 7-row watchlist: TAG @ 10% proximity (worst), 6 untagged @ 1%..6%
      - Pipeline-eval anchor (E1): TAG keeps its A+ tag → makes top-5
      - Latest-eval anchor (E2): TAG has no tags → top-5 falls back to
        proximity → TAG is rank 7 → NOT in the warmed set

    Discriminator: assert "TAG" in `captured["tickers"]`. Fails under
    pre-fix latest-eval-anchor; passes under pipeline-eval anchor.
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app

    cfg, cfg_path = seeded_db

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # E1 — pipeline-bound, TAG=aplus.
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
                   VALUES (?, 'TAG', 'aplus', 110.0, 100.0, 95.0, 'universe')""",
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
            # E2 — later standalone, drops TAG, adds OTHER.
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
                last_close=110.0,           # 10% — worst proximity
                last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            for i, ticker in enumerate(
                ["U01", "U02", "U03", "U04", "U05", "U06"], start=1
            ):
                upsert_watchlist_entry(conn, WatchlistEntry(
                    ticker=ticker, added_date="2026-04-10",
                    last_qualified_date="2026-04-17", status="watch",
                    qualification_count=1, not_qualified_streak=0,
                    last_data_asof_date="2026-04-17",
                    entry_target=100.0, initial_stop_target=95.0,
                    last_close=100.0 + float(i),
                    last_pivot=100.0, last_stop=95.0,
                    last_adr_pct=2.5, missing_criteria=None, notes=None,
                ))
    finally:
        conn.close()

    captured: dict[str, list[str]] = {}
    _patch_route_caches(monkeypatch, captured=captured)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "tickers" in captured, "refresh_all was never invoked"
    # Strict discriminator: under E1 anchor TAG keeps A+ → in top-5 →
    # warmed; under E2 anchor TAG has no tags → falls to rank 7 by
    # proximity → NOT warmed.
    assert "TAG" in captured["tickers"], (
        f"under the pipeline-eval anchor, TAG must remain tagged and "
        f"appear in the warmed top-5; got {captured['tickers']}"
    )
