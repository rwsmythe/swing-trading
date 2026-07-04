from __future__ import annotations

import json

import pytest

from research.harness.shadow_expectancy.io import Bar, parse_bar
from research.harness.shadow_expectancy.validate import (
    validate_bars,
    validate_candidate_levels,
    validate_signal,
)


def _ohlc(o, h, l, c, v=1000.0, provider="yfinance"):  # noqa: E741
    return json.dumps({"open": o, "high": h, "low": l, "close": c,
                       "volume": v, "provider": provider})


def test_parse_bar_reads_lowercase_keys():
    b = parse_bar(_ohlc(10.0, 11.0, 9.5, 10.5), session="2026-05-29")
    assert (b.open, b.high, b.low, b.close, b.session) == (10.0, 11.0, 9.5, 10.5, "2026-05-29")


def test_candidate_levels_ok():
    assert validate_candidate_levels(pivot=10.0) is None


@pytest.mark.parametrize("pivot", [0.0, -5.0, float("nan"), None])
def test_candidate_levels_reject_with_no_candidate_pivot(pivot):
    # spec 3.2: a null / non-finite / <=0 screening pivot is a COMMON expected state, not a
    # corrupt bar -> its OWN reason `no_candidate_pivot`, split from invalid_ohlc.
    assert validate_candidate_levels(pivot=pivot) == "no_candidate_pivot"


def test_candidate_initial_stop_does_not_gate_eligibility():
    # Codex R2-M1: candidate.initial_stop is irrelevant to eligibility -- it is not even a
    # parameter anymore. A valid pivot is accepted regardless of any (stale / inverted)
    # candidate stop, because the mechanical trade stop is entry_bar.low (C1/D6).
    assert validate_candidate_levels(pivot=10.0) is None


def test_bars_reject_high_lt_low():
    bars = [Bar("2026-05-29", 10.0, 9.0, 11.0, 9.5)]  # high < low
    assert validate_bars(bars) == "invalid_ohlc"


def test_bars_reject_nan_and_negative():
    assert validate_bars([Bar("2026-05-29", 10.0, 11.0, -1.0, 10.5)]) == "invalid_ohlc"
    assert validate_bars([Bar("2026-05-29", 10.0, float("inf"), 9.0, 10.5)]) == "invalid_ohlc"


def test_bars_reject_non_chronological_and_duplicate():
    a = Bar("2026-05-30", 10.0, 11.0, 9.5, 10.5)
    b = Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)
    assert validate_bars([a, b]) == "invalid_ohlc"
    assert validate_bars([b, b]) == "invalid_ohlc"


def test_validate_signal_chains_levels_then_bars():
    good = [Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)]
    bad_bar = [Bar("2026-05-29", 10.0, 9.0, 11.0, 9.5)]  # high < low
    assert validate_signal(pivot=10.0, bars=good) is None
    # bad pivot -> levels reject with the pivot-specific reason
    assert validate_signal(pivot=0.0, bars=good) == "no_candidate_pivot"
    # bad bar -> bars reject with invalid_ohlc
    assert validate_signal(pivot=10.0, bars=bad_bar) == "invalid_ohlc"


# --- 19-D epsilon-tolerant reader clamp. Ragged bars lifted verbatim from the live archive. ---
from research.harness.shadow_expectancy.validate import (  # noqa: E402
    clamp_ragged_bars,
    _shape_violation_pct,
)

# Real DINO 06-18: high 65.51 < max(o,c)=65.78 -> hi_delta 0.27; 0.27/64.50 = 0.4186%.
_DINO = Bar(session="2026-06-18", open=65.78, high=65.51, low=63.85, close=64.50)
# Real CALY 07-01: low 18.4001 > min(o,c)=18.09 -> lo_delta 0.3101; /18.64 = 1.6636%.
_CALY = Bar(session="2026-07-01", open=18.09, high=18.99, low=18.4001, close=18.64)
_CLEAN = Bar(session="2026-06-19", open=64.6, high=66.0, low=64.4, close=65.8)


def test_shape_violation_pct_matches_live_magnitudes():
    assert abs(_shape_violation_pct(_DINO) - 0.4186) < 0.001
    assert abs(_shape_violation_pct(_CALY) - 1.6636) < 0.001
    assert _shape_violation_pct(_CLEAN) == 0.0


def test_t4_math_dino_class_clamped_at_1pct_recovers_bar():
    # PRE-FIX (max_pct 0.0): 0.4186 > 0 -> NOT clamped -> validate_bars rejects it.
    off, ev_off = clamp_ragged_bars([_DINO], max_pct=0.0)
    assert off == [_DINO] and ev_off == []
    assert validate_bars(off) == "invalid_ohlc"
    # POST-FIX (max_pct 1.0): clamped high -> 65.78; now valid.
    on, ev_on = clamp_ragged_bars([_DINO], max_pct=1.0)
    assert on[0].high == 65.78 and on[0].low == 63.85    # only high widened
    assert validate_bars(on) is None
    assert len(ev_on) == 1 and ev_on[0].session == "2026-06-18"


def test_t5_math_caly_class_not_clamped_at_1pct_but_clamped_at_2pct():
    # At the production 1.0% threshold CALY stays invalid under BOTH the clamp and validate.
    on, ev = clamp_ragged_bars([_CALY], max_pct=1.0)
    assert on == [_CALY] and ev == []
    assert validate_bars(on) == "invalid_ohlc"
    # The fixture is NOT trivially always-invalid: at 2.0% it clamps + recovers (boundary is real).
    up, ev2 = clamp_ragged_bars([_CALY], max_pct=2.0)
    assert up[0].low == 18.09 and up[0].high == 18.99    # only low widened
    assert validate_bars(up) is None and len(ev2) == 1


def test_clamp_leaves_non_finite_bar_untouched():
    nan_bar = Bar(session="d", open=float("nan"), high=1.0, low=0.5, close=0.9)
    out, ev = clamp_ragged_bars([nan_bar], max_pct=1.0)
    assert out == [nan_bar] and ev == []                 # cannot widen a NaN -> passthrough
    assert validate_bars(out) == "invalid_ohlc"


def test_clamp_is_idempotent_and_never_creates_high_below_low():
    once, _ = clamp_ragged_bars([_DINO], max_pct=1.0)
    twice, ev2 = clamp_ragged_bars(once, max_pct=1.0)
    assert twice == once and ev2 == []                   # already clamped -> no-op
    assert twice[0].high >= twice[0].low
