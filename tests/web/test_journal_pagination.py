"""Phase 14 SB4 Slice 2 Task 2.2 — journal pagination + period-str loosening.

  - page_size bounds the rows returned; page/page_size echoed on the VM.
  - page_size clamped to MAX_PAGE_SIZE.
  - page 2 returns the next slice (no overlap with page 1).
  - an out-of-allowlist period no longer 422s at the route (period is now a
    plain str; build_journal clamps unknown -> the default 'month').
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _seed_n_trades(cfg, n: int) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i in range(n):
                insert_trade_with_event(
                    conn,
                    Trade(
                        id=None, ticker=f"T{i:03d}", entry_date="2026-04-15",
                        entry_price=10.0, initial_shares=100, initial_stop=9.0,
                        current_stop=9.0, state="managing",
                        watchlist_entry_target=None,
                        watchlist_initial_stop=None, notes=None,
                    ),
                    event_ts="2026-04-15T09:30:00",
                )
    finally:
        conn.close()


def test_pagination_bounds_rows(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db
    _seed_n_trades(cfg, 30)
    vm = build_journal(cfg=cfg, period="all", page=1, page_size=20)
    assert len(vm.rows) <= 20
    assert vm.page == 1 and vm.page_size == 20
    assert vm.total_rows == 30
    assert vm.has_next is True


def test_page_size_clamped_to_max(seeded_db):
    from swing.web.view_models.journal import MAX_PAGE_SIZE, build_journal
    cfg, _ = seeded_db
    _seed_n_trades(cfg, 5)
    vm = build_journal(cfg=cfg, period="all", page=1, page_size=10_000)
    assert vm.page_size <= MAX_PAGE_SIZE
    assert vm.page_size == MAX_PAGE_SIZE


def test_page_two_returns_next_slice(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db
    _seed_n_trades(cfg, 30)
    p1 = build_journal(cfg=cfg, period="all", page=1, page_size=20)
    p2 = build_journal(cfg=cfg, period="all", page=2, page_size=20)
    assert len(p1.rows) == 20
    assert len(p2.rows) == 10
    ids_p1 = {r.trade_id for r in p1.rows}
    ids_p2 = {r.trade_id for r in p2.rows}
    assert ids_p1.isdisjoint(ids_p2)
    assert p2.has_next is False


def test_default_page_size_in_band(seeded_db):
    from swing.web.view_models.journal import DEFAULT_PAGE_SIZE
    # The single page-size figure lives in the ~20-25 band.
    assert 20 <= DEFAULT_PAGE_SIZE <= 25


def test_build_journal_clamps_unknown_period_to_default(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db
    vm = build_journal(cfg=cfg, period="fortnight")
    # Clamps to the default rather than raising.
    assert vm.period == "month"


def test_period_str_not_literal_422(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=bogus")
    assert r.status_code == 200


def test_pagination_links_preserve_active_filter(seeded_db):
    # GAP #2: the Prev/Next pagination URLs must carry the active sort/filter
    # state (built from vm.query_state, overriding only `page`) so paging does
    # NOT discard an active filter/sort.
    cfg, cfg_path = seeded_db
    _seed_n_trades(cfg, 30)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=all&page_size=20&filter_state=managing&sort=ticker"
        )
    assert r.status_code == 200
    import re
    m = re.search(r'href="([^"]*page=2[^"]*)"[^>]*rel="next"', r.text)
    assert m, "Next pagination link not found"
    next_url = m.group(1)
    assert "filter_state=managing" in next_url
    assert "sort=ticker" in next_url
    assert "period=all" in next_url
