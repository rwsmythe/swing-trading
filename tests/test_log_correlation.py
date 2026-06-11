from __future__ import annotations

import logging
import threading

import pytest

import swing.log_correlation as lc


@pytest.fixture(autouse=True)
def _reset_correlation_state():
    # Each test starts from a clean carrier; restore env-independence afterward.
    lc._set_for_test(web_request_id="-", pipeline_run_id=None)
    yield
    lc._set_for_test(web_request_id="-", pipeline_run_id=None)


def test_valid_env_token_accepted(monkeypatch):
    monkeypatch.setenv("SWING_WEB_REQUEST_ID", "abc-123-DEF")
    lc.reset_correlation_from_env()
    assert lc.get_web_request_id() == "abc-123-DEF"
    # reset always clears the run id (no run yet) -> renders the placeholder.
    assert lc.get_pipeline_run_id() == "-"


def test_missing_env_falls_back_to_placeholder(monkeypatch):
    monkeypatch.delenv("SWING_WEB_REQUEST_ID", raising=False)
    lc.reset_correlation_from_env()
    assert lc.get_web_request_id() == "-"


@pytest.mark.parametrize("forged", [
    "has space", "new\nline", "tab\tchar", "x" * 65, "", "semi;colon", "slash/y",
    # TRAILING newline/carriage-return: re.match + `$` would ACCEPT "abc\n" (the
    # `$`-before-final-newline gap); fullmatch rejects it. These guard that gap.
    "abc\n", "abc\r", "abc\n\n", "abc\r\n",
])
def test_forged_env_token_rejected(monkeypatch, forged):
    monkeypatch.setenv("SWING_WEB_REQUEST_ID", forged)
    lc.reset_correlation_from_env()
    assert lc.get_web_request_id() == "-"


def test_set_pipeline_run_id_stringifies():
    lc.set_pipeline_run_id(42)
    assert lc.get_pipeline_run_id() == "42"
    lc.set_pipeline_run_id(None)
    assert lc.get_pipeline_run_id() == "-"


def test_reset_clears_stale_run_id(monkeypatch):
    # A stale run id from a prior in-process run MUST NOT bleed past a reset.
    lc.set_pipeline_run_id(99)
    assert lc.get_pipeline_run_id() == "99"
    monkeypatch.delenv("SWING_WEB_REQUEST_ID", raising=False)
    lc.reset_correlation_from_env()
    assert lc.get_pipeline_run_id() == "-"


def test_filter_stamps_both_ids():
    lc._set_for_test(web_request_id="rid-7", pipeline_run_id="55")
    f = lc.CorrelationFilter()
    rec = logging.LogRecord("n", logging.INFO, __file__, 1, "m", None, None)
    assert f.filter(rec) is True
    assert rec.web_request_id == "rid-7"
    assert rec.pipeline_run_id == "55"


def test_filter_stamps_in_worker_thread():
    # The discriminating test a contextvars impl FAILS: a worker thread that did
    # not inherit a ContextVar set on the main thread would render "-"; the
    # process-global carrier is visible from every thread.
    lc._set_for_test(web_request_id="rid-thread", pipeline_run_id="77")
    f = lc.CorrelationFilter()
    captured = {}

    def worker():
        rec = logging.LogRecord("n", logging.INFO, __file__, 1, "m", None, None)
        f.filter(rec)
        captured["web"] = rec.web_request_id
        captured["run"] = rec.pipeline_run_id

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert captured == {"web": "rid-thread", "run": "77"}
