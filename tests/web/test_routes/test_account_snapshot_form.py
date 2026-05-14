"""Phase 10 Sub-bundle E Task T-E.5 — account snapshot form route tests.

Per electives amendment §2 Task E.5 acceptance + CLAUDE.md HTMX-form-
driven gotcha family:
- (a) GET renders form with display-only snapshot_date.
- (b) POST with valid equity_dollars server-stamps snapshot_date +
  returns 204 + HX-Redirect.
- (c) POST with caller-supplied snapshot_date is IGNORED (server-stamp
  wins; tampering surface closed).
- (d) POST with malformed equity_dollars returns 400 + form re-renders.
- (e) HX-Redirect target route resolves (Phase 6 I3 lesson — route-table
  assertion).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from swing.evaluation.dates import last_completed_session
from swing.web.app import create_app


def _count_snapshots(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM account_equity_snapshots"
        ).fetchone()[0]
    finally:
        conn.close()
    return int(n)


def _fetch_snapshot(db_path) -> tuple[str, float, str, str | None]:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT snapshot_date, equity_dollars, source, notes "
            "FROM account_equity_snapshots ORDER BY snapshot_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return tuple(row)


# ---------------------------------------------------------------------------
# GET — form-render
# ---------------------------------------------------------------------------

def test_get_account_snapshot_form_renders_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/account/snapshot")
    assert r.status_code == 200
    assert "Record account snapshot" in r.text


def test_get_form_server_stamps_snapshot_date_display(seeded_db):
    """The display-only span carries ``last_completed_session(now)`` per
    Phase 8 server-stamping discipline + lesson #24."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    expected = last_completed_session(datetime.now()).isoformat()
    with TestClient(app) as client:
        r = client.get("/account/snapshot")
    assert r.status_code == 200
    assert f'data-field="snapshot_date_display">{expected}</span>' in r.text


def test_get_form_includes_hx_headers_propagation(seeded_db):
    """HTMX failure-surface defense — Phase 5 R1 M1 lesson. Real browser
    submissions need the explicit hx-headers attribute on the form so
    OriginGuard strict-mode accepts the POST.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/account/snapshot")
    assert r.status_code == 200
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text


def test_get_form_has_no_hidden_input_for_snapshot_date(seeded_db):
    """Phase 8 server-stamping discipline: snapshot_date MUST be display-
    only ``<span>``, NOT a hidden input (no tampering surface).
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/account/snapshot")
    assert r.status_code == 200
    assert 'name="snapshot_date"' not in r.text
    assert 'type="hidden"' not in r.text


# ---------------------------------------------------------------------------
# POST — happy path
# ---------------------------------------------------------------------------

def test_post_returns_204_with_hx_redirect_on_htmx(seeded_db):
    """Phase 5 R1 M2 lesson — HX-Request submit returns 204+HX-Redirect
    (NOT 303 swap-target).
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/account/snapshot",
            data={"equity_dollars": "2500.00"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/metrics/capital-friction"


def test_post_persists_snapshot_with_source_manual(seeded_db):
    """End-to-end persistence: POST writes one row with source='manual'."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    assert _count_snapshots(cfg.paths.db_path) == 0
    with TestClient(app) as client:
        r = client.post(
            "/account/snapshot",
            data={"equity_dollars": "1234.56", "note": "gate-test"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    assert _count_snapshots(cfg.paths.db_path) == 1
    snapshot_date, equity, source, notes = _fetch_snapshot(cfg.paths.db_path)
    expected_date = last_completed_session(datetime.now()).isoformat()
    assert snapshot_date == expected_date
    assert equity == 1234.56
    assert source == "manual"
    assert notes == "gate-test"


def test_post_without_htmx_header_is_rejected_by_origin_guard(seeded_db):
    """Defense-in-depth: OriginGuard strict-mode rejects POSTs without an
    HX-Request header (or an explicit Origin header). The form-render
    template wires ``hx-headers='{"HX-Request": "true"}'`` so HTMX submits
    pass through; raw curl/scripted POSTs without the header are blocked
    by middleware before reaching the route handler. The 303 fallback
    branch in the route is by-construction unreachable under strict mode
    + dead-code defense for future loosening; this test pins the
    OriginGuard contract.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app, follow_redirects=False) as client:
        r = client.post(
            "/account/snapshot",
            data={"equity_dollars": "500.0"},
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tampering — server-stamp wins
# ---------------------------------------------------------------------------

def test_caller_supplied_snapshot_date_in_post_body_is_ignored(seeded_db):
    """Lesson #24 + Phase 8 R2/R3/R4 — tampered POST body for
    ``snapshot_date`` is IGNORED; server-stamp wins.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    expected = last_completed_session(datetime.now()).isoformat()
    with TestClient(app) as client:
        r = client.post(
            "/account/snapshot",
            data={
                "equity_dollars": "9999.99",
                # Tampered: try to force a far-back date that would
                # bypass current-state semantics. Must be ignored.
                "snapshot_date": "2020-01-01",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    persisted_date, _, _, _ = _fetch_snapshot(cfg.paths.db_path)
    assert persisted_date == expected
    assert persisted_date != "2020-01-01"


# ---------------------------------------------------------------------------
# POST — malformed input
# ---------------------------------------------------------------------------

def test_post_with_malformed_equity_returns_400_and_rerenders(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/account/snapshot",
            data={"equity_dollars": "not-a-number"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "equity_dollars must be a finite number" in r.text
    # Form re-rendered (operator can resubmit without re-typing).
    assert 'value="not-a-number"' in r.text


def test_post_with_negative_equity_returns_400_via_dataclass_validator(seeded_db):
    """Phase 9 ``AccountEquitySnapshot.__post_init__`` rejects negative
    ``equity_dollars`` via ValueError; the route surfaces a 400."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/account/snapshot",
            data={"equity_dollars": "-100.0"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# HX-Redirect target route registered (Phase 6 I3 lesson)
# ---------------------------------------------------------------------------

def test_hx_redirect_target_route_is_registered(seeded_db):
    """Phase 6 I3 lesson: HX-Redirect target route must exist in the app's
    route table. Sub-bundle D shipped /metrics/capital-friction; verify
    pre-emptively against route drift.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/metrics/capital-friction" in paths
    assert "/account/snapshot" in paths
