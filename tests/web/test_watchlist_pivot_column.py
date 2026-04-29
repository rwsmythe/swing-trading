"""CC pivot bug fix — discriminating regression across all three render sites.

Spec §3.9 — Q-G resolution; R1-Major-3 + R2-Major-1.

Each test uses entry_target=$42.00 vs candidates.pivot=$44.50 so the
pre-fix path (entry_target binding) and post-fix path (current_pivot
binding) produce visually distinct output. Lightning trigger fixture
asserts the trigger DOES fire under the entry_target binding even
after the column display switches to current_pivot — proving the
trigger binding survives the column-display change.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _make_watchlist_entry(
    *,
    ticker: str,
    entry_target: float | None = None,
    initial_stop_target: float | None = None,
    last_close: float | None = None,
    last_adr_pct: float = 2.0,
) -> WatchlistEntry:
    """Factory matching swing/data/models.py:130-145 dataclass shape."""
    return WatchlistEntry(
        ticker=ticker,
        added_date="2026-04-29",
        last_qualified_date="2026-04-29",
        status="watch",
        qualification_count=1,
        not_qualified_streak=0,
        last_data_asof_date="2026-04-28",
        entry_target=entry_target,
        initial_stop_target=initial_stop_target,
        last_close=last_close,
        last_pivot=None,
        last_stop=None,
        last_adr_pct=last_adr_pct,
        missing_criteria=None,
        notes=None,
    )


def _seed_watchlist_and_candidate(
    cfg,
    *,
    ticker: str,
    entry_target: float | None,
    candidate_pivot: float | None,
    last_close: float | None,
) -> None:
    """Seed an active watchlist row + a completed pipeline_run + (optionally) a
    candidate row with `pivot=candidate_pivot`. When `candidate_pivot is
    None`, no candidate row exists for the ticker (fallback path)."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            if entry_target is not None:
                upsert_watchlist_entry(
                    conn,
                    _make_watchlist_entry(
                        ticker=ticker,
                        entry_target=entry_target,
                        initial_stop_target=entry_target * 0.95,
                        last_close=last_close,
                    ),
                )
            else:
                # Dash-sentinel path: insert a watchlist row with NULL
                # entry_target via the same factory (NULL is a valid value).
                upsert_watchlist_entry(
                    conn,
                    _make_watchlist_entry(
                        ticker=ticker,
                        entry_target=None,
                        initial_stop_target=None,
                        last_close=last_close,
                    ),
                )
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 1, 0, 1, 0, 0, 0)"""
            )
            eval_run_id = cur.lastrowid
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES ('2026-04-29T08:00:00','2026-04-29T09:00:00',
                           'manual','2026-04-28','2026-04-29','complete',
                           't-test', ?, 'ok')""",
                (eval_run_id,),
            )
            if candidate_pivot is not None:
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, adr_pct, tight_streak, pullback_pct,
                        prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                        rs_method, pattern_tag, notes, sector, industry)
                       VALUES (?, ?, 'watch', ?, ?, ?, 2.0, 5, NULL, NULL,
                               NULL, NULL, 'fallback_spy', NULL, NULL,
                               'Technology', 'Software-Application')""",
                    (
                        eval_run_id,
                        ticker,
                        candidate_pivot,
                        candidate_pivot,
                        candidate_pivot * 0.95,
                    ),
                )
    finally:
        conn.close()


def _patch_price_cache(monkeypatch, ticker: str, price: float | None) -> None:
    """Patch PriceCache.get_many so the dashboard / watchlist rendering does
    not hit yfinance during tests."""
    if price is None:
        snapshot_map: dict[str, PriceSnapshot] = {}
    else:
        snapshot_map = {
            ticker: PriceSnapshot(
                ticker=ticker,
                price=price,
                asof=datetime.now(),
                is_stale=False,
                source="live",
            )
        }
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: snapshot_map[t] for t in tickers if t in snapshot_map
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_dashboard_top5_pivot_column_renders_current_pivot(
    test_cfg, seeded_db, monkeypatch,
):
    """R1-Major-3 site 1: dashboard top-5 watchlist row.

    Discriminating fixture: entry_target=$42.00 vs candidates.pivot=$44.50.
    Pre-fix render emits $42.00; post-fix emits $44.50.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "PYPL", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # The Pivot column for PYPL must render $44.50 (current_pivot), NOT $42.00.
    assert "$44.50" in body, "post-fix Pivot column must render candidates.pivot"
    assert "$42.00" not in body, (
        "pre-fix Pivot column rendered entry_target — fix did not apply to "
        "watchlist_top5_section.html.j2"
    )


def test_standalone_watchlist_pivot_column_renders_current_pivot(
    test_cfg, seeded_db, monkeypatch,
):
    """R1-Major-3 site 2: standalone /watchlist page."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "PYPL", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    body = resp.text
    assert "$44.50" in body
    assert "$42.00" not in body


def test_watchlist_row_close_path_pivot_column_renders_current_pivot(
    test_cfg, seeded_db, monkeypatch,
):
    """R1-Major-3 site 3: GET /watchlist/{ticker}/row close-path.

    Without the WatchlistRowVM.current_pivot extension, this would revert
    to $42.00 (entry_target) post-close, recreating the bug exactly when
    the operator most needs the current value.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "PYPL", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/watchlist/PYPL/row",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200
    body = resp.text
    assert "$44.50" in body, (
        "WatchlistRowVM.current_pivot did not propagate to the row-collapse "
        "render path"
    )
    assert "$42.00" not in body


def test_pivot_column_falls_back_to_entry_target_when_no_candidate(
    test_cfg, seeded_db, monkeypatch,
):
    """When candidates_by_ticker has no row for the ticker (rotated out
    of finviz; not an open trade), the Pivot column falls back to
    entry_target — the fix should not REGRESS this path."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_and_candidate(
        cfg, ticker="NEM", entry_target=42.00,
        candidate_pivot=None, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "NEM", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # Falls back to entry_target.
    assert "$42.00" in body


def test_pivot_column_dash_when_both_absent(
    test_cfg, seeded_db, monkeypatch,
):
    """R1-Minor-3 dash sentinel: when candidate_pivot is absent AND
    entry_target is None, the cell renders '—' (NOT $0.00)."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_and_candidate(
        cfg, ticker="NEM", entry_target=None,
        candidate_pivot=None, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "NEM", 43.00)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # The Pivot cell for NEM renders '—', NOT '$0.00'.
    assert "$0.00" not in body, (
        "R1-Minor-3 dash sentinel: missing pivot must render '—', not '$0.00'"
    )


def test_lightning_trigger_unchanged_uses_entry_target(
    test_cfg, seeded_db, monkeypatch,
):
    """Q4 + spec §3.8 — lightning trigger stays bound to entry_target.

    Discriminating fixture chosen so the trigger fires under entry_target
    binding but would NOT fire under current_pivot binding:
      - entry_target = $42.00; current_pivot = $100.00; price = $41.60.
      - 41.60 ≥ 0.99 × 42 = 41.58 → lightning fires (entry_target binding).
      - 41.60 ≥ 0.99 × 100 = 99   → would NOT fire (current_pivot binding).
    Asserting the lightning glyph IS present proves the trigger binding
    survives the column-display change.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00,
        candidate_pivot=100.00, last_close=41.60,
    )
    _patch_price_cache(monkeypatch, "PYPL", 41.60)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "⚡" in body, (
        "Lightning trigger must remain bound to entry_target after CC pivot "
        "fix — fired at $41.60 ≥ 0.99 × $42.00"
    )
    # Sanity: the column itself shows current_pivot ($100.00).
    assert "$100.00" in body
