"""Phase 14 SB4 gate-fix FIX-3 — filter value-contract, end-to-end.

Operator gate finding (2026-05-30): every filter selection showed "Invalid
filter, showing all" and 'Open' returned nothing.

Two root causes:
  1. The "All" <select> option emits value="" and, via hx-include="closest
     form", every filter change co-submits the OTHER selects' empty values.
     "" is neither None nor an allowlist token, so it tripped invalid_filter.
     Fix: empty-string filter/sort params normalize to None (no filter), so a
     valid selection that co-submits empty siblings is NEVER flagged invalid.
  2. The listing row scope was period-filtered to CLOSED trades only (open
     trades have no closed date so period_filter dropped them), so 'Open'
     showed nothing under the default period. Fix: open trades are always in
     the listing scope ("browse the database", P14.N6).

Coverage (operator directive: verify EVERY option of EVERY dimension):
  - parity: every rendered <select> option value is in its backend allowlist.
  - every state option (incl. virtual groups) filters to exactly that state
    set, never invalid.
  - every pattern option filters to exactly that pattern, never invalid.
  - aplus / non_aplus filter correctly, never invalid.
  - empty-string siblings never trip invalid_filter on a valid selection.
  - 'Open' (and an old open trade) appears under the default (non-all) period.
  - an out-of-allowlist value still falls back gracefully (invalid_filter True,
    no 422).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app
from swing.web.view_models.journal import (
    _FILTER_APLUS,
    _FILTER_PATTERNS,
    _FILTER_STATES,
    _VIRTUAL_STATE_GROUPS,
)

ALL_STATE_OPTIONS = [
    "open", "closed_any", "entered", "managing", "partial_exited",
    "closed", "reviewed",
]
ALL_PATTERN_OPTIONS = [
    "vcp", "flat_base", "cup_with_handle", "high_tight_flag",
    "double_bottom_w",
]
ALL_APLUS_OPTIONS = ["aplus", "non_aplus"]


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


def _seed_full_spread(cfg) -> None:
    """One trade per state, covering every pattern + both A+ states."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid_a = _insert_candidate(conn, ticker="ENT", bucket="aplus")
            _insert_trade(
                conn, ticker="ENT", state="entered",
                chart_pattern_operator="vcp", candidate_id=cid_a,
                trade_origin="pipeline_aplus",
            )
            _insert_trade(
                conn, ticker="MNG", state="managing",
                chart_pattern_operator="flat_base",
                trade_origin="manual_off_pipeline",
            )
            pe = _insert_trade(
                conn, ticker="PEX", state="partial_exited",
                chart_pattern_operator="cup_with_handle",
                trade_origin="manual_off_pipeline",
            )
            _insert_exit(conn, pe, price=11.0, quantity=40)
            cid_c = _insert_candidate(conn, ticker="CLO", bucket="aplus")
            clo = _insert_trade(
                conn, ticker="CLO", state="closed",
                chart_pattern_operator="high_tight_flag", candidate_id=cid_c,
                trade_origin="pipeline_aplus",
            )
            _insert_exit(conn, clo, price=12.0, quantity=100)
            rev = _insert_trade(
                conn, ticker="REV", state="reviewed",
                chart_pattern_operator="double_bottom_w",
                trade_origin="manual_off_pipeline",
            )
            _insert_exit(conn, rev, price=12.0, quantity=100)
    finally:
        conn.close()


@pytest.fixture
def build_journal_for(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db
    _seed_full_spread(cfg)

    def _build(**kwargs):
        return build_journal(cfg=cfg, **kwargs)

    return _build


@pytest.fixture
def client(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_full_spread(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as c:
        yield c


# --- template option values vs backend allowlist parity ---------------------


def _select_option_values(text: str, name: str) -> list[str]:
    m = re.search(
        rf'<select name="{name}".*?</select>', text, re.DOTALL,
    )
    assert m, f"<select name={name}> not found"
    return re.findall(r'<option value="([^"]*)"', m.group(0))


def test_state_select_options_subset_of_allowlist(client):
    r = client.get("/journal?period=all")
    for v in _select_option_values(r.text, "filter_state"):
        if v == "":
            continue  # the "All" sentinel -> no filter
        assert v in _FILTER_STATES, f"state option {v!r} not in allowlist"


def test_pattern_select_options_subset_of_allowlist(client):
    r = client.get("/journal?period=all")
    for v in _select_option_values(r.text, "filter_pattern"):
        if v == "":
            continue
        assert v in _FILTER_PATTERNS, f"pattern option {v!r} not in allowlist"


def test_aplus_select_options_subset_of_allowlist(client):
    r = client.get("/journal?period=all")
    for v in _select_option_values(r.text, "filter_aplus"):
        if v == "":
            continue
        assert v in _FILTER_APLUS, f"aplus option {v!r} not in allowlist"


# --- every option filters to exactly the right subset, never invalid --------


@pytest.mark.parametrize("opt", ALL_STATE_OPTIONS)
def test_every_state_option_filters_correctly(build_journal_for, opt):
    vm = build_journal_for(period="all", filter_state=opt)
    assert vm.invalid_filter is False, f"state={opt} flagged invalid"
    wanted = _VIRTUAL_STATE_GROUPS.get(opt, frozenset({opt}))
    assert vm.rows, f"state={opt} returned no rows"
    assert all(r.state in wanted for r in vm.rows)


@pytest.mark.parametrize("opt", ALL_PATTERN_OPTIONS)
def test_every_pattern_option_filters_correctly(build_journal_for, opt):
    vm = build_journal_for(period="all", filter_pattern=opt)
    assert vm.invalid_filter is False, f"pattern={opt} flagged invalid"
    assert vm.rows, f"pattern={opt} returned no rows"
    assert all(r.chart_pattern == opt for r in vm.rows)


@pytest.mark.parametrize("opt", ALL_APLUS_OPTIONS)
def test_every_aplus_option_filters_correctly(build_journal_for, opt):
    vm = build_journal_for(period="all", filter_aplus=opt)
    assert vm.invalid_filter is False, f"aplus={opt} flagged invalid"
    assert vm.rows, f"aplus={opt} returned no rows"
    if opt == "aplus":
        assert all(r.aplus_bucket == "aplus" for r in vm.rows)
    else:
        assert all(r.aplus_bucket != "aplus" for r in vm.rows)


# --- empty-string siblings + open-scope + graceful fallback -----------------


def test_empty_string_siblings_do_not_flag_invalid(build_journal_for):
    # Selecting State=Open while the OTHER selects submit "" (the "All"
    # option) must NOT flag invalid_filter (the core gate bug).
    vm = build_journal_for(
        period="all", filter_state="open",
        filter_pattern="", filter_aplus="",
    )
    assert vm.invalid_filter is False
    assert all(
        r.state in ("entered", "managing", "partial_exited") for r in vm.rows
    )


def test_all_empty_strings_is_no_filter(build_journal_for):
    vm = build_journal_for(
        period="all", filter_state="", filter_pattern="", filter_aplus="",
        sort="", dir="",
    )
    assert vm.invalid_filter is False
    assert vm.rows  # unfiltered -> all rows present


def test_open_filter_shows_open_under_default_period(seeded_db):
    # An open trade entered well before the default-period cutoff must still
    # appear under filter_state='open' (open trades are always in scope).
    cfg, _ = seeded_db
    from swing.web.view_models.journal import build_journal
    old = (date.today() - timedelta(days=120)).isoformat()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _insert_trade(
                conn, ticker="OLD", entry_date=old, state="managing",
                trade_origin="manual_off_pipeline",
            )
    finally:
        conn.close()
    vm = build_journal(cfg=cfg, period="month", filter_state="open")
    assert vm.invalid_filter is False
    assert any(r.ticker == "OLD" for r in vm.rows), (
        "old open trade missing under default period 'Open' filter"
    )


def test_invalid_value_still_falls_back_gracefully(build_journal_for):
    vm = build_journal_for(period="all", filter_state="bogus_state")
    assert vm.invalid_filter is True
    assert vm.rows  # default = no state filter -> all rows


def test_open_trades_in_default_period_listing_scope(seeded_db):
    # Even with no filter, an old open trade is browsable under the default
    # period (P14.N6 "browse the database").
    cfg, _ = seeded_db
    from swing.web.view_models.journal import build_journal
    old = (date.today() - timedelta(days=200)).isoformat()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _insert_trade(
                conn, ticker="ANCIENT", entry_date=old, state="entered",
                trade_origin="manual_off_pipeline",
            )
    finally:
        conn.close()
    vm = build_journal(cfg=cfg, period="month")
    assert any(r.ticker == "ANCIENT" for r in vm.rows)
