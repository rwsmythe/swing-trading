"""Phase 8 Task 5.1: dashboard tile tests for daily-management state.

Plan: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md §5.1
(Spec §6 read-surfaces / §7.1 dashboard tile / §5.6 read-precedence ladder).

Test contracts (from plan §5.1 Step 1):
  * §5.6 read-precedence: live current_stop = trades.current_stop, NOT
    snapshot's stale copy.
  * trail_MA_eligibility_flag badge visible only when flag=1.
  * planned_target_R renders em-dash placeholder when NULL.
  * position_capital_utilization_pct rendered with PROVISIONAL marker
    (spec §10.5 V1 fallback).
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

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
    planned_target_R: float | None = None,  # noqa: N803  -- spec column name
) -> None:
    """Seed a Phase 7+8 trade row sufficient to drive the dashboard tile.

    Mirrors the helper in ``tests/web/test_daily_management_event_route.py``;
    extended with ``planned_target_R`` (Phase 8 column) so tests can exercise
    the §7.1 NULL-as-em-dash render contract.
    """
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost, planned_target_R) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual_off_pipeline', ?, ?, ?, ?)",
        (
            trade_id, ticker, pre_trade_locked_at[:10],
            entry_price, initial_shares, initial_stop, current_stop, state,
            pre_trade_locked_at, current_size, current_avg_cost,
            planned_target_R,
        ),
    )
    conn.commit()


def _full_snapshot_fields(
    *,
    data_asof_session: str = "2026-05-07",
    current_price: float = 110.0,
    current_stop: float = 95.0,
    open_MFE_R_to_date: float = 1.5,  # noqa: N803  -- spec column name
    open_MAE_R_to_date: float = 0.2,  # noqa: N803  -- spec column name
    maturity_stage: str = "+1.5R_to_+2R",
    trail_MA_candidate_price: float | None = 105.0,  # noqa: N803
    trail_MA_period_days: int | None = 21,  # noqa: N803
    trail_MA_eligibility_flag: int = 0,  # noqa: N803
    position_capital_utilization_pct: float = 0.1467,
    position_capital_denominator_dollars: float = 7500.0,
    position_portfolio_heat_contribution_dollars: float = 50.0,
    pipeline_run_id: int | None = None,
) -> dict[str, Any]:
    """Mirror ``_full_snapshot_fields`` from ``tests/data/test_daily_management_repo.py``.

    All ``snapshot_emit`` required fields populated; defaults overridable per
    test so each contract case can vary one dimension at a time.
    """
    return {
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T00:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": pipeline_run_id,
        "current_price": current_price,
        "current_stop": current_stop,
        "current_size": 50.0,
        "current_avg_cost": 100.0,
        "open_R_effective": 1.0,
        "open_MFE_R_to_date": open_MFE_R_to_date,
        "open_MAE_R_to_date": open_MAE_R_to_date,
        "intraday_high": current_price + 1.0,
        "intraday_low": current_price - 1.0,
        "position_capital_utilization_pct": position_capital_utilization_pct,
        "position_capital_denominator_dollars": (
            position_capital_denominator_dollars
        ),
        "position_portfolio_heat_contribution_dollars": (
            position_portfolio_heat_contribution_dollars
        ),
        "maturity_stage": maturity_stage,
        "trail_MA_candidate_price": trail_MA_candidate_price,
        "trail_MA_period_days": trail_MA_period_days,
        "trail_MA_eligibility_flag": trail_MA_eligibility_flag,
    }


@pytest.fixture
def app_factory(tmp_path: Path, monkeypatch):
    """Yield a factory that opens a fresh DB + returns (app, db_path).

    The factory pattern lets each test seed the DB BEFORE the app reads it
    (the dashboard route opens the connection at request time, so seeding is
    free to happen up to the GET / call).
    """
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    def _factory():
        db_path = tmp_path / "phase8_tile.db"
        ensure_schema(db_path).close()
        base_cfg = load(Path("swing.config.toml"))
        cfg = dc_replace(
            base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
        )
        return create_app(cfg), db_path

    return _factory


def test_dashboard_tile_reads_live_current_stop_from_trades_row(app_factory):
    """§5.6 read-precedence: live current_stop = trades.current_stop, NOT
    snapshot's stale copy.

    Pre-fix expected (if VM reads snapshot's current_stop): rendered HTML
    contains '92.00' (snapshot's stale value).
    Post-fix expected: rendered HTML contains '95.00' (live trades-row value
    after a mid-session stop_adjust).
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(
            conn, trade_id=1, ticker="DHC", state="managing",
            current_stop=92.0,
        )
        # Insert snapshot with the stale current_stop=92.0:
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(current_stop=92.0),
        )
        # Mid-session stop_adjust simulated by direct UPDATE — trades-row
        # diverges from snapshot's stale copy.
        conn.execute(
            "UPDATE trades SET current_stop = 95.0 WHERE id = 1",
        )
        conn.commit()
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    # The dashboard's authoritative live stop is the trades-row value —
    # search the rendered tile region for it.
    assert "$95.00" in response.text or "95.00" in response.text
    # The snapshot's stale value (92.00) appearing as the tile's CURRENT
    # stop would be a §5.6 violation. The Open Positions table also renders
    # current_stop; both must read from trades-row, so 92.00 should NOT
    # appear in any cell labeled "Current stop". Use the daily-mgmt tile's
    # explicit data attribute for a tight assertion.
    tile_section = response.text.split('id="daily-management-tiles"')
    assert len(tile_section) >= 2, "tile section missing from dashboard"
    # The rendered tile MUST surface 95.00 and MUST NOT surface 92.00
    # within its scope (split on the next section closing tag).
    tile_html = tile_section[1].split("</section>")[0]
    assert "95.00" in tile_html
    assert "92.00" not in tile_html


def test_dashboard_tile_trail_MA_eligibility_badge_visible_only_when_TRUE(  # noqa: N802
    app_factory,
):
    """Spec §7.1: trail_MA_eligibility_flag badge visible ONLY when flag=1.

    Post-fix expected: badge text 'TRAIL ELIGIBLE' present in DOM when
    trail_MA_eligibility_flag=1; absent when flag=0.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        # Trade #1: eligible.
        _seed_trade(
            conn, trade_id=1, ticker="DHC", state="managing",
            current_stop=92.0,
        )
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                maturity_stage=">=+2R_trail_eligible",
                trail_MA_candidate_price=95.0,
                trail_MA_eligibility_flag=1,
            ),
        )
        # Trade #2: not eligible.
        _seed_trade(
            conn, trade_id=2, ticker="ZZ", state="managing",
            current_stop=49.0, entry_price=50.0, initial_stop=45.0,
        )
        insert_snapshot(
            conn, trade_id=2,
            snapshot_fields=_full_snapshot_fields(
                maturity_stage="pre_+1.5R",
                trail_MA_candidate_price=None,
                trail_MA_period_days=None,
                trail_MA_eligibility_flag=0,
            ),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text

    # DHC (eligible) row contains the badge text:
    import re
    dhc_row_match = re.search(
        r'<tr[^>]*data-tile-trade-id="1"[^>]*>.*?</tr>',
        body, re.DOTALL,
    )
    assert dhc_row_match, "DHC tile row not found"
    assert "TRAIL ELIGIBLE" in dhc_row_match.group(0)

    # ZZ (not eligible) row does NOT contain the badge text:
    zz_row_match = re.search(
        r'<tr[^>]*data-tile-trade-id="2"[^>]*>.*?</tr>',
        body, re.DOTALL,
    )
    assert zz_row_match, "ZZ tile row not found"
    assert "TRAIL ELIGIBLE" not in zz_row_match.group(0)


def test_dashboard_tile_planned_target_R_renders_dash_when_NULL(  # noqa: N802
    app_factory,
):
    """Spec §7.1: trades.planned_target_R IS NULL → em-dash placeholder.

    Post-fix expected: the rendered tile row's planned_target_R cell
    contains an em-dash ('—').
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(
            conn, trade_id=1, ticker="DHC", state="managing",
            current_stop=92.0, planned_target_R=None,
        )
        insert_snapshot(
            conn, trade_id=1, snapshot_fields=_full_snapshot_fields(),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # Locate the daily-mgmt tile row + assert the em-dash appears within
    # the planned_target_R cell. Cell carries a discriminating data attr
    # so we don't false-match on em-dashes elsewhere on the page.
    import re
    cell_match = re.search(
        r'data-tile-cell="planned_target_R"[^>]*>([^<]*)</',
        body,
    )
    assert cell_match, "planned_target_R cell not found"
    assert "—" in cell_match.group(1)  # em-dash


def test_dashboard_tile_capital_utilization_PROVISIONAL_marker(  # noqa: N802
    app_factory,
):
    """Spec §10.5: V1 capital_utilization renders with PROVISIONAL marker.

    Post-fix expected: text 'PROVISIONAL' (or aria-label / class containing
    that token) appears alongside the capital utilization badge.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(
            conn, trade_id=1, ticker="DHC", state="managing",
        )
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                position_capital_utilization_pct=0.72,
                position_capital_denominator_dollars=7500.0,
            ),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # The PROVISIONAL marker must appear in the daily-mgmt tile section
    # (avoid false-positives elsewhere on the page).
    tile_section = body.split('id="daily-management-tiles"')
    assert len(tile_section) >= 2, "tile section missing from dashboard"
    tile_html = tile_section[1].split("</section>")[0]
    assert "PROVISIONAL" in tile_html or "provisional" in tile_html


def test_dashboard_tile_excludes_closed_trade(app_factory):
    """Spec §7.1: closed trades MUST NOT appear in the dashboard tile.

    Drives the ``list_open_position_active_snapshots`` predicate through
    the VM builder (active-state JOIN filter).
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(
            conn, trade_id=1, ticker="OPEN", state="managing",
        )
        insert_snapshot(
            conn, trade_id=1, snapshot_fields=_full_snapshot_fields(),
        )
        _seed_trade(
            conn, trade_id=2, ticker="DEAD", state="closed",
        )
        insert_snapshot(
            conn, trade_id=2, snapshot_fields=_full_snapshot_fields(),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    tile_section = body.split('id="daily-management-tiles"')
    assert len(tile_section) >= 2, "tile section missing from dashboard"
    tile_html = tile_section[1].split("</section>")[0]
    assert "OPEN" in tile_html
    # Closed trade's ticker MUST NOT appear in the tile section. (It may
    # legitimately appear in other surfaces on the dashboard, e.g. the
    # closed-trades summary; but NOT in the daily-management tile.)
    assert "DEAD" not in tile_html


def test_dashboard_tile_renders_MFE_MAE_R_to_date_values(app_factory):  # noqa: N802
    """Spec §7.1: open_MFE_R_to_date / open_MAE_R_to_date appear in the tile.

    Post-fix expected: rendered tile contains the MFE/MAE numeric values
    sourced from the active snapshot row (snapshot is authoritative for
    in-flight running extrema per §5.6).
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(
            conn, trade_id=1, ticker="DHC", state="managing",
        )
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                open_MFE_R_to_date=2.34,
                open_MAE_R_to_date=0.45,
            ),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    tile_section = body.split('id="daily-management-tiles"')
    tile_html = tile_section[1].split("</section>")[0]
    # Two-decimal R format expected (matches existing tile precision).
    assert "2.34" in tile_html
    assert "0.45" in tile_html
