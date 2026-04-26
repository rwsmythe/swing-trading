"""Tests for swing.recommendations.hypothesis.compute_tripwire_status.

Per brief §4.4 + §5 watch items:
- consecutive_max_loss_streak walks trailing closed trades by entry_date
- absolute_tripwire fires when |cumulative_loss| / starting_equity >=
  absolute_loss_tripwire_pct / 100
- Hypothesis identity: case-insensitive substring of hypothesis name in
  trade.hypothesis_label (matches VIR's free-text backfill).
"""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import Exit, Trade
from swing.data.repos.hypothesis import list_hypotheses
from swing.data.repos.trades import (
    insert_exit_with_event,
    insert_trade_with_event,
)
from swing.recommendations.hypothesis import (
    TripwireStatus,
    compute_tripwire_status,
)


def _setup(tmp_db: Path):
    return ensure_schema(tmp_db)


def _add_open_trade(conn, *, ticker: str, entry_date: str, label: str | None,
                    initial_stop: float = 9.0, entry_price: float = 10.0,
                    shares: int = 100) -> int:
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date, entry_price=entry_price,
        initial_shares=shares, initial_stop=initial_stop, current_stop=initial_stop,
        status="open", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, hypothesis_label=label,
    )
    return insert_trade_with_event(
        conn, trade, event_ts=f"{entry_date}T09:30:00",
    )


def _close_trade_with_r(conn, trade_id: int, *, exit_date: str,
                        r_multiple: float, realized_pnl: float,
                        shares: int = 100, exit_price: float = 9.0):
    e = Exit(
        id=None, trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
        shares=shares, reason="stop-hit", realized_pnl=realized_pnl,
        r_multiple=r_multiple, notes=None,
    )
    insert_exit_with_event(conn, e, event_ts=f"{exit_date}T16:00:00")


def _hyp(conn, name: str):
    return next(h for h in list_hypotheses(conn) if h.name == name)


def test_no_trades_no_tripwire(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            pass
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.current_sample == 0
        assert status.consecutive_max_loss_streak == 0
        assert status.cumulative_loss == 0.0
        assert status.consecutive_tripwire_fired is False
        assert status.absolute_tripwire_fired is False
        assert status.any_tripwire_fired is False
    finally:
        conn.close()


def test_single_loss_does_not_fire(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            t1 = _add_open_trade(
                conn, ticker="VIR", entry_date="2026-04-20",
                label="sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)",
            )
            _close_trade_with_r(
                conn, t1, exit_date="2026-04-22",
                r_multiple=-0.33, realized_pnl=-2.0,
            )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.current_sample == 1
        # -0.33R does NOT count as a max-loss (tripwire pattern is r ≤ -1)
        assert status.consecutive_max_loss_streak == 0
        assert status.cumulative_loss == -2.0
        assert status.any_tripwire_fired is False
    finally:
        conn.close()


def test_consecutive_max_loss_fires_at_threshold(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")  # threshold = 3
        with conn:
            for i, day in enumerate(["2026-04-10", "2026-04-12", "2026-04-14"]):
                tid = _add_open_trade(
                    conn, ticker=f"AAA{i}", entry_date=day,
                    label="Sub-A+ VCP-not-formed inaugural sample",
                )
                _close_trade_with_r(
                    conn, tid, exit_date=day, r_multiple=-1.0, realized_pnl=-50.0,
                )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.consecutive_max_loss_streak == 3
        assert status.consecutive_tripwire_fired is True
        # |cumulative_loss| = 150 / 7500 = 2% — below 5% threshold
        assert status.absolute_tripwire_fired is False
        assert status.any_tripwire_fired is True
    finally:
        conn.close()


def test_consecutive_streak_breaks_on_winner(tmp_db: Path):
    """Winner in the middle resets the trailing streak."""
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            # 2 losses, then 1 winner, then 2 more losses (most recent)
            sequence = [
                ("2026-04-01", -1.0, -50.0),
                ("2026-04-02", -1.5, -75.0),
                ("2026-04-03", +2.0, +100.0),
                ("2026-04-04", -1.0, -50.0),
                ("2026-04-05", -1.0, -50.0),
            ]
            for i, (d, r, p) in enumerate(sequence):
                tid = _add_open_trade(
                    conn, ticker=f"AAA{i}", entry_date=d,
                    label="Sub-A+ VCP-not-formed",
                )
                _close_trade_with_r(
                    conn, tid, exit_date=d, r_multiple=r, realized_pnl=p,
                )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        # Trailing 2 are -1R each; breaks at the +2R earlier
        assert status.consecutive_max_loss_streak == 2
        # Threshold is 3 → not fired
        assert status.consecutive_tripwire_fired is False
    finally:
        conn.close()


def test_absolute_loss_tripwire_fires(tmp_db: Path):
    """Cumulative realized loss exceeds 5% of $7,500 = $375.

    Per pre-fix arithmetic check: -200 + -100 + -100 = -400; |−400| / 7500
    = 5.33% > 5% → fires. With -200 + -100 + -50 = -350; 4.67% < 5% →
    does not fire. The test is constructed to cross the boundary."""
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            for i, (d, r, p) in enumerate([
                ("2026-04-01", -0.5, -200.0),
                ("2026-04-02", -0.5, -100.0),
                ("2026-04-03", -0.5, -100.0),
            ]):
                tid = _add_open_trade(
                    conn, ticker=f"AA{i}", entry_date=d,
                    label="Sub-A+ VCP-not-formed",
                )
                _close_trade_with_r(
                    conn, tid, exit_date=d, r_multiple=r, realized_pnl=p,
                )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.cumulative_loss == -400.0
        assert status.absolute_tripwire_fired is True
        # No -1R streak → consecutive tripwire stays clean
        assert status.consecutive_tripwire_fired is False
        assert status.any_tripwire_fired is True
    finally:
        conn.close()


def test_absolute_loss_threshold_boundary_does_not_fire(tmp_db: Path):
    """Exactly 5% — does the rule fire at >=? Yes per brief: 'cumulative
    realized loss across hypothesis trades exceeds 5% of starting equity'.
    Pinning >= for clarity."""
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            tid = _add_open_trade(
                conn, ticker="ZZZ", entry_date="2026-04-01",
                label="Sub-A+ VCP-not-formed",
            )
            _close_trade_with_r(
                conn, tid, exit_date="2026-04-01",
                r_multiple=-0.5, realized_pnl=-375.0,  # exactly 5%
            )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        # |-375| / 7500 = 0.05 == 0.05 → fires (>=)
        assert status.absolute_tripwire_fired is True
    finally:
        conn.close()


def test_both_tripwires_can_fire_simultaneously(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            for i, d in enumerate(["2026-04-01", "2026-04-02", "2026-04-03"]):
                tid = _add_open_trade(
                    conn, ticker=f"AA{i}", entry_date=d,
                    label="Sub-A+ VCP-not-formed",
                )
                _close_trade_with_r(
                    conn, tid, exit_date=d, r_multiple=-1.0, realized_pnl=-200.0,
                )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.consecutive_tripwire_fired is True
        assert status.absolute_tripwire_fired is True
        assert status.any_tripwire_fired is True
    finally:
        conn.close()


def test_label_match_is_case_insensitive_substring(tmp_db: Path):
    """Per brief §8: VIR's label was 'sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test'
    — must match the 'Sub-A+ VCP-not-formed' hypothesis. Case-insensitive substring."""
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        vir_label = (
            "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); "
            "inaugural trade test"
        )
        with conn:
            tid = _add_open_trade(
                conn, ticker="VIR", entry_date="2026-04-20", label=vir_label,
            )
            _close_trade_with_r(
                conn, tid, exit_date="2026-04-22",
                r_multiple=-0.33, realized_pnl=-2.0,
            )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.current_sample == 1
        assert status.cumulative_loss == -2.0
    finally:
        conn.close()


def test_unrelated_label_does_not_count(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            tid = _add_open_trade(
                conn, ticker="ABC", entry_date="2026-04-01",
                label="A+ baseline trade #1",
            )
            _close_trade_with_r(
                conn, tid, exit_date="2026-04-02",
                r_multiple=-1.0, realized_pnl=-50.0,
            )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        # Sub-A+ VCP-not-formed should see ZERO trades — the label
        # belongs to A+ baseline.
        assert status.current_sample == 0
    finally:
        conn.close()


def test_null_label_never_matches(tmp_db: Path):
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "A+ baseline")
        with conn:
            tid = _add_open_trade(
                conn, ticker="NUL", entry_date="2026-04-01", label=None,
            )
            _close_trade_with_r(
                conn, tid, exit_date="2026-04-02",
                r_multiple=-1.0, realized_pnl=-50.0,
            )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.current_sample == 0
    finally:
        conn.close()


def test_unknown_hypothesis_id_raises(tmp_db: Path):
    import pytest as _pt
    conn = _setup(tmp_db)
    try:
        with _pt.raises(ValueError, match="not found"):
            compute_tripwire_status(
                conn, hypothesis_id=99999, starting_equity=7500.0,
            )
    finally:
        conn.close()


def test_open_trade_does_not_count_toward_sample(tmp_db: Path):
    """Open trades have no realized R; they shouldn't affect the
    tripwire arithmetic. (Implicit per brief §4.4 — R-multiple is
    realized-only.)"""
    conn = _setup(tmp_db)
    try:
        h = _hyp(conn, "Sub-A+ VCP-not-formed")
        with conn:
            _add_open_trade(
                conn, ticker="OPN", entry_date="2026-04-01",
                label="Sub-A+ VCP-not-formed",
            )
        status = compute_tripwire_status(
            conn, hypothesis_id=h.id, starting_equity=7500.0,
        )
        assert status.current_sample == 0
    finally:
        conn.close()
