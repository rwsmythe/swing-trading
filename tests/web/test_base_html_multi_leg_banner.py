"""Phase 12.5 #1 Task T-1.9 — ``base.html.j2`` multi-leg auto-correction
banner block integration tests.

Per plan §A T-1.9 + spec §8.3 + invariant F12 (ASCII-only):

- A new advisory banner renders when
  ``vm.recent_multi_leg_auto_correction_count > 0`` (count populated by
  T-1.7's ``count_recent_multi_leg_auto_corrections`` helper + T-1.8's
  base-layout VM retrofit).
- ABSENT when the count is 0.
- Plural/singular grammar: ``1 multi-leg auto-correction`` vs
  ``2 multi-leg auto-corrections``.
- ASCII-only per F12 LOCK -- no em-dash, no arrows, no unicode glyphs.
- The CLI command rendered verbatim cites T-1.10's filter
  (``swing journal discrepancy list --resolved-by auto_tier1_multi_leg``).

Sibling: ``test_base_layout_discrepancy_banner.py`` covers the existing
``unresolved_material_discrepancies_count`` banner (Phase 10 T-E.3); both
banners render side-by-side per spec §2.4 + §8.4 (the new banner DOES
NOT supersede the existing one).

The seeding helper plants a completed reconciliation_run + a discrepancy
with ``resolved_by='auto_tier1_multi_leg'`` + a matching
reconciliation_corrections row so the T-1.7 helper's
``COUNT(DISTINCT rd.discrepancy_id)`` returns N. The N parameter lets
each test plant exactly the count it wants to assert against.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _seed_multi_leg_auto_corrections(db_path, *, count: int) -> None:
    """Plant ``count`` distinct multi-leg auto-redirect discrepancies on a
    completed reconciliation_run so the T-1.7 helper's
    ``COUNT(DISTINCT rd.discrepancy_id)`` returns exactly ``count``.

    Schema constraints honored:

    - ``reconciliation_runs`` row in ``state='completed'`` so the helper's
      latest-completed-run SELECT picks it.
    - ``reconciliation_discrepancies.resolution='auto_corrected_from_schwab'``
      + ``resolved_by='auto_tier1_multi_leg'`` -- the resolved_by sentinel
      is the helper's filter; the resolution matches the cross-column
      CHECK from migration 0019 (auto_corrected_from_schwab implies
      ambiguity_kind IS NULL).
    - ``reconciliation_corrections.correction_action='auto_applied'`` +
      ``applied_by='auto'`` per migration 0019 CHECKs.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, "
            "'entered', 'S', 'I', 'manual_off_pipeline', "
            "'2026-04-01T09:30:00', 100)"
        )
        conn.execute(
            "INSERT INTO reconciliation_runs "
            "(run_id, period_start, period_end, started_ts, finished_ts, "
            " state, source, source_artifact_path, source_artifact_sha256) "
            "VALUES (1, '2026-04-01', '2026-04-08', "
            "'2026-04-08T16:00:00.000', '2026-04-08T16:00:01.000', "
            "'completed', 'system_audit', 'gate-test', 'gate-test-sha')"
        )
        for i in range(1, count + 1):
            conn.execute(
                "INSERT INTO reconciliation_discrepancies "
                "(discrepancy_id, run_id, discrepancy_type, trade_id, "
                " fill_id, cash_movement_id, "
                " linked_daily_management_record_id, ticker, field_name, "
                " expected_value_json, actual_value_json, delta_text, "
                " material_to_review, resolution, ambiguity_kind, "
                " resolution_reason, resolved_at, resolved_by, "
                " mistake_tag_assigned, created_at) VALUES "
                "(?, 1, 'entry_price_mismatch', 1, NULL, NULL, NULL, 'AAA', "
                " 'entry_price', '\"10.00\"', '\"10.15\"', NULL, 1, "
                " 'auto_corrected_from_schwab', NULL, "
                " 'multi-leg auto-redirect (test)', "
                " '2026-04-08T16:00:02.000', 'auto_tier1_multi_leg', NULL, "
                " '2026-04-08T16:00:00.000')",
                (i,),
            )
            conn.execute(
                "INSERT INTO reconciliation_corrections "
                "(correction_id, discrepancy_id, correction_action, "
                " correction_choice, affected_table, affected_row_id, "
                " field_name, pre_correction_value_json, "
                " source_canonical_value_json, applied_value_json, "
                " operator_truth_value_json, applied_at, applied_by, "
                " correction_set_id, superseded_by_correction_id, "
                " risk_policy_id_at_correction, schwab_api_call_id, "
                " reconciliation_run_id, correction_reason, notes) VALUES "
                "(?, ?, 'auto_applied', 'split_into_partials', 'fills', ?, "
                " 'price', '\"10.00\"', '\"10.15\"', '\"10.15\"', NULL, "
                " '2026-04-08T16:00:02.000', 'auto', NULL, NULL, NULL, "
                " NULL, 1, 'multi-leg auto-redirect (test)', NULL)",
                (i, i, i),
            )
        conn.commit()
    finally:
        conn.close()


def _extract_banner_substring(html: str) -> str:
    """Return the substring spanning the new multi-leg auto-redirect
    banner ``<div>`` so F12 ASCII-only assertions scope to just the
    block under test (not the surrounding page chrome)."""
    marker = 'class="reconciliation-auto-redirect-banner"'
    idx = html.find(marker)
    assert idx != -1, "banner marker not found in rendered HTML"
    # Walk back to the opening '<div' so the substring starts at the
    # element boundary.
    start = html.rfind("<div", 0, idx)
    assert start != -1, "could not locate banner <div> opening tag"
    end = html.find("</div>", idx)
    assert end != -1, "could not locate banner </div> closing tag"
    return html[start : end + len("</div>")]


# ---------------------------------------------------------------------------
# 1. Banner renders when count > 0
# ---------------------------------------------------------------------------


def test_base_layout_multi_leg_banner_renders_when_count_gt_zero(seeded_db):
    """Count > 0 -> banner block + data-banner-count attribute +
    verbatim T-1.10 CLI command all present in rendered HTML."""
    cfg, cfg_path = seeded_db
    _seed_multi_leg_auto_corrections(cfg.paths.db_path, count=3)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    assert 'class="reconciliation-auto-redirect-banner"' in r.text
    assert 'data-banner-count="3"' in r.text
    # T-1.10 filter cited verbatim (spec §8.6 LOCK + plan §D #9).
    assert (
        "swing journal discrepancy list --resolved-by auto_tier1_multi_leg"
        in r.text
    )


# ---------------------------------------------------------------------------
# 2. Banner absent when count == 0
# ---------------------------------------------------------------------------


def test_base_layout_multi_leg_banner_absent_when_count_zero(seeded_db):
    """Count == 0 -> banner block CLASS absent from rendered HTML."""
    cfg, cfg_path = seeded_db
    # Deliberately do NOT seed any multi-leg auto-corrections.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    assert 'class="reconciliation-auto-redirect-banner"' not in r.text


# ---------------------------------------------------------------------------
# 3. Singular grammar at count == 1
# ---------------------------------------------------------------------------


def test_base_layout_multi_leg_banner_singular_form_when_count_one(seeded_db):
    """Count == 1 -> body uses singular 'auto-correction' (no plural 's')."""
    cfg, cfg_path = seeded_db
    _seed_multi_leg_auto_corrections(cfg.paths.db_path, count=1)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    banner = _extract_banner_substring(r.text)
    assert "1 multi-leg auto-correction in" in banner
    # Discriminate against the plural form leaking on a count-1 render.
    assert "1 multi-leg auto-corrections in" not in banner


# ---------------------------------------------------------------------------
# 4. Plural grammar at count > 1
# ---------------------------------------------------------------------------


def test_base_layout_multi_leg_banner_plural_form_when_count_gt_one(seeded_db):
    """Count == 2 -> body uses plural 'auto-corrections' with trailing s."""
    cfg, cfg_path = seeded_db
    _seed_multi_leg_auto_corrections(cfg.paths.db_path, count=2)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    banner = _extract_banner_substring(r.text)
    assert "2 multi-leg auto-corrections in" in banner


# ---------------------------------------------------------------------------
# 5. F12 ASCII-only LOCK
# ---------------------------------------------------------------------------


def test_base_layout_multi_leg_banner_ascii_only(seeded_db):
    """F12 LOCK: banner substring contains ZERO non-ASCII codepoints.

    Pre-empts the CLAUDE.md cp1252-stdout gotcha family at any future
    server-rendered surface (em-dash / arrows / unicode glyphs would
    silently corrupt under non-UTF-8 transport).
    """
    cfg, cfg_path = seeded_db
    _seed_multi_leg_auto_corrections(cfg.paths.db_path, count=3)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    banner = _extract_banner_substring(r.text)
    non_ascii = [c for c in banner if ord(c) >= 128]
    assert non_ascii == [], (
        f"banner contains {len(non_ascii)} non-ASCII codepoint(s): "
        f"{[hex(ord(c)) for c in non_ascii[:10]]}"
    )
    assert all(ord(c) < 128 for c in banner)
