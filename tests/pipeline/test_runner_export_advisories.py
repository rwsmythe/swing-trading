"""3e.8 Bundle 1 Task A.2 — _step_export populates open_trade_advisories.

Captures the BriefingInputs reaching ``build_briefing_view_model`` and
asserts:

  * Pre-refactor baseline was ``open_trade_advisories = {}`` (the empty-
    dict hard-code at the prior runner.py:921). Post-refactor must populate
    the mapping per open trade (A.AC.4 + A.AC.5).
  * When NO advisories trigger, the per-trade value is an empty list
    (A.AC.6 absent-vs-empty distinction).
"""
from __future__ import annotations

import sqlite3
from datetime import date as _date
from pathlib import Path

import pandas as pd

from swing.data.db import ensure_schema


def _seed_open_trade(conn, *, ticker: str, entry_date: str, entry_price: float,
                     initial_stop: float, current_stop: float | None = None,
                     trade_origin: str = "manual_off_pipeline") -> int:
    current_stop = current_stop if current_stop is not None else initial_stop
    cur = conn.execute(
        """INSERT INTO trades
           (ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at,
            current_size)
           VALUES (?, ?, ?, 10, ?, ?, 'managing', ?, '2026-04-01T09:30:00',
                   10.0)""",
        (ticker, entry_date, entry_price, initial_stop, current_stop, trade_origin),
    )
    return int(cur.lastrowid)


def _seed_eval_run(conn, *, action_session: str = "2026-04-15") -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES ('2026-04-15T21:00:00', '2026-04-14', ?, NULL, 0, 0, 0, 0,
                   0, 0, 'v1', 'd')""",
        (action_session,),
    )
    return int(cur.lastrowid)


def _seed_candidate_excluded(conn, *, eval_id: int, ticker: str, close: float):
    """Mirror the _step_evaluate open-position synthesized excluded row that
    keeps PriceCache._last_close fresh for rotated-out tickers."""
    conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            rs_method, notes)
           VALUES (?, ?, 'excluded', ?, NULL, NULL, 'universe', 'open position')""",
        (eval_id, ticker, close),
    )


def _seed_pipeline_run_running(conn) -> tuple[int, str]:
    import uuid
    token = str(uuid.uuid4())
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, trigger, data_asof_date, action_session_date,
            state, lease_token, lease_heartbeat_ts)
           VALUES ('2026-04-15T20:55:00', 'manual', '2026-04-14',
                   '2026-04-15', 'running', ?, '2026-04-15T20:55:00')""",
        (token,),
    )
    return int(cur.lastrowid), token


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def _bars_trail_setup() -> pd.DataFrame:
    closes = [80.0 + (i * 0.7) for i in range(30)]
    dates = pd.date_range("2026-03-01", periods=30, freq="B")
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [1_000_000] * 30},
        index=dates,
    )


class _StubFetcher:
    def __init__(self, per_ticker_bars):
        self._per_ticker_bars = per_ticker_bars
        self.calls: list[tuple[str, int]] = []

    def get(self, ticker, lookback_days, *, as_of_date=None):
        self.calls.append((ticker, lookback_days))
        return self._per_ticker_bars[ticker]


def test_step_export_populates_open_trade_advisories(tmp_path, monkeypatch):
    """Open trade with active trail-MA condition → briefing's
    open_trade_advisories has a non-empty list for the trade.id key.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            eval_id = _seed_eval_run(conn)
            trade_id = _seed_open_trade(
                conn, ticker="ABCD", entry_date="2026-04-01",
                entry_price=100.0, initial_stop=95.0, current_stop=95.0,
            )
            bars = _bars_trail_setup()
            _seed_candidate_excluded(
                conn, eval_id=eval_id, ticker="ABCD",
                close=float(bars["Close"].iloc[-1]),
            )
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    captured: dict = {}

    def fake_build_view_model(inputs):
        captured["open_trade_advisories"] = dict(inputs.open_trade_advisories)
        class _VM:
            briefing_html = ""
            briefing_md = ""
        return _VM()

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model", fake_build_view_model,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing", lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports", lambda **kw: None,
    )

    fetcher = _StubFetcher({"ABCD": _bars_trail_setup()})
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_id,
        action_session=_date(2026, 4, 15),
        data_asof="2026-04-14",
        chart_paths={},
        fetcher=fetcher,
    )

    assert trade_id in captured["open_trade_advisories"], (
        f"open trade {trade_id} must appear as a key in open_trade_advisories; "
        f"got {captured['open_trade_advisories']!r}"
    )
    sugs = captured["open_trade_advisories"][trade_id]
    assert sugs, f"Expected non-empty advisory list; got {sugs!r}"
    rules = {s.rule for s in sugs}
    assert "trail_10ma" in rules


def test_step_export_open_trade_advisories_empty_list_when_no_triggers(
    tmp_path, monkeypatch,
):
    """A.AC.6 — open trade with no active advisory triggers retains the
    trade.id key with an empty list (NOT absent; renderer's `t.id or 0`
    lookup distinguishes empty-list-rendered-empty from absent-no-render).
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            eval_id = _seed_eval_run(conn)
            trade_id = _seed_open_trade(
                conn, ticker="XYZW", entry_date="2026-04-14",
                entry_price=100.0, initial_stop=95.0,
                current_stop=96.0,  # already above trail-proposed
            )
            # 30 flat bars at 95.0 → trail_10ma proposed $94.72 ≤ current_stop $96
            # → no trail advisory fires. Bullish weather + recent entry →
            # no weather + no time_stop.
            closes = [95.0] * 30
            dates = pd.date_range("2026-03-01", periods=30, freq="B")
            bars = pd.DataFrame(
                {"Open": closes, "High": closes, "Low": closes, "Close": closes,
                 "Volume": [1_000_000] * 30},
                index=dates,
            )
            _seed_candidate_excluded(
                conn, eval_id=eval_id, ticker="XYZW", close=95.0,
            )
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    captured: dict = {}

    def fake_build_view_model(inputs):
        captured["open_trade_advisories"] = dict(inputs.open_trade_advisories)
        class _VM:
            briefing_html = ""
            briefing_md = ""
        return _VM()

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model", fake_build_view_model,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing", lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports", lambda **kw: None,
    )

    fetcher = _StubFetcher({"XYZW": bars})
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_id,
        action_session=_date(2026, 4, 15),
        data_asof="2026-04-14",
        chart_paths={},
        fetcher=fetcher,
    )

    assert trade_id in captured["open_trade_advisories"]
    assert captured["open_trade_advisories"][trade_id] == [], (
        f"Expected empty list (A.AC.6); got "
        f"{captured['open_trade_advisories'][trade_id]!r}"
    )


def test_step_export_populates_open_trade_last_prices_from_candidates(
    tmp_path, monkeypatch,
):
    """Codex R1 Major 2 fix — _step_export now populates
    open_trade_last_prices keyed by ticker, sourced from the SAME
    candidate.close used by the advisory composition. Closes the briefing
    "Last column shows entry_price while advisories use newer candidate
    close" contradiction.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            eval_id = _seed_eval_run(conn)
            _seed_open_trade(
                conn, ticker="MJR2", entry_date="2026-04-01",
                entry_price=100.0, initial_stop=95.0,
            )
            _seed_candidate_excluded(
                conn, eval_id=eval_id, ticker="MJR2", close=108.42,
            )
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    captured: dict = {}

    def fake_build_view_model(inputs):
        captured["open_trade_last_prices"] = dict(inputs.open_trade_last_prices)
        class _VM:
            briefing_html = ""
            briefing_md = ""
        return _VM()

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model", fake_build_view_model,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing", lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports", lambda **kw: None,
    )

    fetcher = _StubFetcher({"MJR2": _bars_trail_setup()})
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_id,
        action_session=_date(2026, 4, 15),
        data_asof="2026-04-14",
        chart_paths={},
        fetcher=fetcher,
    )

    assert captured["open_trade_last_prices"] == {"MJR2": 108.42}, (
        f"Expected open_trade_last_prices to be populated from candidate.close "
        f"(R1 Major 2 fix); got {captured['open_trade_last_prices']!r}"
    )


def test_step_export_caches_bars_across_helpers_one_fetch_per_ticker(
    tmp_path, monkeypatch,
):
    """Codex R3 Major #1 closure — when candidate.close is NULL (so the
    last-price helper falls back to OHLCV), the advisory helper AND the
    last-price helper both consult the fetcher for the same ticker. The
    _CachingFetcherWrapper must collapse these to ONE underlying fetcher
    call per (ticker, lookback, as_of_date) tuple so the two helpers
    cannot diverge on a transient fetcher failure between them.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            eval_id = _seed_eval_run(conn)
            _seed_open_trade(
                conn, ticker="CACHE", entry_date="2026-04-01",
                entry_price=100.0, initial_stop=95.0,
            )
            # candidate.close = NULL forces the last-price helper into the
            # OHLCV fallback path.
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method, notes)
                   VALUES (?, 'CACHE', 'excluded', NULL, NULL, NULL,
                           'universe', 'open position')""",
                (eval_id,),
            )
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model",
        lambda inputs: type("VM", (), {"briefing_html": "", "briefing_md": ""})(),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing", lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports", lambda **kw: None,
    )

    fetcher = _StubFetcher({"CACHE": _bars_trail_setup()})
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_id,
        action_session=_date(2026, 4, 15),
        data_asof="2026-04-14",
        chart_paths={},
        fetcher=fetcher,
    )

    # Even though BOTH helpers consulted the fetcher for CACHE (advisory
    # helper unconditionally; last-price helper because candidate.close is
    # NULL), the caching wrapper collapses to ONE underlying call.
    tickers_called = [t for t, _lb in fetcher.calls]
    assert tickers_called == ["CACHE"], (
        f"Expected exactly one underlying fetcher.get call for CACHE across "
        f"both helpers (Codex R3 Major #1 caching guarantee); got "
        f"{fetcher.calls!r}"
    )


def test_step_export_last_prices_falls_back_to_prev_close_when_candidate_close_null(
    tmp_path, monkeypatch,
):
    """Codex R2 Major #2 closure — when the candidate row exists but
    candidate.close IS NULL, _step_export's open_trade_last_prices
    population must fall back to OHLCV previous_close (mirroring the
    advisory composition's same fallback). Otherwise the briefing renderer
    silently degrades to entry_price for Last/R/P&L while advisories fire
    from the newer prev_close — the residual R2 Major #2 contradiction.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            eval_id = _seed_eval_run(conn)
            _seed_open_trade(
                conn, ticker="MJR2B", entry_date="2026-04-01",
                entry_price=100.0, initial_stop=95.0,
            )
            # Candidate exists but close IS NULL — simulates the
            # _step_evaluate degraded path where the synthesized excluded
            # row for an open position didn't acquire a fresh close.
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method, notes)
                   VALUES (?, 'MJR2B', 'excluded', NULL, NULL, NULL,
                           'universe', 'open position')""",
                (eval_id,),
            )
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    captured: dict = {}

    def fake_build_view_model(inputs):
        captured["open_trade_last_prices"] = dict(inputs.open_trade_last_prices)
        class _VM:
            briefing_html = ""
            briefing_md = ""
        return _VM()

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model", fake_build_view_model,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing", lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports", lambda **kw: None,
    )

    bars = _bars_trail_setup()
    expected_prev = float(bars["Close"].iloc[-1])
    fetcher = _StubFetcher({"MJR2B": bars})
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_id,
        action_session=_date(2026, 4, 15),
        data_asof="2026-04-14",
        chart_paths={},
        fetcher=fetcher,
    )

    assert captured["open_trade_last_prices"] == {"MJR2B": expected_prev}, (
        f"R2 Major #2 — last-prices must fall back to OHLCV prev_close "
        f"when candidate.close is NULL; got "
        f"{captured['open_trade_last_prices']!r}"
    )


def test_step_export_no_extra_fetcher_calls_beyond_open_trade_count(
    tmp_path, monkeypatch,
):
    """A.AC.5 + pre-empt-list 'no extra yfinance calls': fetcher.get is
    called exactly once per open trade (the chart-step's fetch is already in
    the archive)."""
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            eval_id = _seed_eval_run(conn)
            tids = []
            for tk in ("AAAA", "BBBB", "CCCC"):
                tids.append(_seed_open_trade(
                    conn, ticker=tk, entry_date="2026-04-14",
                    entry_price=100.0, initial_stop=95.0, current_stop=96.0,
                ))
                _seed_candidate_excluded(
                    conn, eval_id=eval_id, ticker=tk, close=95.0,
                )
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    closes = [95.0] * 30
    dates = pd.date_range("2026-03-01", periods=30, freq="B")
    bars = pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [1_000_000] * 30},
        index=dates,
    )

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model",
        lambda inputs: type("VM", (), {"briefing_html": "", "briefing_md": ""})(),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing", lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports", lambda **kw: None,
    )

    fetcher = _StubFetcher({"AAAA": bars, "BBBB": bars, "CCCC": bars})
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_id,
        action_session=_date(2026, 4, 15),
        data_asof="2026-04-14",
        chart_paths={},
        fetcher=fetcher,
    )

    tickers_called = sorted(t for t, _lb in fetcher.calls)
    assert tickers_called == ["AAAA", "BBBB", "CCCC"], (
        f"Expected exactly one fetcher.get per open trade; got {fetcher.calls!r}"
    )
