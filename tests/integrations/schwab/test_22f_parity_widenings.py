"""22-F Part B -- the WIDENED rows of the F-F2 three-state list (plan 3.1).

`SchwabSchemaParityError` is a `_RedactedMessageError`, NOT a
`SchwabApiError` (the classes are disjoint; F-F2 refused a re-base), so a
tuple naming only `SchwabApiError` lets a parity failure through.

T-B2 -- rows 5, 6 (`cli_schwab.py` `schwab fetch`'s snapshot / orders belts)
and 13 (`pipeline_steps.py` `_step_schwab_snapshot`).

Every planted failure goes through a counting wrapper asserted called (the
did-it-fire rule); each patch target is the name the code resolves at call
time, read from its source.
"""
from __future__ import annotations

from types import SimpleNamespace

from swing.integrations.schwab.client import SchwabSchemaParityError
from tests._22f_proxies import raising
from tests.integrations.test_schwab_fetch_cli import (  # noqa: F401
    _make_cfg,
    _stub_schwabdev_client,
    invoke_cli,
    isolated_db,
    isolated_home,
)

_PARITY = "<accounts.details: missing required key 'x'>"


def _plant_details(monkeypatch):
    """`pipeline_steps` binds `get_account_details` by its module-level
    import, so the module attribute is what `_step_schwab_snapshot`
    resolves per call."""
    planted = raising(SchwabSchemaParityError(_PARITY))
    monkeypatch.setattr(
        "swing.integrations.schwab.pipeline_steps.get_account_details",
        planted)
    return planted


def test_B2a_snapshot_step_contains_parity_as_failed(
        isolated_db, monkeypatch):
    """B2-a (row 13). PRE-FIX: the parity error escapes
    `_step_schwab_snapshot`'s `except SchwabApiError`.  POST-FIX:
    ``status="failed"``, ``error`` starts ``SchwabSchemaParityError:``."""
    from swing.data.db import connect
    from swing.integrations.schwab.pipeline_steps import _step_schwab_snapshot
    planted = _plant_details(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    conn = connect(isolated_db)
    try:
        r = _step_schwab_snapshot(conn, cfg, pipeline_run_id=None,
                                  client=SimpleNamespace(), surface="cli")
    finally:
        conn.close()
    assert planted.calls == 1  # did-it-fire
    assert r["status"] == "failed"
    assert r["error"].startswith("SchwabSchemaParityError:"), r


def test_B2b_fetch_snapshot_parity_is_contained_by_the_step(
        isolated_db, invoke_cli, monkeypatch):
    """B2-b. PRE-FIX: traceback (exit 1, the parity error as
    `result.exception`).  POST-FIX: exit 0, the snapshot step reported
    `failed` (row 13 contains it; row 5 is the belt)."""
    _stub_schwabdev_client(monkeypatch)
    planted = _plant_details(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert planted.calls == 1  # did-it-fire
    assert result.exit_code == 0, (repr(result.exception), result.output)
    assert "failed" in result.output


def _plant_step(monkeypatch, name: str):
    """`schwab_fetch` imports the steps FUNCTION-LOCALLY, so the
    `pipeline_steps` module attribute is read per call."""
    planted = raising(SchwabSchemaParityError(_PARITY))
    monkeypatch.setattr(
        f"swing.integrations.schwab.pipeline_steps.{name}", planted)
    return planted


def test_B2c_fetch_snapshot_belt_types_a_parity_escape(
        isolated_db, invoke_cli, monkeypatch):
    """B2-c (row 5, the belt). PRE-FIX: traceback.  POST-FIX: exit 1,
    `Error: Snapshot step failed: ...`, no traceback."""
    _stub_schwabdev_client(monkeypatch)
    planted = _plant_step(monkeypatch, "_step_schwab_snapshot")
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--snapshot")
    assert planted.calls == 1  # did-it-fire
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1
    assert "Error: Snapshot step failed:" in result.output
    assert "Traceback" not in result.output


def _b4_cfg():
    """Production + ladder enabled so the ladder reaches its try; no
    `cfg.paths` -> `_resolve_cache_dir` is None -> the archive write no-ops
    (the `tests/integrations/schwab/test_ladder_catchall_observability.py`
    world)."""
    return SimpleNamespace(integrations=SimpleNamespace(schwab=SimpleNamespace(
        environment="production", marketdata_ladder_enabled=True)))


class _Snap:
    """Stand-in yfinance quote entry."""


class _Window:
    """Stand-in yfinance window."""


_LADDER_LOG = "swing.integrations.schwab.marketdata_ladder"


def _ladder_records(caplog):
    return [r.getMessage() for r in caplog.records if r.name == _LADDER_LOG]


def _drive_quote(monkeypatch, caplog, exc):
    """`marketdata_ladder` binds `get_quotes_batch` by its module-level
    import, so the module attribute is what the ladder resolves per call."""
    import logging
    import sqlite3

    from swing.integrations.schwab import marketdata_ladder
    planted = raising(exc)
    monkeypatch.setattr(marketdata_ladder, "get_quotes_batch", planted)
    snap = _Snap()
    with caplog.at_level(logging.WARNING, logger=_LADDER_LOG):
        entry, provider = marketdata_ladder.fetch_quote_via_ladder(
            "AAPL", cfg=_b4_cfg(), schwab_client=object(),
            yfinance_fallback_fn=lambda t: snap,
            conn=sqlite3.connect(":memory:"), surface="pipeline",
            pipeline_run_id=None)
    assert planted.calls == 1  # did-it-fire
    assert entry is snap and provider == "yfinance"
    return _ladder_records(caplog)


def _drive_window(monkeypatch, caplog, exc):
    import logging
    import sqlite3

    from swing.integrations.schwab import marketdata_ladder
    planted = raising(exc)
    monkeypatch.setattr(marketdata_ladder, "get_price_history", planted)
    window = _Window()
    with caplog.at_level(logging.WARNING, logger=_LADDER_LOG):
        got, provider = marketdata_ladder.fetch_window_via_ladder(
            "AAPL", start=None, end=None, cfg=_b4_cfg(),
            schwab_client=object(),
            yfinance_fallback_fn=lambda t, s, e: window,
            conn=sqlite3.connect(":memory:"), surface="pipeline",
            pipeline_run_id=None)
    assert planted.calls == 1  # did-it-fire
    assert got is window and provider == "yfinance"
    return _ladder_records(caplog)


_QUOTE_PARITY = "<quotes: missing required key 'x'>"


def test_B4a_quote_parity_reaches_the_named_clause_with_its_text(
        monkeypatch, caplog):
    """B4-a (row 11). PRE-FIX: the parity error falls to the broad
    `except Exception` (`unexpected error from T-C.1 wrapper`).  POST-FIX:
    the NAMED clause's record carries the type AND `str(exc)`; no
    `unexpected error` record; the yfinance fallback is unchanged."""
    recs = _drive_quote(monkeypatch, caplog,
                        SchwabSchemaParityError(_QUOTE_PARITY))
    named = [m for m in recs if "Schwab market-data quote fetch failed" in m]
    assert len(named) == 1, recs
    assert "SchwabSchemaParityError" in named[0]
    assert _QUOTE_PARITY in named[0]
    assert not any("unexpected error" in m for m in recs), recs


def test_B4b_window_parity_reaches_the_named_clause_with_its_text(
        monkeypatch, caplog):
    """B4-b (row 12). Same shape for `fetch_window_via_ladder`."""
    recs = _drive_window(monkeypatch, caplog,
                         SchwabSchemaParityError(_QUOTE_PARITY))
    named = [m for m in recs if "Schwab price_history failed" in m]
    assert len(named) == 1, recs
    assert "SchwabSchemaParityError" in named[0]
    assert _QUOTE_PARITY in named[0]
    assert not any("unexpected error" in m for m in recs), recs


def test_B4c_api_error_named_clause_now_carries_the_redacted_text(
        monkeypatch, caplog):
    """B4-c. `SchwabApiError(500, "x")` on each: the named clause both trees
    (fallback unchanged); POST-FIX its record also carries the error's
    engineered-redacted `__str__`."""
    from swing.integrations.schwab.client import SchwabApiError
    want = "SchwabApiError(status=500, body=<1 bytes>)"
    q = _drive_quote(monkeypatch, caplog, SchwabApiError(500, "x"))
    assert any("Schwab market-data quote fetch failed" in m and want in m
               for m in q), q
    caplog.clear()
    w = _drive_window(monkeypatch, caplog, SchwabApiError(500, "x"))
    assert any("Schwab price_history failed" in m and want in m
               for m in w), w


def test_B4d_control_runtime_error_still_the_broad_clause(
        monkeypatch, caplog):
    """B4-d CONTROL: a planted `RuntimeError("boom")` reaches the broad
    clause on both trees."""
    q = _drive_quote(monkeypatch, caplog, RuntimeError("boom"))
    assert any("unexpected error" in m and "boom" in m for m in q), q
    caplog.clear()
    w = _drive_window(monkeypatch, caplog, RuntimeError("boom"))
    assert any("unexpected error" in m and "boom" in m for m in w), w


def test_B2d_fetch_orders_belt_types_a_parity_escape(
        isolated_db, invoke_cli, monkeypatch):
    """B2-d (row 6). PRE-FIX: traceback.  POST-FIX: exit 1,
    `Error: Orders step failed: ...`."""
    _stub_schwabdev_client(monkeypatch)
    planted = _plant_step(monkeypatch, "_step_schwab_orders")
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--orders")
    assert planted.calls == 1  # did-it-fire
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1
    assert "Error: Orders step failed:" in result.output
    assert "Traceback" not in result.output
