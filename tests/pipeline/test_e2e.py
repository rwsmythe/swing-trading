"""End-to-end pipeline smoke test (slow-marked)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.repos.pipeline import find_run
from swing.pipeline import run_pipeline
from tests.cli.test_cli_eval import _minimal_config


pytestmark = pytest.mark.slow


@pytest.fixture
def phase2_finviz_fixture():
    """Phase-2-compliant fixture with all REQUIRED_COLUMNS from finviz_schema.
    Small (5 tickers) for speed; the E2E test exercises orchestration, not
    bucket-assignment semantics."""
    src = Path(__file__).parent.parent / "fixtures" / "finviz" / "finviz13Apr2026-phase2.csv"
    if not src.exists():
        pytest.skip(f"fixture not found: {src}")
    return src


def test_pipeline_e2e_smoke(tmp_path: Path, phase2_finviz_fixture, monkeypatch):
    """End-to-end run against a Phase-2-schema-compliant fixture with NO
    validate_csv bypass — the full 9-step pipeline including schema gate
    executes cleanly (adversarial review Batch 5 Round 1 Major 1)."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(phase2_finviz_fixture, inbox / phase2_finviz_fixture.name)

    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end="2026-04-13", periods=260)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 260,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "complete", result.error_message

    import sqlite3
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        run = find_run(conn, result.run_id)
        assert run.weather_status == "ok"
        assert run.evaluation_status == "ok"
        assert run.watchlist_status == "ok"
        assert run.recommendations_status == "ok"
        assert run.export_status == "ok"

        eval_rows = conn.execute("SELECT COUNT(*) FROM evaluation_runs").fetchone()[0]
        assert eval_rows == 1
        cand_rows = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        assert cand_rows >= 5
        weather_rows = conn.execute("SELECT COUNT(*) FROM weather_runs").fetchone()[0]
        assert weather_rows == 1
    finally:
        conn.close()

    assert (cfg.paths.exports_dir / run.action_session_date / "briefing.html").exists()
