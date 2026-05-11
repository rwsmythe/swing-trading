"""Trade form VMs — entry/exit/stop."""
from __future__ import annotations

from datetime import datetime

import pytest

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def test_build_entry_form_vm_shape(seeded_db, monkeypatch):
    """Entry form VM populated with ticker, prefilled price/stop, suggested shares."""
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.trades import build_entry_form_vm, TradeEntryFormVM

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=None,
    )
    assert isinstance(vm, TradeEntryFormVM)
    assert vm.ticker == "AAPL"
    assert vm.entry_price == 180.95
    assert vm.initial_stop == 170.0  # from watchlist
    assert vm.watchlist_entry_target == 181.0
    assert vm.soft_warn_threshold == cfg.position_limits.soft_warn_open
    assert vm.hard_cap == cfg.position_limits.hard_cap_open
    # suggested_shares: depends on equity/risk/stop distance — just assert >= 0.
    assert vm.suggested_shares >= 0


def test_build_exit_form_vm_shape(seeded_db, monkeypatch):
    """Exit form VM shows remaining_shares, live exit_price prefill, reason choices."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.trades import build_exit_form_vm, TradeExitFormVM

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(
                ticker="NVDA", price=932.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    vm = build_exit_form_vm(
        trade_id=trade.id, cfg=cfg, cache=cache, executor=None,
    )
    assert isinstance(vm, TradeExitFormVM)
    assert vm.trade.ticker == "NVDA"
    assert vm.exit_price == 932.0
    assert vm.remaining_shares == 5  # no exits yet
    assert "stop-hit" in vm.reasons
    assert "manual" in vm.reasons


def test_build_stop_form_vm_shape(seeded_db):
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.view_models.trades import build_stop_form_vm, TradeStopFormVM

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    vm = build_stop_form_vm(trade_id=trade.id, cfg=cfg)
    assert isinstance(vm, TradeStopFormVM)
    assert vm.trade.ticker == "NVDA"
    assert vm.current_stop == 860.0
    assert vm.suggested_stops == ()  # 3b leaves this empty; 3c populates


# ---------------------------------------------------------------------------
# Phase 7 Sub-C T1 — TradeDetailVM, predicate rewrites, fills migration.
# ---------------------------------------------------------------------------


def _seed_phase7_trade(
    cfg, *, ticker="NVDA", state="entered", initial_shares=100,
    entry_price=100.0, initial_stop=90.0,
    premortem_technical=None, reviewed_at=None,
    pre_trade_locked_at="2026-05-01T16:00:00",
    trade_origin="manual_off_pipeline",
    **trade_kwargs,
) -> int:
    """Insert a Phase 7 trade with arbitrary state + reviewed_at + pre-trade fields.

    state and reviewed_at are post-set via UPDATE because insert_trade_with_event
    does not support setting state to anything other than the input Trade.state
    and reviewed_at is a Phase 6 review-surface field set by review submit.
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-05-01",
                entry_price=entry_price, initial_shares=initial_shares,
                initial_stop=initial_stop, current_stop=initial_stop,
                state="entered",  # always start at 'entered' for INSERT
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin=trade_origin,
                pre_trade_locked_at=pre_trade_locked_at,
                premortem_technical=premortem_technical,
                **trade_kwargs,
            ), event_ts="2026-05-01T16:00:00")
            # Force state + reviewed_at AFTER insert to bypass the legacy
            # 'entered' default that insert_trade_with_event imposes.
            if state != "entered":
                conn.execute(
                    "UPDATE trades SET state=? WHERE id=?", (state, trade_id),
                )
            if reviewed_at is not None:
                conn.execute(
                    "UPDATE trades SET reviewed_at=? WHERE id=?",
                    (reviewed_at, trade_id),
                )
        return trade_id
    finally:
        conn.close()


def _seed_fill(cfg, *, trade_id, action, quantity, price=110.0,
               fill_datetime="2026-05-02T16:00:00", reason=None):
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


def _make_price_cache(cfg, ticker, price):
    """Return (cache, executor) where get_many returns the given snapshot."""
    from datetime import datetime as _dt

    from swing.web.price_cache import PriceCache, PriceSnapshot

    cache = PriceCache(cfg)
    snap = PriceSnapshot(
        ticker=ticker, price=price, asof=_dt.now(),
        is_stale=False, source="live",
    )

    def _get_many(tickers, deadline_seconds, *, executor=None):
        return {t: snap for t in tickers if t == ticker}

    cache.get_many = _get_many  # type: ignore[method-assign]
    return cache, None


# --- TradeDetailVM tests ---------------------------------------------------

def test_trade_detail_vm_state_field_and_badge_label(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, state="partial_exited")
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm is not None
    assert vm.state == "partial_exited"
    assert vm.state_badge_label == "Partial"


def test_trade_detail_vm_badge_label_managing(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, state="managing")
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.state_badge_label == "Managing"


def test_trade_detail_vm_has_pre_trade_data_legacy_null(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, state="reviewed", premortem_technical=None,
        reviewed_at="2026-05-04T10:00:00",
    )
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.has_pre_trade_data is False


def test_trade_detail_vm_has_pre_trade_data_phase7_populated(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, state="entered", premortem_technical="risk-A",
    )
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.has_pre_trade_data is True
    assert vm.trade.premortem_technical == "risk-A"


def test_trade_detail_vm_returns_none_for_missing_trade(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    vm = build_trade_detail_vm(trade_id=99999, cfg=cfg)
    assert vm is None


def test_trade_detail_vm_exposes_trade_origin_and_locked_at(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, state="entered", trade_origin="pipeline_watch_manual",
        pre_trade_locked_at="2026-05-03T09:30:00",
    )
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.trade_origin == "pipeline_watch_manual"
    assert vm.pre_trade_locked_at == "2026-05-03T09:30:00"


def test_trade_detail_vm_audit_entries_empty_when_no_pre_trade_edits(seeded_db):
    """V1: no /trades/{id}/edit-pre-trade route exists, so audit list is empty."""
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, state="entered")
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.audit_entries == ()


def test_trade_detail_vm_fills_collected(seeded_db):
    from swing.web.view_models.trades import build_trade_detail_vm
    cfg, _ = seeded_db
    # tests/web/conftest.py autouse fixture wraps insert_trade_with_event to
    # ALSO write the entry-fill, so don't seed a second entry-fill here.
    trade_id = _seed_phase7_trade(cfg, state="managing", initial_shares=100)
    _seed_fill(
        cfg, trade_id=trade_id, action="trim", quantity=30, price=110.0,
        fill_datetime="2026-05-03T16:00:00",
    )
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert len(vm.fills) == 2
    # Sorted ASC by (fill_datetime, fill_id):
    assert vm.fills[0].action == "entry"
    assert vm.fills[1].action == "trim"


def test_trade_detail_vm_audit_entries_populated_from_pre_trade_edit(seeded_db):
    """trade_events rows with event_type='pre_trade_edit' surface as AuditEntry tuples.

    V1 has no UI for this; the read path must still work for forward-compat.
    """
    import json
    from swing.data.db import connect
    from swing.web.view_models.trades import build_trade_detail_vm

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, state="entered")
    payload = json.dumps({
        "field": "thesis", "old_value": "old", "new_value": "new",
    }, sort_keys=True)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO trade_events
                   (trade_id, ts, event_type, payload_json, rationale)
                   VALUES (?, ?, 'pre_trade_edit', ?, ?)""",
                (trade_id, "2026-05-04T10:00:00", payload, "found typo"),
            )
    finally:
        conn.close()
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert len(vm.audit_entries) == 1
    entry = vm.audit_entries[0]
    assert entry.field == "thesis"
    assert entry.old_value == "old"
    assert entry.new_value == "new"
    assert entry.reason == "found typo"


def test_trade_detail_vm_emotional_state_decoded_from_json_list(seeded_db):
    """Codex R3 Minor 1: emotional_state_pre_trade stored as JSON-list TEXT
    (per spec §1.2 multi-select); VM exposes a tuple of strings so the
    template can render operator-friendly comma-separated text instead of
    raw JSON storage format.

    Discriminating: pre-fix the VM passed the raw JSON string through
    (e.g., `["calm","focused"]`); post-fix the VM decodes to `("calm",
    "focused")` and the detail template renders "calm, focused".
    """
    from swing.web.view_models.trades import build_trade_detail_vm

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, state="entered",
        premortem_technical="risk-A",
        emotional_state_pre_trade='["calm","focused"]',
    )
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.emotional_state_pre_trade == ("calm", "focused")


def test_trade_detail_vm_emotional_state_empty_when_null_or_malformed(seeded_db):
    """Codex R3 Minor 1: NULL / empty / malformed-JSON storage format
    decodes to an empty tuple — template renders nothing rather than
    crashing or leaking storage anomalies."""
    from swing.web.view_models.trades import build_trade_detail_vm

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, state="entered",
        premortem_technical="risk-A",
        emotional_state_pre_trade=None,
    )
    vm = build_trade_detail_vm(trade_id=trade_id, cfg=cfg)
    assert vm.emotional_state_pre_trade == ()


# --- Predicate-rewrite regression tests ------------------------------------


def test_build_exit_form_vm_active_trade_predicate_managing(seeded_db, monkeypatch):  # noqa: ARG001
    """state='managing' is an active state — exit form VM MUST build.

    Discriminating: under the legacy `trade.status != 'open'` predicate this
    test would fail because the migrated `state` column has no 'open' value.
    """
    from swing.web.view_models.trades import build_exit_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="managing")
    cache, executor = _make_price_cache(cfg, "NVDA", 110.0)
    vm = build_exit_form_vm(
        trade_id=trade_id, cfg=cfg, cache=cache, executor=executor,
    )
    assert vm is not None
    assert vm.trade.ticker == "NVDA"


def test_build_exit_form_vm_active_trade_predicate_partial_exited(seeded_db):
    from swing.web.view_models.trades import build_exit_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="partial_exited")
    cache, executor = _make_price_cache(cfg, "NVDA", 110.0)
    vm = build_exit_form_vm(
        trade_id=trade_id, cfg=cfg, cache=cache, executor=executor,
    )
    assert vm is not None


def test_build_exit_form_vm_rejects_closed(seeded_db):
    """state='closed' is not active — exit form rejects."""
    from swing.web.view_models.trades import build_exit_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="closed")
    cache, executor = _make_price_cache(cfg, "NVDA", 110.0)
    vm = build_exit_form_vm(
        trade_id=trade_id, cfg=cfg, cache=cache, executor=executor,
    )
    assert vm is None


def test_build_exit_form_vm_rejects_reviewed(seeded_db):
    from swing.web.view_models.trades import build_exit_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="reviewed",
                                  reviewed_at="2026-05-04T10:00:00")
    cache, executor = _make_price_cache(cfg, "NVDA", 110.0)
    vm = build_exit_form_vm(
        trade_id=trade_id, cfg=cfg, cache=cache, executor=executor,
    )
    assert vm is None


def test_build_stop_form_vm_active_trade_predicate_managing(seeded_db):
    from swing.web.view_models.trades import build_stop_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="managing")
    vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
    assert vm is not None


def test_build_stop_form_vm_rejects_closed(seeded_db):
    from swing.web.view_models.trades import build_stop_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="closed")
    vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
    assert vm is None


def test_build_review_vm_accepts_closed_only(seeded_db):
    """state='closed' and reviewed_at IS NULL → VM builds."""
    from swing.web.view_models.trades import build_review_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="NVDA", state="closed", reviewed_at=None,
    )
    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    assert vm is not None


def test_build_review_vm_rejects_reviewed_state(seeded_db):
    """state='reviewed' + reviewed_at set MUST be rejected.

    Combined-posture coverage: this fixture exercises BOTH the predicate
    guard (line 540, ``state != 'closed'``) AND the defensive ``reviewed_at
    is not None`` guard (line 542). Both fire for a real production-shaped
    already-reviewed row, so vm is None either way. This does NOT
    discriminate the predicate from the defensive guard — that role belongs
    to ``test_build_review_vm_rejects_reviewed_state_discriminates_predicate``
    below, which sets ``reviewed_at=None`` to isolate the predicate.
    """
    from swing.web.view_models.trades import build_review_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="NVDA", state="reviewed",
        reviewed_at="2026-05-04T10:00:00",
    )
    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    assert vm is None


def test_build_review_vm_rejects_reviewed_state_discriminates_predicate(seeded_db):
    """Discriminating: state='reviewed' with reviewed_at=None.

    Isolates the predicate (line 540) from the defensive ``reviewed_at``
    guard (line 542). The fixture creates a deliberately-inconsistent state
    (``state='reviewed'`` without ``reviewed_at`` — not a real production
    state, but it exercises the predicate alone).

    Discrimination:
    - Under the correct predicate ``state != 'closed'``: ``'reviewed' !=
      'closed'`` is True → guard fires → vm is None. ✅ test passes.
    - Under the naïve buggy predicate ``state not in ('closed', 'reviewed')``:
      ``'reviewed' IN {'closed', 'reviewed'}`` is True → ``not in`` is False
      → guard does NOT fire. AND ``reviewed_at is not None`` is False →
      defensive guard does NOT fire either. → vm WOULD build → assert fails.

    The combined ``test_build_review_vm_rejects_reviewed_state`` above
    cannot tell these two predicates apart because its fixture sets
    ``reviewed_at`` and the defensive guard catches the buggy case.
    """
    import sqlite3

    from swing.data.db import connect
    from swing.web.view_models.trades import build_review_vm

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="NVDA", state="reviewed", reviewed_at=None,
    )
    # Force reviewed_at NULL even if any helper path defaulted it; the
    # _seed_phase7_trade impl above only writes reviewed_at when truthy,
    # so this is belt-and-braces against future helper drift.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE trades SET reviewed_at=NULL WHERE id=?", (trade_id,),
            )
    finally:
        conn.close()
    # Sanity-check the seed actually has reviewed_at IS NULL — if it
    # doesn't, the test would silently lose its discrimination.
    conn2 = sqlite3.connect(cfg.paths.db_path)
    try:
        row = conn2.execute(
            "SELECT state, reviewed_at FROM trades WHERE id=?", (trade_id,),
        ).fetchone()
    finally:
        conn2.close()
    assert row == ("reviewed", None), (
        f"discriminator fixture invariant violated: got {row!r}"
    )

    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    assert vm is None


def test_build_review_vm_rejects_open_trade(seeded_db):
    from swing.web.view_models.trades import build_review_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(cfg, ticker="NVDA", state="entered")
    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    assert vm is None


# --- Fills migration regression --------------------------------------------


def test_build_exit_form_vm_remaining_shares_uses_fill_quantity(seeded_db):
    """After migrating from list_exits_for_trade to list_fills_for_trade,
    remaining = initial_shares - sum(non_entry_fill.quantity).

    Discriminating: if the migration mistakenly used Fill.shares (an
    AttributeError) the test would fail; if it left the legacy shim in
    place behavior is unchanged but coverage of the new path is added.
    """
    from swing.web.view_models.trades import build_exit_form_vm
    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="NVDA", state="managing", initial_shares=100,
        entry_price=100.0, initial_stop=90.0,
    )
    # Entry fill so aggregates reflect a real execution chain.
    _seed_fill(
        cfg, trade_id=trade_id, action="entry", quantity=100, price=100.0,
        fill_datetime="2026-05-01T16:00:00",
    )
    _seed_fill(
        cfg, trade_id=trade_id, action="trim", quantity=30, price=110.0,
        fill_datetime="2026-05-03T16:00:00",
    )
    cache, executor = _make_price_cache(cfg, "NVDA", 112.0)
    vm = build_exit_form_vm(
        trade_id=trade_id, cfg=cfg, cache=cache, executor=executor,
    )
    assert vm is not None
    assert vm.remaining_shares == 70


def test_list_all_fills_returns_all_trades(seeded_db):
    """list_all_fills is the new fills-repo helper introduced for Sub-C."""
    from swing.data.db import connect
    from swing.data.repos.fills import list_all_fills
    cfg, _ = seeded_db
    # tests/web/conftest.py autouse fixture writes an entry-fill at trade
    # insert with fill_datetime=event_ts (the trade's pre_trade_locked_at
    # default '2026-05-01T16:00:00'). Don't redundantly seed entry-fills.
    t1 = _seed_phase7_trade(cfg, ticker="AAA", state="entered",
                            initial_shares=10, entry_price=10.0)
    t2 = _seed_phase7_trade(cfg, ticker="BBB", state="entered",
                            initial_shares=20, entry_price=20.0)
    _seed_fill(cfg, trade_id=t1, action="trim", quantity=5, price=11.0,
               fill_datetime="2026-05-03T16:00:00")
    conn = connect(cfg.paths.db_path)
    try:
        fills = list_all_fills(conn)
    finally:
        conn.close()
    # Both autouse entry-fills + one explicit trim = 3.
    assert len(fills) == 3
    # Sorted ASC by (fill_datetime, fill_id). Both autouse entry-fills
    # have the same fill_datetime ('2026-05-01T16:00:00'); fill_id breaks
    # ties. The trim is later.
    assert fills[0].action == "entry"
    assert fills[1].action == "entry"
    assert fills[2].action == "trim"
    assert fills[2].fill_datetime == "2026-05-03T16:00:00"


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.10 — view_models/trades.py migrates the two C.1-deferred
# list_all_exits sites (build_entry_form_vm equity computation +
# build_cadence_complete_vm closed-trades-in-period count) onto the local
# _list_all_exitshape_via_fills helper. Discriminating against (a) helper
# leaking entry fills (would over-count); (b) helper returning empty
# (would zero out aggregates).
# ---------------------------------------------------------------------------


def test_c10_list_all_exitshape_via_fills_filters_entry_fills(seeded_db):
    """C.10 view_models/trades.py helper test: directly inspect the helper's
    output and assert exactly one non-entry shape per seeded trade with
    one explicit exit fill.
    """
    from swing.data.db import connect
    from swing.web.view_models.trades import _list_all_exitshape_via_fills

    cfg, _ = seeded_db
    trade_id = _seed_phase7_trade(
        cfg, ticker="MSFT", state="managing",
        initial_shares=100, entry_price=100.0, initial_stop=90.0,
    )
    # Synthetic entry fill is auto-written by insert_trade_with_event;
    # add an explicit exit fill on top of it.
    _seed_fill(
        cfg, trade_id=trade_id, action="exit", quantity=40, price=120.0,
        fill_datetime="2026-05-04T16:00:00", reason="trim",
    )

    conn = connect(cfg.paths.db_path)
    try:
        shapes = _list_all_exitshape_via_fills(conn)
    finally:
        conn.close()

    assert len(shapes) == 1, (
        f"Adapter returned {len(shapes)} shapes; expected exactly 1 "
        f"(the explicit exit fill — entry fill must be filtered)."
    )
    shape = shapes[0]
    assert shape.trade_id == trade_id
    assert shape.shares == 40
    assert shape.exit_price == 120.0
    assert shape.exit_date == "2026-05-04"
    # realized_pnl = (120 - 100) * 40 = 800
    assert shape.realized_pnl == pytest.approx(800.0)
    # rps = 100 - 90 = 10; r = 800 / (10 * 40) = 2.0
    assert shape.r_multiple == pytest.approx(2.0)


def test_c10_build_entry_form_vm_equity_uses_fills(
    seeded_db, monkeypatch,
):
    """C.10 deferred site: build_entry_form_vm computes equity through
    _list_all_exitshape_via_fills (which sources non-entry fills) rather
    than the legacy list_all_exits shim.

    Discriminating: seed a closed trade with a SUBSTANTIAL realized PnL
    that materially changes the suggested_shares output of compute_shares
    (vs. baseline starting_equity-only equity). compute_shares' shares =
    min(shares_by_risk, shares_by_cap) is monotone in equity, so a
    larger equity yields larger or equal shares. Asserting
    suggested_shares is strictly greater than the no-PnL baseline proves
    the helper threaded realized-PnL into the equity computation.

    If the helper returned empty (un-migrated bug class), suggested_shares
    would equal the no-PnL baseline.
    """
    from swing.web.view_models.trades import build_entry_form_vm

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AMZN", added_date="2026-04-20",
                last_qualified_date="2026-04-20", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-20",
                entry_target=100.0, initial_stop_target=90.0,
                last_close=100.0, last_pivot=100.0, last_stop=90.0,
                last_adr_pct=2.0, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    cache, executor = _make_price_cache(cfg, "AMZN", 100.0)

    # Baseline VM (no closed trades → no realized PnL):
    baseline_vm = build_entry_form_vm(
        ticker="AMZN", cfg=cfg, cache=cache, executor=executor,
    )
    assert baseline_vm is not None
    baseline_shares = baseline_vm.suggested_shares

    # Seed a closed trade with a SUBSTANTIAL realized PnL (>>> floor).
    trade_id = _seed_phase7_trade(
        cfg, ticker="GOOG", state="closed",
        initial_shares=200, entry_price=100.0, initial_stop=90.0,
    )
    _seed_fill(
        cfg, trade_id=trade_id, action="exit", quantity=200, price=200.0,
        fill_datetime="2026-04-29T16:00:00", reason="target",
    )

    # With 200 * (200 - 100) = $20k realized PnL added, equity is now
    # well above the $7.5k floor — compute_shares (which uses real equity,
    # NOT the floor) should yield strictly larger shares.
    after_vm = build_entry_form_vm(
        ticker="AMZN", cfg=cfg, cache=cache, executor=executor,
    )
    assert after_vm is not None
    assert after_vm.suggested_shares > baseline_shares, (
        f"build_entry_form_vm suggested_shares should rise after seeding "
        f"$20k of realized PnL via non-entry exit fills. baseline="
        f"{baseline_shares}, after={after_vm.suggested_shares}. If equal, "
        f"the C.10 _list_all_exitshape_via_fills helper returned empty "
        f"(equity unchanged from starting_equity)."
    )


def test_c10_build_cadence_complete_vm_consumes_fills(seeded_db):
    """C.10 deferred site: build_cadence_complete_vm uses
    _list_all_exitshape_via_fills for the closed-trades-in-period count.

    Discriminating: seed two closed trades with explicit exit fills, one
    in-period and one out-of-period. The VM's n_closed_trades_in_period
    must match the in-period count (1). If the helper leaked entry fills
    the count would still be 1 (entries don't have exit_date in the
    period span window) — but if the helper returned an empty list, the
    count would be 0.
    """
    from swing.data.db import connect as _connect
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.view_models.trades import build_cadence_complete_vm

    cfg, _ = seeded_db
    # Pre-create a daily review row for 2026-05-04.
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-05-04", period_end="2026-05-04",
                scheduled_date="2026-05-05",
            )
    finally:
        conn.close()
    assert review_id is not None

    # In-period closed trade.
    in_trade = _seed_phase7_trade(
        cfg, ticker="WMT", state="closed",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    _seed_fill(
        cfg, trade_id=in_trade, action="exit", quantity=10, price=110.0,
        fill_datetime="2026-05-04T15:30:00", reason="target",
    )
    # Out-of-period closed trade (exit before period_start).
    out_trade = _seed_phase7_trade(
        cfg, ticker="TGT", state="closed",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    _seed_fill(
        cfg, trade_id=out_trade, action="exit", quantity=10, price=105.0,
        fill_datetime="2026-05-01T15:30:00", reason="target",
    )

    vm = build_cadence_complete_vm(cfg=cfg, review_id=review_id)
    assert vm is not None
    assert vm.n_closed_trades_in_period == 1, (
        f"C.10 build_cadence_complete_vm should count exactly 1 "
        f"in-period closed trade; got {vm.n_closed_trades_in_period}. "
        f"If 0, the migration helper returned empty (no fills surfaced)."
    )


# ---------------------------------------------------------------------------
# 3e.16 — build_cadence_complete_vm populates trades_during_period via
# list_trades_with_activity_in_period.
# ---------------------------------------------------------------------------


def test_3e16_build_cadence_complete_vm_populates_trades_during_period(seeded_db):
    """The builder must populate trades_during_period with one TradeSummaryVM
    per trade returned by list_trades_with_activity_in_period."""
    from swing.data.db import connect as _connect
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.view_models.trades import (
        TradeSummaryVM,
        build_cadence_complete_vm,
    )

    cfg, _ = seeded_db
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-05-04", period_end="2026-05-04",
                scheduled_date="2026-05-05",
            )
    finally:
        conn.close()
    assert review_id is not None

    # Two trades: one opened+closed same-period; one entered before but
    # received an event in period.
    rt = _seed_phase7_trade(
        cfg, ticker="RND", state="entered",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    # Override entry_date so it falls inside the daily period.
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE trades SET entry_date='2026-05-04' WHERE id=?", (rt,),
            )
    finally:
        conn.close()
    _seed_fill(
        cfg, trade_id=rt, action="exit", quantity=10, price=110.0,
        fill_datetime="2026-05-04T15:30:00", reason="target",
    )
    # Force state to closed (the exit-fill insert doesn't auto-close in this fixture).
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute("UPDATE trades SET state='closed' WHERE id=?", (rt,))
    finally:
        conn.close()

    ev = _seed_phase7_trade(
        cfg, ticker="EVT", state="managing",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    # Add a note event inside the period; entry_date is 2026-05-01 (out of period).
    from swing.data.repos.trades import add_note_event
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            add_note_event(
                conn, trade_id=ev, event_ts="2026-05-04T11:00:00",
                note="watching SMA",
            )
    finally:
        conn.close()

    vm = build_cadence_complete_vm(cfg=cfg, review_id=review_id)
    assert vm is not None
    assert isinstance(vm.trades_during_period, tuple)
    assert len(vm.trades_during_period) == 2
    for row in vm.trades_during_period:
        assert isinstance(row, TradeSummaryVM)

    by_ticker = {r.ticker: r for r in vm.trades_during_period}
    assert by_ticker["RND"].state_tag == "[OPENED+CLOSED]"
    assert by_ticker["RND"].realized_R == pytest.approx(2.0)
    assert by_ticker["EVT"].state_tag == "[EVENT]"
    assert by_ticker["EVT"].realized_R is None


def test_3e16_build_cadence_complete_vm_empty_when_no_activity(seeded_db):
    """A review with no trade activity in its period must produce
    trades_during_period == () (empty tuple)."""
    from swing.data.db import connect as _connect
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.view_models.trades import build_cadence_complete_vm

    cfg, _ = seeded_db
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-06-01", period_end="2026-06-01",
                scheduled_date="2026-06-02",
            )
    finally:
        conn.close()
    assert review_id is not None

    # Trade entered + closed BEFORE period — should not surface.
    tid = _seed_phase7_trade(
        cfg, ticker="OUT", state="entered",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    _seed_fill(
        cfg, trade_id=tid, action="exit", quantity=10, price=105.0,
        fill_datetime="2026-05-04T15:30:00", reason="target",
    )

    vm = build_cadence_complete_vm(cfg=cfg, review_id=review_id)
    assert vm is not None
    assert vm.trades_during_period == ()


def test_3e16_n_closed_trades_count_consistent_with_summary_list(seeded_db):
    """The existing n_closed_trades_in_period count must agree with the
    closed-subset of the new trades_during_period list (priority-coding
    OPENED+CLOSED also counts as closed-in-period)."""
    from swing.data.db import connect as _connect
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.view_models.trades import build_cadence_complete_vm

    cfg, _ = seeded_db
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            review_id = insert_pre_create(
                conn, review_type="daily",
                period_start="2026-05-04", period_end="2026-05-04",
                scheduled_date="2026-05-05",
            )
    finally:
        conn.close()

    # In-period closed.
    t_closed = _seed_phase7_trade(
        cfg, ticker="WMT", state="entered",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    _seed_fill(
        cfg, trade_id=t_closed, action="exit", quantity=10, price=110.0,
        fill_datetime="2026-05-04T15:30:00", reason="target",
    )
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?", (t_closed,),
            )
    finally:
        conn.close()
    # In-period EVENT (no exit) — should NOT contribute to closed count.
    t_event = _seed_phase7_trade(
        cfg, ticker="EVT", state="managing",
        initial_shares=10, entry_price=100.0, initial_stop=95.0,
    )
    from swing.data.repos.trades import add_note_event
    conn = _connect(cfg.paths.db_path)
    try:
        with conn:
            add_note_event(
                conn, trade_id=t_event, event_ts="2026-05-04T11:00:00",
                note="watching",
            )
    finally:
        conn.close()

    vm = build_cadence_complete_vm(cfg=cfg, review_id=review_id)
    assert vm is not None
    closed_in_summary = sum(
        1 for r in vm.trades_during_period
        if "CLOSED" in r.state_tag
    )
    assert closed_in_summary == vm.n_closed_trades_in_period == 1
