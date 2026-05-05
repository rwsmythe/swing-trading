"""Pipeline runner: orchestrates 9 steps, records per-step status, aborts on evaluation fail."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run
from swing.pipeline.runner import run_pipeline_internal, RunResult


def _ohlcv(closes=None, end="2026-04-15"):
    closes = closes or [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def test_runner_completes_all_steps(tmp_path: Path, monkeypatch):
    """End-to-end happy path with mocked PriceFetcher + finviz CSV."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = ["No.", "Ticker", "Sector", "Industry", "Country", "Price", "Change",
            "Average Volume", "Relative Volume", "Average True Range",
            "52-Week High", "52-Week Low", "Market Cap"]
    csv.write_text(
        ",".join(cols) + "\n"
        "1,AAPL,Tech,Hardware,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3000000000\n"
        "2,MSFT,Tech,Software,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3500000000\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _ohlcv(),
    )

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert isinstance(result, RunResult)
    assert result.state == "complete"

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "complete"
        assert run.weather_status == "ok"
        assert run.evaluation_status == "ok"
        assert run.watchlist_status == "ok"
        assert run.recommendations_status == "ok"
        assert run.export_status == "ok"
    finally:
        conn.close()


def test_runner_detects_mid_run_lease_revocation(tmp_path: Path, monkeypatch):
    """Adversarial review Batch 4 Round 1 Critical 1: a force-clear happening
    between step-boundaries must abort subsequent DB-writing steps. The runner
    calls _verify_lease_still_held at the start of each write-step; a revoked
    lease raises LeaseRevoked which exits the step loop before canonical writes
    happen."""
    from tests.cli.test_cli_eval import _minimal_config
    from swing.data.repos.pipeline import force_clear

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    csv = cfg.paths.finviz_inbox_dir / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    csv.write_text(cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
                   encoding="utf-8")

    # Monkeypatch: first time anything fetches OHLCV, we force-clear the lease.
    # This simulates an admin revoking the lease after CSV validation but before
    # the evaluate step's writes land.
    import sqlite3
    cleared = {"done": False}
    original_get = None

    def fetcher_get(self, ticker, lookback_days, *, as_of_date=None):
        if not cleared["done"]:
            conn = sqlite3.connect(cfg.paths.db_path)
            try:
                row = conn.execute(
                    "SELECT id FROM pipeline_runs WHERE state='running'"
                ).fetchone()
                if row is not None:
                    with conn:
                        force_clear(conn, run_id=row[0],
                                    error_message="test-revoke")
                    cleared["done"] = True
            finally:
                conn.close()
        return _ohlcv()

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fetcher_get)

    from swing.pipeline.runner import run_pipeline_internal
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    # The runner catches LeaseRevoked at the top-level step loop and surfaces
    # state='force_cleared' without attempting a lease.release() that would
    # re-raise.
    assert result.state == "force_cleared"
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "force_cleared"
    finally:
        conn.close()


def test_runner_refreshes_close_for_open_trade_not_in_finviz(
    tmp_path: Path, monkeypatch,
):
    """Regression: open-trade tickers that don't appear in today's finviz CSV
    previously got no candidate row — so PriceCache._last_close() fell back to
    whatever stale row was last written (potentially days old). The dashboard
    "Last price" for held positions would silently lag reality.

    After the fix, every pipeline run writes a candidates row for each open
    trade with the ticker's fresh close (bucket='excluded', notes='open
    position') so the price-cache fallback picks up today's value.
    """
    from tests.cli.test_cli_eval import _minimal_config
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    # Seed an open trade for VIR (NOT in finviz CSV below).
    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(
                conn, Trade(
                    id=None, ticker="VIR", entry_date="2026-04-15",
                    entry_price=10.5, initial_shares=100, initial_stop=9.5,
                    current_stop=9.5, state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts="2026-04-15T09:30:00",
            )
    finally:
        conn.close()

    csv = cfg.paths.finviz_inbox_dir / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    # Finviz CSV contains AAPL — NOT VIR.
    csv.write_text(
        cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
        encoding="utf-8",
    )

    # Fetcher returns a distinctive close per ticker so we can verify the row
    # for VIR carries its own close, not AAPL's.
    vir_closes = [11.0 + i * 0.01 for i in range(260)]  # last close = 13.59
    aapl_closes = [180.0 + i * 0.5 for i in range(260)]

    def fake_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "VIR":
            return _ohlcv(closes=vir_closes)
        return _ohlcv(closes=aapl_closes)

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fake_get)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete"

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            """SELECT c.close, c.bucket FROM candidates c
               JOIN evaluation_runs e ON e.id = c.evaluation_run_id
               WHERE c.ticker = 'VIR'
               ORDER BY e.run_ts DESC LIMIT 1"""
        ).fetchone()
        assert row is not None, (
            "pipeline must write a candidates row for open-trade tickers "
            "that aren't in the finviz CSV, so PriceCache._last_close sees "
            "a fresh close"
        )
        close, bucket = row
        assert close is not None, (
            "the candidates.close for the open-trade ticker must carry the "
            "ticker's own close, not NULL"
        )
        assert abs(close - vir_closes[-1]) < 1e-6, (
            f"candidates.close for VIR should equal the ticker's last fetched "
            f"close ({vir_closes[-1]}); got {close}"
        )
    finally:
        conn.close()


def test_runner_aborts_on_evaluation_fail(tmp_path: Path, monkeypatch):
    """Spec §5.3: evaluation failure => abort. Watchlist/recommendations/charts/export skipped."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    csv = cfg.paths.finviz_inbox_dir / "finviz15Apr2026.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    cols = "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap"
    csv.write_text(cols + "\n1,AAPL,T,H,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3e9\n",
                   encoding="utf-8")

    def fail_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "QQQ":
            return _ohlcv()
        raise RuntimeError("simulated yfinance outage")

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fail_get)

    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "failed"

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.state == "failed"
        assert run.evaluation_status == "failed"
        assert run.watchlist_status in (None, "skipped")
        assert run.recommendations_status in (None, "skipped")
        assert run.export_status in (None, "skipped")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.10 — pipeline/runner.py migrates the three list_all_exits
# call sites onto the local _exits_via_fills_for_equity helper. Direct
# helper-level test asserts (a) entry fills are filtered, (b) realized_pnl
# is derived from the parent trade's entry_price.
# ---------------------------------------------------------------------------


def test_c10_exits_via_fills_for_equity_filters_entry_fills(
    tmp_path: Path,
) -> None:
    """C.10: _exits_via_fills_for_equity returns ExitLike rows for non-
    entry fills only. The synthetic entry fill written by
    insert_trade_with_event must NOT surface in the helper output.
    Discriminating against (a) helper leaking entry fills (would over-
    count realized PnL) and (b) helper returning empty.
    """
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    from swing.pipeline.runner import _exits_via_fills_for_equity

    conn = ensure_schema(tmp_path / "phase7_c10.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="ABC", entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=10,
                    initial_stop=90.0, current_stop=90.0,
                    state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None, notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=tid,
                    fill_datetime="2026-04-20T16:00:00",
                    action="exit", quantity=10, price=110.0,
                    reason="target",
                ),
                event_ts="2026-04-20T16:00:00",
            )
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?", (tid,),
            )
        shapes = _exits_via_fills_for_equity(conn)
    finally:
        conn.close()
    # Exactly one non-entry shape; realized_pnl = (110 - 100) * 10 = 100.
    assert len(shapes) == 1, (
        f"_exits_via_fills_for_equity returned {len(shapes)} rows; "
        f"expected exactly 1 (the explicit exit fill — synthetic entry "
        f"fill must be filtered)."
    )
    assert shapes[0].trade_id == tid
    assert shapes[0].realized_pnl == 100.0
