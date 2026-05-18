"""Phase 12.5 #2 Task T-2.5 — `GET /reconcile/discrepancy/{id}/resolve`
route handler regression tests.

Covers the 3 dispositions from spec §4.1 flow + 4 invariant-pin tests:

  - 200 + form body for a discrepancy in ``pending_ambiguity_resolution``
    state (happy path).
  - 404 + ``error_kind=not_found`` for an unknown discrepancy_id.
  - 409 + ``error_kind=already_resolved`` for a terminal-state discrepancy.
  - 409 + ``error_kind=already_resolved`` for a NULL-ambiguity_kind defensive
    branch (uses ``PRAGMA ignore_check_constraints`` to bypass the migration
    0019 cross-column CHECK; mirrors T-2.3 fixture precedent).
  - F13 DB connection closure on the 404 early-return path
    (patches sqlite3.connect to return a Mock; asserts ``.close()`` called).
  - F14 ``apply_overrides`` discipline at route entry (patches the import
    site + asserts called with ``request.app.state.cfg``).
  - Route table registration (Phase 6 I3 defense-in-depth).

Schema constraints honored mirror
``tests/web/test_reconcile_resolve_vm_builder.py:_seed_discrepancy``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app


def _seed_discrepancy(
    db_path: Path,
    *,
    resolution: str = "pending_ambiguity_resolution",
    ambiguity_kind: str | None = "multi_partial_vs_consolidated",
    resolution_reason: str | None = None,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    expected_value_json: str | None = '{"price": 10.0}',
    actual_value_json: str | None = '{"price": 10.10}',
    resolved_at: str | None = None,
    resolved_by: str | None = None,
    bypass_check: bool = False,
) -> int:
    """Plant a minimal discrepancy row + its supporting rows directly in
    the test cfg's DB path. Mirrors ``test_reconcile_resolve_vm_builder._seed_discrepancy``.

    ``bypass_check=True`` enables ``PRAGMA ignore_check_constraints=1`` so
    a defensive ``ambiguity_kind IS NULL`` row can be seeded under
    ``resolution='pending_ambiguity_resolution'`` (migration 0019's cross-
    column CHECK would otherwise reject; test asserts the route's
    defense-in-depth branch).
    """
    conn = sqlite3.connect(str(db_path))
    try:
        if bypass_check:
            conn.execute("PRAGMA ignore_check_constraints = 1")
        cur = conn.execute(
            """
            INSERT INTO trades (
                ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, state, trade_origin, pre_trade_locked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "AAA", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
                "manual_off_pipeline", "2026-04-27T16:00:00",
            ),
        )
        trade_id = int(cur.lastrowid)
        fcur = conn.execute(
            """
            INSERT INTO fills (trade_id, fill_datetime, action, quantity, price)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 10.0),
        )
        fill_id = int(fcur.lastrowid)
        rcur = conn.execute(
            """
            INSERT INTO reconciliation_runs (source, started_ts, state)
            VALUES (?, ?, ?)
            """,
            ("schwab_api", "2026-05-18T12:00:00", "running"),
        )
        run_id = int(rcur.lastrowid)
        dcur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
                expected_value_json, actual_value_json, delta_text,
                material_to_review, resolution, ambiguity_kind,
                resolution_reason, resolved_at, resolved_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, discrepancy_type, trade_id, fill_id, "AAA", field_name,
                expected_value_json, actual_value_json, "+$0.10", 1,
                resolution, ambiguity_kind, resolution_reason,
                resolved_at, resolved_by,
                "2026-05-18T12:00:00",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return discrepancy_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. Happy path — 200 + form body
# ---------------------------------------------------------------------------


def test_get_returns_200_for_pending_ambiguity_discrepancy(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{discrepancy_id}/resolve")
    assert r.status_code == 200, r.text[:300]
    # Template renders the form with the data-resolve-form="true" marker.
    assert 'data-resolve-form="true"' in r.text


# ---------------------------------------------------------------------------
# 2. 404 — unknown discrepancy id
# ---------------------------------------------------------------------------


def test_get_returns_404_for_unknown_discrepancy_id(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/reconcile/discrepancy/99999/resolve")
    assert r.status_code == 404, r.text[:300]
    # Error template renders with the not_found discriminator.
    assert 'data-error-kind="not_found"' in r.text
    assert "not_found" in r.text


# ---------------------------------------------------------------------------
# 3. 409 — terminal-state discrepancy
# ---------------------------------------------------------------------------


def test_get_returns_409_for_terminal_resolution(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    # Cross-column CHECK in migration 0019 keeps ambiguity_kind NOT NULL
    # for both ``pending_ambiguity_resolution`` AND
    # ``operator_resolved_ambiguity`` (both states track the ambiguity
    # type). Route's 409 condition is OR-shaped — non-pending resolution
    # alone trips it regardless of ambiguity_kind.
    discrepancy_id = _seed_discrepancy(
        cfg.paths.db_path,
        resolution="operator_resolved_ambiguity",
        ambiguity_kind="multi_partial_vs_consolidated",
        resolved_at="2026-05-18T13:00:00",
        resolved_by="operator",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{discrepancy_id}/resolve")
    assert r.status_code == 409, r.text[:300]
    assert 'data-error-kind="already_resolved"' in r.text
    # Body cites the terminal resolution value.
    assert "operator_resolved_ambiguity" in r.text


# ---------------------------------------------------------------------------
# 4. 409 — NULL ambiguity_kind defensive branch
# ---------------------------------------------------------------------------


def test_get_returns_409_for_null_ambiguity_kind(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(
        cfg.paths.db_path,
        resolution="pending_ambiguity_resolution",
        ambiguity_kind=None,
        bypass_check=True,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/reconcile/discrepancy/{discrepancy_id}/resolve")
    assert r.status_code == 409, r.text[:300]
    assert 'data-error-kind="already_resolved"' in r.text


# ---------------------------------------------------------------------------
# 5. F13 — DB connection closure on 404 early-return path
# ---------------------------------------------------------------------------


def test_get_closes_db_connection_on_404_path(
    seeded_db: tuple[Config, Path],
) -> None:
    """Patch ``sqlite3.connect`` at the reconcile route module's import site
    so the test can capture the connection wrapper + assert ``.close()`` was
    called on the 404 early-return path (F13 LOCK)."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    real_connect = sqlite3.connect
    seen_conns: list[MagicMock] = []

    def fake_connect(*args, **kwargs):
        real_conn = real_connect(*args, **kwargs)
        spy = MagicMock(wraps=real_conn)
        # Required so the route's ``count_*`` helpers (which call execute)
        # still work through the spy.
        spy.close = MagicMock(side_effect=real_conn.close)
        seen_conns.append(spy)
        return spy

    with patch("swing.web.routes.reconcile.sqlite3.connect", fake_connect):
        with TestClient(app) as client:
            r = client.get("/reconcile/discrepancy/99999/resolve")
    assert r.status_code == 404, r.text[:300]
    # At least one connection was opened by the route handler, AND every
    # connection it opened had .close() called (try/finally guarantee).
    assert len(seen_conns) >= 1
    for spy in seen_conns:
        spy.close.assert_called()


# ---------------------------------------------------------------------------
# 6. F14 — apply_overrides discipline at route entry
# ---------------------------------------------------------------------------


def test_get_calls_apply_overrides(
    seeded_db: tuple[Config, Path],
) -> None:
    """Patch ``swing.web.routes.reconcile.apply_overrides`` and assert it
    was called with ``request.app.state.cfg`` (the raw, pre-override cfg).
    F14 LOCK — Phase 12 Sub-bundle B Codex R1 Critical #1 inheritance."""
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    from swing.web.routes import reconcile as reconcile_module

    real_apply = reconcile_module.apply_overrides
    spy_apply = MagicMock(side_effect=real_apply)
    with patch.object(reconcile_module, "apply_overrides", spy_apply):
        with TestClient(app) as client:
            r = client.get(
                f"/reconcile/discrepancy/{discrepancy_id}/resolve",
            )
    assert r.status_code == 200, r.text[:300]
    spy_apply.assert_called()
    # First positional arg is app.state.cfg (the post-startup, potentially
    # divergence-corrected immutable Config).
    called_cfg = spy_apply.call_args.args[0]
    assert called_cfg is app.state.cfg


# ---------------------------------------------------------------------------
# 8. Codex R1 Major #2 — sqlite3.OperationalError during pre-flight reads
#    routes to db_unavailable 503 (NOT bubbled 500).
# ---------------------------------------------------------------------------


def test_get_returns_503_on_db_locked_during_get_discrepancy(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R1 Major #2: existing OperationalError catch wrapped only the
    service-call block. If a pre-flight read (``get_discrepancy`` or any of
    the count_* helpers) raises ``sqlite3.OperationalError("database is
    locked")``, the route MUST render the ``db_unavailable`` 503 error
    template instead of bubbling a 500.
    """
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_get_discrepancy(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    with patch(
        "swing.web.routes.reconcile.get_discrepancy",
        side_effect=fake_get_discrepancy,
    ):
        with TestClient(app) as client:
            r = client.get(
                f"/reconcile/discrepancy/{discrepancy_id}/resolve",
            )
    assert r.status_code == 503, r.text[:300]
    assert 'data-error-kind="db_unavailable"' in r.text


# ---------------------------------------------------------------------------
# 9. Codex R3 Major #1 — sqlite3.connect() itself raises OperationalError
#    BEFORE the existing pre-flight try/except wrapping is entered.
#    Routes to db_unavailable 503 (NOT bubbled 500).
# ---------------------------------------------------------------------------


def test_get_returns_503_on_db_locked_during_connect(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R3 Major #1: ``sqlite3.connect(cfg.paths.db_path)`` itself
    can raise ``sqlite3.OperationalError`` (e.g. "unable to open database
    file") BEFORE the existing inner try/except wraps the count_* helpers
    and ``get_discrepancy``. The route MUST catch this and render the
    canonical ``db_unavailable`` 503 template instead of bubbling 500.
    """
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_connect(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    with patch(
        "swing.web.routes.reconcile.sqlite3.connect",
        side_effect=fake_connect,
    ):
        with TestClient(app) as client:
            r = client.get(
                f"/reconcile/discrepancy/{discrepancy_id}/resolve",
            )
    assert r.status_code == 503, r.text[:300]
    assert 'data-error-kind="db_unavailable"' in r.text


# ---------------------------------------------------------------------------
# 10. Codex R4 Major #1 — builder ValueError classification at the GET
#     handler. The pre-flight check uses get_discrepancy(), but the builder
#     performs its OWN second get_discrepancy() call. Between the pre-flight
#     and the builder call a concurrent writer may DELETE the row OR flip
#     resolution to terminal-state OR (defensively) NULL ambiguity_kind. The
#     builder raises ValueError with one of 3 distinct messages; classify and
#     route to 404 / 409 / 500 respectively (mirrors the R3 Minor #1 fix in
#     _render_form_with_error so GET + POST re-render share the same dispatch).
# ---------------------------------------------------------------------------


def test_get_returns_404_when_builder_raises_value_error_for_not_found(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R4 Major #1 — pre-flight succeeds (pending discrepancy seeded);
    builder raises ``ValueError('discrepancy not found')`` because a
    concurrent writer DELETE-d the row between the route's first
    ``get_discrepancy()`` and the builder's internal second
    ``get_discrepancy()``. Route MUST render 404 + ``not_found`` template
    (not bubble 500).
    """
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_builder(*args, **kwargs):
        raise ValueError("discrepancy not found")

    with patch(
        "swing.web.routes.reconcile.build_reconcile_discrepancy_resolve_vm",
        side_effect=fake_builder,
    ):
        with TestClient(app) as client:
            r = client.get(
                f"/reconcile/discrepancy/{discrepancy_id}/resolve",
            )
    assert r.status_code == 404, r.text[:300]
    assert 'data-error-kind="not_found"' in r.text


def test_get_returns_409_when_builder_raises_value_error_for_terminal_state(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R4 Major #1 — pre-flight succeeds (pending discrepancy seeded);
    builder raises ``ValueError('discrepancy is not pending_ambiguity_resolution;
    got resolution=operator_resolved_ambiguity')`` because a concurrent writer
    flipped the row to terminal state. Route MUST render 409 +
    ``already_resolved`` template (not bubble 500).
    """
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_builder(*args, **kwargs):
        raise ValueError(
            "discrepancy is not pending_ambiguity_resolution; "
            "got resolution=operator_resolved_ambiguity"
        )

    with patch(
        "swing.web.routes.reconcile.build_reconcile_discrepancy_resolve_vm",
        side_effect=fake_builder,
    ):
        with TestClient(app) as client:
            r = client.get(
                f"/reconcile/discrepancy/{discrepancy_id}/resolve",
            )
    assert r.status_code == 409, r.text[:300]
    assert 'data-error-kind="already_resolved"' in r.text


def test_get_returns_500_when_builder_raises_value_error_for_invariant_violation(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R4 Major #1 — pre-flight succeeds; builder raises
    ``ValueError('discrepancy has no ambiguity_kind; cannot render Tier-2
    resolve form')`` (schema-CHECK normally forbids; defense-in-depth for
    any other unforeseen ValueError text from the builder). Route MUST
    render 500 + ``service_error`` template with redacted message (the
    exc text is logged but not surfaced to the operator).
    """
    cfg, cfg_path = seeded_db
    discrepancy_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_builder(*args, **kwargs):
        raise ValueError(
            "discrepancy has no ambiguity_kind; cannot render Tier-2 "
            "resolve form"
        )

    with patch(
        "swing.web.routes.reconcile.build_reconcile_discrepancy_resolve_vm",
        side_effect=fake_builder,
    ):
        with TestClient(app) as client:
            r = client.get(
                f"/reconcile/discrepancy/{discrepancy_id}/resolve",
            )
    assert r.status_code == 500, r.text[:300]
    assert 'data-error-kind="service_error"' in r.text


# ---------------------------------------------------------------------------
# 7. Route registration — defense-in-depth per Phase 6 I3 lesson
# ---------------------------------------------------------------------------


def test_get_route_registered_on_app_routes(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    target = "/reconcile/discrepancy/{discrepancy_id}/resolve"
    matching = [
        r for r in app.routes
        if getattr(r, "path", None) == target
        and "GET" in getattr(r, "methods", ())
    ]
    assert matching, (
        f"expected GET {target!r} registered on app.routes; "
        f"got routes={[getattr(r, 'path', None) for r in app.routes]}"
    )
