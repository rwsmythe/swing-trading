"""Phase 12.5 #2 T-2.11 — slow E2E happy-path: dashboard banner -> resolve
form -> POST -> 204 + HX-Redirect -> banner clears.

Per plan §A T-2.11 acceptance + §H operator-witnessed gate surface S2/S3/S4
verbatim: a single end-to-end flow exercises every load-bearing component
landed in T-2.1 .. T-2.10 in one bound integration test (slow-marked so the
fast suite stays under runtime budget; `pytest -m slow` runs it).

The test plants a full DB state (trade + entry-fill + reconciliation_run +
material pending-ambiguity discrepancy), then walks the operator path:

  1. GET /dashboard            -> banner renders with data-banner-resolve-link
                                  pointing at the seeded discrepancy.
  2. GET /reconcile/discrepancy/{disc_id}/resolve
                               -> 200 + pre-resolution context + menu + hidden
                                  anchor.
  3. POST same URL             -> 204 + HX-Redirect.
  4. DB query                  -> reconciliation_corrections row with
                                  applied_by='operator' +
                                  correction_action='operator_resolved_ambiguity'.
  5. DB query                  -> reconciliation_discrepancies.resolved_by =
                                  'operator_web' (F2 LOCK).
  6. GET /dashboard            -> banner cleared (count==0 -> banner suppressed).

TestClient lifespan discipline (CLAUDE.md gotcha) — uses ``with TestClient(app)
as client:`` so ``app.state.price_fetch_executor`` and ``app.state.cfg`` are
initialized.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import Config, load
from swing.data.db import ensure_schema
from swing.web.app import create_app

pytestmark = pytest.mark.slow


def _seed_pending_ambiguity(db_path: Path) -> int:
    """Plant a trade + entry-fill + reconciliation_run + material
    pending_ambiguity_resolution discrepancy. Returns the discrepancy_id.

    Mirrors the fixture shape used in
    ``tests/web/test_reconcile_resolve_post_route.py:_seed_discrepancy``
    with ``material_to_review=1`` so it lands in the banner set.
    """
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
                "WEB", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
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
                run_id, discrepancy_type, trade_id, fill_id, ticker,
                field_name, expected_value_json, actual_value_json, delta_text,
                material_to_review, resolution, ambiguity_kind,
                resolution_reason, resolved_at, resolved_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, "entry_price_mismatch", trade_id, fill_id, "WEB",
                "price", '{"price": 10.0}', '{"price": 10.10}', "+$0.10",
                1, "pending_ambiguity_resolution",
                "multi_partial_vs_consolidated",
                None, None, None,
                "2026-05-18T12:00:00",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return discrepancy_id
    finally:
        conn.close()


def _make_cfg(tmp_path: Path) -> tuple[Config, Path]:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def test_phase12_5_bundle_2_web_tier2_happy_path(tmp_path: Path) -> None:
    """End-to-end: banner -> form -> POST -> banner clears."""
    cfg, cfg_path = _make_cfg(tmp_path)
    disc_id = _seed_pending_ambiguity(cfg.paths.db_path)
    expected_resolve_link = f"/reconcile/discrepancy/{disc_id}/resolve"
    app = create_app(cfg, cfg_path)

    with TestClient(app) as client:
        # ---------------------------------------------------------------
        # Step 1: GET / (dashboard) renders the banner with the resolve link.
        # The dashboard is mounted at "/" per swing/web/routes/dashboard.py;
        # the POST handler emits HX-Redirect: /dashboard?reconcile_resolved=...
        # which is a SPA-style query token target (browser navigates to "/"
        # with that query string after the HTMX swap). The dashboard path
        # accepts any query string.
        # ---------------------------------------------------------------
        r1 = client.get("/")
        assert r1.status_code == 200, r1.text[:300]
        assert 'data-banner-resolve-link="true"' in r1.text, (
            "expected banner link present on dashboard"
        )
        assert f'href="{expected_resolve_link}"' in r1.text, (
            f"banner link target should point at the seeded discrepancy "
            f"({expected_resolve_link})"
        )

        # ---------------------------------------------------------------
        # Step 2: GET the resolve form -> 200 + form artifacts.
        # ---------------------------------------------------------------
        r2 = client.get(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            headers={"HX-Request": "true"},
        )
        assert r2.status_code == 200, r2.text[:300]
        # Pre-resolution context block exists.
        body2 = r2.text
        assert 'data-resolve-form="true"' in body2, (
            "expected resolve form root marker"
        )
        # The choice menu rendered (at least one menu option for the
        # ambiguity_kind we seeded - 'keep_journal_as_is' is in
        # multi_partial_vs_consolidated's static menu).
        assert "keep_journal_as_is" in body2, (
            "expected static choice 'keep_journal_as_is' rendered in menu"
        )
        # Hidden anchor name + value.
        assert 'name="ambiguity_kind_at_render"' in body2, (
            "expected hidden anchor input"
        )
        assert "multi_partial_vs_consolidated" in body2, (
            "expected anchor value rendered for the seeded ambiguity kind"
        )

        # ---------------------------------------------------------------
        # Step 3: POST resolution -> 204 + HX-Redirect.
        # ---------------------------------------------------------------
        r3 = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "operator-acked via web E2E test",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
        assert r3.status_code == 204, r3.text[:300]
        hx_redirect = r3.headers.get("HX-Redirect", "")
        assert hx_redirect.startswith(
            "/dashboard?reconcile_resolved="
        ), hx_redirect

    # -------------------------------------------------------------------
    # Step 4: reconciliation_corrections row with applied_by='operator' +
    #         correction_action='operator_resolved_ambiguity'.
    # -------------------------------------------------------------------
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        row = conn.execute(
            "SELECT applied_by, correction_action, correction_reason "
            "FROM reconciliation_corrections "
            "WHERE discrepancy_id = ? "
            "ORDER BY correction_id DESC LIMIT 1",
            (disc_id,),
        ).fetchone()
        assert row is not None, "expected a reconciliation_corrections row"
        applied_by, correction_action, correction_reason = row
        assert applied_by == "operator", applied_by
        assert correction_action == "operator_resolved_ambiguity", (
            correction_action
        )
        assert "operator-acked via web E2E test" in (correction_reason or ""), (
            correction_reason
        )

        # ---------------------------------------------------------------
        # Step 5: reconciliation_discrepancies.resolved_by='operator_web'.
        # ---------------------------------------------------------------
        drow = conn.execute(
            "SELECT resolution, resolved_by "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (disc_id,),
        ).fetchone()
        assert drow is not None
        assert drow[0] == "operator_resolved_ambiguity", drow
        assert drow[1] == "operator_web", drow
    finally:
        conn.close()

    # -------------------------------------------------------------------
    # Step 6: GET /dashboard -> banner cleared (count drops to 0 ->
    #         banner block suppressed entirely).
    # -------------------------------------------------------------------
    app2 = create_app(cfg, cfg_path)
    with TestClient(app2) as client:
        r6 = client.get("/")
        assert r6.status_code == 200, r6.text[:300]
        assert 'data-banner-resolve-link="true"' not in r6.text, (
            "expected banner to be cleared after the resolution; "
            "data-banner-resolve-link should not appear"
        )
        assert 'data-banner="unresolved-material-discrepancies"' not in r6.text, (
            "expected entire banner block suppressed when count=0"
        )
