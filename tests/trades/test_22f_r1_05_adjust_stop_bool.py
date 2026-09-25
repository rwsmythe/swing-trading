"""22-F R1-05 -- `adjust_stop` returns `bool` (CHARC's GRANTED amendment to
`swing/trades/stop_adjust.py`, bounded to this one additive change): True
when `update_stop_with_event` ran, False on the equal-stop no-op.  PRE-FIX
it returned None on both paths.  A counting wrapper at the name
`adjust_stop` resolves at call time (`swing.trades.stop_adjust.
update_stop_with_event`) asserts which path ran (did-it-fire)."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import CountingWrapper


@pytest.fixture
def conn(tmp_path: Path):
    c = ensure_schema(tmp_path / "t.db")
    c.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, "
        " initial_stop, current_stop, state, trade_origin, "
        " pre_trade_locked_at, current_size, current_avg_cost) "
        "VALUES (1, 'DHC', '2026-05-01', 100.0, 50, 90.0, 92.0, "
        "'managing', 'manual_off_pipeline', '2026-05-01T09:30:00', "
        "50.0, 100.0)")
    c.commit()
    yield c
    c.close()


def _req(new_stop: float):
    from swing.trades.stop_adjust import StopAdjustRequest
    return StopAdjustRequest(trade_id=1, new_stop=new_stop,
                             rationale="manual-trail", notes=None,
                             event_ts="2026-05-07T18:00:00", force=False)


@pytest.mark.parametrize("new_stop,expected,calls", [
    (92.0, False, 0),
    (95.0, True, 1),
])
def test_adjust_stop_reports_whether_it_wrote(new_stop, expected, calls,
                                              conn, monkeypatch):
    import swing.trades.stop_adjust as mod
    wrapper = CountingWrapper(mod.update_stop_with_event)
    monkeypatch.setattr(mod, "update_stop_with_event", wrapper)
    out = mod.adjust_stop(conn, _req(new_stop))
    assert wrapper.calls == calls
    assert out is expected
    stop = conn.execute("SELECT current_stop FROM trades WHERE id = 1"
                        ).fetchone()[0]
    assert stop == new_stop
