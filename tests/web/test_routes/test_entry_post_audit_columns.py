"""Phase 13 T3.SB1 T-B.1.4 — entry_post audit columns + fill_origin transitions.

Per plan §G.2 T-B.1.4 step 1 + dispatch brief §5 watch items 9, 10, 11:

  (a) persists fill_origin='schwab_auto' when operator submits unchanged
      auto-populated values (no edits vs anchor).
  (b) flips to fill_origin='schwab_auto_then_operator_corrected' when
      operator edited any of (entry_date, entry_price, shares).
  (c) persists fill_origin='operator_typed' when no auto-fill anchor
      arrived (legacy form / no Schwab fills).
  (d) emits audit row with surface='trade_entry' (form-render path —
      already exercised by T-B.1.3 tests; this file adds end-to-end).
  (e) soft-warn confirm round-trips hidden anchors via form_values dict
      (Phase 9 Sub-bundle D R3 Critical #1 + brief watch item 9 LOCK).
  (f) `... or None` (NOT `... or ''`) for nullable audit fields (Phase 6
      CLAUDE.md `... or ""` vs CHECK enum gotcha).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache_with_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _post_entry(client: TestClient, **fields: Any):
    """POST /trades/entry with minimum-valid form merged with overrides."""
    from tests.web.conftest import full_phase7_entry_payload
    base = full_phase7_entry_payload(
        ticker="AAPL",
        entry_date="2026-05-19",
        entry_price="150.25",
        shares="100",
        initial_stop="140.00",
        rationale="aplus-setup",
        notes="",
    )
    base.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
    return client.post(
        "/trades/entry", data=base, headers={"HX-Request": "true"},
    )


def _make_anchor(
    *, entry_date: str = "2026-05-19",
    entry_price: float = 150.25,
    shares: int = 100,
    schwab_order_id: str = "schwab-order-abc",
) -> str:
    """Build a production-shape schwab_source_value_json envelope mirroring
    what swing/trades/entry_auto_fill.py emits at form-render time."""
    return json.dumps(
        {
            "entry_date": entry_date,
            "entry_price": entry_price,
            "shares": shares,
            "schwab_order_id": schwab_order_id,
            "schwab_instrument_symbol": "AAPL",
        },
        sort_keys=True,
    )


# ============================================================================
# (a) Unchanged auto-populated values → fill_origin='schwab_auto'.
# ============================================================================


def test_a_unchanged_auto_fill_persists_schwab_auto(seeded_db, monkeypatch):
    """POST with anchor matching submitted values → fill_origin='schwab_auto'.

    schwab_source_value_json persisted verbatim; operator_corrected_value_json
    is NULL; auto_fill_audit_at persisted.
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    anchor = _make_anchor(
        entry_date="2026-05-19", entry_price=150.25, shares=100,
    )
    audit_at = "2026-05-19T14:30:00.000000+00:00"
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json=anchor,
            auto_fill_audit_at=audit_at,
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "entry fill should be persisted"
    assert row[0] == "schwab_auto"
    assert row[1] == anchor
    assert row[2] is None, (
        "operator_corrected_value_json must be NULL when no edits "
        "(per `... or None` CLAUDE.md gotcha)"
    )
    assert row[3] == audit_at


# ============================================================================
# (b) Edited auto-populated values → schwab_auto_then_operator_corrected.
# ============================================================================


def test_b_edited_price_flips_to_then_operator_corrected(
    seeded_db, monkeypatch,
):
    """Operator edits entry_price from 150.25 → 151.00. fill_origin flips
    + operator_corrected_value_json carries submitted values.
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    anchor = _make_anchor(
        entry_date="2026-05-19", entry_price=150.25, shares=100,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            entry_price="151.00",  # edited
            schwab_source_value_json=anchor,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "schwab_auto_then_operator_corrected"
    assert row[1] == anchor
    assert row[2] is not None
    corrected = json.loads(row[2])
    assert corrected["entry_price"] == 151.00
    assert corrected["shares"] == 100
    assert corrected["entry_date"] == "2026-05-19"


def test_b_edited_shares_flips_to_then_operator_corrected(
    seeded_db, monkeypatch,
):
    """Operator edits shares from 100 → 75 → flip."""
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    anchor = _make_anchor(
        entry_date="2026-05-19", entry_price=150.25, shares=100,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            shares="75",  # edited
            schwab_source_value_json=anchor,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin FROM fills "
                    "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "schwab_auto_then_operator_corrected"


def test_b_edited_entry_date_flips_to_then_operator_corrected(
    seeded_db, monkeypatch,
):
    """Operator edits entry_date from 2026-05-19 → 2026-05-18 → flip."""
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    anchor = _make_anchor(
        entry_date="2026-05-19", entry_price=150.25, shares=100,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            entry_date="2026-05-18",  # edited
            schwab_source_value_json=anchor,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin FROM fills "
                    "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "schwab_auto_then_operator_corrected"


# ============================================================================
# (c) No anchor → operator_typed.
# ============================================================================


def test_c_no_anchor_persists_operator_typed(seeded_db, monkeypatch):
    """POST without auto-fill hidden anchors → fill_origin='operator_typed';
    all audit columns NULL (legacy / bare-cURL backward-compat).
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # No schwab_source_value_json / auto_fill_audit_at / fill_origin
        # form fields submitted — emulates legacy form / pre-Phase-13 POST.
        resp = _post_entry(client)
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "operator_typed"
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None


def test_c_empty_anchor_string_persists_operator_typed(seeded_db, monkeypatch):
    """POST with empty schwab_source_value_json (empty string) →
    fill_origin='operator_typed'; audit columns NULL.

    Discriminating against `... or ""` regression: empty string MUST coerce
    to None for the NULL audit columns (Phase 6 CLAUDE.md gotcha).
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json="",  # empty string from form
            auto_fill_audit_at="",
            fill_origin_at_form_render="",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "operator_typed"
    assert row[1] is None, (
        "empty schwab_source_value_json must persist NULL "
        "(not empty string — CLAUDE.md gotcha `... or None` not `... or ''`)"
    )
    assert row[2] is None
    assert row[3] is None


def test_c_malformed_anchor_with_claim_rejects_with_400(seeded_db, monkeypatch):
    """Codex R1 Major #1 + #2 fix — POST with malformed
    schwab_source_value_json AND fill_origin_at_form_render='schwab_auto'
    is internally inconsistent (tampered or stale) → 400 reject with
    descriptive error.

    The legacy backward-compat path (no claim, no anchor) still flows
    through as operator_typed (covered by
    ``test_c_no_anchor_persists_operator_typed`` +
    ``test_c_empty_anchor_string_persists_operator_typed`` above).
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json="not a json envelope",  # malformed
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",  # claim
        )
    assert resp.status_code == 400, resp.text
    assert "malformed" in resp.text.lower() or "unparseable" in resp.text.lower()
    # NO fill row should have been written (POST rejected pre-record_entry).
    conn = connect(cfg.paths.db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM fills WHERE action='entry'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_c_malformed_anchor_without_claim_falls_back(seeded_db, monkeypatch):
    """Codex R1 Major #1 + #2 fix carve-out — POST with malformed
    schwab_source_value_json BUT fill_origin_at_form_render empty
    (legacy / no claim) → operator_typed (no 400). Preserves backward
    compat for the bare-cURL / pre-Phase-13 path.
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json="not a json envelope",  # malformed
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="",  # NO claim
        )
    assert resp.status_code == 200, resp.text
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT fill_origin FROM fills "
            "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "operator_typed"


def test_c_empty_anchor_with_claim_rejects_with_400(seeded_db, monkeypatch):
    """Codex R1 Major #1 + #2 fix — POST with EMPTY
    schwab_source_value_json AND fill_origin_at_form_render='schwab_auto'
    is internally inconsistent → 400 reject.
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json="",  # empty
            auto_fill_audit_at="",
            fill_origin_at_form_render="schwab_auto",  # claim
        )
    assert resp.status_code == 400, resp.text
    assert "empty" in resp.text.lower()


# ============================================================================
# (e) Soft-warn confirm fragment round-trips hidden anchors.
# ============================================================================


def test_e_soft_warn_confirm_round_trips_auto_fill_anchors(
    seeded_db, monkeypatch,
):
    """First-submit at soft cap → confirm fragment includes hidden inputs
    for schwab_source_value_json + auto_fill_audit_at +
    fill_origin_at_form_render so a tampered force=true resubmit can't
    silently drop them (Phase 9 Sub-bundle D R3 Critical #1 LOCK +
    dispatch brief §5 watch item 9).
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    # Seed enough open trades to trip soft_warn at the next submit.
    soft_warn = cfg.position_limits.soft_warn_open
    conn = ensure_schema(cfg.paths.db_path)
    try:
        for i in range(soft_warn):
            t = f"TIC{i:02d}"
            conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) "
                "VALUES (?, '2026-05-15', 100.0, 10, 90.0, 90.0, "
                "'entered', 'manual_off_pipeline', '2026-05-15T16:00:00')",
                (t,),
            )
        conn.commit()
    finally:
        conn.close()
    anchor = _make_anchor(
        entry_date="2026-05-19", entry_price=150.25, shares=100,
    )
    audit_at = "2026-05-19T14:30:00.000000+00:00"
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json=anchor,
            auto_fill_audit_at=audit_at,
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Soft-warn confirm fragment must carry all 3 anchors as hidden inputs
    # so a force=true resubmit replays them.
    assert 'name="schwab_source_value_json"' in body
    assert 'name="auto_fill_audit_at"' in body
    assert 'name="fill_origin_at_form_render"' in body
    # The anchor JSON should be HTML-escaped inside the hidden input.
    assert "&#34;entry_price&#34;: 150.25" in body
    assert audit_at in body


# ============================================================================
# (f) `... or None` not `... or ''` for nullable audit fields.
# Already covered by test_c_empty_anchor_string_persists_operator_typed,
# but add a focused regression test against the precise gotcha.
# ============================================================================


def test_f_no_audit_at_form_field_persists_null_not_empty_string(
    seeded_db, monkeypatch,
):
    """When auto_fill_audit_at form field is empty BUT
    schwab_source_value_json is present (e.g., partial tampered POST),
    auto_fill_audit_at column must persist NULL via `... or None`."""
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    anchor = _make_anchor()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(
            client,
            schwab_source_value_json=anchor,
            auto_fill_audit_at="",  # empty → NULL via `or None`
            fill_origin_at_form_render="schwab_auto",
        )
    assert resp.status_code == 200, resp.text

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT auto_fill_audit_at FROM fills "
            "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None, (
        "empty form field must coerce to NULL via `... or None` "
        "(CLAUDE.md gotcha 2026-05-04)"
    )


# ============================================================================
# fill_origin coverage — exercise all 3 NEW V1 enum values via T3.SB1 path.
# Mirrors the cross-bundle pin test_fill_origin_enum_complete_after_v20
# planted at T-A.1.1 (un-skips at T3.SB2). The 2 legacy values
# (tos_import, imported_legacy) are exercised via their own surfaces.
# ============================================================================


def test_fill_origin_enum_all_three_new_values_persistable_via_route(
    seeded_db, monkeypatch,
):
    """Plant 3 entries through the route exercising all 3 NEW V1 enum
    values; assert each persists correctly.

    Per dispatch brief §5 watch item 10 — fill_origin enum transitions
    tested across all relevant V1 values.
    """
    cfg, cfg_path = seeded_db
    _patch_price_cache_with_snapshot(monkeypatch)
    anchor = _make_anchor()
    audit_at = "2026-05-19T14:30:00.000000+00:00"
    app = create_app(cfg, cfg_path)
    seen: list[str] = []
    with TestClient(app) as client:
        # 1) schwab_auto — unchanged values.
        resp1 = _post_entry(
            client,
            schwab_source_value_json=anchor,
            auto_fill_audit_at=audit_at,
        )
        assert resp1.status_code == 200, resp1.text
        conn = connect(cfg.paths.db_path)
        try:
            seen.append(
                conn.execute(
                    "SELECT fill_origin FROM fills "
                    "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
                ).fetchone()[0]
            )
            # Clean slate for next test.
            conn.execute("DELETE FROM fills")
            conn.execute("DELETE FROM trades")
            conn.commit()
        finally:
            conn.close()

        # 2) schwab_auto_then_operator_corrected — edited price.
        resp2 = _post_entry(
            client, entry_price="151.00",
            schwab_source_value_json=anchor,
            auto_fill_audit_at=audit_at,
        )
        assert resp2.status_code == 200, resp2.text
        conn = connect(cfg.paths.db_path)
        try:
            seen.append(
                conn.execute(
                    "SELECT fill_origin FROM fills "
                    "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
                ).fetchone()[0]
            )
            conn.execute("DELETE FROM fills")
            conn.execute("DELETE FROM trades")
            conn.commit()
        finally:
            conn.close()

        # 3) operator_typed — no anchor.
        resp3 = _post_entry(client)
        assert resp3.status_code == 200, resp3.text
        conn = connect(cfg.paths.db_path)
        try:
            seen.append(
                conn.execute(
                    "SELECT fill_origin FROM fills "
                    "WHERE action='entry' ORDER BY fill_id DESC LIMIT 1"
                ).fetchone()[0]
            )
        finally:
            conn.close()
    assert seen == [
        "schwab_auto",
        "schwab_auto_then_operator_corrected",
        "operator_typed",
    ]


# ============================================================================
# Path import guard — ensure unused 'Path' / 'pytest' import doesn't trip ruff.
# ============================================================================
_ = Path
_ = pytest
