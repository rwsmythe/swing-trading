"""Task 8 -- ladder catch-all observability (OQ-D).

Both ladder `except Exception` catch-alls must log the exception CLASS + MESSAGE
(so a silent Schwab->yfinance degrade, e.g. an audit `database is locked`, is
diagnosable) and must NOT attach `exc_info` (traceback frames carry local-variable
bytes that bypass message-level redaction discipline).

GROUNDING DEVIATION (re-grep STEP 0): the plan's third test
(`test_window_catchall_message_is_redacted`) imported a nonexistent module
`swing.integrations.schwab.log_redaction` and assumed the catch-all message is
scrubbed by the setLogRecordFactory redactor. It is NOT: the redactor only
rewrites records whose name starts with `_SCHWABDEV_LOGGER_PREFIX == "Schwabdev"`
(swing/integrations/schwab/client.py:72,168), and the ladder logs through its own
`swing.integrations.schwab.marketdata_ladder` logger. The real redaction-safety
guarantee OQ-D specified is therefore: emit only the exception's
(redaction-disciplined) __str__ with NO exc_info/stack_info. The third test below
asserts that genuine contract. In production the only unexpected exception that
reaches these arms is the raw audit `sqlite3.OperationalError` ('database is
locked') -- no secret bytes -- or a SchwabApiError whose __str__ is already
redaction-disciplined.
"""
import logging
import sqlite3
from types import SimpleNamespace

from swing.integrations.schwab import marketdata_ladder


def _cfg():
    # production + ladder enabled so the ladder attempts Schwab (reaching the
    # try/except), with no cfg.paths -> _resolve_cache_dir returns None ->
    # _persist_window_to_archive no-ops.
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production", marketdata_ladder_enabled=True,
            )
        )
    )


def _conn():
    # Unused on the catch-all path (get_quotes_batch/get_price_history are
    # monkeypatched to raise before touching conn), but the signature requires it.
    return sqlite3.connect(":memory:")


class _DummySnap:
    """Stand-in PriceSnapshot returned by the quote yfinance fallback."""


class _DummyWindow:
    """Stand-in window returned by the window yfinance fallback."""


def test_window_catchall_logs_class_and_message_no_exc_info(monkeypatch, caplog):
    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(marketdata_ladder, "get_price_history", _boom)

    def _yf(ticker, start, end):
        return _DummyWindow()

    with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.marketdata_ladder"):
        window, provider = marketdata_ladder.fetch_window_via_ladder(
            "AAPL", start=None, end=None, cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=_yf, conn=_conn(), surface="pipeline",
            pipeline_run_id=None,
        )
    assert provider == "yfinance"
    rec = [r for r in caplog.records if "AAPL" in r.getMessage()][-1]
    assert "OperationalError" in rec.getMessage()
    assert "database is locked" in rec.getMessage()
    assert rec.exc_info is None  # NO traceback


def test_quote_catchall_logs_class_and_message(monkeypatch, caplog):
    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(marketdata_ladder, "get_quotes_batch", _boom)
    with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.marketdata_ladder"):
        entry, provider = marketdata_ladder.fetch_quote_via_ladder(
            "AAPL", cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=lambda t: _DummySnap(),
            conn=_conn(), surface="pipeline", pipeline_run_id=None,
        )
    assert provider == "yfinance"
    rec = [r for r in caplog.records if "AAPL" in r.getMessage()][-1]
    assert "OperationalError" in rec.getMessage()
    assert "database is locked" in rec.getMessage()
    assert rec.exc_info is None


def test_catchalls_attach_no_exc_info_or_stack_info(monkeypatch, caplog):
    # Genuine redaction-safety contract (see module docstring): the catch-alls
    # must emit message-only (the exception's disciplined __str__), never a
    # traceback (exc_info) or stack dump (stack_info) that could carry secret
    # local-variable bytes past message-level redaction.
    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(marketdata_ladder, "get_price_history", _boom)
    monkeypatch.setattr(marketdata_ladder, "get_quotes_batch", _boom)
    with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.marketdata_ladder"):
        marketdata_ladder.fetch_window_via_ladder(
            "AAPL", start=None, end=None, cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=lambda t, s, e: _DummyWindow(),
            conn=_conn(), surface="pipeline", pipeline_run_id=None,
        )
        marketdata_ladder.fetch_quote_via_ladder(
            "MSFT", cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=lambda t: _DummySnap(),
            conn=_conn(), surface="pipeline", pipeline_run_id=None,
        )
    recs = [r for r in caplog.records if "unexpected error" in r.getMessage()]
    assert len(recs) >= 2
    assert all(r.exc_info is None for r in recs)
    assert all(r.stack_info is None for r in recs)
