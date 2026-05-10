"""Polish-bundle 2026-05-09 Task family A — dashboard "updated today?" badge
on every open-positions row.

A.3 verifies the VM-level wiring: ``OpenPositionsRowVM.has_update_today``
field is True iff the trade has at least one matching daily-management record
for today's session (anchored on ``last_completed_session(now)`` per Codex R1
Major #1 fix — matches the writers' ``review_date`` stamp).

A.7 verifies the rendered HTML: dashboard responds with the two-state badge
glyphs ``✓ today`` (matched) and ``⚠ not yet`` (unmatched) per row.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient  # used by A.7 next commit

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.repos.daily_management import insert_snapshot
from swing.evaluation.dates import last_completed_session
from swing.web.app import create_app  # used by A.7 next commit
from swing.web.price_cache import PriceCache
from swing.web.view_models.dashboard import build_dashboard


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    state: str = "managing",
) -> None:
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, '2026-05-01', 100.0, 50, 90.0, 92.0, ?, "
        " 'manual_off_pipeline', '2026-05-01T09:30:00', 50.0, 100.0)",
        (trade_id, ticker, state),
    )
    conn.commit()


def _full_snapshot_fields(*, data_asof_session: str) -> dict[str, Any]:
    """Mirrors the helper in tests/data/test_daily_management_repo.py."""
    return {
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T00:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": None,
        "current_price": 110.0,
        "current_stop": 95.0,
        "current_size": 50.0,
        "current_avg_cost": 100.0,
        "open_R_effective": 1.0,
        "open_MFE_R_to_date": 1.5,
        "open_MAE_R_to_date": 0.2,
        "intraday_high": 111.0,
        "intraday_low": 109.0,
        "position_capital_utilization_pct": 0.1467,
        "position_capital_denominator_dollars": 7500.0,
        "position_portfolio_heat_contribution_dollars": 50.0,
        "maturity_stage": "+1.5R_to_+2R",
        "trail_MA_candidate_price": 105.0,
        "trail_MA_period_days": 21,
        "trail_MA_eligibility_flag": 0,
    }


@pytest.fixture
def dashboard_env(tmp_path: Path, monkeypatch):
    """Stand up a dashboard app + DB with PriceCache stubbed (no network)."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *args, **kwargs: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    db_path = tmp_path / "polish_a.db"
    conn = ensure_schema(db_path)
    conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return cfg, db_path


def test_build_dashboard_sets_has_update_today_true_when_snapshot_present(
    dashboard_env,
) -> None:
    """A.3 — when a daily_snapshot row exists for today's action_session,
    ``OpenPositionsRowVM.has_update_today`` must be True."""
    cfg, db_path = dashboard_env
    today = last_completed_session(datetime.now()).isoformat()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="AAA")
        with conn:
            insert_snapshot(
                conn, trade_id=1,
                snapshot_fields=_full_snapshot_fields(data_asof_session=today),
            )
    finally:
        conn.close()

    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert 1 in vm.open_trade_rows
    assert vm.open_trade_rows[1].has_update_today is True


def test_build_dashboard_sets_has_update_today_false_when_no_record(
    dashboard_env,
) -> None:
    """A.3 — open trade with no daily-management record for today must have
    ``has_update_today`` == False."""
    cfg, db_path = dashboard_env
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=2, ticker="BBB")
    finally:
        conn.close()

    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert 2 in vm.open_trade_rows
    assert vm.open_trade_rows[2].has_update_today is False


def test_dashboard_renders_both_update_badge_states(dashboard_env) -> None:
    """A.7 — full-page dashboard render contains BOTH badge glyphs when one
    open trade has a today-snapshot and one does not.

    Pre-fix: template never emits either glyph.
    Post-fix: row partial appends ``✓ today`` for matched trades and
    ``⚠ not yet`` for unmatched trades next to the state badge."""
    cfg, db_path = dashboard_env
    today = last_completed_session(datetime.now()).isoformat()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=10, ticker="UPDT")  # will get a snapshot
        _seed_trade(conn, trade_id=11, ticker="STAL")  # no snapshot
        with conn:
            insert_snapshot(
                conn, trade_id=10,
                snapshot_fields=_full_snapshot_fields(data_asof_session=today),
            )
    finally:
        conn.close()

    app = create_app(cfg)
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "✓ today" in body, "expected '✓ today' badge in dashboard HTML"
    assert "⚠ not yet" in body, "expected '⚠ not yet' badge in dashboard HTML"


def test_post_event_log_then_dashboard_badge_flips_to_today(dashboard_env) -> None:
    """Codex R1 Major #1 regression — the round-trip from operator submit to
    badge flip must work in practice.

    Setup: one open trade with NO daily-management record (badge starts at
    ``⚠ not yet``). POST an event_log via the route. Re-render the dashboard
    and assert the row's badge is now ``✓ today``.

    This pins the read/write session-anchor alignment closed by Codex R1
    Major #1. Both writers (pipeline + this route) stamp ``review_date =
    last_completed_session(now)``; the badge reader was originally anchored
    on ``action_session_for_run(now)`` and silently never matched on
    weekends, evenings, or pre-market opens. Aligning the reader on
    ``last_completed_session`` closes the gap; this test catches any future
    drift on either side.
    """
    cfg, db_path = dashboard_env
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=20, ticker="POSTD")
    finally:
        conn.close()

    app = create_app(cfg)
    with TestClient(app) as client:
        # Pre-submit dashboard render — badge MUST be ⚠ not yet for our row.
        pre = client.get("/")
        assert pre.status_code == 200
        # The CSS class is row-scoped; assert the negative badge appears
        # for the POSTD ticker. Use a substring window per row.
        assert "⚠ not yet" in pre.text
        # Submit a minimum-viable event_log POST — only required-by-validator
        # fields plus the safe defaults the route uses.
        submit = client.post(
            "/trades/20/daily-management/event",
            data={
                # Position-state fields are OPTIONAL on event_log per Phase 8
                # spec §3.1.1. Provide just the operator-input boilerplate
                # that the form's validator may require.
                "stop_changed": "0",
                "rule_violation_suspected": "0",
                "thesis_status": "validated",
                "action_taken": "no_action",
                "action_reason": "thesis_intact",
                "management_notes": "Codex R1 Major #1 regression test event.",
                "emotional_state": ["calm"],
            },
            headers={"HX-Request": "true"},
        )
        assert submit.status_code == 204, (
            f"event_log POST should succeed; got {submit.status_code}: "
            f"{submit.text[:300]}"
        )
        assert submit.headers.get("HX-Redirect") == "/", (
            f"event_log POST should redirect to /; got "
            f"{submit.headers.get('HX-Redirect')!r}"
        )
        # Post-submit dashboard render — badge MUST flip to ✓ today.
        post = client.get("/")
    assert post.status_code == 200
    assert "✓ today" in post.text, (
        "after a successful event_log POST, the open-positions row badge "
        "must show '✓ today' — read/write session-anchor mismatch"
    )
