"""D79 T7a -- ``check_exit_preconditions``, the six refusals made importable
(CHARC executing FORK 1 ruling: A1, the helper PURE).

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md`` T7;
the ruling is block-quoted in the exec ledger beside it. The helper takes the
trade ROW and the request and performs NO read, so the route can ORDER the
refusals before the F1 question while ``record_exit``'s own in-lock call
stays the barrier. Discriminator (iv): each of the six refusals raises with
the EXISTING message text, in the ruled order, and ``inspect.signature``
shows no connection parameter (a helper that reads would need one).
"""
from __future__ import annotations

import inspect
import math

import pytest

from swing.data.models import Trade
from swing.trades.exit import (
    ExitPriceRefusedError,
    ExitReason,
    ExitRequest,
    check_exit_preconditions,
)


def _trade(*, state: str = "entered", current_size: float = 10.0) -> Trade:
    return Trade(
        id=7, ticker="NVDA", entry_date="2026-04-15", entry_price=100.0,
        initial_shares=10, initial_stop=95.0, current_stop=95.0, state=state,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        current_size=current_size,
    )


def _req(**over) -> ExitRequest:
    fields = dict(trade_id=7, exit_date="2026-05-21", exit_price=131.0,
                  shares=3, reason=ExitReason.MANUAL, notes=None,
                  rationale="manual", event_ts="2026-05-21T16:00:00")
    fields.update(over)
    return ExitRequest(**fields)


def test_t7a_iv_signature_takes_no_connection():
    params = list(inspect.signature(check_exit_preconditions).parameters)
    assert params == ["trade", "req"]
    assert not any("conn" in p for p in params)


def test_t7a_iv_accepts_a_valid_request():
    assert check_exit_preconditions(_trade(), _req()) is None
    # Exactly the remaining size is allowed (the bound is "exceeds").
    assert check_exit_preconditions(_trade(), _req(shares=10)) is None


@pytest.mark.parametrize("trade, req, exc_type, text", [
    (_trade(), _req(reason="manual"), ValueError,
     "invalid exit reason: manual"),
    (_trade(), _req(shares=0), ValueError, "shares must be > 0; got 0"),
    (_trade(), _req(exit_price=0.0), ExitPriceRefusedError,
     "exit price must be > 0; got 0.0"),
    (_trade(), _req(exit_price=math.nan), ExitPriceRefusedError,
     "exit price must be > 0; got nan"),
    (None, _req(), ValueError, "trade 7 not found"),
    (_trade(state="closed"), _req(), ValueError,
     "trade 7 not active (state='closed'); exits only permitted from "
     "['entered', 'managing', 'partial_exited']"),
    (_trade(current_size=2.0), _req(), ValueError,
     "exit shares 3 exceeds remaining current_size 2.0"),
])
def test_t7a_iv_each_refusal_keeps_its_existing_text(trade, req, exc_type,
                                                     text):
    with pytest.raises(exc_type) as info:
        check_exit_preconditions(trade, req)
    assert str(info.value) == text


def test_t7a_iv_the_refusals_run_in_the_ruled_order():
    """Invalid reason, shares, price, not found, not active, exceeds: a
    request failing EVERY check names the first, and each one removed
    reveals the next."""
    bad = dict(reason="manual", shares=-1, exit_price=0.0)
    closed_small = _trade(state="closed", current_size=0.0)
    seen: list[str] = []
    steps = [
        (None, bad),
        (None, dict(bad, reason=ExitReason.MANUAL)),
        (None, dict(bad, reason=ExitReason.MANUAL, shares=3)),
        (None, {}),
        (closed_small, {}),
        (_trade(current_size=0.0), {}),
    ]
    for trade, over in steps:
        with pytest.raises(ValueError) as info:
            check_exit_preconditions(trade, _req(**over))
        seen.append(str(info.value).split(";")[0].split(" got")[0])
    assert seen == [
        "invalid exit reason: manual",
        "shares must be > 0",
        "exit price must be > 0",
        "trade 7 not found",
        "trade 7 not active (state='closed')",
        "exit shares 3 exceeds remaining current_size 0.0",
    ]
