"""Phase 14 Sub-bundle 3 T-3.4 (§C.4a) — market_weather trend-state derivation.
MIGRATED at the Phase 14 close-out follow-on (F-2): the two LIVE call sites
(pipeline `_step_charts` + the interactive `POST /dashboard/weather-chart/refresh`
handler) now compute the trend state LIVE from a wide benchmark fetch via
`swing.evaluation.criteria.trend_template.structural_stage` (was
`current_stage`, which read PERSISTED criteria for a benchmark not in the
evaluated set -> always 'undefined'). The dead/defensive JIT branch still
defaults to an honest "undefined".

Expansion #10c discipline (byte-parity-insufficient): we assert the ACTUAL
state value derived at each production call site reaches the renderer, using a
NON-LITERAL sentinel so a test cannot pass against the old hardcoded
"stage_2"/"n/a" literals. Fail-soft to "undefined" (NOT "n/a") on any error;
the pipeline step must NOT abort.
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import ChartRender
from swing.data.repos.chart_renders import refresh_chart_render
from swing.web.app import create_app

# Sentinel that can NEVER be confused with the old hardcoded literals.
_TREND_SENTINEL = "sentinel_stage_xyz"


# ---------------------------------------------------------------------------
# Pipeline-site harness (reuses the _step_charts substrate shape).
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline_db(tmp_path):
    """Schema + a state='running' pipeline_run so `lease.fenced_write`
    succeeds. Returns (cfg, run_id, eval_run_id)."""
    from swing.config import load as load_config
    from swing.data.db import ensure_schema as _ensure
    from tests.cli.test_cli_eval import _minimal_config

    # Use a dedicated subdir so this fixture does not collide with the
    # conftest `seeded_db`/`test_cfg` fixture (which also creates a top-level
    # `project` dir under the same tmp_path) when a test uses both.
    base = tmp_path / "pipeline_db"
    base.mkdir()
    project = base / "project"
    project.mkdir()
    home = base / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_config(cfg_path)
    _ensure(cfg.paths.db_path).close()

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO evaluation_runs
                    (run_ts, data_asof_date, action_session_date,
                     finviz_csv_path, tickers_evaluated, aplus_count,
                     watch_count, skip_count, excluded_count, error_count)
                VALUES ('2026-05-22T09:00:00', '2026-05-21', '2026-05-22',
                        NULL, 1, 1, 0, 0, 0, 0)
                """
            )
            eval_run_id = int(cur.lastrowid)
            cur = conn.execute(
                """
                INSERT INTO pipeline_runs
                    (started_ts, trigger, data_asof_date,
                     action_session_date, state, lease_token,
                     evaluation_run_id)
                VALUES ('2026-05-22T08:00:00', 'manual', '2026-05-21',
                        '2026-05-22', 'running', 't-step', ?)
                """,
                (eval_run_id,),
            )
            run_id = int(cur.lastrowid)
    finally:
        conn.close()
    return cfg, run_id, eval_run_id


def _make_bars(periods: int = 60) -> pd.DataFrame:
    closes = [100.0 + i * 0.1 for i in range(periods)]
    idx = pd.bdate_range(start="2026-01-02", periods=periods)
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * periods,
    }, index=idx)


class _StubOhlcvCache:
    def get_or_fetch(self, *, ticker: str, window_days: int = 200) -> pd.DataFrame:
        return _make_bars()


def _run_step_charts(*, cfg, run_id, eval_run_id, ohlcv_cache):
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_charts
    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token="t-step")
    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id,
        data_asof="2026-05-21", ohlcv_cache=ohlcv_cache,
    )


def _capture_weather_kwargs(monkeypatch, module):
    """Spy the `render_market_weather_svg` symbol on `module`, capturing the
    `trend_template_state` kwarg of the LAST invocation. Returns the captured
    dict (read after the call)."""
    captured: dict = {}

    def spy(*, bars, trend_template_state):
        captured["trend_template_state"] = trend_template_state
        return b"<svg>weather</svg>"

    monkeypatch.setattr(module, "render_market_weather_svg", spy)
    return captured


# ---------------------------------------------------------------------------
# Pipeline-site tests.
# ---------------------------------------------------------------------------


def test_pipeline_weather_render_computes_real_trend_state(
    pipeline_db, monkeypatch,
):
    """The pipeline site derives trend_template_state from
    `structural_stage` — the sentinel reaches the renderer (NOT the old
    hardcoded "stage_2")."""
    cfg, run_id, eval_run_id = pipeline_db
    import swing.pipeline.runner as runner_mod

    monkeypatch.setattr(
        runner_mod, "structural_stage",
        lambda closes, *, rising_period: _TREND_SENTINEL,
    )
    captured = _capture_weather_kwargs(monkeypatch, runner_mod)
    _run_step_charts(
        cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )
    assert captured.get("trend_template_state") == _TREND_SENTINEL


def test_pipeline_weather_failsoft_to_undefined_does_not_abort_step(
    pipeline_db, monkeypatch, caplog,
):
    """If `structural_stage` raises, the pipeline site fails soft to
    "undefined" (NOT "n/a"), logs a WARNING, and `_step_charts` completes
    without raising."""
    cfg, run_id, eval_run_id = pipeline_db
    import swing.pipeline.runner as runner_mod

    def _boom(closes, *, rising_period):
        raise RuntimeError("structural_stage failed (synthetic)")

    monkeypatch.setattr(runner_mod, "structural_stage", _boom)
    captured = _capture_weather_kwargs(monkeypatch, runner_mod)

    with caplog.at_level(logging.WARNING):
        # Must NOT raise.
        _run_step_charts(
            cfg=cfg, run_id=run_id, eval_run_id=eval_run_id,
            ohlcv_cache=_StubOhlcvCache(),
        )

    assert captured.get("trend_template_state") == "undefined"
    assert any(
        "structural_stage" in rec.getMessage() for rec in caplog.records
    ), "expected a WARNING mentioning structural_stage"


# ---------------------------------------------------------------------------
# Refresh-handler harness (reuses the dashboard chart-integration shape).
# ---------------------------------------------------------------------------


def _seed_complete_run(conn) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token)
        VALUES ('2026-05-20T09:00:00', '2026-05-20T09:05:00',
                'manual', '2026-05-19', '2026-05-20', 'complete', 't-x')
        """
    )
    return int(cur.lastrowid)


def _refresh_df() -> pd.DataFrame:
    idx = pd.date_range("2026-05-15", periods=60, freq="B")
    return pd.DataFrame({
        "Open": [100.0] * 60, "High": [101.0] * 60, "Low": [99.0] * 60,
        "Close": [100.5] * 60, "Volume": [1_000_000] * 60,
    }, index=idx)


class _RefreshStubOhlcvCache:
    def get_or_fetch(self, *, ticker, window_days=180):
        return _refresh_df()

    def is_degraded(self):
        return False


def _make_refresh_app(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_run(conn)
            # Seed a stale cache row so the refresh has something to replace.
            refresh_chart_render(conn, ChartRender(
                id=None, ticker=cfg.rs.benchmark_ticker,
                surface="market_weather",
                chart_svg_bytes=b"<svg>STALE</svg>",
                source_data_hash="hash-w",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=run_id, pattern_class=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    return app, cfg, cfg_path


def test_weather_refresh_handler_computes_real_trend_state(
    seeded_db, monkeypatch,
):
    """The refresh handler derives trend_template_state from
    `structural_stage` — the sentinel reaches the renderer (NOT the old
    hardcoded "n/a")."""
    import swing.web.routes.dashboard as dash_mod

    monkeypatch.setattr(
        dash_mod, "structural_stage",
        lambda closes, *, rising_period: _TREND_SENTINEL,
    )
    captured = _capture_weather_kwargs(monkeypatch, dash_mod)

    app, _cfg, _cfg_path = _make_refresh_app(seeded_db)
    with TestClient(app) as client:
        app.state.ohlcv_cache = _RefreshStubOhlcvCache()
        r = client.post(
            "/dashboard/weather-chart/refresh",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text
    assert captured.get("trend_template_state") == _TREND_SENTINEL


def test_weather_refresh_failsoft_to_undefined(seeded_db, monkeypatch, caplog):
    """If `structural_stage` raises in the refresh handler, fail soft to
    "undefined" (NOT "n/a"), log a WARNING, and still 204 (no crash)."""
    import swing.web.routes.dashboard as dash_mod

    def _boom(closes, *, rising_period):
        raise RuntimeError("structural_stage failed (synthetic)")

    monkeypatch.setattr(dash_mod, "structural_stage", _boom)
    captured = _capture_weather_kwargs(monkeypatch, dash_mod)

    app, _cfg, _cfg_path = _make_refresh_app(seeded_db)
    with caplog.at_level(logging.WARNING):
        with TestClient(app) as client:
            app.state.ohlcv_cache = _RefreshStubOhlcvCache()
            r = client.post(
                "/dashboard/weather-chart/refresh",
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 204, r.text
    assert captured.get("trend_template_state") == "undefined"
    assert any(
        "structural_stage" in rec.getMessage() for rec in caplog.records
    ), "expected a WARNING mentioning structural_stage"


# ---------------------------------------------------------------------------
# JIT default (dead/defensive) — honest "undefined".
# ---------------------------------------------------------------------------


def test_chart_jit_market_weather_default_is_undefined(tmp_path):
    """BEHAVIORAL: with NO trend kwarg, the JIT market_weather branch passes
    trend_template_state="undefined" to the renderer (NOT the old
    "stage_2")."""
    import importlib

    from swing.data.db import ensure_schema
    import swing.web.chart_jit as mod
    from swing.web.chart_jit import get_or_render_surface

    conn = ensure_schema(tmp_path / "jit_weather.db")
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2026-05-22T00:00:00.000', 'manual', '2026-05-22', "
            "'2026-05-22', 'complete', 'tok-jit-w')"
        )
        run_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _make_bars()

    captured: dict = {}

    def spy(*, bars, trend_template_state):
        captured["trend_template_state"] = trend_template_state
        return b"<svg>jit</svg>"

    mod._RENDERERS["market_weather"] = spy
    try:
        get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="market_weather", ticker="SPY",
            pipeline_run_id=run_id, data_asof_date="2026-05-22",
        )
    finally:
        importlib.reload(mod)

    assert captured.get("trend_template_state") == "undefined"


# ---------------------------------------------------------------------------
# Two-live-site uniformity: both live sites derive from current_stage.
# ---------------------------------------------------------------------------


def test_weather_two_live_callsites_identical_kwarg_derivation(
    pipeline_db, seeded_db, monkeypatch,
):
    """Both LIVE call sites (pipeline + refresh) derive trend_template_state
    from `structural_stage` — the SAME sentinel reaches the renderer at both,
    proving uniform derivation (Expansion #10c)."""
    # --- Pipeline site ---
    cfg_p, run_id, eval_run_id = pipeline_db
    import swing.pipeline.runner as runner_mod
    monkeypatch.setattr(
        runner_mod, "structural_stage",
        lambda closes, *, rising_period: _TREND_SENTINEL,
    )
    pipeline_captured = _capture_weather_kwargs(monkeypatch, runner_mod)
    _run_step_charts(
        cfg=cfg_p, run_id=run_id, eval_run_id=eval_run_id,
        ohlcv_cache=_StubOhlcvCache(),
    )

    # --- Refresh site ---
    import swing.web.routes.dashboard as dash_mod
    monkeypatch.setattr(
        dash_mod, "structural_stage",
        lambda closes, *, rising_period: _TREND_SENTINEL,
    )
    refresh_captured = _capture_weather_kwargs(monkeypatch, dash_mod)
    app, _cfg, _cfg_path = _make_refresh_app(seeded_db)
    with TestClient(app) as client:
        app.state.ohlcv_cache = _RefreshStubOhlcvCache()
        r = client.post(
            "/dashboard/weather-chart/refresh",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text

    assert pipeline_captured.get("trend_template_state") == _TREND_SENTINEL
    assert refresh_captured.get("trend_template_state") == _TREND_SENTINEL
    assert (
        pipeline_captured["trend_template_state"]
        == refresh_captured["trend_template_state"]
    )
