"""Phase 13 T3.SB1 T-B.1.3 — entry_form auto-fill integration tests.

Per plan §G.2 T-B.1.3 step 1 + dispatch brief §5 watch items 7, 8, 14, 15:

  (a) auto-fill populated when Schwab returns BUY fill — template renders
      auto-populated values in input fields + hidden anchor + display-only
      audit metadata.
  (b) advisory banner when no match.
  (c) sandbox short-circuits — advisory banner; NO hidden anchor.
  (d) hidden audit anchors present (schwab_source_value_json +
      auto_fill_audit_at) — exact-fragment assertion.
  (e) VM has banner-pin fields with correct defaults.
  (f) VM populates banner-pin fields from discrepancies-helper at
      build_entry_form_vm time (forward-binding lesson #12).
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from swing.data.db import ensure_schema
from swing.trades.entry_auto_fill import EntryAutoFillResult
from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _patch_price_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _patch_auto_fill(
    monkeypatch: pytest.MonkeyPatch,
    result: EntryAutoFillResult,
) -> list:
    """Patch swing.trades.entry_auto_fill.resolve_entry_auto_fill to return
    ``result`` and record call kwargs.
    """
    calls: list = []

    def fake_resolve(
        *,
        ticker: str,
        cfg: Any,
        conn: Any,
        now: Any = None,
        lookback_days: int = 7,
    ) -> EntryAutoFillResult:
        calls.append({
            "ticker": ticker,
            "cfg": cfg,
            "conn": conn,
            "now": now,
            "lookback_days": lookback_days,
        })
        return result

    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.resolve_entry_auto_fill",
        fake_resolve,
    )
    return calls


def _seed_watchlist_row(cfg, ticker: str = "AAPL") -> None:
    """Seed a single watchlist row so the entry form renders for the ticker."""
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, last_qualified_date, "
            "status, qualification_count, not_qualified_streak, "
            "last_data_asof_date, entry_target, last_close) "
            f"VALUES ('{ticker}', '2026-04-01','2026-05-15','watch',1,0,"
            "'2026-05-15',105.0,100.0)"
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# (a) Populated auto-fill — values flow into form inputs + hidden anchor.
# ============================================================================


def test_a_populated_auto_fill_renders_values_and_hidden_anchor(
    seeded_db, monkeypatch,
):
    """Schwab returns matching BUY fill → form inputs pre-populated with
    execution-grain values + hidden anchor + display-only audit metadata."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    auto_fill = EntryAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        entry_date="2026-05-19",
        entry_price=150.25,
        shares=100,
        advisory_text=None,
        schwab_source_value_json='{"entry_date": "2026-05-19", '
        '"entry_price": 150.25, "shares": 100, '
        '"schwab_order_id": "order-abc"}',
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Hidden anchor (transport from GET to POST). Jinja2 autoescape
    # converts double-quotes inside the JSON value to `&#34;`; assert
    # the escaped substring to match what the operator's browser actually
    # receives.
    assert 'name="schwab_source_value_json"' in body
    assert '&#34;entry_price&#34;: 150.25' in body
    assert 'name="auto_fill_audit_at"' in body
    assert '2026-05-19T14:30:00.000000+00:00' in body
    assert 'name="fill_origin_at_form_render"' in body
    assert 'value="schwab_auto"' in body

    # Auto-populated entry_price flows through to the input value.
    assert 'value="150.25"' in body

    # Display-only audit metadata visible.
    assert "Auto-fill source:" in body
    assert "schwab_auto" in body

    # NO advisory banner on populated kind.
    assert "Schwab auto-fill: " not in body or "auto-fill:</strong>" not in body


# ============================================================================
# (b) Empty Schwab response → advisory banner; NO hidden anchor.
# ============================================================================


def test_b_empty_auto_fill_renders_advisory_banner(seeded_db, monkeypatch):
    """Schwab returns no orders → 'No matching Schwab BUY fills' advisory.

    Hidden anchor MUST NOT be emitted on non-populated kinds (operator
    enters values manually; nothing to anchor against at POST).
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    auto_fill = EntryAutoFillResult(
        kind="empty",
        fill_origin="operator_typed",
        advisory_text=(
            "No matching Schwab BUY fills for AAPL in last 7 days; "
            "please enter manually."
        ),
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Advisory banner present.
    assert "Schwab auto-fill:" in body
    assert "No matching Schwab BUY fills for AAPL" in body

    # NO hidden anchor.
    assert 'name="schwab_source_value_json"' not in body


# ============================================================================
# (c) Sandbox short-circuit — advisory banner; NO hidden anchor.
# ============================================================================


def test_c_sandbox_short_circuit_renders_advisory(seeded_db, monkeypatch):
    """sandbox kind → advisory banner; NO Schwab call fired."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    auto_fill = EntryAutoFillResult(
        kind="sandbox_short_circuit",
        fill_origin="operator_typed",
        advisory_text=(
            "Schwab integration in sandbox mode; auto-fill disabled."
        ),
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    assert "Schwab auto-fill:" in body
    assert "sandbox mode" in body
    # No hidden anchor under sandbox.
    assert 'name="schwab_source_value_json"' not in body


# ============================================================================
# (c2) DEGRADED short-circuit also renders advisory.
# ============================================================================


def test_c_degraded_short_circuit_renders_advisory(seeded_db, monkeypatch):
    """degraded kind → advisory banner."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    auto_fill = EntryAutoFillResult(
        kind="degraded",
        fill_origin="operator_typed",
        advisory_text=(
            "Schwab integration degraded: refresh_token expired. "
            "Auto-fill unavailable."
        ),
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    assert "Schwab auto-fill:" in body
    assert "degraded" in body.lower()


# ============================================================================
# (d) Hidden audit anchors (schwab_source_value_json + auto_fill_audit_at).
# ============================================================================


def test_d_hidden_audit_anchors_present_on_populated(seeded_db, monkeypatch):
    """Discriminating: hidden inputs for schwab_source_value_json +
    auto_fill_audit_at + fill_origin_at_form_render are present on
    populated kind.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    auto_fill = EntryAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        entry_date="2026-05-19",
        entry_price=200.0,
        shares=50,
        schwab_source_value_json='{"entry_price": 200.0, "shares": 50}',
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    body = resp.text

    assert 'type="hidden" name="schwab_source_value_json"' in body
    assert 'type="hidden" name="auto_fill_audit_at"' in body
    assert 'type="hidden" name="fill_origin_at_form_render"' in body


# ============================================================================
# (e) TradeEntryFormVM has banner-pin fields with correct defaults.
# ============================================================================


def test_e_vm_has_banner_pin_field_defaults():
    """TradeEntryFormVM exposes banner-pin fields with safe defaults
    (forward-binding lesson #12: any future full-page render path that
    extends base.html.j2 reads these without UndefinedError).
    """
    from swing.web.view_models.trades import TradeEntryFormVM
    vm = TradeEntryFormVM(
        ticker="AAPL",
        entry_date="2026-05-19",
        entry_price=100.0,
        initial_stop=95.0,
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        suggested_shares=10,
        risk_dollars=50.0,
        risk_pct=0.5,
        soft_warn_threshold=5,
        hard_cap=10,
        open_count=0,
    )
    # Banner-pin fields default to safe values.
    assert vm.unresolved_material_discrepancies_count == 0
    assert vm.recent_multi_leg_auto_correction_count == 0
    assert vm.banner_resolve_link is None
    # Auto-fill fields default to operator_typed / None.
    assert vm.auto_fill_kind == "operator_typed"
    assert vm.auto_fill_fill_origin == "operator_typed"
    assert vm.auto_fill_entry_date is None
    assert vm.auto_fill_entry_price is None
    assert vm.auto_fill_shares is None
    assert vm.auto_fill_advisory_text is None
    assert vm.auto_fill_schwab_source_value_json is None
    assert vm.auto_fill_audit_at is None


# ============================================================================
# (f) Banner-pin field POPULATION at build_entry_form_vm time.
# ============================================================================


def test_f_vm_populates_banner_pin_fields_from_helpers(seeded_db, monkeypatch):
    """build_entry_form_vm calls count_unresolved_material +
    count_recent_multi_leg_auto_corrections +
    fetch_first_pending_ambiguity_resolve_link_path and populates the VM
    accordingly.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    _patch_auto_fill(
        monkeypatch,
        EntryAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="x",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
        ),
    )

    # Patch helper functions to return discriminating sentinels.
    # The build_entry_form_vm imports the helpers inline; patch on the
    # `swing.metrics.discrepancies` module so any subsequent import
    # picks up the patched values.
    monkeypatch.setattr(
        "swing.metrics.discrepancies.count_unresolved_material",
        lambda conn: 7,
    )
    monkeypatch.setattr(
        "swing.metrics.discrepancies.count_recent_multi_leg_auto_corrections",
        lambda conn: 3,
    )
    monkeypatch.setattr(
        "swing.metrics.discrepancies"
        ".fetch_first_pending_ambiguity_resolve_link_path",
        lambda conn: "/journal/discrepancy/42/resolve",
    )

    from swing.web.price_cache import PriceCache
    from swing.web.view_models.trades import build_entry_form_vm
    cache = PriceCache.__new__(PriceCache)  # bypass __init__
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=None,
    )
    assert vm.unresolved_material_discrepancies_count == 7
    assert vm.recent_multi_leg_auto_correction_count == 3
    assert vm.banner_resolve_link == "/journal/discrepancy/42/resolve"


# ============================================================================
# Schwab integration discipline regression — entry_form invokes the
# auto-fill resolver with the expected ticker.
# ============================================================================


def test_auto_fill_resolver_called_with_uppercased_ticker(
    seeded_db, monkeypatch,
):
    """Defense-in-depth: even if operator submits lowercase ticker via URL,
    auto-fill resolver receives uppercase per ticker-normalization
    convention in build_entry_form_vm.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    calls = _patch_auto_fill(
        monkeypatch,
        EntryAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="x",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
        ),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=aapl")
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1
    assert calls[0]["ticker"] == "AAPL"


# ============================================================================
# HTMX gotcha trinity preservation — embedded form keeps hx-headers.
# ============================================================================


def test_htmx_gotcha_trinity_preserved(seeded_db, monkeypatch):
    """The entry form retains hx-headers='{"HX-Request": "true"}' on the
    embedded <form> (Phase 5 R1 M1 OriginGuard strict-mode discipline
    + dispatch brief §5 watch item 6).
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    _patch_auto_fill(
        monkeypatch,
        EntryAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="x",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
        ),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    body = resp.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in body
