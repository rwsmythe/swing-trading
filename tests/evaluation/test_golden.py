"""Golden test: hand-verified OHLCV -> expected bucket.

Unlike parity (which anchors to legacy output), golden fixtures encode domain
knowledge — they are the real correctness test.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_one

GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden"


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _fixtures():
    return sorted(p for p in GOLDEN_DIR.glob("*.csv"))


@pytest.mark.parametrize("fixture_csv", _fixtures(), ids=lambda p: p.stem)
def test_golden_expected_bucket(fixture_csv: Path, sample_config):
    expected = yaml.safe_load(
        (fixture_csv.parent / f"{fixture_csv.stem}.expected.yaml").read_text()
    )
    df = _load_csv(fixture_csv)

    ticker = fixture_csv.stem.upper()
    # Put ticker at TOP of RS universe so TT8 passes (rank 99 >= 70 threshold)
    # Override per fixture where TT8 should fail.
    returns = {ticker: 1.00, "REF1": 0.10, "REF2": 0.20, "REF3": 0.40, "REF4": 0.50}
    if "rs_low" in fixture_csv.stem:
        returns[ticker] = -0.20  # force bottom rank -> TT8 fails

    ctx = CandidateContext(
        ticker=ticker,
        ohlcv=df,
        config=sample_config,
        batch=BatchContext(
            returns_12w_by_ticker=returns,
            universe_tickers=(ticker, "REF1", "REF2", "REF3", "REF4"),
            universe_version="golden-v1",
            universe_hash="x",
            spy_return_12w=0.08,
        ),
        market=MarketContext(),
        current_equity=10000.0,
    )
    candidate = evaluate_one(ctx)
    assert candidate.bucket == expected["expected_bucket"], (
        f"Expected {expected['expected_bucket']} but got {candidate.bucket}. "
        f"Criteria: {[(c.criterion_name, c.result) for c in candidate.criteria]}"
    )
