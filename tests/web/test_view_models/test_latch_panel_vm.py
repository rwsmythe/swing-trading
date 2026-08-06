"""LatchPanelVM -- the zone verdict, the state label, and the display filter."""
from __future__ import annotations

from datetime import datetime

import pytest

from swing.data.db import connect
from swing.evaluation.dates import PageKind
from swing.web.view_models.latches import LatchPanelVM, build_latch_panel_vm

NOW = datetime(2026, 7, 25, 12, 0)     # Saturday -> action session 2026-07-27


def _set_last_close(cfg, ticker, price):
    """The panel's price source is the most recent persisted `candidates.close`
    -- a pure SELECT. Seeding a later `bucket='watch'` row is exactly how the
    live corpus carries a newer close for a ticker whose latch is still armed
    (FTRE runs 122-125 are precisely this shape)."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(900, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 0, 1, 0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(900, ?, 'watch', ?, 18.34, 14.88, 'universe')", (ticker, price))
    conn.close()


def _seed(cfg, rows):
    conn = connect(cfg.paths.db_path)
    with conn:
        for rid, asof, action, ticker, bucket, pivot, stop in rows:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
                (rid, f"{asof}T17:30:05", asof, action))
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) "
                "VALUES (?, ?, ?, 17.76, ?, ?, 'universe')",
                (rid, ticker, bucket, pivot, stop))
    conn.close()


_FTRE = [(121, "2026-07-17", "2026-07-20", "FTRE", "aplus", 18.34, 14.88)]


def _clear_closes(cfg):
    """`candidates.close` is NULLABLE (migration 0001 puts no NOT NULL on it),
    so 'no price at all' is a REACHABLE production shape, not a fiction."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute("UPDATE candidates SET close = NULL")
    conn.close()


def _vm(cfg, *, price=None, now=NOW):
    if price is None:
        _clear_closes(cfg)
    else:
        _set_last_close(cfg, "FTRE", price)
    conn = connect(cfg.paths.db_path)
    try:
        return build_latch_panel_vm(conn, cfg, now=now)
    finally:
        conn.close()


def test_vm_declares_forward_planning_and_overrides_the_banner_anchor(seeded_db):
    """`_base_banner_fields` hardcodes the HISTORY_ANALYSIS anchor; the panel
    is FORWARD_PLANNING, so the builder must OVERRIDE the spread value or the
    rendered topbar contradicts the declared PAGE_KIND."""
    from swing.evaluation.dates import action_session_for_run, last_completed_session
    cfg, _ = seeded_db
    assert LatchPanelVM.PAGE_KIND is PageKind.FORWARD_PLANNING
    vm = _vm(cfg)
    assert vm.session_date == action_session_for_run(NOW).isoformat()
    assert vm.session_date != last_completed_session(NOW).isoformat()


@pytest.mark.parametrize("price,expected_position", [
    (17.76, "below_pivot"),   # the FIRE-day close -- not yet triggered
    (18.34, "in_zone"),       # exactly AT the pivot -- inclusive lower bound
    (18.60, "in_zone"),
    (18.89, "in_zone"),       # exactly AT the cap (rounds to 18.89) -- inclusive
    (19.52, "above_zone"),    # the LIVE 2026-07-24 close -- do not chase
    (None,  "unknown"),
])
def test_current_price_vs_zone(seeded_db, price, expected_position):
    """Brief section 1.1's 'current price vs zone'. Both bounds are INCLUSIVE
    and compared at display precision, so a sub-cent difference cannot flip the
    verdict. FAILS an implementation that omits the comparison, that uses a
    strict bound, or that treats an absent price as `below_pivot`."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    vm = _vm(cfg, price=price)
    assert vm.rows[0].zone_position == expected_position


def test_a_sub_cent_boundary_price_does_not_flip_the_verdict(seeded_db):
    """18.8901 rounds to 18.89 == the cap, so it is IN ZONE. A raw float
    comparison against 18.8902 would call it above_zone."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    assert _vm(cfg, price=18.8901).rows[0].zone_position == "in_zone"


def test_the_panel_renders_the_zone_verdict_not_just_the_number(seeded_db):
    """GET-equivalent render with a stubbed price of 19.52 must carry the
    ABOVE-ZONE label, not merely '19.52'. This is the 2026-07-23 situation in
    which declining to chase was CORRECT."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg, price=19.52).rows[0]
    assert row.current_price == "19.52"
    assert "ABOVE ZONE" in row.zone_position_label


def test_an_out_of_zone_armed_latch_renders_the_label_and_stays_armed(seeded_db):
    """Plan A.7.1: zone escape is an ATTRIBUTE of the armed state, never a
    terminal. An implementation that added a zone-escape clear condition FAILS
    both halves."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg, price=19.52).rows[0]
    assert row.state == "armed"
    assert row.clear_reason is None
    assert "ARMED - OUT OF ZONE" in row.state_label
    assert "pullback" in row.state_label


def test_an_in_zone_armed_latch_reads_armed_in_zone(seeded_db):
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    assert _vm(cfg, price=18.60).rows[0].state_label == "ARMED - IN ZONE"


def _write_archive_bars(cfg, ticker, rows):
    """Shape-A archive bars as `(iso_session, close)` -- the only read-side
    source that DATES a close per row."""
    from pathlib import Path

    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ]).to_parquet(cache / f"{ticker.upper()}.yfinance.parquet")


def test_the_price_is_always_labelled_last_close_and_stale(seeded_db):
    """The panel GET deliberately takes NO live quote (that would write an
    audit row from a GET -- an A4 breach), so the price is the most recent
    persisted `candidates.close`. It must never pass for a live quote: the
    source, the date CLAIM and the stale flag are all rendered.

    RE-EXPRESSED, NOT DELETED (Arc 21-G Task 6, RD OQ-3). The shipped assertion
    was `price_asof == "2026-07-24"` -- the RUN STAMP, which is only an UPPER
    BOUND on the close's own date. There is no archive bar here, so nothing
    dates this close, and the honest claim is the bound. `price_asof` now
    carries the date the panel can PROVE or nothing at all, so a future
    consumer reading it can no longer be handed a stamp shaped like a per-row
    date."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg, price=19.52).rows[0]
    assert row.price_source == "last_close"
    assert row.price_is_stale is True
    assert row.price_asof == "-"
    assert row.price_asof_basis == "close dated on or before 2026-07-24"


def test_a_corroborated_close_states_its_proven_date(seeded_db):
    """The paired half: the claim must not degrade to the upper-bound form
    unconditionally, or the card tells the operator LESS than it knows."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 19.52)])
    row = _vm(cfg, price=19.52).rows[0]
    assert row.price_asof == "2026-07-24"
    assert row.price_asof_basis == "close dated 2026-07-24"


def test_an_absent_price_does_not_block_the_row(seeded_db):
    """A6: current_price '-', zone_position 'unknown', row still rendered with
    its frozen pivot/stop/horizon. `candidates.close` is NULLABLE, so this is a
    reachable shape."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg, price=None).rows[0]
    assert row.current_price == "-"
    assert row.zone_position == "unknown"
    assert row.state_label == "ARMED"
    assert (row.latched_pivot, row.invalidation_level) == ("18.34", "14.88")
    assert row.horizon_expiry == "2026-08-31"


def test_a_price_read_failure_degrades_without_losing_the_row(seeded_db, monkeypatch):
    """A6 again, one layer down: an exploding price read must not 500 or drop
    the mandate."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)

    import swing.web.view_models.latches as vm_mod

    def _boom(*_a, **_k):
        raise RuntimeError("price boom")

    monkeypatch.setattr(vm_mod, "load_last_closes", _boom)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg, now=NOW)
    finally:
        conn.close()
    assert vm.available is True
    assert len(vm.rows) == 1
    assert vm.rows[0].current_price == "-"


def test_the_builder_takes_no_price_cache_so_a_get_cannot_fetch(seeded_db):
    """THE A4 STRUCTURAL GUARANTEE (Codex executing R1). `PriceCache.get_many`
    looks read-only, but a cache MISS submits `_fetch_with_fallback` to the
    executor, which routes the Schwab -> yfinance ladder -- and BOTH legs write
    audit rows. Passing the cache into the panel builder therefore made
    `GET /latches` a WRITER during market hours on a cold cache.

    The guarantee is now structural rather than behavioural: the builder has no
    cache parameter at all, so there is nothing to fetch with. This test fails
    the moment someone re-adds one."""
    import inspect

    params = set(inspect.signature(build_latch_panel_vm).parameters)
    assert params == {"conn", "cfg", "now"}
    assert "cache" not in params and "executor" not in params


def test_the_invalidation_label_travels_with_the_number(seeded_db):
    """RD gate condition on plan G.5 at the VM level, so a future template
    rewrite cannot drop the qualifier."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg).rows[0]
    assert row.invalidation_label == "invalidation (stop level only)"


def test_live_latches_sort_before_cleared_ones(seeded_db):
    """A cleared latch must never push a live mandate below the fold."""
    cfg, _ = seeded_db
    _seed(cfg, [
        (99, "2026-06-24", "2026-06-25", "VSTS", "aplus", 13.56, 11.62),
        (126, "2026-07-24", "2026-07-27", "VSTS", "aplus", 16.90, 13.40),
    ])
    conn = connect(cfg.paths.db_path)
    with conn:
        cid = conn.execute(
            "SELECT id FROM candidates WHERE evaluation_run_id = 99").fetchone()[0]
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at, candidate_id) VALUES "
            "(17, 'VSTS', '2026-06-25', 13.61, 15, 11.62, 11.62, 'entered', "
            "'pipeline_aplus', '2026-06-24T20:06:25', ?)", (cid,))
    conn.close()
    vm = _vm(cfg)
    assert [r.is_live for r in vm.rows] == [True, False]
    assert vm.rows[1].state == "filled"
    assert vm.live_candidate_ids == (vm.rows[0].candidate_id,)


def test_the_display_lookback_keeps_a_recent_clear_and_drops_an_old_one(seeded_db):
    """The DISPLAY filter only (LATCH_PANEL_LOOKBACK_SESSIONS == 40). The
    DERIVATION always folds every fire, so the re-confirmation chain is never
    truncated -- only the render is bounded.

    Verified arithmetic (this is what makes the test discriminating rather than
    merely green): SLDB fires 2026-04-22 and horizon-expires 2026-06-04. That
    clear is 35 sessions behind the 2026-07-27 action session -- INSIDE the
    lookback -- and 45 sessions behind 2026-08-10 -- OUTSIDE it. So the SAME
    fixture must render in the first call and drop in the second; a builder
    with no filter, or one that filters live latches too, fails one half."""
    cfg, _ = seeded_db
    _seed(cfg, [
        (9, "2026-04-21", "2026-04-22", "SLDB", "aplus", 8.866, 6.40),
        (121, "2026-07-17", "2026-07-20", "FTRE", "aplus", 18.34, 14.88),
    ])
    conn = connect(cfg.paths.db_path)
    try:
        near = build_latch_panel_vm(conn, cfg, now=NOW)
        far = build_latch_panel_vm(
            conn, cfg, now=datetime(2026, 8, 8, 12, 0))
    finally:
        conn.close()
    assert sorted(r.ticker for r in near.rows) == ["FTRE", "SLDB"]
    assert [r.ticker for r in far.rows] == ["FTRE"]     # FTRE is still LIVE


def test_a_superseded_latch_renders_as_a_normal_historical_terminal(seeded_db):
    """Codex R8-2: `superseded` is a first-class terminal, so the row VM must
    materialize it like any other cleared latch -- no crash, no silent drop,
    and a label naming the re-base."""
    cfg, _ = seeded_db
    _seed(cfg, [
        (121, "2026-07-17", "2026-07-20", "FTRE", "aplus", 18.34, 14.88),
        (125, "2026-07-23", "2026-07-24", "FTRE", "aplus", 20.19, 16.515),
    ])
    vm = _vm(cfg)
    states = {r.state for r in vm.rows}
    assert states == {"armed", "superseded"}
    sup = next(r for r in vm.rows if r.state == "superseded")
    assert "SUPERSEDED" in sup.state_label
    assert sup.clear_reason == "superseded"
    assert sup.clear_session == "2026-07-24"
    assert sup.latched_pivot == "18.34"      # its OWN frozen value kept


def test_a_declined_latch_never_renders_as_HORIZON_EXPIRED():
    """T1.3 render half. Option B (OQ-2, applied to `declined` per residual R1)
    puts THREE reasons behind one state, so the label must branch on the REASON
    the way `superseded` already does -- otherwise the card tells the operator
    his own decision was a deadline expiring.

    Called directly rather than through the panel because at this commit no
    emitter produces the terminal: the vocabulary is legal and simply never
    occurs yet, which is the #11 property Task 1 exists to establish.
    """
    from dataclasses import replace as _replace
    from datetime import date

    from swing.latches.identity import LatchIdentity
    from swing.latches.models import Latch
    from swing.web.view_models.latches import _state_label

    expired = Latch(
        identity=LatchIdentity(
            candidate_id=9276, evaluation_run_id=103, ticker="FTRE",
            detection_date="2026-07-01", pipeline_run_id=116),
        latched_pivot=18.34, latched_initial_stop=15.00, zone_cap=18.89,
        anchor=date(2026, 7, 1), horizon_expiry=date(2026, 8, 13),
        sessions_elapsed=30, sessions_to_horizon=0,
        state="horizon_expired", clear_reason="horizon",
        clear_session=date(2026, 8, 13))
    declined = _replace(expired, clear_reason="declined",
                        clear_session=date(2026, 7, 30))
    assert _state_label(expired, "unknown") == "HORIZON EXPIRED"
    label = _state_label(declined, "unknown")
    assert label == "DECLINED - operator declined on 2026-07-30"
    assert "HORIZON" not in label


def test_the_beacon_payload_carries_the_render_time_anchor_and_the_live_set(
        seeded_db):
    """The A4 seam's anchor. A payload built at POST time instead would
    re-introduce the GET/POST TOCTOU the hazard-2 gotcha forbids.

    ARC 21-B SPLITS THE ID FIELD BY ACTIONABILITY (the R7 CRITICAL). `_vm`
    seeds no close DATED the derivation session, so the regime is
    undeterminable and this card's prepared order is WITHHELD -- which is the
    live state of every card today, and exactly the state a single
    `candidate_ids` field would have recorded as a full "he saw the mandate"
    view."""
    import json
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    vm = _vm(cfg)
    payload = json.loads(vm.beacon_payload_json)
    assert payload["view_session_date"] == "2026-07-27" == vm.horizon_session
    assert payload["withheld_candidate_ids"] == str(vm.rows[0].candidate_id)
    assert payload["actionable_candidate_ids"] == ""


def test_the_telemetry_echo_says_not_yet_recorded_when_no_view_row_exists(seeded_db):
    """The self-revealing check: a silently-broken beacon is visible to the
    operator on every visit."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    assert "NOT YET RECORDED" in _vm(cfg).rows[0].telemetry_label


def test_bars_through_and_absence_are_both_rendered(seeded_db):
    """A6: never a silent 'not invalidated'."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg).rows[0]
    assert row.bars_available is False
    assert row.bars_through == "-"
