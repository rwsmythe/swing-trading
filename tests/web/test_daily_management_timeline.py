"""Phase 8 Task 5.1: per-trade timeline tests.

Plan: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md §5.1
(Spec §7.2 timeline contract — chronological with deterministic tiebreak;
default-excludes-superseded; snapshot vs event_log row distinction).

The route under test is GET ``/trades/{trade_id}`` (the canonical trade
detail page, registered by Phase 7 Sub-C C.5; Phase 8 Task 5.1 extends the
template with the timeline section).
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
from swing.data.repos.daily_management import (
    insert_event_log,
    insert_snapshot,
)
from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "DHC",
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


def _full_snapshot_fields(
    *,
    data_asof_session: str,
    review_date: str | None = None,
    created_at: str | None = None,
    current_price: float = 110.0,
    current_stop: float = 95.0,
    open_MFE_R_to_date: float = 1.5,  # noqa: N803
    open_MAE_R_to_date: float = 0.2,  # noqa: N803
    maturity_stage: str = "+1.5R_to_+2R",
    trail_MA_eligibility_flag: int = 0,  # noqa: N803
) -> dict[str, Any]:
    rd = review_date if review_date is not None else data_asof_session
    ca = (
        created_at
        if created_at is not None else f"{data_asof_session}T00:00:00"
    )
    return {
        "review_date": rd,
        "data_asof_session": data_asof_session,
        "created_at": ca,
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": None,
        "current_price": current_price,
        "current_stop": current_stop,
        "current_size": 50.0,
        "current_avg_cost": 100.0,
        "open_R_effective": 1.0,
        "open_MFE_R_to_date": open_MFE_R_to_date,
        "open_MAE_R_to_date": open_MAE_R_to_date,
        "intraday_high": current_price + 1.0,
        "intraday_low": current_price - 1.0,
        "position_capital_utilization_pct": 0.1467,
        "position_capital_denominator_dollars": 7500.0,
        "position_portfolio_heat_contribution_dollars": 50.0,
        "maturity_stage": maturity_stage,
        "trail_MA_candidate_price": 105.0,
        "trail_MA_period_days": 21,
        "trail_MA_eligibility_flag": trail_MA_eligibility_flag,
    }


def _minimal_event_log_fields(
    *,
    data_asof_session: str,
    review_date: str | None = None,
    created_at: str | None = None,
    management_notes: str | None = None,
) -> dict[str, Any]:
    rd = review_date if review_date is not None else data_asof_session
    ca = (
        created_at
        if created_at is not None else f"{data_asof_session}T12:00:00"
    )
    return {
        "review_date": rd,
        "data_asof_session": data_asof_session,
        "created_at": ca,
        "mfe_mae_precision_level": "daily_approximate",
        "stop_changed": 0,
        "action_taken": "hold",
        "rule_violation_suspected": 0,
        "emotional_state": "[]",
        "management_notes": management_notes,
    }


@pytest.fixture
def app_factory(tmp_path: Path, monkeypatch):
    """Yield a factory that opens a fresh DB + returns (app, db_path)."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    def _factory():
        db_path = tmp_path / "phase8_timeline.db"
        ensure_schema(db_path).close()
        base_cfg = load(Path("swing.config.toml"))
        cfg = dc_replace(
            base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
        )
        return create_app(cfg), db_path

    return _factory


def test_timeline_orders_chronologically_with_tiebreak(app_factory):
    """Spec §7.2: ORDER BY review_date ASC, created_at ASC,
    management_record_id ASC.

    Post-fix expected: two same-day event_log rows with same created_at
    render in management_record_id ASC order in the rendered HTML.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
        rec_a = insert_event_log(
            conn, trade_id=1,
            event_log_fields=_minimal_event_log_fields(
                data_asof_session="2026-05-07",
                created_at="2026-05-07T10:00:00",
                management_notes="FIRST_NOTE_MARKER",
            ),
        )
        rec_b = insert_event_log(
            conn, trade_id=1,
            event_log_fields=_minimal_event_log_fields(
                data_asof_session="2026-05-07",
                created_at="2026-05-07T10:00:00",  # SAME wall-clock
                management_notes="SECOND_NOTE_MARKER",
            ),
        )
        assert rec_b > rec_a
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    pos_a = body.find("FIRST_NOTE_MARKER")
    pos_b = body.find("SECOND_NOTE_MARKER")
    assert pos_a >= 0 and pos_b >= 0
    assert pos_a < pos_b  # ASC order in DOM


def test_timeline_renders_event_log_and_snapshot_rows_distinctly(app_factory):
    """Spec §7.2: snapshot row carries 'snapshot' badge text; event_log row
    carries 'event' badge text.

    Post-fix expected: both substrings appear in the timeline section of
    the trade-detail page.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                data_asof_session="2026-05-07",
            ),
        )
        insert_event_log(
            conn, trade_id=1,
            event_log_fields=_minimal_event_log_fields(
                data_asof_session="2026-05-07",
            ),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    timeline_section = body.split('id="daily-management-timeline"')
    assert len(timeline_section) >= 2, "timeline section missing"
    timeline_html = timeline_section[1].split("</section>")[0].lower()
    assert "snapshot" in timeline_html
    assert "event" in timeline_html


def test_timeline_default_excludes_superseded_rows(app_factory):
    """Spec §7.2: default rendering filters to ``is_superseded = 0``.

    Post-fix expected: the superseded snapshot row's distinguishing marker
    price is NOT visible in the default render; the active-row marker IS.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
        rec_id = insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                data_asof_session="2026-05-06",
                current_price=100.0,  # marker price for stale row
            ),
        )
        conn.execute(
            "UPDATE daily_management_records SET is_superseded = 1 "
            "WHERE management_record_id = ?", (rec_id,),
        )
        conn.commit()
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                data_asof_session="2026-05-07",
                current_price=200.0,  # marker price for fresh row
            ),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    timeline_section = body.split('id="daily-management-timeline"')
    assert len(timeline_section) >= 2, "timeline section missing"
    timeline_html = timeline_section[1].split("</section>")[0]
    assert "200.00" in timeline_html  # fresh active row visible
    assert "100.00" not in timeline_html  # superseded row hidden


def test_timeline_renders_for_closed_trade(app_factory):
    """Spec §7.2: timeline is per-trade, agnostic of state — closed trades
    must still surface their snapshot/event_log history.

    Post-fix expected: GET /trades/{id} returns 200 + timeline section
    populated even when the trade is in 'closed' state.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DEAD", state="closed")
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields=_full_snapshot_fields(
                data_asof_session="2026-05-05",
            ),
        )
    finally:
        conn.commit()
        conn.close()

    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    assert 'id="daily-management-timeline"' in body


# ---------------------------------------------------------------------------
# Codex R1 Major 2: event-log form must be reachable from the trade-detail
# UI for ACTIVE trades; absent for closed trades.
# ---------------------------------------------------------------------------


def test_event_log_form_present_on_detail_page_for_active_trade(app_factory):
    """Codex R1 Major 2 discriminator (active-trade branch).

    Plan §5.0 acceptance criterion: the operator must be able to reach the
    event-log form via the trade-detail UI for active trades. Pre-fix:
    detail.html.j2 included the timeline partial but never rendered the
    event-log form partial; the route handler did not build the form VM.

    Post-fix: form HTML present (id selector + POST action both render).
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, state="managing")
    finally:
        conn.close()
    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    assert 'id="daily-management-event-form-1"' in body, (
        "trade-detail page MUST render the event-log form for active trades; "
        "operator cannot reach the form otherwise (POST endpoint exists "
        "but no UI surface). See Codex R1 Major 2."
    )
    assert 'hx-post="/trades/1/daily-management/event"' in body, (
        "form must POST to the daily-management event route"
    )


def test_event_log_form_absent_on_detail_page_for_closed_trade(app_factory):
    """Codex R1 Major 2 discriminator (closed-trade branch).

    Closed trades MUST NOT surface the event-log form (state-machine
    invariant: only entered/managing/partial_exited can record new events).
    Pre-fix this branch was vacuously satisfied because no form ever
    rendered; post-fix it must be actively gated by trade.state.
    """
    app, db_path = app_factory()
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=2, state="managing")
        # Mark closed AFTER seed so the helper's CHECK-constrained insert
        # path stays valid.
        conn.execute("UPDATE trades SET state='closed' WHERE id=2")
        conn.commit()
    finally:
        conn.close()
    with TestClient(app) as client:
        response = client.get("/trades/2")
    assert response.status_code == 200
    body = response.text
    assert 'id="daily-management-event-form-2"' not in body, (
        "closed trades MUST NOT render the event-log form (state-machine "
        "invariant: only active states can record new events)."
    )
