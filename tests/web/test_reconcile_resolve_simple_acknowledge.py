"""Phase 18 — web simple-acknowledge coverage for plain-unresolved discrepancies.

The web resolve window handled only two shapes (orphan +
``pending_ambiguity_resolution`` tier-2). A plain-``unresolved`` advisory
discrepancy of an allowlisted type (``cash_movement_mismatch`` /
``equity_delta``) fell through to the tier-2 state guard and got a 409 with the
MISLEADING "no longer in pending_ambiguity_resolution state" copy. This arc adds
a simple-acknowledge branch for the allowlisted types (clearing via
``resolve_discrepancy`` -> ``acknowledged_immaterial``, the exact orphan POST
path) and an HONEST ``not_web_acknowledgeable`` error_kind for the
non-allowlisted unresolved case.

Distinguishing (feedback_regression_test_arithmetic): pre-fix an ``unresolved``
``cash_movement_mismatch`` GET -> 409 misleading already_resolved page; post-fix
-> 200 simple acknowledge form. The allowlist is an EXPLICIT enumerated constant
(NOT MATERIAL_BY_TYPE-derived), pinned by the DISCR test (a material=0 type NOT
in the allowlist -- ``sector_tamper``/``snapshot_mismatch`` -- does NOT get the
form).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app
from swing.web.routes.reconcile import (
    _SIMPLE_ACKNOWLEDGEABLE_TYPES,
    _is_simple_acknowledgeable_discrepancy,
)


class _Disc:
    """A minimal duck-typed discrepancy stand-in for the pure predicate unit."""

    def __init__(self, discrepancy_type: str, trade_id: int | None = None) -> None:
        self.discrepancy_type = discrepancy_type
        self.trade_id = trade_id


# ---------------------------------------------------------------------------
# Task 1 — the allowlist constant + the pure predicate
# ---------------------------------------------------------------------------


def test_allowlist_is_exactly_the_two_v1_types() -> None:
    """The allowlist is the explicit enumerated V1 set -- NOT material=0
    derived. ``sector_tamper`` / ``snapshot_mismatch`` are material=0 but
    NOT in the allowlist."""
    assert _SIMPLE_ACKNOWLEDGEABLE_TYPES == frozenset(
        {"cash_movement_mismatch", "equity_delta"}
    )


def test_predicate_true_for_allowlisted_types() -> None:
    assert _is_simple_acknowledgeable_discrepancy(_Disc("cash_movement_mismatch"))
    assert _is_simple_acknowledgeable_discrepancy(_Disc("equity_delta"))


def test_predicate_false_for_non_allowlisted_types() -> None:
    # orphan type is handled by its OWN branch, not the simple branch
    assert not _is_simple_acknowledgeable_discrepancy(
        _Disc("untracked_broker_position")
    )
    # material=1 mismatch type
    assert not _is_simple_acknowledgeable_discrepancy(_Disc("stop_mismatch"))


def test_predicate_discr_material0_non_allowlisted_excluded() -> None:
    """DISCR — the enumerated-not-derived discriminator. A material=0 type
    NOT in the allowlist (``sector_tamper`` / ``snapshot_mismatch``) is
    excluded; a MATERIAL_BY_TYPE-derived set would wrongly include them."""
    assert not _is_simple_acknowledgeable_discrepancy(_Disc("sector_tamper"))
    assert not _is_simple_acknowledgeable_discrepancy(_Disc("snapshot_mismatch"))


# ---------------------------------------------------------------------------
# Seeding helpers (production INSERT path)
# ---------------------------------------------------------------------------


def _seed_discrepancy(
    db_path: Path,
    *,
    discrepancy_type: str,
    resolution: str = "unresolved",
    ambiguity_kind: str | None = None,
    material: int = 0,
    ticker: str = "QQQ",
    trade_id: int | None = None,
) -> int:
    """Insert a discrepancy via the raw table INSERT (production shape).

    ``ambiguity_kind`` NULL for the unresolved advisory rows; a
    ``pending_ambiguity_resolution`` row requires ambiguity_kind NOT NULL (the
    migration-0031 cross-column CHECK).
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES (?, ?, ?)",
            ("schwab_api", "2026-06-18T12:00:00", "completed"),
        )
        run_id = int(rcur.lastrowid)
        resolved_at = None
        resolved_by = None
        resolution_reason = None
        if resolution == "pending_ambiguity_resolution":
            if ambiguity_kind is None:
                ambiguity_kind = "unsupported"
            resolution_reason = "classifier: no sub-classifier"
        elif resolution not in ("unresolved",):
            resolved_at = "2026-06-18T13:00:00"
            resolved_by = "operator"
            # The models validator requires a non-empty reason for terminal
            # resolutions (e.g. journal_corrected).
            resolution_reason = "operator resolved out of pending"
        dcur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
                ticker, field_name, expected_value_json, actual_value_json,
                delta_text, material_to_review, resolution, ambiguity_kind,
                resolution_reason, resolved_at, resolved_by, created_at
            ) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?)
            """,
            (
                run_id, discrepancy_type, trade_id, ticker, "equity",
                '{"expected": 100.0}', '{"actual": 200.0}',
                f"{ticker}: advisory drift",
                material, resolution, ambiguity_kind, resolution_reason,
                resolved_at, resolved_by, "2026-06-18T12:00:00",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return discrepancy_id
    finally:
        conn.close()


def _resolution_row(db_path: Path, discrepancy_id: int) -> tuple:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT resolution, resolved_by, ambiguity_kind FROM "
            "reconciliation_discrepancies WHERE discrepancy_id = ?",
            (discrepancy_id,),
        ).fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET-FORM — allowlisted types render the simple acknowledge form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "discrepancy_type", ["cash_movement_mismatch", "equity_delta"]
)
def test_get_allowlisted_unresolved_renders_simple_form(
    seeded_db: tuple[Config, Path], discrepancy_type: str,
) -> None:
    """POST-fix: 200 simple acknowledge form. PRE-fix: the row falls through
    to the tier-2 guard -> 409 misleading already_resolved (no form marker;
    "no longer in pending_ambiguity_resolution" PRESENT)."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, discrepancy_type=discrepancy_type)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-simple-acknowledge-form="true"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text
    assert f'action="/reconcile/discrepancy/{did}/resolve"' in r.text
    assert "no longer in pending_ambiguity_resolution" not in r.text


# ---------------------------------------------------------------------------
# POST-CLEAR — POST clears to acknowledged_immaterial; 204+HX-Redirect & 303
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "discrepancy_type", ["cash_movement_mismatch", "equity_delta"]
)
def test_post_allowlisted_htmx_clears_204_hx_redirect(
    seeded_db: tuple[Config, Path], discrepancy_type: str,
) -> None:
    """HTMX arm: 204 + HX-Redirect; row -> acknowledged_immaterial,
    resolved_by operator_web. PRE-fix: tier-2 guard -> 409, row stays
    unresolved."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, discrepancy_type=discrepancy_type)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "Recurring monthly deposit."},
            headers={"HX-Request": "true"},
        )
        # HX-Redirect target must exist.
        target = r.headers.get("HX-Redirect", "")
        dash = client.get("/dashboard")
    assert r.status_code == 204, r.text[:400]
    assert target == f"/dashboard?reconcile_resolved=disc-{did}"
    assert dash.status_code == 200
    resolution, resolved_by, _ = _resolution_row(cfg.paths.db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert resolved_by == "operator_web"


def test_post_allowlisted_non_htmx_303_fallback(
    seeded_db: tuple[Config, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-HTMX arm: 303 redirect; same target; row cleared.

    The production OriginGuard is hardwired strict (``app.py`` ``strict=True``)
    so a non-HTMX POST is 403'd by the middleware BEFORE the route -- the same
    reason the orphan/tier-2 POST tests are all HTMX-only. To exercise the
    route's 303 fallback branch (byte-mirrored from the orphan path for the
    documented OriginGuard non-strict deployment), force the guard non-strict
    for this app and send a same-origin (no HX-Request) POST.
    """
    import swing.web.app as app_mod
    from swing.web.middleware.origin_guard import OriginGuardMiddleware

    orig_init = OriginGuardMiddleware.__init__

    def _non_strict_init(self, app, *, bound_host, bound_port, strict=False):
        orig_init(
            self, app, bound_host=bound_host, bound_port=bound_port,
            strict=False,
        )

    monkeypatch.setattr(
        app_mod.OriginGuardMiddleware, "__init__", _non_strict_init
    )
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path, discrepancy_type="cash_movement_mismatch"
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app, base_url="http://127.0.0.1:8080") as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": ""},
            headers={"Origin": "http://127.0.0.1:8080"},
            follow_redirects=False,
        )
    assert r.status_code == 303, r.text[:400]
    assert r.headers.get("location") == f"/dashboard?reconcile_resolved=disc-{did}"
    resolution, _, _ = _resolution_row(cfg.paths.db_path, did)
    assert resolution == "acknowledged_immaterial"


# ---------------------------------------------------------------------------
# COPY-FIX — non-allowlisted, non-tier-2 unresolved -> honest copy
# ---------------------------------------------------------------------------


def test_get_non_allowlisted_unresolved_honest_copy(
    seeded_db: tuple[Config, Path],
) -> None:
    """A material=1 ``stop_mismatch`` left unresolved gets the HONEST
    ``not_web_acknowledgeable`` copy, NOT the misleading
    "no longer in pending_ambiguity_resolution" copy."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path, discrepancy_type="stop_mismatch", material=1,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="not_web_acknowledgeable"' in r.text
    assert "not web-acknowledgeable" in r.text
    assert "no longer in pending_ambiguity_resolution" not in r.text


def test_post_non_allowlisted_unresolved_honest_copy(
    seeded_db: tuple[Config, Path],
) -> None:
    """POST routes the non-allowlisted unresolved case to the same honest
    error_kind."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path, discrepancy_type="stop_mismatch", material=1,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "x"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="not_web_acknowledgeable"' in r.text
    assert "no longer in pending_ambiguity_resolution" not in r.text


def test_terminal_tier2_still_already_resolved_copy(
    seeded_db: tuple[Config, Path],
) -> None:
    """Regression arm: a genuinely-terminal tier-2 row (resolved out of
    pending) still routes to ``already_resolved`` with the unchanged copy --
    the honest copy is scoped to the unresolved-non-allowlisted case, not a
    blanket replacement."""
    cfg, cfg_path = seeded_db
    # A tier-2 ambiguity type resolved out of pending (terminal). The
    # cross-column CHECK requires ambiguity_kind NULL once resolution leaves
    # the pending set, so resolved_by is set + ambiguity_kind NULL.
    did = _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_type="unmatched_open_fill",
        resolution="journal_corrected",
        material=1,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="already_resolved"' in r.text
    assert "no longer in pending_ambiguity_resolution" in r.text


# ---------------------------------------------------------------------------
# DISCR (route level) — material=0 non-allowlisted does NOT get the form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "discrepancy_type", ["sector_tamper", "snapshot_mismatch"]
)
def test_get_material0_non_allowlisted_no_form(
    seeded_db: tuple[Config, Path], discrepancy_type: str,
) -> None:
    """DISCR — ``sector_tamper`` / ``snapshot_mismatch`` are material=0 but
    NOT in the allowlist: no simple form; the honest error copy instead. A
    MATERIAL_BY_TYPE-derived set would WRONGLY render the form."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(cfg.paths.db_path, discrepancy_type=discrepancy_type)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="not_web_acknowledgeable"' in r.text
    assert 'data-simple-acknowledge-form="true"' not in r.text


# ---------------------------------------------------------------------------
# TOCTOU — the race ladder preserved
# ---------------------------------------------------------------------------


def test_post_toctou_concurrent_resolve_returns_409(
    seeded_db: tuple[Config, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The simple-acknowledge POST passes require_current_resolution; a
    concurrent resolve makes the anchored resolve raise
    DiscrepancyResolutionStateError -> 409 race disposition; the row reflects
    the FIRST winner, not operator_web. PRE-fix (omitting the anchor): the
    second resolve overwrites + returns 204 -> the 'first winner' assertion
    fails."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path, discrepancy_type="cash_movement_mismatch"
    )
    app = create_app(cfg, cfg_path)

    from swing.trades.reconciliation import (
        DiscrepancyResolutionStateError,
        resolve_discrepancy as real_resolve,
    )

    def racing_resolve(conn, **kwargs):
        # Simulate a concurrent winner: resolve the row out-of-band FIRST
        # (different resolved_by), then call the real resolver with the stale
        # require_current_resolution anchor -> it raises.
        side = sqlite3.connect(str(cfg.paths.db_path))
        try:
            side.execute("BEGIN IMMEDIATE")
            side.execute(
                "UPDATE reconciliation_discrepancies SET resolution = ?, "
                "resolved_by = ?, resolved_at = ? WHERE discrepancy_id = ? "
                "AND resolution = 'unresolved'",
                ("acknowledged_immaterial", "concurrent_winner",
                 "2026-06-18T13:30:00", did),
            )
            side.commit()
        finally:
            side.close()
        return real_resolve(conn, **kwargs)

    # The route imports resolve_discrepancy from swing.trades.reconciliation
    # at call time INSIDE the branch, so patch the symbol THERE.
    import swing.trades.reconciliation as recon_mod
    monkeypatch.setattr(recon_mod, "resolve_discrepancy", racing_resolve)

    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "race"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409, r.text[:400]
    assert 'data-error-kind="already_resolved"' in r.text
    resolution, resolved_by, _ = _resolution_row(cfg.paths.db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert resolved_by == "concurrent_winner"
    assert DiscrepancyResolutionStateError is not None  # imported for clarity


# ---------------------------------------------------------------------------
# ORPHAN-REG — the orphan path is byte-unchanged
# ---------------------------------------------------------------------------


def test_orphan_path_unchanged_get(
    seeded_db: tuple[Config, Path],
) -> None:
    """The orphan path still wins its own branch + renders the orphan form
    (NOT the new sibling). Disjoint type set -> provably unaffected."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_type="untracked_broker_position",
        material=1,
        ticker="SPCX",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-orphan-acknowledge-form="true"' in r.text
    assert 'data-simple-acknowledge-form="true"' not in r.text


def test_orphan_path_unchanged_post(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_type="untracked_broker_position",
        material=1,
        ticker="SPCX",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{did}/resolve",
            data={"resolution_reason": "Journaled SPCX."},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:400]
    resolution, _, _ = _resolution_row(cfg.paths.db_path, did)
    assert resolution == "acknowledged_immaterial"


# ---------------------------------------------------------------------------
# TIER2-REG — the tier-2 ambiguity path is byte-unchanged + branch-ordering
# ---------------------------------------------------------------------------


def test_tier2_pending_ambiguity_unchanged(
    seeded_db: tuple[Config, Path],
) -> None:
    """A pending_ambiguity_resolution row with a non-null ambiguity_kind
    renders the tier-2 resolve form, not the simple form."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_type="unmatched_open_fill",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="multi_match_within_window",
        material=1,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-simple-acknowledge-form="true"' not in r.text
    assert 'data-orphan-acknowledge-form="true"' not in r.text


def test_tier2_branch_ordering_allowlisted_type_pending_not_hijacked(
    seeded_db: tuple[Config, Path],
) -> None:
    """BRANCH-ORDERING LOCK: a pending-ambiguity row of an ALLOWLISTED type
    (ambiguity_kind set) is NOT hijacked into the simple-acknowledge form --
    it stays the tier-2 form because the simple branch gates on ambiguity_kind
    IS NULL too."""
    cfg, cfg_path = seeded_db
    did = _seed_discrepancy(
        cfg.paths.db_path,
        discrepancy_type="cash_movement_mismatch",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="multi_match_within_window",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{did}/resolve")
    assert r.status_code == 200, r.text[:400]
    assert 'data-simple-acknowledge-form="true"' not in r.text
