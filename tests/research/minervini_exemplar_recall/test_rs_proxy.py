# tests/research/minervini_exemplar_recall/test_rs_proxy.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.config import Config
from swing.evaluation.rs import compute_rs


def _bars(closes, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [1_000] * len(closes)},
        index=idx,
    )


def test_p0_excess_pass_boundary(tmp_path):
    from research.harness.minervini_exemplar_recall.rs_proxy import build_batch

    cfg = Config.from_defaults()  # horizon_weeks=12 -> H=60; need 61 bars; fallback_extreme_pct=20.0
    # 70 bars; exemplar rises so trailing-60 return = 125/100 - 1 = 0.25; SPY flat (return 0).
    ex_closes = [100.0] * 10 + list(_lin(100.0, 125.0, 60))
    spy_closes = [100.0] * 70
    ex = _bars(ex_closes)
    spy = _bars(spy_closes)
    session = ex.index[-1].date()
    out = build_batch(ticker="AAA", exemplar_sliced=ex, spy_full=spy, session=session, config=cfg)
    assert out.rs_path == "P0"
    assert out.excess == pytest.approx(0.25, abs=1e-6)
    # Drive it through compute_rs to confirm TT8 would PASS (excess 0.25 >= 0.20).
    rs = compute_rs("AAA", out.batch.returns_12w_by_ticker, out.batch.universe_tickers,
                    spy_return=out.batch.spy_return_12w)
    assert rs.method == "fallback_spy"
    assert rs.return_vs_spy == pytest.approx(0.25, abs=1e-6)


def test_p0_na_band(tmp_path):
    from research.harness.minervini_exemplar_recall.rs_proxy import build_batch

    cfg = Config.from_defaults()
    ex = _bars([100.0] * 10 + list(_lin(100.0, 115.0, 60)))  # trailing-60 return 0.15 -> na band
    spy = _bars([100.0] * 70)
    out = build_batch(ticker="AAA", exemplar_sliced=ex, spy_full=spy, session=ex.index[-1].date(), config=cfg)
    assert out.excess == pytest.approx(0.15, abs=1e-6)  # in [-0.20, 0.20) -> TT8 na


def test_p1_when_spy_too_short_yields_unavailable(tmp_path):
    from research.harness.minervini_exemplar_recall.rs_proxy import build_batch

    cfg = Config.from_defaults()
    ex = _bars([100.0 + i for i in range(70)])
    spy = _bars([100.0] * 30)  # < 61 bars -> P0 precondition fails -> P1
    out = build_batch(ticker="AAA", exemplar_sliced=ex, spy_full=spy, session=ex.index[-1].date(), config=cfg)
    assert out.rs_path == "P1"
    assert out.excess is None
    # INVARIANT: empty returns dict -> compute_rs returns 'unavailable' before touching spy_return.
    assert out.batch.returns_12w_by_ticker == {}
    rs = compute_rs("AAA", out.batch.returns_12w_by_ticker, out.batch.universe_tickers,
                    spy_return=out.batch.spy_return_12w)
    assert rs.method == "unavailable"  # WRONG-PATH (P1 inserts a ticker key): 'fallback_spy'.


def _lin(a, b, n):
    step = (b - a) / (n - 1)
    return [a + step * i for i in range(n)]
