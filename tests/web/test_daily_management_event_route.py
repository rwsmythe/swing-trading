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
                "emotional_state": ["calm"],
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
                "emotional_state": ["calm"],
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
                "emotional_state": ["calm"],
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
                "emotional_state": ["calm"],
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



# ---------------------------------------------------------------------------
# Codex R3 Major #2: review_date / data_asof_session must default to
# last_completed_session(now) (NOT date.today()). Spec §4.5.
# Weekend / holiday / pre-close submissions otherwise create rows anchored
# to non-session dates, breaking same-session snapshot context. The route
# must server-stamp on POST (do NOT trust hidden form fields — same fix
# pattern as R2 Major #2 for created_at).
# ---------------------------------------------------------------------------


def test_event_log_form_vm_defaults_review_date_to_last_completed_session(
    app_with_seeded_trade,
):
    """VM defaults must use last_completed_session(now) — Saturday
    submission anchors to the prior Friday, NOT Saturday."""
    import datetime as _dt

    import swing.web.view_models.trades as vm_mod

    app, db_path = app_with_seeded_trade
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))

    # Pin "now" to Saturday 2026-05-09 14:00 HST (operator local TZ).
    saturday = _dt.datetime(2026, 5, 9, 14, 0, 0)

    class _FrozenDatetime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return saturday
            return saturday.replace(tzinfo=tz)

    # Patch the `datetime` symbol the VM builder uses (lazy-imported inside
    # the function — patch the module-attribute it imports from).
    import datetime as _real_dt
    monkeypatch_target = vm_mod
    saved = getattr(monkeypatch_target, "datetime", _real_dt.datetime)
    try:
        monkeypatch_target.datetime = _FrozenDatetime  # type: ignore[attr-defined]
        vm = vm_mod.build_event_log_form_vm(trade_id=1, cfg=cfg)
    finally:
        monkeypatch_target.datetime = saved  # type: ignore[attr-defined]

    assert vm is not None
    # Saturday 2026-05-09 → last completed session = Friday 2026-05-08.
    assert vm.review_date == "2026-05-08", (
        f"review_date={vm.review_date!r}; expected last_completed_session "
        "(Friday 2026-05-08), not date.today() (Saturday 2026-05-09)"
    )
    assert vm.data_asof_session == "2026-05-08", (
        f"data_asof_session={vm.data_asof_session!r}; expected last_completed_session "
        "(Friday 2026-05-08), not date.today() (Saturday 2026-05-09)"
    )


def test_event_log_form_partial_does_not_render_hidden_review_date():
    """Major #2: hidden review_date form input must be removed; route
    server-stamps from last_completed_session(now) on POST."""
    template_path = Path(
        "swing/web/templates/partials/daily_management_event_form.html.j2",
    )
    text = template_path.read_text(encoding="utf-8")
    assert 'name="review_date"' not in text, (
        "hidden review_date input must be removed; route server-stamps from "
        "last_completed_session(now)"
    )


def test_event_log_form_partial_does_not_render_hidden_data_asof_session():
    """Major #2: hidden data_asof_session form input must be removed."""
    template_path = Path(
        "swing/web/templates/partials/daily_management_event_form.html.j2",
    )
    text = template_path.read_text(encoding="utf-8")
    assert 'name="data_asof_session"' not in text, (
        "hidden data_asof_session input must be removed; route server-stamps"
    )


def test_event_log_post_server_stamps_review_date_ignoring_form_value(
    app_with_seeded_trade,
):
    """Tampered/stale review_date and data_asof_session form values
    must be IGNORED; the persisted row carries the SERVER-stamped session
    anchor (last_completed_session(now))."""
    import datetime as _dt

    from swing.evaluation.dates import last_completed_session

    app, db_path = app_with_seeded_trade
    tampered_review = "1999-01-01"
    tampered_session = "2099-12-31"

    expected_session = last_completed_session(_dt.datetime.now()).isoformat()

    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "0",
                "action_taken": "hold",
                "rule_violation_suspected": "0",
                "emotional_state": ["calm"],
                "review_date": tampered_review,  # <-- malicious / stale
                "data_asof_session": tampered_session,
                "mfe_mae_precision_level": "daily_approximate",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 204

    conn = connect(db_path)
    try:
        review_date, data_asof_session = conn.execute(
            "SELECT review_date, data_asof_session FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'",
        ).fetchone()
    finally:
        conn.close()

    assert review_date != tampered_review, (
        f"route trusted client-supplied review_date: persisted={review_date!r}"
    )
    assert data_asof_session != tampered_session, (
        f"route trusted client-supplied data_asof_session: persisted={data_asof_session!r}"
    )
    assert review_date == expected_session, (
        f"review_date={review_date!r}, expected last_completed_session={expected_session!r}"
    )
    assert data_asof_session == expected_session, (
        f"data_asof_session={data_asof_session!r}, expected={expected_session!r}"
    )


def test_event_log_form_partial_does_not_render_hidden_mfe_mae_precision_level():
    """Codex R4 Major #2: hidden mfe_mae_precision_level form input must be
    removed. The route server-stamps 'daily_approximate' (V1's only emitter
    tier); accepting the value from the form lets a tampered POST persist
    'intraday_exact' or 'intraday_estimated' precision metadata that doesn't
    match the actual data source — misleading audit metadata."""
    template_path = Path(
        "swing/web/templates/partials/daily_management_event_form.html.j2",
    )
    text = template_path.read_text(encoding="utf-8")
    assert 'name="mfe_mae_precision_level"' not in text, (
        "hidden mfe_mae_precision_level input must be removed; route "
        "server-stamps 'daily_approximate' (Codex R4 Major #2)"
    )


def test_event_log_post_server_stamps_mfe_mae_precision_level_ignoring_form_value(
    app_with_seeded_trade,
):
    """Codex R4 Major #2: tampered ``mfe_mae_precision_level`` form value
    (e.g., ``intraday_exact``) MUST be ignored — the persisted row carries
    the SERVER-stamped value ``daily_approximate`` (V1's only emitter tier
    per spec §10.7)."""
    app, db_path = app_with_seeded_trade
    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "0",
                "action_taken": "hold",
                "rule_violation_suspected": "0",
                "emotional_state": ["calm"],
                # <-- tampered: V1 only emits daily_approximate; client
                # cannot upgrade audit metadata to intraday tiers.
                "mfe_mae_precision_level": "intraday_exact",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 204

    conn = connect(db_path)
    try:
        precision = conn.execute(
            "SELECT mfe_mae_precision_level FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'",
        ).fetchone()[0]
    finally:
        conn.close()

    assert precision == "daily_approximate", (
        f"route trusted client-supplied mfe_mae_precision_level: "
        f"persisted={precision!r}; expected SERVER-stamped 'daily_approximate'"
    )


def test_event_log_post_multi_checkbox_emotional_state_persists_as_json_list(  # noqa: N802
    app_with_seeded_trade,
):
    """code-review I1 fix: emotional_state form input is multi-checkbox.

    Discriminating test: pre-fix route used ``_opt("emotional_state")`` which
    returns a single str (last value wins); post-fix uses
    ``_emotional_state_from_form(form)`` which calls ``form.getlist`` +
    JSON-encodes. Submit two checked values; verify both persist as a JSON
    list in the audit row.
    """
    import json

    app, db_path = app_with_seeded_trade
    with TestClient(app) as client:
        response = client.post(
            "/trades/1/daily-management/event",
            data={
                "stop_changed": "0",
                "action_taken": "hold",
                "rule_violation_suspected": "0",
                # httpx encodes Python lists as multi-value form fields:
                # emotional_state=calm&emotional_state=focused.
                # form.getlist("emotional_state") collects both.
                "emotional_state": ["calm", "confident"],
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 204

    conn = connect(db_path)
    try:
        emotional_state = conn.execute(
            "SELECT emotional_state FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'",
        ).fetchone()[0]
    finally:
        conn.close()

    parsed = json.loads(emotional_state)
    assert parsed == ["calm", "confident"], (
        f"multi-checkbox values did not persist as JSON list: "
        f"persisted={emotional_state!r}; expected JSON list "
        f'["calm", "confident"]'
    )


def test_event_log_form_template_renders_emotional_state_checkboxes():
    """code-review I1 fix: form template uses checkbox loop over canonical
    DAILY_MGMT_EMOTIONAL_STATES (mirrors Phase 7 entry-form pattern).

    Discriminating test: pre-fix template had a single ``<input type="text"
    name="emotional_state">`` with JSON literal default ``[]``; post-fix
    template iterates over ``vm.emotional_state_options`` rendering one
    ``<input type="checkbox" name="emotional_state" value="...">`` per
    canonical state. Verify the template source code asserts the new shape.
    """
    template_path = Path(
        "swing/web/templates/partials/daily_management_event_form.html.j2",
    )
    text = template_path.read_text(encoding="utf-8")
    # Old shape MUST be absent (single text input with [] default).
    assert (
        "<input type=\"text\" name=\"emotional_state\""
        not in text
    ), "form template still has single-text-input emotional_state field"
    # New shape: checkbox loop over options.
    assert "vm.emotional_state_options" in text, (
        "form template missing vm.emotional_state_options iteration"
    )
    assert (
        "type=\"checkbox\" name=\"emotional_state\""
        in text
    ), "form template missing checkbox inputs for emotional_state"


def test_event_log_form_vm_exposes_canonical_emotional_state_options(
    app_with_seeded_trade,
):
    """code-review I1 fix: build_event_log_form_vm populates
    emotional_state_options from DAILY_MGMT_EMOTIONAL_STATES (canonical
    Phase 7 entry vocabulary mirror per swing.trades.daily_management:129).

    Discriminating test: pre-fix VM had no emotional_state_options field;
    template rendered a text input with literal JSON default. Post-fix VM
    field is populated from canonical constant; template iterates it.

    Reuses ``app_with_seeded_trade`` fixture for clean DB lifecycle on
    Windows (tempfile.TemporaryDirectory + WAL-mode SQLite produces ACL
    teardown failures; pytest's tmp_path-via-fixture sidesteps that).
    """
    from swing.trades.daily_management import DAILY_MGMT_EMOTIONAL_STATES
    from swing.web.view_models.trades import build_event_log_form_vm

    _, db_path = app_with_seeded_trade
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    vm = build_event_log_form_vm(trade_id=1, cfg=cfg)

    assert vm is not None, "VM build returned None for active trade"
    assert vm.emotional_state_options == DAILY_MGMT_EMOTIONAL_STATES, (
        f"VM options drift from canonical: vm.emotional_state_options="
        f"{vm.emotional_state_options!r}; canonical="
        f"{DAILY_MGMT_EMOTIONAL_STATES!r}"
    )
    assert vm.emotional_state_set == (), (
        f"VM emotional_state_set should default to empty tuple on initial "
        f"render (no preserved checked-state); got {vm.emotional_state_set!r}"
    )
