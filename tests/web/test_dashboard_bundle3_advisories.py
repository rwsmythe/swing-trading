"""3e.8 Bundle 3 — dashboard threads maturity_stage from daily_snapshot
into the §4.A.bis advisory (build_dashboard composition site).

Discriminating: two trades on the same dashboard, one with maturity_stage
``pre_+1.5R`` (→ "20MA") and one with ``>=+2R_trail_eligible`` (→ "10MA").
The rendered HTML must contain BOTH MAs in distinct advisory messages —
proves per-trade maturity_stage threading is correct (not a stuck constant).
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.repos.daily_management import insert_snapshot
from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    state: str = "managing",
    entry_price: float = 100.0,
    initial_stop: float = 90.0,
    initial_shares: int = 50,
    current_avg_cost: float = 100.0,
    current_size: float = 50.0,
    current_stop: float = 92.0,
    pre_trade_locked_at: str = "2026-05-01T09:30:00",
) -> None:
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual_off_pipeline', ?, ?, ?)",
        (
            trade_id, ticker, pre_trade_locked_at[:10],
            entry_price, initial_shares, initial_stop, current_stop, state,
            pre_trade_locked_at, current_size, current_avg_cost,
        ),
    )
    conn.commit()


def _snapshot_fields(
    *,
    data_asof_session: str = "2026-05-07",
    maturity_stage: str = "pre_+1.5R",
    current_price: float = 110.0,
    current_stop: float = 95.0,
) -> dict:
    return {
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T00:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": None,
        "current_price": current_price,
        "current_stop": current_stop,
        "current_size": 50.0,
        "current_avg_cost": 100.0,
        "open_R_effective": 1.0,
        "open_MFE_R_to_date": 1.0,
        "open_MAE_R_to_date": 0.1,
        "intraday_high": current_price + 1.0,
        "intraday_low": current_price - 1.0,
        "position_capital_utilization_pct": 0.15,
        "position_capital_denominator_dollars": 7500.0,
        "position_portfolio_heat_contribution_dollars": 50.0,
        "maturity_stage": maturity_stage,
        "trail_MA_candidate_price": 105.0,
        "trail_MA_period_days": 21,
        "trail_MA_eligibility_flag": 0,
    }


@pytest.fixture
def app_factory(tmp_path: Path, monkeypatch):
    """Yield (app, db_path). PriceCache stubbed with two open-trade snapshots."""
    from datetime import datetime
    from swing.web.price_cache import PriceSnapshot

    def _stub_get_many(self, tickers, deadline_seconds, *, executor=None):
        return {
            t: PriceSnapshot(
                ticker=t, price=110.0,
                asof=datetime(2026, 5, 7, 16, 0, 0),
                is_stale=False, source="last_close",
            )
            for t in tickers
        }
    monkeypatch.setattr(PriceCache, "get_many", _stub_get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    def _factory():
        db_path = tmp_path / "phase3e8_b3.db"
        ensure_schema(db_path).close()
        base_cfg = load(Path("swing.config.toml"))
        cfg = dc_replace(
            base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
        )
        return create_app(cfg), db_path

    return _factory


def test_dashboard_renders_per_trade_maturity_stage_advisory(app_factory):
    """Two trades, two distinct maturity stages → two distinct recommended
    MAs in rendered open-positions advisory column.

    Discriminating against a stuck-constant or shared-state bug: if
    threading were broken and both trades shared maturity_stage, only ONE
    MA would appear in the rendered HTML.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="AAAA")
        _seed_trade(conn, trade_id=2, ticker="BBBB")
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_snapshot_fields(maturity_stage="pre_+1.5R"),
        )
        insert_snapshot(
            conn, trade_id=2,
            snapshot_fields=_snapshot_fields(
                maturity_stage=">=+2R_trail_eligible",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # Sanity: open-positions table renders both tickers.
    assert "AAAA" in body, "trade AAAA missing from dashboard"
    assert "BBBB" in body, "trade BBBB missing from dashboard"
    # Both maturity-stage advisories must render with their distinct MAs.
    assert "Maturity stage pre_+1.5R" in body, (
        f"§4.A.bis advisory for pre_+1.5R not in body. Snippet: "
        f"{body[body.find('AAAA'):body.find('AAAA')+1500]!r}"
    )
    assert "Maturity stage &gt;=+2R_trail_eligible" in body or (
        "Maturity stage >=+2R_trail_eligible" in body
    ), "§4.A.bis advisory for >=+2R_trail_eligible not in body"
    # Distinct recommended-MA strings appear; if threading were broken, the
    # value of one trade would leak into the other.
    assert "20MA" in body
    assert "10MA" in body


def test_dashboard_omits_maturity_advisory_for_trade_without_snapshot(
    app_factory,
):
    """Trade with NO active snapshot must not render the §4.A.bis advisory.

    Other advisories (trail-10ma etc.) may still render; we assert only the
    targeted rule's absence.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="AAAA")
        # NO insert_snapshot for trade 1.
    finally:
        conn.close()

    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # No maturity-stage advisory should render for this trade.
    assert "Maturity stage" not in r.text
