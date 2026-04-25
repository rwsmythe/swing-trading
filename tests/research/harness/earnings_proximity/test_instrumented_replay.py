"""Instrumented-replay tests for the candidate-sparsity diagnostic.

The instrumented replay is a thin wrapper around the standard ``replay()``
that emits one ``EvaluationRecord`` per (ticker, date) pair the evaluator
saw — including non-A+ outcomes — with per-criterion pass/fail dictionaries
and a ``binding_constraint`` field naming the first criterion that blocked
A+ classification (after honoring trend-template ``allowed_miss_names``).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from research.harness.earnings_proximity import instrumented_replay as mod
from research.harness.earnings_proximity.replay import build_harness_config
from swing.data.models import Candidate, CriterionResult


def _build_ohlcv(start: str, n_bars: int, base_close: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n_bars, freq="B")
    return pd.DataFrame(
        {
            "Open": [base_close + i * 0.1 for i in range(n_bars)],
            "High": [base_close + i * 0.1 + 0.5 for i in range(n_bars)],
            "Low": [base_close + i * 0.1 - 0.5 for i in range(n_bars)],
            "Close": [base_close + i * 0.1 for i in range(n_bars)],
            "Volume": [1_000_000 for _ in range(n_bars)],
        },
        index=idx,
    )


def _crit(name: str, layer: str, result: str = "pass") -> CriterionResult:
    return CriterionResult(criterion_name=name, layer=layer, result=result)


# Production criterion names, in the order evaluator builds them.
TT_NAMES = (
    "TT1_close_above_ma200",
    "TT2_ma150_above_ma200",
    "TT3_ma200_rising",
    "TT4_ma50_above_ma150",
    "TT5_close_above_ma50",
    "TT6_close_high_52w_margin",
    "TT7_close_low_52w_min",
    "TT8_rs_rank",
)
VCP_NAMES = (
    "prior_trend",
    "ma_stack_short",
    "rising_ma_short",
    "proximity",
    "adr",
    "pullback",
    "tightness",
    "vcp",
    "orderliness",
)


def _all_pass_criteria() -> tuple[CriterionResult, ...]:
    return (
        *(_crit(n, "trend_template") for n in TT_NAMES),
        *(_crit(n, "vcp") for n in VCP_NAMES),
        _crit("risk_feasibility", "risk"),
    )


def _candidate(
    ticker: str,
    *,
    bucket: str,
    criteria: tuple[CriterionResult, ...],
    pivot: float = 110.0,
    stop: float = 100.0,
) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket=bucket,
        close=109.5,
        pivot=pivot,
        initial_stop=stop,
        adr_pct=4.5,
        tight_streak=3,
        pullback_pct=15.0,
        prior_trend_pct=30.0,
        rs_rank=80,
        rs_return_12w_vs_spy=0.15,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=criteria,
    )


# ----------------------------------------------------------------------------
# Per-(ticker, date) record emission
# ----------------------------------------------------------------------------


def test_record_emitted_for_every_evaluable_ticker_date(monkeypatch):
    """Two trading days × two tickers = 4 records, regardless of bucket."""
    def fake_evaluate_one(ctx):
        bucket = "aplus" if ctx.ticker == "AAPL" else "watch"
        crits = _all_pass_criteria() if ctx.ticker == "AAPL" else (
            *(_crit(n, "trend_template") for n in TT_NAMES),
            *(_crit(n, "vcp") for n in VCP_NAMES[:1]),  # prior_trend pass
            _crit(VCP_NAMES[1], "vcp", "fail"),  # ma_stack_short fails
            *(_crit(n, "vcp") for n in VCP_NAMES[2:]),
            _crit("risk_feasibility", "risk"),
        )
        return _candidate(ctx.ticker, bucket=bucket, criteria=crits)

    monkeypatch.setattr(mod, "evaluate_one", fake_evaluate_one)

    ohlcv = {
        "AAPL": _build_ohlcv("2024-01-02", 300),
        "MSFT": _build_ohlcv("2024-01-02", 300),
    }
    trading_days = [date(2025, 2, 24), date(2025, 2, 25)]
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL", "MSFT"),
            trading_days=trading_days,
            ohlcv=ohlcv,
            earnings={"AAPL": [], "MSFT": []},
            cfg=build_harness_config(),
        )
    )
    assert len(records) == 4
    seen = {(r.ticker, r.date) for r in records}
    assert seen == {
        ("AAPL", date(2025, 2, 24)),
        ("AAPL", date(2025, 2, 25)),
        ("MSFT", date(2025, 2, 24)),
        ("MSFT", date(2025, 2, 25)),
    }


# ----------------------------------------------------------------------------
# binding_constraint — semantics
# ----------------------------------------------------------------------------


def test_binding_constraint_none_for_aplus(monkeypatch):
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="aplus", criteria=_all_pass_criteria()),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    assert records[0].bucket == "aplus"
    assert records[0].binding_constraint is None


def test_binding_constraint_first_failing_vcp_for_watch(monkeypatch):
    """Watch bucket: ma_stack_short fails first → binding=ma_stack_short."""
    crits = (
        *(_crit(n, "trend_template") for n in TT_NAMES),
        _crit("prior_trend", "vcp"),
        _crit("ma_stack_short", "vcp", "fail"),  # FIRST fail
        *(_crit(n, "vcp") for n in VCP_NAMES[2:]),
        _crit("risk_feasibility", "risk"),
    )
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="watch", criteria=crits),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    assert records[0].bucket == "watch"
    assert records[0].binding_constraint == "ma_stack_short"


def test_binding_constraint_skips_allowed_miss_tt8(monkeypatch):
    """TT8 fail is in allowed_miss_names → A+ can still apply; binding=None."""
    crits = (
        *(_crit(n, "trend_template") for n in TT_NAMES[:7]),
        _crit("TT8_rs_rank", "trend_template", "fail"),  # allowed miss
        *(_crit(n, "vcp") for n in VCP_NAMES),
        _crit("risk_feasibility", "risk"),
    )
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="aplus", criteria=crits),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    assert records[0].bucket == "aplus"
    assert records[0].binding_constraint is None


def test_binding_constraint_picks_non_allowed_tt_fail(monkeypatch):
    """Non-allowed TT fail (e.g., TT1) → binding=TT1, even if other TTs also fail."""
    crits = (
        _crit("TT1_close_above_ma200", "trend_template", "fail"),
        *(_crit(n, "trend_template") for n in TT_NAMES[1:]),
        *(_crit(n, "vcp") for n in VCP_NAMES),
        _crit("risk_feasibility", "risk"),
    )
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="skip", criteria=crits),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    assert records[0].binding_constraint == "TT1_close_above_ma200"


def test_binding_constraint_picks_risk_feasibility_when_all_others_pass(monkeypatch):
    crits = (
        *(_crit(n, "trend_template") for n in TT_NAMES),
        *(_crit(n, "vcp") for n in VCP_NAMES),
        _crit("risk_feasibility", "risk", "fail"),
    )
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="skip", criteria=crits),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    assert records[0].bucket == "skip"
    assert records[0].binding_constraint == "risk_feasibility"


def test_binding_constraint_treats_na_as_fail(monkeypatch):
    """NA results count as fails for binding identification (per scoring.py:21)."""
    crits = (
        *(_crit(n, "trend_template") for n in TT_NAMES[:3]),
        _crit("TT4_ma50_above_ma150", "trend_template", "na"),  # NA → first non-pass
        *(_crit(n, "trend_template") for n in TT_NAMES[4:]),
        *(_crit(n, "vcp") for n in VCP_NAMES),
        _crit("risk_feasibility", "risk"),
    )
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="skip", criteria=crits),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    assert records[0].binding_constraint == "TT4_ma50_above_ma150"


# ----------------------------------------------------------------------------
# Aplus-only fields populated correctly
# ----------------------------------------------------------------------------


def test_aplus_record_has_entry_and_stop_and_earnings(monkeypatch):
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(
            ctx.ticker, bucket="aplus", criteria=_all_pass_criteria(), pivot=120.0, stop=110.0
        ),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": [date(2025, 4, 1)]},
            cfg=build_harness_config(),
        )
    )
    rec = records[0]
    assert rec.bucket == "aplus"
    assert rec.entry_target == pytest.approx(120.0)
    assert rec.initial_stop == pytest.approx(110.0)
    assert rec.next_earnings_date == date(2025, 4, 1)
    assert rec.absent_earnings_data is False


def test_non_aplus_record_has_no_signal_fields(monkeypatch):
    crits = (
        _crit("TT1_close_above_ma200", "trend_template", "fail"),
        *(_crit(n, "trend_template") for n in TT_NAMES[1:]),
        *(_crit(n, "vcp") for n in VCP_NAMES),
        _crit("risk_feasibility", "risk"),
    )
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="skip", criteria=crits),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": [date(2025, 4, 1)]},
            cfg=build_harness_config(),
        )
    )
    rec = records[0]
    assert rec.bucket == "skip"
    assert rec.entry_target is None
    assert rec.initial_stop is None
    assert rec.next_earnings_date is None
    assert rec.absent_earnings_data is None


# ----------------------------------------------------------------------------
# Aplus-signal extractor: round-trips back to an AplusSignal for callers that
# need the same shape as the standard replay.
# ----------------------------------------------------------------------------


def test_aplus_signals_from_records_round_trip(monkeypatch):
    """Filter records to A+ then convert to AplusSignals — same shape as replay()."""
    monkeypatch.setattr(
        mod,
        "evaluate_one",
        lambda ctx: _candidate(ctx.ticker, bucket="aplus", criteria=_all_pass_criteria()),
    )
    records = list(
        mod.instrumented_replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": []},
            cfg=build_harness_config(),
        )
    )
    signals = mod.aplus_signals_from(records)
    assert len(signals) == 1
    assert signals[0].ticker == "AAPL"
    assert signals[0].absent_earnings_data is True
    assert signals[0].next_earnings_date is None


# ----------------------------------------------------------------------------
# Aggregation helpers
# ----------------------------------------------------------------------------


def test_aggregate_binding_constraints_counts_per_criterion():
    """Sum binding_constraint occurrences across records."""
    records = (
        mod.EvaluationRecord(
            ticker="A",
            date=date(2025, 1, 1),
            bucket="skip",
            criterion_results=(),
            binding_constraint="ma_stack_short",
            entry_target=None,
            initial_stop=None,
            next_earnings_date=None,
            absent_earnings_data=None,
        ),
        mod.EvaluationRecord(
            ticker="B",
            date=date(2025, 1, 1),
            bucket="skip",
            criterion_results=(),
            binding_constraint="ma_stack_short",
            entry_target=None,
            initial_stop=None,
            next_earnings_date=None,
            absent_earnings_data=None,
        ),
        mod.EvaluationRecord(
            ticker="C",
            date=date(2025, 1, 1),
            bucket="watch",
            criterion_results=(),
            binding_constraint="vcp",
            entry_target=None,
            initial_stop=None,
            next_earnings_date=None,
            absent_earnings_data=None,
        ),
        mod.EvaluationRecord(
            ticker="D",
            date=date(2025, 1, 1),
            bucket="aplus",
            criterion_results=(),
            binding_constraint=None,
            entry_target=None,
            initial_stop=None,
            next_earnings_date=None,
            absent_earnings_data=None,
        ),
    )
    counts = mod.aggregate_binding_constraints(records)
    assert counts["ma_stack_short"] == 2
    assert counts["vcp"] == 1
    # A+ records contribute None — exposed under a sentinel key for transparency.
    assert counts[mod.APLUS_KEY] == 1


# ----------------------------------------------------------------------------
# CSV writer
# ----------------------------------------------------------------------------


def test_write_records_csv_round_trip(tmp_path):
    """CSV schema is stable: ticker,date,bucket,binding_constraint,<criterion columns>."""
    record = mod.EvaluationRecord(
        ticker="AAPL",
        date=date(2025, 2, 24),
        bucket="watch",
        criterion_results=(
            ("TT1_close_above_ma200", "pass"),
            ("ma_stack_short", "fail"),
        ),
        binding_constraint="ma_stack_short",
        entry_target=None,
        initial_stop=None,
        next_earnings_date=None,
        absent_earnings_data=None,
    )
    out = tmp_path / "records.csv"
    mod.write_records_csv([record], out)
    text = out.read_text(encoding="utf-8")
    # Header has the criterion columns expanded as named columns.
    assert "ticker,date,bucket,binding_constraint" in text
    assert "TT1_close_above_ma200" in text
    assert "ma_stack_short" in text
    # Row contains pass/fail values.
    assert "AAPL,2025-02-24,watch,ma_stack_short" in text
