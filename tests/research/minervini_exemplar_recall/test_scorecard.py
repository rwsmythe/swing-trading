# tests/research/minervini_exemplar_recall/test_scorecard.py
from __future__ import annotations

import pytest


def test_wilson_interval_known_value():
    from research.harness.minervini_exemplar_recall.scorecard import wilson_interval

    ci = wilson_interval(8, 10, z=1.96)
    # Wilson 95% CI for 8/10 at z=1.96:
    #   center = (0.8 + 1.96^2/20)/(1 + 1.96^2/10) = 0.716738
    #   half   = 1.96*sqrt(0.8*0.2/10 + 1.96^2/400)/(1 + 1.96^2/10) = 0.226582
    # WRONG-PATH (normal/Wald): lower = 0.8 - 0.2479 = 0.5521.  RIGHT-PATH (Wilson): 0.4902.
    assert ci.lower == pytest.approx(0.4902, abs=1e-3)
    assert ci.upper == pytest.approx(0.9433, abs=1e-3)
    assert ci.p_hat == pytest.approx(0.8)
    assert ci.n == 10


def test_wilson_interval_n_zero_is_uninformative():
    from research.harness.minervini_exemplar_recall.scorecard import wilson_interval

    ci = wilson_interval(0, 0)
    assert ci.lower == 0.0 and ci.upper == 1.0 and ci.n == 0


def test_clustered_resample_keeps_amzn_rows_together():
    import random

    from research.harness.minervini_exemplar_recall.scorecard import _clustered_resample

    by_ticker = {"AMZN": [("AMZN", True), ("AMZN", False)], "MSFT": [("MSFT", True)], "CSCO": [("CSCO", True)]}
    rng = random.Random(123)
    for _ in range(500):
        rows = _clustered_resample(rng, by_ticker)
        amzn = sum(1 for r in rows if r[0] == "AMZN")
        # WRONG-PATH (IID row bootstrap): AMZN count can be odd.
        # RIGHT-PATH (cluster on ticker): AMZN's two rows always move together -> even.
        assert amzn % 2 == 0


def test_bootstrap_is_deterministic():
    from research.harness.minervini_exemplar_recall.scorecard import ticker_clustered_bootstrap

    rows = [("AMZN", True), ("AMZN", False), ("MSFT", True), ("CSCO", True), ("INTC", False)]
    val = lambda rs: sum(1 for _, ok in rs if ok) / len(rs) if rs else 0.0
    a = ticker_clustered_bootstrap(rows, val, b=200, base_seed=7)
    b = ticker_clustered_bootstrap(rows, val, b=200, base_seed=7)
    assert (a.lower, a.upper) == (b.lower, b.upper)
    assert a.b == 200


def test_screening_recall_stratified_excludes_attrition():
    from research.harness.minervini_exemplar_recall.scorecard import screening_recall

    # 10 total: 4 surfaced, 2 gate-skip, 3 insufficient, 1 no_data.
    outcomes = (["surfaced_aplus"] * 2 + ["surfaced_watch"] * 2 + ["skip_gate_rejection"] * 2
                + ["skip_insufficient_history"] * 3 + ["no_data"])
    full, screenable = screening_recall(outcomes)
    # full = 4/10 = 0.4 ; screenable denom excludes insufficient+no_data -> 4/6.
    assert full == pytest.approx(0.4)
    assert screenable == pytest.approx(4 / 6)
