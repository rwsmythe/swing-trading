"""Phase 12.5 #2 T-2.11 — XSS-escape + forbidden-sentinel audit on the
``/reconcile/discrepancy/{id}/resolve`` resolve form.

Per plan §A T-2.11 acceptance + L-W5 defense-in-depth + the project's
``ASCII-only banner text`` cp1252 gotcha family: any operator-typed
text rendered back into HTML MUST be Jinja-autoescaped so a
``<script>`` payload typed into ``resolution_reason`` or ``custom_value``
flows through to the page as ``&lt;script&gt;``, NOT as raw HTML.

Plus a forbidden-sentinel non-leak audit: a unique sentinel string is
NEVER injected anywhere in the test; the test renders + submits a
no-op resolution and asserts the sentinel is absent from every
operator-visible surface AND every DB column that could plausibly
carry operator-typed text. Belt-and-suspenders defense in depth.

Tests:
  - test_resolve_form_xss_escape_via_resolution_reason
  - test_resolve_form_no_forbidden_sentinel_emit
  - test_resolve_form_xss_escape_via_custom_value_rerender
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app

_FORBIDDEN_SENTINEL = "COPOWERS-FORBIDDEN-RECONCILE-SENTINEL-XYZ"


def _seed_discrepancy(
    db_path: Path,
    *,
    resolution_reason: str | None = None,
) -> int:
    """Mirror tests/web/test_reconcile_resolve_post_route.py:_seed_discrepancy
    (default pending_ambiguity / multi_partial_vs_consolidated). Accepts an
    optional ``resolution_reason`` plant so the XSS test can put a script
    payload directly in the pre-resolution context surface."""
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
                run_id, "entry_price_mismatch", trade_id, fill_id, "AAA",
                "price", '{"price": 10.0}', '{"price": 10.10}', "+$0.10",
                1, "pending_ambiguity_resolution",
                "multi_partial_vs_consolidated",
                resolution_reason, None, None,
                "2026-05-18T12:00:00",
            ),
        )
        discrepancy_id = int(dcur.lastrowid)
        conn.commit()
        return discrepancy_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# XSS-escape on the GET form-render path via resolution_reason
# ---------------------------------------------------------------------------


def test_resolve_form_xss_escape_via_resolution_reason(
    seeded_db: tuple[Config, Path],
) -> None:
    """Plant a <script> payload in ``disc.resolution_reason`` so it flows
    through the pre-resolution context section of the form; assert it
    renders ESCAPED (not raw)."""
    cfg, cfg_path = seeded_db
    # Unique payload string so a stray inline-script block (the page's own
    # 12-line JS toggle) doesn't false-positive the assertion.
    payload_raw = '<script>alert("XSS-1")</script>'
    payload_escaped = "&lt;script&gt;alert(&#34;XSS-1&#34;)&lt;/script&gt;"
    disc_id = _seed_discrepancy(
        cfg.paths.db_path, resolution_reason=payload_raw,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200, r.text[:300]
    # Literal raw payload MUST NOT appear in the response body.
    assert payload_raw not in r.text, (
        "XSS regression: raw <script>alert(\"XSS-1\")</script> "
        "leaked into the rendered HTML"
    )
    # Literal escaped form (or an equivalent autoescape) MUST appear,
    # confirming the payload was rendered as text, not as live HTML.
    # Jinja's default autoescape uses &#34; for double-quotes; the
    # assertion uses the canonical Jinja-emitted shape.
    assert payload_escaped in r.text, (
        "expected Jinja-escaped <script> payload in rendered HTML; got: "
        f"{r.text[:500]!r}"
    )


# ---------------------------------------------------------------------------
# XSS-escape on the 400 re-render path via custom_value
# ---------------------------------------------------------------------------


def test_resolve_form_xss_escape_via_custom_value_rerender(
    seeded_db: tuple[Config, Path],
) -> None:
    """Submit a <script> payload as ``custom_value`` with malformed JSON so
    the 400 re-render path preserves ``prior_custom_value_raw`` byte-for-
    byte; assert the preserved value is rendered ESCAPED (not raw)."""
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    payload_raw = '<script>alert("XSS-2")</script>'
    payload_escaped = "&lt;script&gt;alert(&#34;XSS-2&#34;)&lt;/script&gt;"
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "consolidate_using_operator_vwap",
                "custom_value": payload_raw,  # malformed JSON triggers 400.
                "resolution_reason": "xss-rerender-test",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
    # The malformed JSON branch fires a 400 re-render with the prior
    # custom_value preserved byte-for-byte into a textarea.
    assert r.status_code == 400, r.text[:300]
    assert payload_raw not in r.text, (
        "XSS regression on 400 re-render: raw <script> leaked into the "
        "rendered HTML via prior_custom_value_raw"
    )
    assert payload_escaped in r.text, (
        "expected Jinja-escaped <script> payload in the re-rendered "
        f"textarea; got: {r.text[:500]!r}"
    )


# ---------------------------------------------------------------------------
# Forbidden-sentinel non-leak audit (defense-in-depth).
# ---------------------------------------------------------------------------


def test_resolve_form_no_forbidden_sentinel_emit(
    seeded_db: tuple[Config, Path],
) -> None:
    """Plant the sentinel NOWHERE. Render the form + submit a no-op
    resolution. Assert the sentinel is absent from every operator-visible
    surface AND every DB column that could carry operator-typed text.

    Belt-and-suspenders defense in depth -- if any current OR future
    refactor accidentally introduces the sentinel into a template default,
    a constant, or a debug emission, this test catches it.
    """
    cfg, cfg_path = seeded_db
    disc_id = _seed_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_get = client.get(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            headers={"HX-Request": "true"},
        )
        assert r_get.status_code == 200, r_get.text[:300]
        # (a) form-render response body has no sentinel.
        assert _FORBIDDEN_SENTINEL not in r_get.text, (
            "forbidden sentinel leaked into form-render response body"
        )

        r_post = client.post(
            f"/reconcile/discrepancy/{disc_id}/resolve",
            data={
                "choice_code": "keep_journal_as_is",
                "resolution_reason": "no-op sentinel audit",
                "ambiguity_kind_at_render": "multi_partial_vs_consolidated",
            },
            headers={"HX-Request": "true"},
        )
        assert r_post.status_code == 204, r_post.text[:300]
        # (b) POST response body has no sentinel. The 204 body should be
        # empty, but check anyway.
        assert _FORBIDDEN_SENTINEL not in r_post.text, (
            "forbidden sentinel leaked into POST response body"
        )

    # DB-side absence checks.
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        # (c) reconciliation_corrections.correction_reason -- newest row.
        crow = conn.execute(
            "SELECT correction_reason FROM reconciliation_corrections "
            "WHERE discrepancy_id = ? "
            "ORDER BY correction_id DESC LIMIT 1",
            (disc_id,),
        ).fetchone()
        assert crow is not None
        correction_reason = crow[0] or ""
        assert _FORBIDDEN_SENTINEL not in correction_reason, (
            "forbidden sentinel leaked into "
            "reconciliation_corrections.correction_reason"
        )

        # (d) reconciliation_discrepancies.resolution_reason +
        # (e) reconciliation_discrepancies.resolved_by.
        drow = conn.execute(
            "SELECT resolution_reason, resolved_by "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (disc_id,),
        ).fetchone()
        assert drow is not None
        resolution_reason, resolved_by = drow
        assert _FORBIDDEN_SENTINEL not in (resolution_reason or ""), (
            "forbidden sentinel leaked into "
            "reconciliation_discrepancies.resolution_reason"
        )
        assert _FORBIDDEN_SENTINEL not in (resolved_by or ""), (
            "forbidden sentinel leaked into "
            "reconciliation_discrepancies.resolved_by"
        )
    finally:
        conn.close()
