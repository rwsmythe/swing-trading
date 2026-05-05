"""OpenPositionsRowVM assembly — pure helper, no I/O."""
from __future__ import annotations

from datetime import datetime

from swing.data.models import Trade
from swing.web.price_cache import PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM


def _mk_trade(id_=42, ticker="AAPL", stop=170.0) -> Trade:
    return Trade(
        id=id_, ticker=ticker, entry_date="2026-04-15",
        entry_price=180.0, initial_shares=5, initial_stop=170.0,
        current_stop=stop, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C T2 helpers — seed Phase 7 trades with arbitrary state and
# Fill-based execution events. Mirrors the helper convention used by
# tests/web/test_view_models/test_trades.py for C.1 (which also forces
# state via UPDATE post-INSERT to bypass insert_trade_with_event's default).
# ---------------------------------------------------------------------------


def _seed_phase7_trade(
    cfg, *, ticker="AAPL", state="entered", initial_shares=100,
    entry_price=180.0, initial_stop=170.0,
    pre_trade_locked_at="2026-04-15T09:30:00",
    trade_origin="manual_off_pipeline",
) -> int:
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=entry_price, initial_shares=initial_shares,
                initial_stop=initial_stop, current_stop=initial_stop,
                state="entered",  # always start at 'entered' for INSERT
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin=trade_origin,
                pre_trade_locked_at=pre_trade_locked_at,
            ), event_ts="2026-04-15T09:30:00")
            if state != "entered":
                conn.execute(
                    "UPDATE trades SET state=? WHERE id=?",
                    (state, trade_id),
                )
        return trade_id
    finally:
        conn.close()


def _seed_fill(cfg, *, trade_id, action, quantity, price=185.0,
               fill_datetime="2026-04-17T10:00:00", reason=None):
    from swing.data.db import connect
    from swing.data.models import Fill
    from swing.data.repos.fills import insert_fill_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_fill_with_event(conn, Fill(
                fill_id=None, trade_id=trade_id,
                fill_datetime=fill_datetime, action=action,
                quantity=quantity, price=price, reason=reason,
            ), event_ts=fill_datetime)
    finally:
        conn.close()


def _fetch_trade(cfg, trade_id):
    from swing.data.db import connect
    from swing.data.repos.trades import get_trade
    conn = connect(cfg.paths.db_path)
    try:
        return get_trade(conn, trade_id)
    finally:
        conn.close()


def test_vm_pure_assembly_with_snapshot_and_advisories():
    from swing.web.view_models.open_positions_row import (
        _open_positions_row_vm, OpenPositionsRowVM,
    )
    trade = _mk_trade()
    snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    advs = (AdvisorySuggestionVM(rule="breakeven", message="move stop to entry"),)
    vm = _open_positions_row_vm(
        trade=trade, price_snapshot=snap, remaining_shares=5, advisories=advs,
        state_badge_label="Entered",
    )
    assert isinstance(vm, OpenPositionsRowVM)
    assert vm.trade is trade
    assert vm.price_snapshot is snap
    assert vm.remaining_shares == 5
    assert vm.advisories == advs
    assert vm.state_badge_label == "Entered"


def test_vm_pure_assembly_with_no_snapshot_and_no_advisories():
    from swing.web.view_models.open_positions_row import _open_positions_row_vm
    trade = _mk_trade()
    vm = _open_positions_row_vm(
        trade=trade, price_snapshot=None, remaining_shares=3, advisories=(),
        state_badge_label="Entered",
    )
    assert vm.price_snapshot is None
    assert vm.advisories == ()
    assert vm.remaining_shares == 3


def test_build_open_positions_row_single_row(seeded_db, monkeypatch):
    """build_open_positions_row does one get_many + one list_fills_for_trade
    + one advisories compute; returns OpenPositionsRowVM."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="AAPL", state="entered", initial_shares=10,
    )
    trade = _fetch_trade(cfg, trade_id)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=182.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.trade.ticker == "AAPL"
    assert vm.price_snapshot is not None
    assert vm.price_snapshot.price == 182.0
    assert vm.remaining_shares == 10  # no exits seeded
    assert isinstance(vm.advisories, tuple)


def test_build_open_positions_row_remaining_shares_uses_fill_quantity(
    seeded_db, monkeypatch,
):
    """Discriminating: under buggy `Exit.shares` access, AttributeError raises;
    under correct `Fill.quantity`, remaining = initial_shares - sum(quantity)
    over non-entry fills only."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="AAPL", state="managing", initial_shares=100,
    )
    _seed_fill(
        cfg, trade_id=trade_id, action="trim", quantity=30, price=185.0,
        fill_datetime="2026-04-17T10:00:00", reason="partial",
    )
    trade = _fetch_trade(cfg, trade_id)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=188.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.remaining_shares == 70  # 100 - 30


def test_build_open_positions_row_excludes_entry_fills_from_remaining(
    seeded_db, monkeypatch,
):
    """Discriminating: buggy code would sum entry+trim quantities (subtracting
    the entry-fill from initial_shares), giving 100 - 100 - 30 = -30."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="AAPL", state="managing", initial_shares=100,
    )
    _seed_fill(
        cfg, trade_id=trade_id, action="entry", quantity=100, price=180.0,
        fill_datetime="2026-04-15T09:31:00",
    )
    _seed_fill(
        cfg, trade_id=trade_id, action="trim", quantity=30, price=185.0,
        fill_datetime="2026-04-17T10:00:00", reason="partial",
    )
    trade = _fetch_trade(cfg, trade_id)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=188.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    # NOT -30 (entry-fill excluded); NOT 100 (trim must subtract).
    assert vm.remaining_shares == 70


def test_build_open_positions_row_state_badge_label_managing(
    seeded_db, monkeypatch,
):
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="AAPL", state="managing")
    trade = _fetch_trade(cfg, trade_id)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=182.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.state_badge_label == "Managing"


def test_build_open_positions_row_state_badge_label_partial_exited(
    seeded_db, monkeypatch,
):
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="AAPL", state="partial_exited")
    trade = _fetch_trade(cfg, trade_id)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=182.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.state_badge_label == "Partial"


def test_open_positions_row_vm_dataclass_includes_state_badge_label():
    """Schema-shape: dataclass field exists."""
    from dataclasses import fields
    from swing.web.view_models.open_positions_row import OpenPositionsRowVM
    field_names = {f.name for f in fields(OpenPositionsRowVM)}
    assert "state_badge_label" in field_names


def test_build_open_positions_row_plumbs_ohlcv_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4: build_open_positions_row receives ohlcv_cache and plumbs
    sma10/20/50 + previous_close into AdvisoryContext."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime
    from swing.web.view_models.open_positions_row import build_open_positions_row
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.data.models import Trade

    cfg, _ = test_cfg
    trade = Trade(
        id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        initial_shares=10, initial_stop=170.0, current_stop=170.0,
        state="entered", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = build_open_positions_row(
            trade=trade, cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache,
            executor=ex,
        )

    rules = {a.rule for a in vm.advisories}
    assert "exit_below_50ma" in rules


# ---------------------------------------------------------------------------
# build_open_positions_expanded predicate-rewrite tests (Phase 7 Sub-C C.2).
# ---------------------------------------------------------------------------


def test_build_open_positions_expanded_accepts_partial_exited(seeded_db):
    """state='partial_exited' is active — VM MUST build."""
    from swing.data.db import connect
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="AAPL", state="partial_exited",
    )
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(
            conn=conn, cfg=cfg, trade_id=trade_id,
        )
    finally:
        conn.close()
    assert vm is not None
    assert vm.ticker == "AAPL"


def test_build_open_positions_expanded_accepts_managing(seeded_db):
    """state='managing' is active — VM MUST build.

    Discriminating: under naive `trade.status != "open"` the constant
    comparison would be True (no `status == "open"` row exists post-Phase-7),
    rejecting all valid managing trades — this test ensures the multi-state
    predicate is in effect.
    """
    from swing.data.db import connect
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="AAPL", state="managing")
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(
            conn=conn, cfg=cfg, trade_id=trade_id,
        )
    finally:
        conn.close()
    assert vm is not None
    assert vm.ticker == "AAPL"


def test_build_open_positions_expanded_accepts_entered(seeded_db):
    """state='entered' is active — VM MUST build."""
    from swing.data.db import connect
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="AAPL", state="entered")
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(
            conn=conn, cfg=cfg, trade_id=trade_id,
        )
    finally:
        conn.close()
    assert vm is not None


def test_build_open_positions_expanded_rejects_closed(seeded_db):
    from swing.data.db import connect
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="AAPL", state="closed")
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(
            conn=conn, cfg=cfg, trade_id=trade_id,
        )
    finally:
        conn.close()
    assert vm is None


def test_build_open_positions_expanded_rejects_reviewed(seeded_db):
    from swing.data.db import connect
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="AAPL", state="reviewed")
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(
            conn=conn, cfg=cfg, trade_id=trade_id,
        )
    finally:
        conn.close()
    assert vm is None


def test_build_open_positions_expanded_returns_none_for_missing_trade(seeded_db):
    from swing.data.db import connect
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(
            conn=conn, cfg=cfg, trade_id=999999,
        )
    finally:
        conn.close()
    assert vm is None
