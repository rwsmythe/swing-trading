"""Phase 14 SB4 Slice 3 Task 3.1 — server-side sort/filter in build_journal.

Discriminating coverage:
  - sort by final_r desc orders rows (None-last).
  - filter_state='reviewed' returns only state=='reviewed' (coupled to
    complete_trade_review per R2 M#6); 'open' virtual group narrows to
    {entered,managing,partial_exited}.
  - filter_pattern='vcp' narrows to that pattern_class.
  - filter_aplus include/exclude (the spec §5.2 "has-A+ flag" filter).
  - bad sort / filter falls back to the default + sets invalid_filter (no raise).
"""
from __future__ import annotations

import pytest

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event


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


def _insert_candidate(conn, *, ticker, bucket) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count)
           VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                   NULL, 1, 0, 1, 0, 0, 0)"""
    )
    run_id = cur.lastrowid
    cur = conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            adr_pct, rs_method)
           VALUES (?, ?, ?, 10.0, 10.5, 9.5, 2.0, 'fallback_spy')""",
        (run_id, ticker, bucket),
    )
    return cur.lastrowid


@pytest.fixture
def build_journal_for(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db

    def _build(**kwargs):
        return build_journal(cfg=cfg, **kwargs)

    return _build


@pytest.fixture
def mixed_states(seeded_db):
    """A spread of states + final_r values + patterns for sort/filter tests."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # closed, final_r ~ +2.0, vcp
            a = _insert_trade(
                conn, ticker="AAA", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="closed",
                chart_pattern_operator="vcp",
            )
            _insert_exit(conn, a, price=12.0, quantity=100)
            # closed, final_r ~ -1.0, flat_base
            b = _insert_trade(
                conn, ticker="BBB", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="closed",
                chart_pattern_operator="flat_base",
            )
            _insert_exit(conn, b, price=9.0, quantity=100)
            # reviewed, final_r ~ +1.0
            c = _insert_trade(
                conn, ticker="CCC", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="reviewed",
                chart_pattern_operator="vcp",
            )
            _insert_exit(conn, c, price=11.0, quantity=100)
            # open (managing), final_r None
            _insert_trade(
                conn, ticker="OPN", entry_price=10.0, initial_shares=50,
                initial_stop=9.0, state="managing",
            )
    finally:
        conn.close()
    return cfg


@pytest.fixture
def aplus_trade_with_candidate(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid = _insert_candidate(conn, ticker="APL", bucket="aplus")
            _insert_trade(
                conn, ticker="APL", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="managing",
                trade_origin="pipeline_aplus", candidate_id=cid,
            )
            # A non-A+ trade so non_aplus has something to keep.
            _insert_trade(
                conn, ticker="NOC", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="managing",
                trade_origin="manual_off_pipeline",
            )
    finally:
        conn.close()
    return cfg


def test_sort_by_final_r_desc(build_journal_for, mixed_states):
    vm = build_journal_for(period="all", sort="final_r", dir="desc")
    finals = [r.final_r for r in vm.rows if r.final_r is not None]
    assert finals == sorted(finals, reverse=True)


def test_sort_none_last(build_journal_for, mixed_states):
    # None final_r (open trade) sorts to the END for both directions.
    vm = build_journal_for(period="all", sort="final_r", dir="desc")
    finals = [r.final_r for r in vm.rows]
    none_indices = [i for i, v in enumerate(finals) if v is None]
    non_none = [i for i, v in enumerate(finals) if v is not None]
    assert all(ni > max(non_none) for ni in none_indices)


def test_filter_state_reviewed(build_journal_for, mixed_states):
    vm = build_journal_for(period="all", filter_state="reviewed")
    assert vm.rows
    assert all(r.state == "reviewed" for r in vm.rows)


def test_filter_state_open_virtual_group(build_journal_for, mixed_states):
    vm = build_journal_for(period="all", filter_state="open")
    assert vm.rows
    assert all(
        r.state in ("entered", "managing", "partial_exited") for r in vm.rows
    )


def test_filter_pattern_vcp(build_journal_for, mixed_states):
    vm = build_journal_for(period="all", filter_pattern="vcp")
    assert vm.rows
    assert all(r.chart_pattern == "vcp" for r in vm.rows)


def test_filter_aplus_includes_excludes(
    build_journal_for, aplus_trade_with_candidate,
):
    incl = build_journal_for(period="all", filter_aplus="aplus")
    assert incl.rows
    assert all(r.aplus_bucket == "aplus" for r in incl.rows)
    excl = build_journal_for(period="all", filter_aplus="non_aplus")
    assert excl.rows
    assert all(r.aplus_bucket != "aplus" for r in excl.rows)


def test_bad_sort_falls_back_and_flags(build_journal_for, mixed_states):
    vm = build_journal_for(period="all", sort="; DROP TABLE")
    assert vm.invalid_filter is True
    assert vm.rows is not None  # unfiltered/default set still returned


def test_bad_filter_state_falls_back_and_flags(build_journal_for, mixed_states):
    vm = build_journal_for(period="all", filter_state="bogus")
    assert vm.invalid_filter is True
    # default = no state filter applied, so all states present.
    assert vm.rows


def test_query_state_only_set_params(build_journal_for, mixed_states):
    vm = build_journal_for(
        period="all", sort="final_r", dir="desc", filter_state="reviewed",
    )
    qs = vm.query_state
    assert qs["sort"] == "final_r"
    assert qs["dir"] == "desc"
    assert qs["filter_state"] == "reviewed"
    # Unset params are absent (not empty strings).
    assert "filter_pattern" not in qs
    assert "filter_aplus" not in qs
