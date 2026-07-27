"""LatchPanelVM -- the zone verdict, the state label, and the display filter."""
from __future__ import annotations

from datetime import datetime

import pytest

from swing.data.db import connect
from swing.evaluation.dates import PageKind
from swing.web.price_cache import PriceSnapshot
from swing.web.view_models.latches import LatchPanelVM, build_latch_panel_vm

NOW = datetime(2026, 7, 25, 12, 0)     # Saturday -> action session 2026-07-27


class _FakeCache:
    """Serves ONE price for every requested ticker (or nothing)."""

    def __init__(self, price=None, *, source="live", is_stale=False):
        self._price = price
        self._source = source
        self._is_stale = is_stale

    def get_many(self, tickers, deadline_seconds, *, executor=None):
        if self._price is None:
            return {}
        return {
            t: PriceSnapshot(ticker=t, price=self._price, asof=NOW,
                             is_stale=self._is_stale, source=self._source)
            for t in tickers
        }


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


def _vm(cfg, *, price=None, source="live", is_stale=False):
    conn = connect(cfg.paths.db_path)
    try:
        return build_latch_panel_vm(
            conn, cfg, _FakeCache(price, source=source, is_stale=is_stale),
            None, now=NOW)
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


def test_a_last_close_fallback_price_is_labelled_stale(seeded_db):
    """`PriceCache` falls back to the most recent `candidates.close`, which for
    a ticker that rotated out of the screen can be days old. It must not render
    as a live quote."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg, price=17.76, source="last_close", is_stale=True).rows[0]
    assert row.price_source == "last_close"
    assert row.price_is_stale is True


def test_an_absent_price_snapshot_does_not_block_the_row(seeded_db):
    """A6: current_price '-', zone_position 'unknown', row still rendered with
    its frozen pivot/stop/horizon."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    row = _vm(cfg, price=None).rows[0]
    assert row.current_price == "-"
    assert row.zone_position == "unknown"
    assert row.state_label == "ARMED"
    assert (row.latched_pivot, row.invalidation_level) == ("18.34", "14.88")
    assert row.horizon_expiry == "2026-08-31"


def test_a_price_cache_failure_degrades_without_losing_the_row(seeded_db):
    """A6 again, one layer down: an exploding cache must not 500 or drop the
    mandate."""
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)

    class _Boom:
        def get_many(self, *a, **k):
            raise RuntimeError("price boom")

    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg, _Boom(), None, now=NOW)
    finally:
        conn.close()
    assert vm.available is True
    assert len(vm.rows) == 1
    assert vm.rows[0].current_price == "-"


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
        near = build_latch_panel_vm(conn, cfg, _FakeCache(), None, now=NOW)
        far = build_latch_panel_vm(
            conn, cfg, _FakeCache(), None, now=datetime(2026, 8, 8, 12, 0))
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


def test_the_beacon_payload_carries_the_render_time_anchor_and_the_live_set(
        seeded_db):
    """The A4 seam's anchor. A payload built at POST time instead would
    re-introduce the GET/POST TOCTOU the hazard-2 gotcha forbids."""
    import json
    cfg, _ = seeded_db
    _seed(cfg, _FTRE)
    vm = _vm(cfg)
    payload = json.loads(vm.beacon_payload_json)
    assert payload["view_session_date"] == "2026-07-27" == vm.horizon_session
    assert payload["candidate_ids"] == str(vm.rows[0].candidate_id)


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
