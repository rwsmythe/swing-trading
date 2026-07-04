"""Arc 19-F — web resolve surface: FK-orphan (raw-deleted subject) branch.

The dashboard cash-review badge (operator complaint 2026-07-02) is lit by
reconciliation discrepancy 73, a ``cash_movement_mismatch`` /
``pending_ambiguity_resolution`` / ``ambiguity_kind='schwab_returned_no_match'``
row referencing ``cash_movement_id=5`` -- a row RD raw-DELETED in the D19
double-debit correction. Today the tier-2 resolver RAISES reading the gone row
(GET renders a dead-end tier-2 form; POST 400-loops). This arc adds an FK-orphan
branch that recognizes the missing subject and routes it to a terminal
``acknowledged_immaterial`` acknowledge form.

Seeding discipline (18-B.1): the dangling-FK orphan is planted via a RAW
``conn.execute`` INSERT with ``PRAGMA foreign_keys = OFF`` -- DETECTION of
pre-existing bad state, not the write path.

Distinguishing (feedback_regression_test_arithmetic): PRE-fix the disc-73-shape
GET falls to the tier-2 form (no acknowledge-form marker) and the POST 400-loops
(row stays pending); POST-fix the GET renders the acknowledge form and the POST
clears the row to acknowledged_immaterial (badge -> False).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app
from swing.web.routes.reconcile import _FK_ORPHAN_CLEARABLE_RESOLUTIONS
from swing.web.view_models.dashboard import _compute_cash_coherence_badge


def test_fk_orphan_clearable_resolutions_constant() -> None:
    assert _FK_ORPHAN_CLEARABLE_RESOLUTIONS == frozenset(
        {"unresolved", "pending_ambiguity_resolution"}
    )


# ---------------------------------------------------------------------------
# Seeding (production INSERT shape; FK OFF to plant the dangling reference)
# ---------------------------------------------------------------------------


def _seed_cash_movement(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "INSERT INTO cash_movements (date, kind, amount) VALUES (?, ?, ?)",
            ("2026-06-15", "withdraw", 372.48),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _seed_discrepancy(
    db_path: Path,
    *,
    discrepancy_type: str = "cash_movement_mismatch",
    resolution: str = "pending_ambiguity_resolution",
    ambiguity_kind: str | None = "schwab_returned_no_match",
    cash_movement_id: int | None = None,
    fill_id: int | None = None,
    trade_id: int | None = None,
    material: int = 0,
    ticker: str = "CASH",
) -> int:
    """Insert a discrepancy via a raw INSERT with FK enforcement OFF (so a
    dangling ``cash_movement_id`` reference can exist, mirroring the D19
    raw-delete)."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES (?, ?, ?)",
            ("schwab_api", "2026-06-19T12:00:00", "completed"),
        )
        run_id = int(rcur.lastrowid)
        resolved_at = None
        resolved_by = None
        resolution_reason = None
        if resolution == "pending_ambiguity_resolution":
            if ambiguity_kind is None:
                ambiguity_kind = "schwab_returned_no_match"
            resolution_reason = "classifier: schwab_returned_no_match"
        elif resolution != "unresolved":
            resolved_at = "2026-06-19T13:00:00"
            resolved_by = "operator"
            ambiguity_kind = None
            resolution_reason = "operator resolved out of pending"
        dcur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
                ticker, field_name, expected_value_json, actual_value_json,
                delta_text, material_to_review, resolution, ambiguity_kind,
                resolution_reason, resolved_at, resolved_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
                ticker, "net_amount",
                '{"amount": 372.48, "date": "2026-06-15", "kind": "withdraw"}',
                '{"matched": null}',
                f"{ticker}: 372.48 withdraw unmatched",
                material, resolution, ambiguity_kind, resolution_reason,
                resolved_at, resolved_by, "2026-06-19T21:07:27.837",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return discrepancy_id
    finally:
        conn.close()


def _row(db_path: Path, discrepancy_id: int) -> tuple:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT resolution, resolved_by, ambiguity_kind, resolution_reason "
            "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
            (discrepancy_id,),
        ).fetchone()
    finally:
        conn.close()


def _badge(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    try:
        return _compute_cash_coherence_badge(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET — disc-73-shape FK-orphan renders the acknowledge form
# ---------------------------------------------------------------------------


def test_get_fk_orphan_pending_renders_acknowledge_form(
    seeded_db: tuple[Config, Path],
) -> None:
    """POST-fix: 200 acknowledge form naming the missing subject row. PRE-fix:
    the row falls to the tier-2 form (no acknowledge-form marker)."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=987654)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-simple-acknowledge-form="true"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text
    assert "cash_movements row (id=987654)" in r.text
    assert "no longer in pending_ambiguity_resolution" not in r.text
    # NOT the tier-2 choice-menu form.
    assert 'name="choice_code"' not in r.text


def test_get_fk_orphan_terminal_returns_409(
    seeded_db: tuple[Config, Path],
) -> None:
    """An already-resolved FK-orphan (row still missing) -> 409, no form."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path,
        resolution="acknowledged_immaterial",
        cash_movement_id=987654,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="already_resolved"' in r.text
    assert 'data-simple-acknowledge-form="true"' not in r.text


# ---------------------------------------------------------------------------
# NO-REGRESSION — a LIVE FK row still reaches the tier-2 form unchanged
# ---------------------------------------------------------------------------


def test_get_orphan_predicate_db_busy_returns_503(
    seeded_db: tuple[Config, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1M2: a transient lock during the FK-orphan SELECT shares the canonical
    503 ladder (not a bare 500). Monkeypatch the predicate to raise a transient
    OperationalError; assert 503. PRE-fix (call outside the pre-flight try):
    the OperationalError bubbles to a 500."""
    cfg, cfg_path = seeded_db
    cm_id = _seed_cash_movement(cfg.paths.db_path)
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=cm_id)
    app = create_app(cfg, cfg_path)

    import swing.web.routes.reconcile as recon_route

    def _busy(_conn, _disc):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(recon_route, "orphaned_affected_target", _busy)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 503, r.text[:400]
    assert 'data-error-kind="db_unavailable"' in r.text


def test_get_live_cash_fk_still_tier2_form(
    seeded_db: tuple[Config, Path],
) -> None:
    """A pending cash_movement_mismatch whose cash_movement_id EXISTS is NOT an
    orphan -> reaches the tier-2 resolve form exactly as today."""
    cfg, cfg_path = seeded_db
    cm_id = _seed_cash_movement(cfg.paths.db_path)
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=cm_id)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-simple-acknowledge-form="true"' not in r.text


# ---------------------------------------------------------------------------
# POST — the round-trip clear (the disc-73 live-heal shape) + badge clears
# ---------------------------------------------------------------------------


def test_post_fk_orphan_htmx_clears_204_and_badge(
    seeded_db: tuple[Config, Path],
) -> None:
    """HTMX arm: 204 + HX-Redirect; row -> acknowledged_immaterial with the
    orphan-marked reason naming the missing subject + ambiguity_kind cleared;
    the cash-review badge (whose ONLY trigger was this row) -> False. PRE-fix:
    the tier-2 resolver 400-loops on the gone row (badge stays lit)."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=5)
    assert _badge(cfg.paths.db_path) is True
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "subject row deleted in D19"},
            headers={"HX-Request": "true"},
        )
        target = r.headers.get("HX-Redirect", "")
        dash = client.get("/dashboard")
    assert r.status_code == 204, r.text[:400]
    assert target == f"/dashboard?reconcile_resolved=disc-{did}"
    assert dash.status_code == 200
    resolution, resolved_by, ambiguity_kind, reason = _row(cfg.paths.db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert resolved_by == "operator_web"
    assert ambiguity_kind is None
    assert reason.startswith("orphan-resolved (subject row gone): cash_movements id=5")
    assert reason.endswith("subject row deleted in D19")
    assert _badge(cfg.paths.db_path) is False


def test_post_fk_orphan_empty_reason_still_marks_orphan(
    seeded_db: tuple[Config, Path],
) -> None:
    """An empty operator reason still persists the non-empty orphan marker
    (F1 audit discipline)."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=5)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": ""},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:400]
    _, _, _, reason = _row(cfg.paths.db_path, did)
    assert reason.startswith("orphan-resolved (subject row gone): cash_movements id=5")


# ---------------------------------------------------------------------------
# IDEMPOTENCY — a SECOND POST/GET on the terminal orphan -> 409, no re-mutation
# ---------------------------------------------------------------------------


def test_post_fk_orphan_second_post_409(
    seeded_db: tuple[Config, Path],
) -> None:
    """The terminal orphan (row still missing -> predicate still returns the
    target) is NOT clearable -> 409, no re-mutation."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=5)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "first"},
            headers={"HX-Request": "true"},
        )
        assert first.status_code == 204
        _, _, _, first_reason = _row(cfg.paths.db_path, did)
        second = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "second"},
            headers={"HX-Request": "true"},
        )
        get_terminal = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert second.status_code == 409, second.text[:400]
    assert 'data-error-kind="already_resolved"' in second.text
    assert get_terminal.status_code == 409
    # No re-mutation: the reason is still the FIRST resolve's marker.
    _, _, _, reason_after = _row(cfg.paths.db_path, did)
    assert reason_after == first_reason
    assert reason_after.endswith("first")


# ---------------------------------------------------------------------------
# NO-REGRESSION — a LIVE tier-2 row POST is byte-identical (routes to tier-2)
# ---------------------------------------------------------------------------


def test_post_live_cash_fk_not_hijacked_by_orphan_branch(
    seeded_db: tuple[Config, Path],
) -> None:
    """A pending cash_movement_mismatch whose cash_movement_id EXISTS is NOT an
    orphan: the POST does NOT route to the FK-orphan resolver (it reaches the
    tier-2 anchor path). The FK-orphan branch would have set resolved_by
    ``operator_web`` + an orphan marker; assert it did NOT (the tier-2 path
    rejects on the missing anchor with a non-orphan error)."""
    cfg, cfg_path = seeded_db
    cm_id = _seed_cash_movement(cfg.paths.db_path)
    did = _seed_discrepancy(cfg.paths.db_path, cash_movement_id=cm_id)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "x"},
            headers={"HX-Request": "true"},
        )
    # The tier-2 path is exercised (anchor-mismatch 400/409 without an orphan
    # marker); the row is NOT cleared by the FK-orphan resolver.
    resolution, resolved_by, _, reason = _row(cfg.paths.db_path, did)
    assert resolution == "pending_ambiguity_resolution"
    assert resolved_by is None
    assert reason is None or "orphan-resolved" not in reason
