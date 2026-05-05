"""JournalVM + builder."""
from __future__ import annotations

import pytest


def test_build_journal_default_period_month(seeded_db):
    from swing.web.view_models.journal import JournalVM, build_journal
    cfg, _ = seeded_db
    vm = build_journal(cfg=cfg, period="month")
    assert isinstance(vm, JournalVM)
    assert vm.period == "month"
    # Empty DB -> stats show zeros.
    assert vm.stats.n_trades == 0


def test_build_journal_rejects_unknown_period(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db
    with pytest.raises(ValueError, match="period"):
        build_journal(cfg=cfg, period="fortnight")


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.9 — journal VM consumes fills (non-entry) via local
# _ExitShape adapter rather than the legacy `list_all_exits` shim.
# Discriminating: under buggy code that returns no exits, total_pnl == 0;
# under buggy code that includes entry fills, the closed-trade aggregation
# would double-count or miscount realized contributions.
# ---------------------------------------------------------------------------


def _seed_closed_trade_with_exit(cfg) -> int:
    """Seed one closed trade + its exit fill. Returns trade_id."""
    from swing.data.db import connect
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker="MSFT", entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10,
                initial_stop=90.0, current_stop=90.0,
                state="closed", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            tid = insert_trade_with_event(
                conn, trade, event_ts="2026-04-15T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=tid,
                    fill_datetime="2026-04-20T15:30:00",
                    action="exit", quantity=10, price=120.0, reason="target",
                ),
                event_ts="2026-04-20T15:30:00",
            )
            return tid
    finally:
        conn.close()


def test_c9_journal_vm_consumes_fills_not_legacy_exits(seeded_db):
    """C.9: journal stats source from non-entry fills via the local
    _ExitShape adapter. realized_pnl = (120-100)*10 = $200; r_multiple
    = 200 / ((100-90)*10) = 2.0; one win, total_pnl=200, total_r=2.0.

    Discriminating: under buggy code (no migration helper / no fills
    returned) total_pnl==0 and n_trades==0. Under buggy code that
    leaks entry fills, the win count is wrong (two "exits" per trade).
    """
    from swing.web.view_models.journal import build_journal

    cfg, _ = seeded_db
    _seed_closed_trade_with_exit(cfg)

    vm = build_journal(cfg=cfg, period="all")

    assert vm.stats.n_trades == 1, (
        f"Expected 1 closed trade in stats; got {vm.stats.n_trades}. "
        f"Zero suggests the fills→exit-shape migration helper produced "
        f"no exits; >1 suggests entry fills leaked through."
    )
    assert vm.stats.n_wins == 1
    assert vm.stats.total_pnl == pytest.approx(200.0)
    assert vm.stats.total_r == pytest.approx(2.0)


def test_c9_journal_helper_filters_entry_fills(seeded_db):
    """C.9 discriminating: the migration helper MUST filter entry fills.
    Inspect the helper's output directly.
    """
    from swing.data.db import connect
    from swing.web.view_models.journal import _list_all_exitshape_via_fills

    cfg, _ = seeded_db
    _seed_closed_trade_with_exit(cfg)

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            shapes = _list_all_exitshape_via_fills(conn)
    finally:
        conn.close()

    # Exactly 1 non-entry shape (the explicit exit fill); the synthetic
    # entry fill from insert_trade_with_event must NOT appear.
    assert len(shapes) == 1
    assert shapes[0].shares == 10
    assert shapes[0].exit_date == "2026-04-20"
    assert shapes[0].realized_pnl == pytest.approx(200.0)
    assert shapes[0].r_multiple == pytest.approx(2.0)
