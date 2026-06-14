from __future__ import annotations

import pytest

from swing.data.models import YfinanceCall


def _valid_single(**over) -> dict:
    base = dict(
        call_id=None,
        ts="2026-06-14T00:00:00",
        call_type="download_single",
        ticker="AAPL",
        ticker_count=None,
        response_time_ms=12,
        status="success",
        rows_returned=5,
        error_message=None,
        pipeline_run_id=None,
        surface="cli",
    )
    base.update(over)
    return base


def test_valid_single_constructs():
    YfinanceCall(**_valid_single())


def test_valid_batch_constructs():
    YfinanceCall(**_valid_single(
        call_type="download_batch", ticker=None, ticker_count=8, surface="pipeline",
        pipeline_run_id=7,
    ))


def test_pipeline_null_run_id_constructs():
    # Section-9 LOCK: NO dataclass run-linkage validator. A pipeline row with a
    # NULL run id (e.g. a post-prune SET-NULLed row read back) MUST construct.
    YfinanceCall(**_valid_single(surface="pipeline", pipeline_run_id=None))


def test_cli_with_run_id_constructs():
    # No dataclass run-linkage validator -> cli + run id does NOT raise at the model.
    YfinanceCall(**_valid_single(surface="cli", pipeline_run_id=3))


@pytest.mark.parametrize("field,value", [
    ("status", "bogus"),
    ("call_type", "frobnicate"),
    ("surface", "mobile"),
])
def test_enum_outside_frozenset_raises(field, value):
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(**{field: value}))


def test_negative_response_time_raises():
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(response_time_ms=-1))


def test_negative_rows_returned_raises():
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(rows_returned=-1))


@pytest.mark.parametrize("field", [
    "response_time_ms", "rows_returned", "pipeline_run_id", "ticker_count",
])
def test_bool_rejected_for_every_integer_field(field):
    # bool is an int subclass; reject it explicitly (Codex R17).
    over = {field: True}
    if field == "ticker_count":
        # ticker_count is exercised on a batch row (ticker NULL)
        over.update(call_type="download_batch", ticker=None, surface="pipeline",
                    pipeline_run_id=7)
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(**over))


def test_error_message_none_ok():
    YfinanceCall(**_valid_single(status="error", error_message=None))


def test_shape_batch_with_ticker_raises():
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(call_type="download_batch", ticker="AAPL",
                                     ticker_count=3))


def test_shape_batch_without_ticker_count_raises():
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(call_type="download_batch", ticker=None,
                                     ticker_count=None))


@pytest.mark.parametrize("ct", ["download_single", "download_intraday"])
def test_shape_single_with_ticker_count_raises(ct):
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(call_type=ct, ticker="AAPL", ticker_count=3))


@pytest.mark.parametrize("ct", ["download_single", "download_intraday"])
def test_shape_single_without_ticker_raises(ct):
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(call_type=ct, ticker=None, ticker_count=None))


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_whitespace_ticker_raises(bad):
    with pytest.raises(ValueError):
        YfinanceCall(**_valid_single(ticker=bad))
