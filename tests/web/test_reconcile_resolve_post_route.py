"""Phase 12.5 #2 Task T-2.6 — `POST /reconcile/discrepancy/{id}/resolve`
route handler regression tests.

Covers the 9 dispositions from spec §4.2 + plan §A T-2.6 acceptance + L-W2
LOCK race-fix pin:

  1. Happy path — 204 + HX-Redirect to /dashboard?reconcile_resolved={cid}.
  2. reconciliation_corrections row written with applied_by='operator' +
     correction_action='operator_resolved_ambiguity'.
  3. reconciliation_discrepancies.resolved_by flipped to 'operator_web'
     (F2 LOCK — surface attribution distinguishability from CLI).
  4. 400 + re-render on empty choice_code (with error_band_field_hint).
  5. 409 + anchor_mismatch on hidden-anchor drift (state-changed).
  6. 400 + re-render on pick_schwab_record_<N> out-of-range.
  7. 400 + re-render on malformed custom_value JSON (preserves byte-for-byte).
  8. 400 + re-render when ValidatorRejectedError raised (rejection text).
  9. 409 (NOT 400) when service ValueError fires AND a concurrent writer
     transitioned the discrepancy to terminal state — L-W2 BINDING race fix.

All POST submissions include ``HX-Request: true`` header per F4 LOCK
(OriginGuard strict-mode discipline). Schema constraints mirror
``tests/web/test_reconcile_resolve_get_route.py:_seed_discrepancy``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

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
) -> int:
    """Plant a minimal pending_ambiguity_resolution discrepancy row. Mirrors
    the GET route test fixture but defaults to a Tier-2 state."""
    conn = sqlite3.connect(str(db_path))
    try:
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
# 1. Happy path — 204 + HX-Redirect
# ---------------------------------------------------------------------------


def test_post_happy_path_returns_204_with_hx_redirect_to_dashboard(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "Schwab partial aggregation; accept.",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:300]
    hx_redirect = r.headers.get("HX-Redirect", "")
    assert hx_redirect.startswith("/dashboard?reconcile_resolved="), hx_redirect


# ---------------------------------------------------------------------------
# 2. reconciliation_corrections row shape — applied_by='operator',
#    correction_action='operator_resolved_ambiguity'
# ---------------------------------------------------------------------------


def test_post_writes_reconciliation_corrections_row_with_applied_by_operator(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "operator_web shape pin",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:300]
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        row = conn.execute(
            "SELECT applied_by, correction_action "
            "FROM reconciliation_corrections "
            "WHERE discrepancy_id = ? "
            "ORDER BY correction_id DESC LIMIT 1",
            (disc_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "expected a reconciliation_corrections row"
    applied_by, correction_action = row
    assert applied_by == "operator", applied_by
    assert correction_action == "operator_resolved_ambiguity", correction_action


# ---------------------------------------------------------------------------
# 3. resolved_by='operator_web' (F2 LOCK distinguishability)
# ---------------------------------------------------------------------------


def test_post_flips_discrepancy_resolved_by_to_operator_web(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "F2 surface attribution",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text[:300]
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        row = conn.execute(
            "SELECT resolution, resolved_by "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (disc_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    resolution, resolved_by = row
    assert resolution == "operator_resolved_ambiguity", resolution
    assert resolved_by == "operator_web", resolved_by


# ---------------------------------------------------------------------------
# 4. 400 — empty choice_code
# ---------------------------------------------------------------------------


def test_post_returns_400_on_empty_choice_code(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "",
                "resolution_reason": "test reason",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400, r.text[:300]
    # Re-rendered form with error band citing choice_code field hint.
    assert 'data-error-field="choice_code"' in r.text
    assert 'data-resolve-form="true"' in r.text


# ---------------------------------------------------------------------------
# 5. 409 — hidden-anchor mismatch
# ---------------------------------------------------------------------------


def test_post_returns_409_on_hidden_anchor_mismatch(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    # Real discrepancy ambiguity_kind = multi_partial_vs_consolidated;
    # submit with a stale/tampered anchor value that doesn't match.
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "test reason",
                "ambiguity_kind_at_render": "unsupported",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409, r.text[:300]
    assert 'data-error-kind="anchor_mismatch"' in r.text
    assert "state changed" in r.text.lower()


# ---------------------------------------------------------------------------
# 6. 400 — pick_schwab_record_<N> out of range
# ---------------------------------------------------------------------------


def test_post_returns_400_on_pick_schwab_record_out_of_range(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(
        cfg.paths.db_path,
        ambiguity_kind="multi_match_within_window",
        resolution_reason="Schwab returned 3 orders within the match window",
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        expected_value_json=(
            '{"price": 10.0, "quantity": 100, "fill_datetime": "2026-04-27T14:23:00"}'
        ),
        actual_value_json='{"matched": null}',
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "pick_schwab_record_5",
                "custom_value": '{"price": 10.0, "quantity": 100, "fill_datetime": "2026-04-27T14:23:00"}',
                "resolution_reason": "test pick out-of-range",
                "ambiguity_kind_at_render": "multi_match_within_window",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400, r.text[:300]
    assert "out of range" in r.text.lower()
    assert "pick_schwab_record_1 .. pick_schwab_record_3" in r.text


# ---------------------------------------------------------------------------
# 7. 400 — malformed custom_value JSON; preserve byte-for-byte
# ---------------------------------------------------------------------------


def test_post_returns_400_on_malformed_custom_value_json(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    bad_json = '{invalid'
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "consolidate_using_operator_vwap",
                "custom_value": bad_json,
                "resolution_reason": "test malformed JSON",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400, r.text[:300]
    # Preserves the malformed value byte-for-byte in the re-rendered textarea.
    assert bad_json in r.text


# ---------------------------------------------------------------------------
# 8. 400 — ValidatorRejectedError surfaced in error band
# ---------------------------------------------------------------------------


def test_post_returns_400_when_validator_rejected_error_raised(
    seeded_db: tuple[Config, Path],
) -> None:
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    from swing.trades.reconciliation_auto_correct import ValidatorRejectedError

    def fake_apply(*args, **kwargs):
        raise ValidatorRejectedError("price must be > 0")

    with patch(
        "swing.web.routes.reconcile.apply_tier2_resolution",
        side_effect=fake_apply,
    ):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "keep_journal_as_is",
                    "resolution_reason": "validator rejection test",
                    "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 400, r.text[:500]
    # Dump body slice if assertion fails — Jinja autoescape converts ``>`` to ``&gt;``
    body = r.text
    has_rejection_text = (
        "price must be &gt; 0" in body
        or "price must be > 0" in body
    )
    assert has_rejection_text, (
        f"expected validator rejection text in body; got len={len(body)} "
        f"snippet={body[:1000]!r}"
    )
    assert 'data-resolve-form="true"' in body


# ---------------------------------------------------------------------------
# 9. L-W2 LOCK — ValueError concurrent race returns 409 (NOT 400)
# ---------------------------------------------------------------------------


def test_post_value_error_concurrent_race_returns_409_not_400(
    seeded_db: tuple[Config, Path],
) -> None:
    """L-W2 LOCK: when ``apply_tier2_resolution`` raises ``ValueError`` AND
    a concurrent writer (modeled here via a side-connection commit before
    the patched service raises) flipped the discrepancy to a terminal
    state, the route MUST re-read on a FRESH connection + respond 409 +
    error_kind='already_resolved' (NOT 400 + re-render which would loop
    the operator).

    The mutation uses a SEPARATE sqlite3 connection — the route handler's
    own connection snapshot may not see the side-conn's commit without
    the fresh-connect-after-ValueError pattern.
    """
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    db_path = str(cfg.paths.db_path)

    def mutate_then_raise(*args, **kwargs):
        # SEPARATE connection -- the route's own conn snapshot may not see
        # this without the fresh-connect-after-ValueError pattern. Commit
        # explicitly to publish to other connections.
        side_conn = sqlite3.connect(db_path)
        try:
            side_conn.execute(
                "UPDATE reconciliation_discrepancies "
                "SET resolution = 'operator_resolved_ambiguity', "
                "    resolved_by = 'operator' "
                "WHERE discrepancy_id = ?",
                (disc_id,),
            )
            side_conn.commit()
        finally:
            side_conn.close()
        raise ValueError("discrepancy is no longer pending")

    with patch(
        "swing.web.routes.reconcile.apply_tier2_resolution",
        side_effect=mutate_then_raise,
    ):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "keep_journal_as_is",
                    "resolution_reason": "race fix L-W2",
                    "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 409, (
        f"expected 409 (concurrent-resolve race); got {r.status_code}; "
        f"body={r.text[:300]}"
    )
    assert 'data-error-kind="already_resolved"' in r.text, r.text[:400]


# ---------------------------------------------------------------------------
# 10. Codex R1 Major #2 — sqlite3.OperationalError during pre-flight reads
#     routes to db_unavailable 503 (NOT bubbled 500). Mirrors the GET
#     route test_get_returns_503_on_db_locked_during_get_discrepancy
#     coverage for the POST handler.
# ---------------------------------------------------------------------------


def test_post_returns_503_on_db_locked_during_get_discrepancy(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R1 Major #2: existing OperationalError catch wrapped only the
    ``apply_tier2_resolution`` service call. If a pre-flight read
    (``get_discrepancy`` or any of the count_* helpers) raises
    ``sqlite3.OperationalError("database is locked")``, the POST handler
    MUST render the ``db_unavailable`` 503 error template instead of
    bubbling a 500.
    """
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_get_discrepancy(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    with patch(
        "swing.web.routes.reconcile.get_discrepancy",
        side_effect=fake_get_discrepancy,
    ):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "keep_journal_as_is",
                    "resolution_reason": "OperationalError pre-flight scope",
                    "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 503, r.text[:300]
    assert 'data-error-kind="db_unavailable"' in r.text


# ---------------------------------------------------------------------------
# 11. Codex R2 Major #1 — _render_form_with_error builder OperationalError
#     during re-render path must route to db_unavailable 503 (NOT bubble
#     500). The 400 re-render fires when POST validation fails (e.g., empty
#     choice_code); the builder reads count_unresolved_material + the
#     discrepancy via get_discrepancy + executes Pass A/B reads. If the DB
#     is locked at the moment of re-render, the builder raises
#     sqlite3.OperationalError that the existing pre-flight/service
#     catches miss (their try blocks already exited).
# ---------------------------------------------------------------------------


def test_post_rerender_returns_503_on_db_locked_during_builder(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R2 Major #1: re-render path through ``_render_form_with_error``
    invokes ``build_reconcile_discrepancy_resolve_vm`` which performs
    its own DB reads. If the DB is locked at the moment of re-render
    (after the pre-flight checks succeeded), the builder raises
    ``sqlite3.OperationalError`` outside the existing OperationalError
    catch ladder (which only wraps the pre-flight reads + the
    ``apply_tier2_resolution`` service call).

    The handler MUST catch the OperationalError emitted by the builder
    and render the canonical ``db_unavailable`` 503 template.
    """
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_builder(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    # Trigger the 400 re-render path via empty choice_code. The handler
    # passes the pre-flight checks (existence + state + anchor) then hits
    # the choice_code == '' branch -> _render_form_with_error -> builder
    # -> OperationalError.
    with patch(
        "swing.web.routes.reconcile.build_reconcile_discrepancy_resolve_vm",
        side_effect=fake_builder,
    ):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "",
                    "resolution_reason": "builder OperationalError",
                    "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 503, (
        f"expected 503 (builder OperationalError); got {r.status_code}; "
        f"body={r.text[:300]}"
    )
    assert 'data-error-kind="db_unavailable"' in r.text, r.text[:400]


def test_post_rerender_returns_409_when_builder_raises_value_error(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R2 Major #1 sibling: ``_render_form_with_error`` invokes the
    builder which defensively asserts ``disc.resolution ==
    'pending_ambiguity_resolution'``. If a concurrent writer flipped the
    discrepancy to terminal state between the pre-flight read and the
    re-render, the builder raises ``ValueError``. The handler MUST treat
    that as already_resolved 409 (matching the pre-flight 409 disposition)
    instead of bubbling 500.
    """
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def fake_builder(*args, **kwargs):
        raise ValueError(
            f"discrepancy {disc_id} is no longer in "
            "pending_ambiguity_resolution state"
        )

    with patch(
        "swing.web.routes.reconcile.build_reconcile_discrepancy_resolve_vm",
        side_effect=fake_builder,
    ):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "",
                    "resolution_reason": "builder ValueError race",
                    "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 409, (
        f"expected 409 (builder ValueError -> terminal-state race); got "
        f"{r.status_code}; body={r.text[:300]}"
    )
    assert 'data-error-kind="already_resolved"' in r.text, r.text[:400]


# ---------------------------------------------------------------------------
# 12. Codex R2 Major #2 — sibling-except OperationalError cascade. The
#     R1 LOCK introduced _reread_discrepancy_resolution() inside the
#     except ValueError block; if that fresh-connect read itself raises
#     OperationalError, Python's exception-handling rules do NOT cascade
#     to the sibling except sqlite3.OperationalError clause on the same
#     try block. Wrap the re-read in its own try/except.
# ---------------------------------------------------------------------------


def test_post_value_error_concurrent_race_503_on_db_lock_during_reread(
    seeded_db: tuple[Config, Path],
) -> None:
    """Codex R2 Major #2: the L-W2 race-fix re-read inside ``except
    ValueError`` opens a FRESH ``sqlite3.connect`` to bypass the route's
    own connection snapshot. If that fresh DB itself is locked, the
    re-read raises ``sqlite3.OperationalError`` which does NOT cascade
    through the sibling ``except sqlite3.OperationalError:`` on the same
    try block. The handler MUST wrap the re-read in its own try/except
    and route to db_unavailable 503.

    Discriminator: assert 503 + db_unavailable (NOT 500, NOT 409
    already_resolved, NOT 400 re-render).
    """
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)

    def raise_value_error(*args, **kwargs):
        raise ValueError("service-layer ValueError")

    def fake_reread(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    with patch(
        "swing.web.routes.reconcile.apply_tier2_resolution",
        side_effect=raise_value_error,
    ), patch(
        "swing.web.routes.reconcile._reread_discrepancy_resolution",
        side_effect=fake_reread,
    ):
        with TestClient(app) as client:
            r = client.post(
                f"/reconcile/discrepancy/{disc_id}/resolve",
                data={
                    "choice_code": "keep_journal_as_is",
                    "resolution_reason": "race reread OperationalError cascade",
                    "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
                },
                headers={"HX-Request": "true"},
            )
    assert r.status_code == 503, (
        f"expected 503 (re-read OperationalError); got {r.status_code}; "
        f"body={r.text[:300]}"
    )
    assert 'data-error-kind="db_unavailable"' in r.text, r.text[:400]
