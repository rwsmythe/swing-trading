"""Phase 14 SB4 gate-fix FIX-2 — sort works on ALL listing columns.

Root cause fixed: _SORT_KEYS omitted open_price/shares/closing_price/
chart_pattern/aplus_bucket/hypothesis_label (+ the 2 new FIX-1 columns
exit_date/days_open), so clicking those headers silently flagged
invalid_filter and never sorted.

Discriminating coverage:
  - each newly-sortable column sorts ascending AND descending, with a valid
    (non-invalid_filter) result.
  - nullable columns (closing_price/final_r/exit_date/days_open/chart_pattern/
    aplus_bucket/hypothesis_label) sort None-LAST in BOTH directions.
  - a sort on a newly-added key preserves an active filter in query_state.
"""
from __future__ import annotations

import pytest

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.view_models.journal import _SORT_KEYS

NEWLY_SORTABLE = [
    "open_price", "shares", "closing_price", "chart_pattern",
    "aplus_bucket", "hypothesis_label", "exit_date", "days_open",
]
NULLABLE_KEYS = [
    "closing_price", "final_r", "exit_date", "days_open",
    "chart_pattern", "aplus_bucket", "hypothesis_label",
]


def _insert_trade(conn, **overrides) -> int:
    base = dict(
        id=None, ticker="TST", entry_date="2026-04-15",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )
    base.update(overrides)
    return insert_trade_with_event(
        conn, Trade(**base), event_ts="2026-04-15T09:30:00",
    )


def _insert_exit(conn, tid, *, price, quantity, when="2026-04-20T15:30:00"):
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=tid, fill_datetime=when,
            action="exit", quantity=quantity, price=price, reason="target",
        ),
        event_ts=when,
    )


@pytest.fixture
def build_journal_for(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db

    def _build(**kwargs):
        return build_journal(cfg=cfg, **kwargs)

    return _build


@pytest.fixture
def spread(seeded_db):
    """A spread of closed + open trades so every sortable column has a mix of
    values AND some Nones (open trades -> None closing/final_r/exit_date)."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            a = _insert_trade(
                conn, ticker="AAA", entry_date="2026-04-10", entry_price=10.0,
                initial_shares=100, initial_stop=9.0, state="closed",
                chart_pattern_operator="vcp", hypothesis_label="alpha",
            )
            _insert_exit(conn, a, price=12.0, quantity=100,
                         when="2026-04-20T15:30:00")
            b = _insert_trade(
                conn, ticker="BBB", entry_date="2026-04-12", entry_price=20.0,
                initial_shares=50, initial_stop=18.0, state="reviewed",
                chart_pattern_operator="flat_base", hypothesis_label="beta",
            )
            _insert_exit(conn, b, price=22.0, quantity=50,
                         when="2026-04-25T15:30:00")
            # Open trade: closing_price/final_r/exit_date all None; chart
            # pattern / hypothesis None too.
            _insert_trade(
                conn, ticker="OPN", entry_date="2026-04-16", entry_price=5.0,
                initial_shares=200, initial_stop=4.5, state="managing",
            )
    finally:
        conn.close()
    return cfg


def test_every_listing_column_is_in_sort_allowlist():
    # The byte-level contract that broke: each rendered sort control's key must
    # be an accepted sort key.
    for key in NEWLY_SORTABLE:
        assert key in _SORT_KEYS


@pytest.mark.parametrize("key", NEWLY_SORTABLE)
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_newly_sortable_column_sorts(build_journal_for, spread, key, direction):
    vm = build_journal_for(period="all", sort=key, dir=direction)
    assert vm.invalid_filter is False, f"{key} {direction} flagged invalid"
    values = [getattr(r, key) for r in vm.rows]
    present = [v for v in values if v is not None]
    # Present values are correctly ordered for the requested direction.
    assert present == sorted(present, reverse=(direction == "desc"))


@pytest.mark.parametrize("key", NULLABLE_KEYS)
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_nullable_columns_sort_none_last(build_journal_for, spread, key, direction):
    vm = build_journal_for(period="all", sort=key, dir=direction)
    values = [getattr(r, key) for r in vm.rows]
    none_idx = [i for i, v in enumerate(values) if v is None]
    present_idx = [i for i, v in enumerate(values) if v is not None]
    if none_idx and present_idx:
        assert min(none_idx) > max(present_idx), (
            f"{key} {direction}: None did not sort last"
        )


def test_sort_on_new_key_preserves_active_filter(build_journal_for, spread):
    vm = build_journal_for(
        period="all", sort="open_price", dir="desc", filter_state="closed_any",
    )
    assert vm.query_state["sort"] == "open_price"
    assert vm.query_state["dir"] == "desc"
    assert vm.query_state["filter_state"] == "closed_any"
    assert vm.invalid_filter is False
