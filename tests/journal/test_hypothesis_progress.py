"""Tests for swing.journal.stats.compute_hypothesis_progress_breakdown.

Per brief §4.5:
- One row per registered hypothesis (active + paused + closed)
- Per row: id, name, target/current sample, mean R, win rate, tripwire
  status, status (status string carries over)
- Renders cleanly even with zero matched trades for the hypothesis
"""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import Exit, Trade
from swing.data.repos.trades import (
    insert_exit_with_event,
    insert_trade_with_event,
)
from swing.journal.stats import (
    HypothesisProgress,
    compute_hypothesis_progress_breakdown,
)


def _setup(tmp_db: Path):
    return ensure_schema(tmp_db)


def _add_closed(conn, *, ticker, entry_date, label, r_multiple, realized_pnl,
                shares=100, entry_price=10.0):
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date, entry_price=entry_price,
        initial_shares=shares, initial_stop=9.0, current_stop=9.0,
        status="open", state="entered", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, hypothesis_label=label,
    )
    tid = insert_trade_with_event(conn, trade, event_ts=f"{entry_date}T09:30:00")
    insert_exit_with_event(
        conn, Exit(
            id=None, trade_id=tid, exit_date=entry_date, exit_price=9.0,
            shares=shares, reason="stop-hit", realized_pnl=realized_pnl,
            r_multiple=r_multiple, notes=None,
        ),
        event_ts=f"{entry_date}T16:00:00",
    )
    return tid


def _add_open(conn, *, ticker, entry_date, label, shares=100, entry_price=10.0):
    """Insert an open trade (no exit). Used to test in-flight count."""
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date, entry_price=entry_price,
        initial_shares=shares, initial_stop=9.0, current_stop=9.0,
        status="open", state="entered", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, hypothesis_label=label,
    )
    return insert_trade_with_event(conn, trade, event_ts=f"{entry_date}T09:30:00")


def test_breakdown_has_one_row_per_hypothesis(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
        assert len(rows) == 4
        assert all(isinstance(r, HypothesisProgress) for r in rows)
        names = [r.name for r in rows]
        assert names == [
            "A+ baseline",
            "Near-A+ defensible: extension test",
            "Sub-A+ VCP-not-formed",
            "Capital-blocked: smaller-position test",
        ]
    finally:
        conn.close()


def test_breakdown_zero_state(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
        for r in rows:
            assert r.current_sample == 0
            assert r.mean_r_multiple is None  # undefined when no samples
            assert r.win_rate is None
            assert r.tripwire_fired is False
            assert r.status == "active"
    finally:
        conn.close()


def test_breakdown_vir_attributed_to_sub_aplus(tmp_db: Path):
    """Per brief done-criteria: VIR should appear as 1/5 sample under
    Sub-A+ VCP-not-formed (the backfilled label starts with that
    name)."""
    conn = _setup(tmp_db)
    try:
        with conn:
            _add_closed(
                conn, ticker="VIR", entry_date="2026-04-20",
                label=("sub-A+ VCP-not-formed test (proximity_20ma + "
                       "tightness fails); inaugural trade test"),
                r_multiple=-0.33, realized_pnl=-2.0,
            )
        rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
        sub = next(r for r in rows if r.name == "Sub-A+ VCP-not-formed")
        assert sub.current_sample == 1
        assert sub.target_sample == 5
        assert sub.mean_r_multiple == -0.33
        # win_rate suppressed when N < 3 (matches existing breakdown's
        # _MIN_TRADES_FOR_WIN_RATE)
        assert sub.win_rate is None
        assert sub.tripwire_fired is False
    finally:
        conn.close()


def test_breakdown_tripwire_label_when_streak_fires(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        with conn:
            for i, day in enumerate(["2026-04-10", "2026-04-12", "2026-04-14"]):
                _add_closed(
                    conn, ticker=f"AA{i}", entry_date=day,
                    label="Sub-A+ VCP-not-formed test",
                    r_multiple=-1.0, realized_pnl=-100.0,
                )
        rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
        sub = next(r for r in rows if r.name == "Sub-A+ VCP-not-formed")
        assert sub.tripwire_fired is True
        assert sub.consecutive_max_loss_streak == 3


    finally:
        conn.close()


def test_breakdown_in_flight_counts_open_prefix_matching_trades(tmp_db: Path):
    """Open trades whose hypothesis_label prefix-matches a hypothesis name
    contribute to in_flight_sample (display-only) but NOT current_sample
    (which requires realized R-multiple = closed)."""
    conn = _setup(tmp_db)
    try:
        with conn:
            # Two open prefix-matchers for Sub-A+ VCP-not-formed.
            _add_open(
                conn, ticker="DHC", entry_date="2026-04-27",
                label="sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)",
            )
            _add_open(
                conn, ticker="CC", entry_date="2026-04-30",
                label="Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness",
            )
            # One open trade with NULL label — must not contribute anywhere.
            _add_open(
                conn, ticker="UNK", entry_date="2026-04-30", label=None,
            )
        rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
        sub = next(r for r in rows if r.name == "Sub-A+ VCP-not-formed")
        # Discriminator: in_flight is the open-prefix-matching count;
        # current_sample stays at 0 because no closed trades exist. If
        # the new field were misnamed or never populated by the compute
        # fn, this assertion fails.
        assert sub.current_sample == 0, (
            f"current_sample should remain 0 (no closed trades); got {sub.current_sample}"
        )
        assert sub.in_flight_sample == 2, (
            f"in_flight_sample should count 2 open prefix-matchers (DHC, CC); "
            f"got {sub.in_flight_sample}"
        )
        # Other hypotheses see 0 (no prefix-match) — confirms no cross-attribution.
        for r in rows:
            if r.name != "Sub-A+ VCP-not-formed":
                assert r.in_flight_sample == 0, (
                    f"hypothesis {r.name!r} in_flight should be 0; "
                    f"got {r.in_flight_sample}"
                )
    finally:
        conn.close()


def test_render_progress_section_includes_all_hypotheses(tmp_db: Path):
    """The CLI calls a tiny render helper to make text output easy to
    test. Smoke test: section contains every hypothesis name + the
    sample fraction."""
    from swing.journal.stats import render_hypothesis_progress

    conn = _setup(tmp_db)
    try:
        rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
        text = render_hypothesis_progress(rows)
        assert "Hypothesis investigation progress" in text
        for name in [
            "A+ baseline", "Near-A+ defensible: extension test",
            "Sub-A+ VCP-not-formed", "Capital-blocked: smaller-position test",
        ]:
            assert name in text
            assert "0 / " in text
    finally:
        conn.close()


def test_render_progress_section_includes_tripwire_warning(tmp_db: Path):
    from swing.journal.stats import render_hypothesis_progress

    conn = _setup(tmp_db)
    try:
        with conn:
            for i, day in enumerate(["2026-04-10", "2026-04-12", "2026-04-14"]):
                _add_closed(
                    conn, ticker=f"AA{i}", entry_date=day,
                    label="Sub-A+ VCP-not-formed test",
                    r_multiple=-1.0, realized_pnl=-100.0,
                )
        rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
        text = render_hypothesis_progress(rows)
        assert "TRIPWIRE FIRED" in text
        assert "consecutive" in text.lower()
    finally:
        conn.close()
