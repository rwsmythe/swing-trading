"""Phase 14 Sub-bundle 1 P14.N3 dashboard VM denominator-stamping tests.

Per spec section 6.2 (denominator-stamping mirror per maturity.py:197-219)
+ R3.M1 LOCK (PROPORTION-unit semantic; recompute via
compute_position_capital_utilization).

Tests open a tmp-path DB via ensure_schema(); plant a Phase 7+8 open trade
+ active daily_management snapshot row; invoke build_dashboard against a
PriceCache stub; assert per-tile field values for the P14.N3 4-field
extension (denominator_dollars_resolved / is_provisional / pct_effective /
policy_missing).
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.repos.account_equity_snapshots import (
    insert_snapshot as insert_aes_snapshot,
)
from swing.data.repos.daily_management import (
    insert_snapshot as insert_dm_snapshot,
)
from swing.evaluation.dates import last_completed_session
from swing.trades.daily_management import (
    compute_position_capital_utilization,
)
from swing.web.price_cache import PriceCache
from swing.web.view_models.dashboard import build_dashboard

_TODAY_SESSION = last_completed_session(datetime.now()).isoformat()


def _seed_vsat_trade(conn: sqlite3.Connection) -> None:
    """Seed an open VSAT trade. current_size=10.0, current_price=42.0,
    so utilization @ 7500 denom = 0.056 (5.6%); @ 12345 denom = 0.034
    (3.4%); divergent denoms exercise the recompute path."""
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (1, 'VSAT', '2026-05-01', 40.0, 10, 38.0, 40.0, 'managing', "
        " 'manual_off_pipeline', '2026-05-01T09:30:00', 10.0, 40.0)",
    )
    conn.commit()


def _full_snapshot_fields(
    *,
    data_asof_session: str = _TODAY_SESSION,
    util_pct: float = 0.056,
    denom_dollars: float = 7500.0,
    current_price: float = 42.0,
) -> dict[str, Any]:
    """Snapshot fields satisfying OPERATION_REQUIRED_FIELDS['snapshot_emit']."""
    return {
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T00:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": None,
        "current_price": current_price,
        "current_stop": 40.0,
        "current_size": 10.0,
        "current_avg_cost": 40.0,
        "open_R_effective": 1.0,
        "open_MFE_R_to_date": 1.0,
        "open_MAE_R_to_date": 0.2,
        "intraday_high": 42.5,
        "intraday_low": 41.5,
        "position_capital_utilization_pct": util_pct,
        "position_capital_denominator_dollars": denom_dollars,
        "position_portfolio_heat_contribution_dollars": 20.0,
        "maturity_stage": "pre_+1.5R",
        "trail_MA_candidate_price": None,
        "trail_MA_period_days": None,
        "trail_MA_eligibility_flag": 0,
    }


@pytest.fixture
def planted_vsat_env(tmp_path: Path, monkeypatch):
    """Plant an open VSAT trade + active daily_management snapshot row for
    today's last-completed session. PriceCache stubbed to return empty
    snapshots (tile is built from snapshot row, not live PriceCache).

    Returns (cfg, db_path) so tests can mutate state per their need
    (e.g., plant an account_equity_snapshot for LIVE path; flip
    risk_policy is_active=0 for NoActivePolicyError test).
    """
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *args, **kwargs: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    db_path = tmp_path / "p14n3.db"
    ensure_schema(db_path).close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    conn = connect(db_path)
    try:
        _seed_vsat_trade(conn)
        with conn:
            insert_dm_snapshot(
                conn, trade_id=1,
                snapshot_fields=_full_snapshot_fields(),
            )
    finally:
        conn.close()
    return cfg, db_path


def _get_vsat_tile(vm):
    return next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )


def test_provisional_when_no_account_equity_snapshot_row(planted_vsat_env):
    """No account_equity_snapshots row covering data_asof_session ->
    is_provisional=True; denom = capital_floor_constant_dollars
    (spec section 6.1)."""
    cfg, _ = planted_vsat_env
    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    tile = _get_vsat_tile(vm)
    assert tile.position_capital_utilization_is_provisional is True
    # PROVISIONAL fallback uses capital_floor_constant_dollars (7500.0).
    assert tile.position_capital_denominator_dollars_resolved == pytest.approx(
        7500.0
    )
    assert tile.position_capital_policy_missing is False


def test_live_when_account_equity_snapshot_covers_data_asof_session(
    planted_vsat_env,
):
    """account_equity_snapshots row with snapshot_date <= data_asof_session
    -> is_provisional=False; denom = snapshot equity (spec section 6.5
    example #2)."""
    cfg, db_path = planted_vsat_env
    conn = connect(db_path)
    try:
        with conn:
            insert_aes_snapshot(
                conn,
                snapshot_date=_TODAY_SESSION,
                equity_dollars=12345.0,
                source="manual",
                source_artifact_path="test:fixture:p14n3-live",
                recorded_at=datetime.now().isoformat(timespec="seconds"),
                recorded_by="test",
                notes="P14.N3 LIVE fixture",
            )
    finally:
        conn.close()
    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    tile = _get_vsat_tile(vm)
    assert tile.position_capital_utilization_is_provisional is False
    assert tile.position_capital_denominator_dollars_resolved == pytest.approx(
        12345.0
    )
    assert tile.position_capital_policy_missing is False


def test_effective_pct_reuses_stored_when_denominators_match(
    planted_vsat_env,
):
    """When snap.position_capital_denominator_dollars == freshly-resolved
    via math.isclose(rel_tol=1e-9), reuse stored proportion (spec section
    6.2 denominator-stamping mirror per maturity.py:215-219).

    Fixture planted stored_denom=7500.0 + util=0.056 + no
    account_equity_snapshot row -> resolver returns
    capital_floor_constant_dollars (default 7500.0) -- denominators match;
    tile reuses stored util.
    """
    cfg, _ = planted_vsat_env
    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    tile = _get_vsat_tile(vm)
    # Stored matches resolved -> pct_effective == stored util.
    assert tile.position_capital_utilization_pct_effective == pytest.approx(
        tile.position_capital_utilization_pct
    )


def test_effective_pct_recomputed_via_compute_position_capital_utilization_when_denominators_diverge(  # noqa: E501
    planted_vsat_env,
):
    """When stored denominator != freshly-resolved, recompute as
    PROPORTION via compute_position_capital_utilization (R3.M1 LOCK).

    Plant a divergent account_equity snapshot (12345 vs stored 7500); the
    math.isclose comparison fails; the recompute path fires; util_pct_eff
    is the PROPORTION (current_size * current_price / denom_resolved =
    10 * 42 / 12345 = 0.034). Critically NOT a percent (would be 3.4
    which would render as 340.0% via template * 100.0).
    """
    cfg, db_path = planted_vsat_env
    conn = connect(db_path)
    try:
        with conn:
            insert_aes_snapshot(
                conn,
                snapshot_date=_TODAY_SESSION,
                equity_dollars=12345.0,
                source="manual",
                source_artifact_path="test:fixture:p14n3-divergent",
                recorded_at=datetime.now().isoformat(timespec="seconds"),
                recorded_by="test",
                notes="P14.N3 divergent-denom fixture",
            )
    finally:
        conn.close()
    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    tile = _get_vsat_tile(vm)
    expected = compute_position_capital_utilization(
        current_size=10.0,
        current_price=42.0,
        denominator_dollars=tile.position_capital_denominator_dollars_resolved,
    )
    assert tile.position_capital_utilization_pct_effective == pytest.approx(
        expected
    )
    # Sanity: PROPORTION-unit (R3.M1 LOCK) -- value < 1.0 for a 10-share
    # @ $42 position against 12345 denom; NOT a percent (would be 3.4).
    assert tile.position_capital_utilization_pct_effective < 1.0


def test_no_active_risk_policy_renders_provisional_not_500(
    planted_vsat_env,
):
    """Codex R1.M#1 + R2.M#1+M#2 LOCK + spec section 6.4 second bullet:
    when risk_policy has zero rows with is_active=1, build_dashboard MUST
    NOT raise NoActivePolicyError -- it MUST render the tile with
    policy_missing=True so the template surfaces a distinct PROVISIONAL +
    extra-caveat badge."""
    cfg, db_path = planted_vsat_env
    conn = connect(db_path)
    try:
        conn.execute("UPDATE risk_policy SET is_active = 0")
        conn.commit()
    finally:
        conn.close()
    cache = PriceCache(cfg.web)
    # Must NOT raise NoActivePolicyError.
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    tile = _get_vsat_tile(vm)
    assert tile.position_capital_policy_missing is True
    assert tile.position_capital_utilization_is_provisional is True
    assert tile.position_capital_denominator_dollars_resolved == 0.0
    # With denom_resolved=0.0, util_pct_effective is None (the recompute
    # short-circuits per the denom_resolved > 0 guard); template renders
    # ASCII dash + the policy-missing badge.
    assert tile.position_capital_utilization_pct_effective is None


def test_malformed_data_asof_session_falls_back_to_page_asof_date(
    planted_vsat_env,
):
    """date.fromisoformat raises ValueError on malformed
    snap.data_asof_session -> fall back to page-level last_completed_session
    anchor (mirrors maturity.py:190-194). No raise; tile constructed; the
    PROVISIONAL/LIVE state reflects the page-level anchor."""
    cfg, db_path = planted_vsat_env
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE daily_management_records "
            "SET data_asof_session = 'not-a-date'"
        )
        conn.commit()
    finally:
        conn.close()
    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    tile = _get_vsat_tile(vm)
    # No raise; tile constructed; is_provisional is a bool.
    assert isinstance(tile.position_capital_utilization_is_provisional, bool)
    # policy_missing is False (active policy row present); the fallback to
    # page asof_date applies cleanly.
    assert tile.position_capital_policy_missing is False
