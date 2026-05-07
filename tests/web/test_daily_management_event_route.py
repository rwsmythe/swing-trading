"""Phase 8 Task 5.0: route-level tests for POST /trades/{id}/daily-management/event.

Plan: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md §5.0.

Three browser-only HTMX failure surfaces enforced (Phase 5 R1 M1 + M2 + Phase
6 R5 I3 lessons):

  (a) Embedded form propagates HX-Request header via
      ``hx-headers='{"HX-Request": "true"}'`` (OriginGuard strict-mode).
  (b) Success-path response = 204 + ``HX-Redirect: /trades/{trade_id}``
      (NOT 303 → swap-target — htmx.js swallows 303 transparently).
  (c) HX-Redirect target route IS registered in app.routes (Phase 6 I3
      operator-witnessed lesson — TestClient verifies the header but
      does NOT follow the redirect).

T3.2 carry-forward: stale-form guard rejects when ``prior_stop`` no longer
matches ``trades.current_stop`` (a stop_adjust raced between render + POST).
The route hands the dataclass-built ``EventLogRequest`` to ``record_event_log``,
which surfaces ``ValidationException`` for both missing required fields and
the stale-form / no-op-stop guards. The route translates ``ValidationException``
to a 422 response (form re-render).
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.web.app import create_app


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "DHC",
    entry_price: float = 100.0,
    initial_stop: float = 90.0,
    initial_shares: int = 50,
    current_avg_cost: float = 100.0,
    current_size: float = 50.0,
    current_stop: float = 92.0,
    pre_trade_locked_at: str = "2026-05-01T09:30:00",
    state: str = "managing",
) -> None:
    """Mirror the Phase 8 service-test seed helper (NOT NULL + CHECK only)."""
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


@pytest.fixture
def app_with_seeded_trade(tmp_path: Path):
    """FastAPI app with one ``managing`` trade (id=1, current_stop=92.0)."""
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    try:
        _seed_trade(
            conn, trade_id=1, ticker="DHC", state="managing",
            entry_price=100.0, initial_stop=90.0, initial_shares=50,
            current_avg_cost=100.0, current_size=50.0, current_stop=92.0,
            pre_trade_locked_at="2026-05-01T09:30:00",
        )
    finally:
        conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg), db_path


def test_event_log_post_success_returns_204_with_HX_Redirect(  # noqa: N802
    app_with_seeded_trade,
):
    """No stop-change path: 204 + HX-Redirect: /trades/1; event_log row exists."""
    app, db_path = app_with_seeded_trade
    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "0",
                "action_taken": "hold",
                "rule_violation_suspected": "0",
                "emotional_state": '["calm"]',
                "created_at": "2026-05-07T18:00:00",
                "review_date": "2026-05-07",
                "data_asof_session": "2026-05-07",
                "mfe_mae_precision_level": "daily_approximate",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/trades/1"

    # Side-effect: event_log row exists for this trade.
    conn = connect(db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'",
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_event_log_post_HX_Redirect_target_route_registered(  # noqa: N802
    app_with_seeded_trade,
):
    """Phase 6 R5 I3 lesson: HX-Redirect target route MUST exist in app.routes.

    The success-path emits ``HX-Redirect: /trades/{trade_id}``; verify a route
    with a path-template matching ``/trades/{...}`` (NOT the daily-management
    sub-route) is registered.
    """
    app, _ = app_with_seeded_trade
    paths = {getattr(r, "path", None) for r in app.routes}
    assert any(
        p
        and p.startswith("/trades/")
        and "{" in p
        and not p.endswith("/daily-management/event")
        and not p.endswith("/exit")
        and not p.endswith("/exit/form")
        and not p.endswith("/stop")
        and not p.endswith("/stop/form")
        and not p.endswith("/cancel")
        and not p.endswith("/review")
        and not p.endswith("/row")
        and not p.endswith("/expand")
        for p in paths
    ), f"no GET /trades/{{trade_id}} target found; routes: {paths}"
    # And specifically: GET /trades/{trade_id} renders 200 (target resolves).
    with TestClient(app) as client:
        r = client.get("/trades/1")
    assert r.status_code == 200


def test_event_log_post_validation_failure_returns_422(app_with_seeded_trade):
    """stop_changed=1 without new_stop / prior_stop / reason → 422."""
    app, _ = app_with_seeded_trade
    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "1",
                # new_stop, prior_stop, stop_change_reason intentionally missing.
                "action_taken": "move_stop",
                "action_reason": "breakout_confirmed",
                "rule_violation_suspected": "0",
                "emotional_state": '["calm"]',
                "created_at": "2026-05-07T18:00:00",
                "review_date": "2026-05-07",
                "data_asof_session": "2026-05-07",
                "mfe_mae_precision_level": "daily_approximate",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 422


def test_event_log_form_partial_includes_HX_Request_header_propagation():  # noqa: N802
    """Phase 5 R1 M1 lesson: embedded HTMX form MUST propagate HX-Request via
    ``hx-headers='{"HX-Request": "true"}'``. Otherwise OriginGuard strict-mode
    rejects nested form submits with 403.

    The form template is the source of truth — verify the literal marker is
    present so the real-browser submit succeeds (TestClient doesn't catch
    this; tests pass the header explicitly).
    """
    template_path = Path(
        "swing/web/templates/partials/daily_management_event_form.html.j2",
    )
    text = template_path.read_text(encoding="utf-8")
    assert "hx-headers" in text
    assert '"HX-Request": "true"' in text


def test_event_log_post_writes_event_log_and_stop_adjust_atomically(
    app_with_seeded_trade,
):
    """stop_changed=1 with all required fields → 204; the §A.1 single-transaction
    contract from T3.2 means: event_log row + linked trade_events row +
    trades.current_stop updated. The route delegates to ``record_event_log``.
    """
    app, db_path = app_with_seeded_trade
    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "1",
                "prior_stop": "92.0",
                "new_stop": "95.0",
                "stop_change_reason": "trail_to_breakout_low",
                "action_taken": "move_stop",
                "action_reason": "breakout_confirmed",
                "rule_violation_suspected": "0",
                "emotional_state": '["calm"]',
                "created_at": "2026-05-07T18:00:00",
                "review_date": "2026-05-07",
                "data_asof_session": "2026-05-07",
                "mfe_mae_precision_level": "daily_approximate",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/trades/1"

    # Side-effects: trades.current_stop bumped + event_log linked to trade_events.
    conn = connect(db_path)
    try:
        new_stop = conn.execute(
            "SELECT current_stop FROM trades WHERE id = 1",
        ).fetchone()[0]
        assert new_stop == 95.0
        link = conn.execute(
            "SELECT linked_trade_event_id FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'",
        ).fetchone()[0]
        assert link is not None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Codex R2 Major #2: route must server-stamp ``created_at`` (not trust client).
# ---------------------------------------------------------------------------
#
# Pre-fix: ``created_at`` was rendered as a hidden form field and read back
# from the form payload on POST. A stale form (page open across sessions)
# or a tampered submission would persist the wrong audit timestamp. Fix:
# the route stamps ``created_at`` at handler entry (naive UTC ISO per
# spec §8.4); the form no longer carries a hidden created_at input.


def test_event_log_post_server_stamps_created_at_ignoring_form_value(
    app_with_seeded_trade,
):
    """Tampered/stale ``created_at`` in the form payload must be IGNORED;
    the persisted row carries the SERVER-stamped time."""
    import datetime as _dt

    app, db_path = app_with_seeded_trade
    tampered = "1999-01-01T00:00:00"  # absurd far-past timestamp
    before = _dt.datetime.now(_dt.UTC).replace(tzinfo=None, microsecond=0)
    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "0",
                "action_taken": "hold",
                "rule_violation_suspected": "0",
                "emotional_state": '["calm"]',
                "created_at": tampered,  # <-- malicious / stale
                "review_date": "2026-05-07",
                "data_asof_session": "2026-05-07",
                "mfe_mae_precision_level": "daily_approximate",
            },
            headers={"HX-Request": "true"},
        )
    after = _dt.datetime.now(_dt.UTC).replace(tzinfo=None, microsecond=0)
    assert response.status_code == 204

    conn = connect(db_path)
    try:
        persisted = conn.execute(
            "SELECT created_at FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'",
        ).fetchone()[0]
    finally:
        conn.close()
    # Persisted value MUST NOT equal the tampered form value.
    assert persisted != tampered, (
        f"route trusted client-supplied created_at: persisted={persisted!r}"
    )
    # And it MUST be within the request window (server-stamped).
    persisted_dt = _dt.datetime.fromisoformat(persisted)
    # Allow either naive or aware (route convention is naive UTC ISO).
    if persisted_dt.tzinfo is not None:
        persisted_dt = persisted_dt.astimezone(_dt.UTC).replace(tzinfo=None)
    assert before <= persisted_dt <= after + _dt.timedelta(seconds=2), (
        f"persisted={persisted_dt!r} outside [{before!r}, {after!r}]"
    )


def test_event_log_form_partial_does_not_render_hidden_created_at():
    """Major #2: the hidden ``created_at`` form input must be removed (the
    route server-stamps; rendering the input invites tampering and stale
    values when the page sits open across sessions)."""
    template_path = Path(
        "swing/web/templates/partials/daily_management_event_form.html.j2",
    )
    text = template_path.read_text(encoding="utf-8")
    assert 'name="created_at"' not in text, (
        "hidden created_at input must be removed; route server-stamps"
    )
