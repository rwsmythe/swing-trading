"""Phase 13 T3.SB2 T-B.2.2 — exit_form auto-fill integration tests.

SELL-side mirror of test_entry_form_auto_fill.py. Per plan §G.5 T-B.2.2
step 1 + dispatch brief §5 watch items + FORWARD-BINDING WATCH ITEM:

  (a) auto-fill populated when Schwab returns SELL fill — single-fill case
      renders auto-populated values in input fields + hidden anchor +
      display-only audit metadata.
  (b) advisory banner when no match.
  (c) sandbox short-circuits — advisory banner; NO hidden anchor.
  (d) hidden audit anchors present (schwab_source_value_json +
      auto_fill_audit_at + fill_origin_at_form_render).
  (e) multi-partial-exit list rendering — when multiple SELL fills returned,
      template renders each as a selectable candidate (radio buttons) +
      per-candidate hidden inputs (candidate_signature_hash_<i> +
      candidate_order_id_<i>).
  (f) TradeExitFormVM has banner-pin fields with safe defaults (field-
      duplication convention per Codex R1 Major #4 ACCEPT on T3.SB1).
  (g) TradeExitFormVM populates banner-pin fields from
      swing.metrics.discrepancies helpers (forward-binding lesson #12).
  Plus: HTMX gotcha trinity preserved + auto-fill resolver called with
  uppercased ticker.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event, list_open_trades
from swing.trades.exit_auto_fill import (
    ExitAutoFillCandidate,
    ExitAutoFillResult,
)
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=110.0, asof=datetime.now(),
                is_stale=False, source="live",
            )
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _patch_auto_fill(
    monkeypatch: pytest.MonkeyPatch,
    result: ExitAutoFillResult,
) -> list:
    """Patch swing.trades.exit_auto_fill.resolve_exit_auto_fill to return
    ``result`` and record call kwargs.
    """
    calls: list = []

    def fake_resolve(
        *,
        trade_id: int,
        ticker: str,
        entry_date: str,
        cfg: Any,
        conn: Any,
        now: Any = None,
    ) -> ExitAutoFillResult:
        calls.append({
            "trade_id": trade_id,
            "ticker": ticker,
            "entry_date": entry_date,
            "cfg": cfg,
            "conn": conn,
            "now": now,
        })
        return result

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.resolve_exit_auto_fill",
        fake_resolve,
    )
    return calls


def _seed_open_trade(cfg, ticker: str = "NVDA") -> int:
    """Seed a single open trade and return its id."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=95.0,
                current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
        return int(trade.id)
    finally:
        conn.close()


def _single_candidate(
    *, date: str = "2026-05-19", price: float = 120.50, quantity: int = 10,
    signature_hash: str = "sig-abc-123",
    order_id: str | None = "order-xyz",
) -> ExitAutoFillCandidate:
    return ExitAutoFillCandidate(
        date=date, price=price, quantity=quantity,
        signature_hash=signature_hash, order_id=order_id,
    )


# ============================================================================
# (a) Populated auto-fill — values flow into form inputs + hidden anchor.
# ============================================================================


def test_a_populated_auto_fill_renders_values_and_hidden_anchor(
    seeded_db, monkeypatch,
):
    """Schwab returns single matching SELL fill -> form inputs pre-populated
    with execution-grain values + hidden anchor + display-only audit metadata.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    cand = _single_candidate(
        date="2026-05-19", price=120.50, quantity=10,
        signature_hash="sig-abc-123", order_id="order-xyz",
    )
    auto_fill = ExitAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        exit_date="2026-05-19",
        exit_price=120.50,
        closed_shares=10,
        candidates=[cand],
        advisory_text=None,
        schwab_source_value_json=(
            '{"exit_date": "2026-05-19", "exit_price": 120.5, '
            '"closed_shares": 10, "schwab_order_id": "order-xyz"}'
        ),
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Hidden anchor (transport from GET to POST). Jinja2 autoescape
    # converts double-quotes inside the JSON value to `&#34;`.
    assert 'name="schwab_source_value_json"' in body
    assert '&#34;exit_price&#34;: 120.5' in body
    assert 'name="auto_fill_audit_at"' in body
    assert '2026-05-19T14:30:00.000000+00:00' in body
    assert 'name="fill_origin_at_form_render"' in body
    assert 'value="schwab_auto"' in body

    # Auto-populated exit_price flows through to the input value.
    assert 'value="120.50"' in body

    # Display-only audit metadata visible (server-stamped, not <input>).
    assert "Auto-fill source:" in body
    assert "schwab_auto" in body


# ============================================================================
# (b) Empty Schwab response -> advisory banner; NO hidden anchor.
# ============================================================================


def test_b_empty_auto_fill_renders_advisory_banner(seeded_db, monkeypatch):
    """Schwab returns no SELL fills -> advisory banner; NO hidden anchor."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    auto_fill = ExitAutoFillResult(
        kind="empty",
        fill_origin="operator_typed",
        advisory_text=(
            "No matching Schwab SELL fills for NVDA since 2026-04-15; "
            "please enter manually."
        ),
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text

    assert "Schwab auto-fill:" in body
    assert "No matching Schwab SELL fills for NVDA" in body
    assert 'name="schwab_source_value_json"' not in body


# ============================================================================
# (c) Sandbox short-circuit -> advisory banner; NO hidden anchor.
# ============================================================================


def test_c_sandbox_short_circuit_renders_advisory(seeded_db, monkeypatch):
    """sandbox kind -> advisory banner; NO Schwab call fired."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    auto_fill = ExitAutoFillResult(
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
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text

    assert "Schwab auto-fill:" in body
    assert "sandbox mode" in body
    assert 'name="schwab_source_value_json"' not in body


# ============================================================================
# (d) Hidden audit anchors present on populated kind.
# ============================================================================


def test_d_hidden_audit_anchors_present_on_populated(seeded_db, monkeypatch):
    """Discriminating: hidden inputs for schwab_source_value_json +
    auto_fill_audit_at + fill_origin_at_form_render are present on
    populated kind.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    cand = _single_candidate(
        date="2026-05-19", price=200.0, quantity=5,
        signature_hash="sig-d", order_id="ord-d",
    )
    auto_fill = ExitAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        exit_date="2026-05-19",
        exit_price=200.0,
        closed_shares=5,
        candidates=[cand],
        schwab_source_value_json='{"exit_price": 200.0, "closed_shares": 5}',
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    body = resp.text

    assert 'type="hidden" name="schwab_source_value_json"' in body
    assert 'type="hidden" name="auto_fill_audit_at"' in body
    assert 'type="hidden" name="fill_origin_at_form_render"' in body


# ============================================================================
# (e) Multi-partial-exit list rendering + per-candidate hidden inputs.
# ============================================================================


def test_e_multi_partial_renders_candidate_list_with_per_candidate_hidden_inputs(
    seeded_db, monkeypatch,
):
    """When Schwab returns >=2 SELL fills (scaled-out), the template
    renders each as a selectable candidate (radio buttons), one row per
    candidate, with per-candidate hidden inputs:
      - candidate_signature_hash_<i>
      - candidate_order_id_<i>

    Forward-binding for T-B.2.3: POST handler reads operator's selected
    radio + maps to the server-rendered per-candidate envelope so a
    non-default selection records correct provenance.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    c0 = ExitAutoFillCandidate(
        date="2026-05-15", price=110.25, quantity=3,
        signature_hash="sig-cand-0", order_id="order-0",
    )
    c1 = ExitAutoFillCandidate(
        date="2026-05-17", price=115.50, quantity=4,
        signature_hash="sig-cand-1", order_id="order-1",
    )
    c2 = ExitAutoFillCandidate(
        date="2026-05-19", price=120.00, quantity=3,
        signature_hash="sig-cand-2", order_id="order-2",
    )
    # chosen (default) = most-recent = c2
    auto_fill = ExitAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        exit_date=c2.date,
        exit_price=c2.price,
        closed_shares=c2.quantity,
        candidates=[c0, c1, c2],
        schwab_source_value_json=(
            '{"exit_date": "2026-05-19", "exit_price": 120.0, '
            '"closed_shares": 3, "candidate_count": 3}'
        ),
        auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
    )
    _patch_auto_fill(monkeypatch, auto_fill)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Per-candidate hidden inputs for the FORWARD-BINDING WATCH ITEM —
    # all three indices appear so POST handler can verify operator's
    # selected candidate index maps to a server-rendered candidate.
    assert 'name="candidate_signature_hash_0"' in body
    assert 'name="candidate_signature_hash_1"' in body
    assert 'name="candidate_signature_hash_2"' in body
    assert 'value="sig-cand-0"' in body
    assert 'value="sig-cand-1"' in body
    assert 'value="sig-cand-2"' in body

    assert 'name="candidate_order_id_0"' in body
    assert 'name="candidate_order_id_1"' in body
    assert 'name="candidate_order_id_2"' in body
    assert 'value="order-0"' in body
    assert 'value="order-1"' in body
    assert 'value="order-2"' in body

    # Selectable group: radio buttons for candidate selection.
    assert 'type="radio"' in body
    assert 'name="candidate_index"' in body

    # Per-candidate visible values (date / price / quantity).
    assert "2026-05-15" in body
    assert "2026-05-17" in body
    assert "2026-05-19" in body
    assert "110.25" in body
    assert "115.50" in body
    assert "120.00" in body

    # Default selection: most-recent candidate (index 2) is pre-checked.
    # Look for the checked attribute alongside index 2's value.
    assert 'value="2"' in body and 'checked' in body


# ============================================================================
# (f) TradeExitFormVM has banner-pin fields with safe defaults
#     (field-duplication convention per project; NOT inheritance).
# ============================================================================


def test_f_vm_has_banner_pin_field_defaults():
    """TradeExitFormVM exposes banner-pin fields with safe defaults
    (forward-binding lesson #12: any future full-page render path that
    extends base.html.j2 reads these without UndefinedError).
    """
    from swing.data.models import Trade
    from swing.web.view_models.trades import TradeExitFormVM
    trade = Trade(
        id=1, ticker="NVDA", entry_date="2026-04-15",
        entry_price=100.0, initial_shares=10, initial_stop=95.0,
        current_stop=95.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    vm = TradeExitFormVM(
        trade=trade,
        exit_date="2026-05-19",
        exit_price=110.0,
        remaining_shares=10,
        reasons=("stop-hit",),
    )
    # Banner-pin fields default to safe values.
    assert vm.unresolved_material_discrepancies_count == 0
    assert vm.recent_multi_leg_auto_correction_count == 0
    assert vm.banner_resolve_link is None
    # Auto-fill fields default to operator_typed / None.
    assert vm.auto_fill_kind == "operator_typed"
    assert vm.auto_fill_fill_origin == "operator_typed"
    assert vm.auto_fill_exit_date is None
    assert vm.auto_fill_exit_price is None
    assert vm.auto_fill_closed_shares is None
    assert vm.auto_fill_candidates is None
    assert vm.auto_fill_advisory_text is None
    assert vm.auto_fill_schwab_source_value_json is None
    assert vm.auto_fill_audit_at is None


# ============================================================================
# (g) Banner-pin field POPULATION at build_exit_form_vm time.
# ============================================================================


def test_g_vm_populates_banner_pin_fields_from_helpers(
    seeded_db, monkeypatch,
):
    """build_exit_form_vm calls count_unresolved_material +
    count_recent_multi_leg_auto_corrections +
    fetch_first_pending_ambiguity_resolve_link_path and populates the VM
    accordingly (forward-binding lesson #12).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="x",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
        ),
    )

    monkeypatch.setattr(
        "swing.metrics.discrepancies.count_unresolved_material",
        lambda conn: 11,
    )
    monkeypatch.setattr(
        "swing.metrics.discrepancies.count_recent_multi_leg_auto_corrections",
        lambda conn: 5,
    )
    monkeypatch.setattr(
        "swing.metrics.discrepancies"
        ".fetch_first_pending_ambiguity_resolve_link_path",
        lambda conn: "/journal/discrepancy/77/resolve",
    )

    from swing.web.view_models.trades import build_exit_form_vm
    cache = PriceCache.__new__(PriceCache)  # bypass __init__
    vm = build_exit_form_vm(
        trade_id=trade_id, cfg=cfg, cache=cache, executor=None,
    )
    assert vm is not None
    assert vm.unresolved_material_discrepancies_count == 11
    assert vm.recent_multi_leg_auto_correction_count == 5
    assert vm.banner_resolve_link == "/journal/discrepancy/77/resolve"


# ============================================================================
# Schwab integration discipline regression — exit_form invokes the
# auto-fill resolver with the expected (trade_id, uppercase ticker,
# entry_date).
# ============================================================================


def test_auto_fill_resolver_called_with_trade_anchors(
    seeded_db, monkeypatch,
):
    """The exit_form handler calls resolve_exit_auto_fill with the
    trade's trade_id, ticker (uppercased), and entry_date.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    calls = _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="x",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
        ),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1
    assert calls[0]["trade_id"] == trade_id
    assert calls[0]["ticker"] == "NVDA"
    assert calls[0]["entry_date"] == "2026-04-15"


# ============================================================================
# HTMX gotcha trinity preservation — embedded form keeps hx-headers.
# ============================================================================


def test_htmx_gotcha_trinity_preserved(seeded_db, monkeypatch):
    """The exit form retains hx-headers='{"HX-Request": "true"}' on the
    embedded <form> (Phase 5 R1 M1 OriginGuard strict-mode discipline).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="x",
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
        ),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            f"/trades/{trade_id}/exit/form",
            headers={"HX-Request": "true"},
        )
    body = resp.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in body
