"""Phase 18 Arc 18-H.6.1 Part 2 — web FK-null-safe orphan resolver.

The banner-link (Part 1) can now point the operator at an
``untracked_broker_position`` orphan's ``/reconcile/discrepancy/{id}/resolve``
form. Because the orphan stays ``unresolved`` (Part 3, NOT
``pending_ambiguity_resolution``), the tier-2 form's pending-only gate would
otherwise 409 it. This route's orphan branch instead renders a no-FK-safe
acknowledge form (GET) and clears the orphan via ``resolve_discrepancy`` ->
``acknowledged_immaterial`` (POST). No new schema (C2).

Distinguishing (feedback_regression_test_arithmetic): pre-fix an
``unresolved`` orphan GET -> 409 already_resolved (it is not
``pending_ambiguity_resolution``); the FK-requiring tier-2 POST path would
raise. Post-fix GET -> 200 acknowledge form; POST -> 204 + the orphan reaches
``acknowledged_immaterial``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app


def _seed_orphan(
    db_path: Path,
    *,
    resolution: str = "unresolved",
    ticker: str = "SPCX",
    ambiguity_kind: str | None = None,
) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES (?, ?, ?)",
            ("schwab_api", "2026-06-15T12:00:00", "completed"),
        )
        run_id = int(rcur.lastrowid)
        resolved_at = None
        resolved_by = None
        resolution_reason = None
        # pending_ambiguity_resolution requires ambiguity_kind NOT NULL (the
        # migration-0031 cross-column CHECK) but resolved_at/by stay NULL.
        if resolution == "pending_ambiguity_resolution":
            if ambiguity_kind is None:
                ambiguity_kind = "unsupported"
            resolution_reason = "classifier: no sub-classifier"
        elif resolution != "unresolved":
            resolved_at = "2026-06-15T13:00:00"
            resolved_by = "operator"
        dcur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
                ticker, field_name, expected_value_json, actual_value_json,
                delta_text, material_to_review, resolution, ambiguity_kind,
                resolution_reason, resolved_at, resolved_by, created_at
            ) VALUES (?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?)
            """,
            (
                run_id, "untracked_broker_position", ticker, "broker_position",
                '{"journal_qty": 0}', '{"market_value": 411.9, "qty": 2.0}',
                "SPCX: +2.00 sh @ $+411.90 held at broker, not in journal",
                1, resolution, ambiguity_kind, resolution_reason,
                resolved_at, resolved_by, "2026-06-15T12:00:00",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return discrepancy_id
    finally:
        conn.close()


def _resolution(db_path: Path, discrepancy_id: int) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT resolution FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (discrepancy_id,),
        ).fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET — orphan acknowledge form
# ---------------------------------------------------------------------------


def test_get_orphan_renders_acknowledge_form(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    did = _seed_orphan(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-orphan-acknowledge-form="true"' in r.text
    assert "SPCX" in r.text


def test_get_resolved_orphan_returns_409(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    did = _seed_orphan(
        cfg.paths.db_path, resolution="acknowledged_immaterial",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="already_resolved"' in r.text


# ---------------------------------------------------------------------------
# POST — clear the orphan
# ---------------------------------------------------------------------------


def test_post_orphan_clears_to_acknowledged_immaterial(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    did = _seed_orphan(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "Journaled SPCX IPO shares."},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:400]
    assert r.headers.get("HX-Redirect", "").startswith("/dashboard")
    assert _resolution(cfg.paths.db_path, did) == "acknowledged_immaterial"


def test_post_orphan_without_reason_still_clears(
    seeded_db: tuple[Config, Path],
) -> None:
    """acknowledged_immaterial allows a NULL reason (models validator)."""
    cfg, cfg_path = seeded_db
    did = _seed_orphan(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": ""},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:400]
    assert _resolution(cfg.paths.db_path, did) == "acknowledged_immaterial"


def test_post_orphan_already_resolved_returns_409(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    did = _seed_orphan(
        cfg.paths.db_path, resolution="acknowledged_immaterial",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "x"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="already_resolved"' in r.text


# ---------------------------------------------------------------------------
# Codex R2 Major #1 — the LIVE-ID-68 legacy pending_ambiguity_resolution case
# ---------------------------------------------------------------------------


def test_get_legacy_pending_orphan_renders_acknowledge_form(
    seeded_db: tuple[Config, Path],
) -> None:
    """An orphan 18-H.6 already swept into pending_ambiguity_resolution
    (the live ID-68 case) is still clearable: GET renders the acknowledge
    form (pre-fix: 409 already_resolved)."""
    cfg, cfg_path = seeded_db
    did = _seed_orphan(
        cfg.paths.db_path, resolution="pending_ambiguity_resolution",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-orphan-acknowledge-form="true"' in r.text


def test_post_legacy_pending_orphan_clears_and_nulls_ambiguity_kind(
    seeded_db: tuple[Config, Path],
) -> None:
    """POST clears a legacy pending_ambiguity_resolution orphan to
    acknowledged_immaterial (the resolver NULLs ambiguity_kind so the
    cross-column CHECK permits the transition)."""
    cfg, cfg_path = seeded_db
    did = _seed_orphan(
        cfg.paths.db_path, resolution="pending_ambiguity_resolution",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "Journaled SPCX; clear legacy orphan."},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:400]
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        resolution, ambiguity_kind = conn.execute(
            "SELECT resolution, ambiguity_kind FROM "
            "reconciliation_discrepancies WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
    finally:
        conn.close()
    assert resolution == "acknowledged_immaterial"
    assert ambiguity_kind is None
