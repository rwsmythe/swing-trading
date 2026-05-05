"""Tests for swing.journal.stats.compute_hypothesis_progress_breakdown.

Per brief §4.5:
- One row per registered hypothesis (active + paused + closed)
- Per row: id, name, target/current sample, mean R, win rate, tripwire
  status, status (status string carries over)
- Renders cleanly even with zero matched trades for the hypothesis
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
# B.9: Exit dataclass + insert_exit_with_event removed (Phase 7); fills
# repo is the canonical execution log. Hypothesis progress stats consume
# the fills-backed _ExitLikeRow shim transparently — Sub-C T1 deletes
# the shim once the remaining web view models migrate.
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.journal.stats import (
    HypothesisProgress,
    compute_hypothesis_progress_breakdown,
)


def _setup(tmp_db: Path):
    return ensure_schema(tmp_db)


def _add_closed(conn, *, ticker, entry_date, label, r_multiple, realized_pnl,
                shares=100, entry_price=10.0, state="closed"):
    """Insert trade + entry-fill + exit-fill, then UPDATE state to closed.

    `state` lets the caller seed a 'reviewed' (post-review) terminal trade
    too; B.9's closed-or-reviewed predicate must sweep both.

    NB: r_multiple/realized_pnl arguments are passed through but the shim
    re-derives them from fills — the test asserts on the value stored in
    HypothesisProgress.mean_r_multiple, which the compute fn calculates
    from the shim, so we make sure the fill price + initial_stop yield the
    requested r_multiple. With initial_stop=9.0 and entry_price=10.0
    (risk-per-share = 1.0), exit_price = entry_price + r_multiple gives
    the right per-share R; quantity scales linearly so the share-weighted
    R for a single full exit equals the requested r_multiple.
    """
    entry_ts = f"{entry_date}T09:30:00"
    exit_ts = f"{entry_date}T16:00:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date, entry_price=entry_price,
        initial_shares=shares, initial_stop=9.0, current_stop=9.0,
        state="entered", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, hypothesis_label=label,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at=entry_ts,
    )
    tid = insert_trade_with_event(conn, trade, event_ts=entry_ts)
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=tid, fill_datetime=entry_ts,
            action="entry", quantity=float(shares), price=entry_price,
        ),
        event_ts=entry_ts,
    )
    # Exit price chosen to reproduce the requested r_multiple under the
    # shim's recomputation (risk_per_share = entry_price - 9.0 = 1.0).
    exit_price = entry_price + r_multiple
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=tid, fill_datetime=exit_ts,
            action="exit", quantity=float(shares), price=exit_price,
            reason="stop-hit",
        ),
        event_ts=exit_ts,
    )
    conn.execute("UPDATE trades SET state=? WHERE id=?", (state, tid))
    return tid


def _add_open(conn, *, ticker, entry_date, label, shares=100, entry_price=10.0):
    """Insert an open trade (no exit). Used to test in-flight count."""
    entry_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date, entry_price=entry_price,
        initial_shares=shares, initial_stop=9.0, current_stop=9.0,
        state="entered", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, hypothesis_label=label,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at=entry_ts,
    )
    tid = insert_trade_with_event(conn, trade, event_ts=entry_ts)
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=tid, fill_datetime=entry_ts,
            action="entry", quantity=float(shares), price=entry_price,
        ),
        event_ts=entry_ts,
    )
    return tid


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
        # B.9: shim recomputes r_multiple from fills; FP arithmetic of
        # (exit_price - entry_price) / risk_per_share introduces ε noise.
        assert sub.mean_r_multiple == pytest.approx(-0.33, abs=1e-9)
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


def test_breakdown_includes_reviewed_trades_in_current_sample(tmp_db: Path):
    """B.9 discriminator: a 'reviewed' (post-review-completed) trade
    counts toward current_sample alongside 'closed'. Pre-fix
    list_closed_trades returned only state='closed'; reviewed trades
    silently dropped from hypothesis attribution + win-rate math.
    """
    conn = _setup(tmp_db)
    try:
        with conn:
            _add_closed(
                conn, ticker="AAA", entry_date="2026-04-10",
                label="Sub-A+ VCP-not-formed test",
                r_multiple=-0.5, realized_pnl=-50.0, state="closed",
            )
            _add_closed(
                conn, ticker="BBB", entry_date="2026-04-11",
                label="Sub-A+ VCP-not-formed test",
                r_multiple=-0.5, realized_pnl=-50.0, state="reviewed",
            )
        rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
        sub = next(r for r in rows if r.name == "Sub-A+ VCP-not-formed")
        assert sub.current_sample == 2, (
            f"current_sample must include closed AND reviewed trades; "
            f"got {sub.current_sample}. Pre-fix the predicate was state == "
            f"'closed' so the reviewed trade dropped out."
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
