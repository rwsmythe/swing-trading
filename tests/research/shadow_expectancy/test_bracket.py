from __future__ import annotations

import pytest

from research.harness.shadow_expectancy.bracket import (
    ma_exit_fill, price_stop_fill,
)


def test_price_stop_realistic_gaps_through_below_stop():
    # gap-down open below stop: realistic fills at min(stop, open) = open
    assert price_stop_fill("realistic", stop=9.0, bar_open=8.5) == 8.5


def test_price_stop_realistic_no_gap_fills_at_stop():
    assert price_stop_fill("realistic", stop=9.0, bar_open=9.4) == 9.0


def test_price_stop_favorable_always_at_stop():
    assert price_stop_fill("favorable_reprice", stop=9.0, bar_open=8.5) == 9.0


def test_ma_exit_realistic_is_next_open():
    assert ma_exit_fill("realistic", signal_close=11.0, next_open=10.6) == 10.6


def test_ma_exit_favorable_is_max_of_close_and_open():
    assert ma_exit_fill("favorable_reprice", signal_close=11.0, next_open=10.6) == 11.0
    assert ma_exit_fill("favorable_reprice", signal_close=10.4, next_open=10.9) == 10.9


def test_favorable_ge_realistic_for_a_given_exit():
    for arm_pair in [(9.0, 8.5), (9.0, 9.4)]:
        stop, op = arm_pair
        assert (price_stop_fill("favorable_reprice", stop=stop, bar_open=op)
                >= price_stop_fill("realistic", stop=stop, bar_open=op))
