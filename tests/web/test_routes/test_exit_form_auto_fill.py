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

import re
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
        existing_fill_order_ids: Any = None,
        existing_fill_value_tuples: Any = None,
    ) -> ExitAutoFillResult:
        calls.append({
            "trade_id": trade_id,
            "ticker": ticker,
            "entry_date": entry_date,
            "cfg": cfg,
            "conn": conn,
            "now": now,
            "existing_fill_order_ids": existing_fill_order_ids,
            "existing_fill_value_tuples": existing_fill_value_tuples,
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

    # Negative defense-in-depth: single-fill case (candidates length 1)
    # must NOT render the multi-partial radio fieldset nor emit per-
    # candidate hidden inputs. Guards against a regression in the
    # template's `{% if vm.auto_fill_candidates|length > 1 %}` gate.
    assert 'type="radio"' not in body, (
        "single-fill case must not render radio fieldset"
    )
    assert 'candidate_signature_hash_' not in body, (
        "single-fill case must not emit per-candidate hidden inputs"
    )


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

    # Tightened per-candidate radio co-location: every candidate index
    # i in {0, 1, 2} must appear inside a single <input> tag carrying
    # type="radio" AND name="candidate_index" AND value="<i>" — i.e. the
    # three attributes are co-located on the same radio element, not
    # merely all present somewhere in the body. Guards against a
    # regression that splits the radio group across multiple element
    # types or renames the group.
    for i in (0, 1, 2):
        radio_pattern = (
            r'<input\b[^>]*\btype="radio"[^>]*\bname="candidate_index"'
            r'[^>]*\bvalue="' + str(i) + r'"'
            r'|<input\b[^>]*\bvalue="' + str(i) + r'"'
            r'[^>]*\bname="candidate_index"[^>]*\btype="radio"'
            r'|<input\b[^>]*\bname="candidate_index"[^>]*\bvalue="'
            + str(i) + r'"[^>]*\btype="radio"'
            r'|<input\b[^>]*\btype="radio"[^>]*\bvalue="' + str(i) + r'"'
            r'[^>]*\bname="candidate_index"'
        )
        assert re.search(radio_pattern, body), (
            f"radio for candidate index {i} must co-locate "
            f'type="radio" + name="candidate_index" + value="{i}" '
            "on the same <input> element"
        )

    # Default selection: most-recent candidate (index 2) is pre-checked.
    # Tightened from substring-coincidence (`'value="2"' in body and
    # 'checked' in body`) to a regex requiring `value="2"` and
    # `checked` to co-locate on the same element (either order, since
    # Jinja attribute order may shift). The prior assertion passed
    # even if an unrelated element carried value="2" while a totally
    # different element was checked.
    checked_default_pattern = (
        r'\bvalue="2"[^>]*\bchecked\b'
        r'|\bchecked\b[^>]*\bvalue="2"'
    )
    assert re.search(checked_default_pattern, body), (
        'default selection: candidate index 2 must carry value="2" + '
        "checked on the same element"
    )


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
# Codex R1 Major #4 — already-recorded fills excluded from candidates.
# ============================================================================


def test_major4_existing_fills_order_ids_passed_to_resolver(
    seeded_db, monkeypatch,
):
    """Codex R1 Major #4 + R2 M#3 — VM builder collects ``schwab_order_id``
    from any already-recorded non-entry fills' ``schwab_source_value_json``
    envelopes and passes them as ``existing_fill_order_ids`` to the
    resolver.

    Codex R2 M#3 REVISION: only the envelope's pre-existing
    ``schwab_order_id`` field (the actually-persisted Schwab order's id)
    contributes to ``existing_fill_order_ids``. The
    ``selected_candidate_order_id`` field (audit-only field for which
    candidate the operator picked at form-render) is NOT extracted as an
    order-id dedupe key — the non-default-radio-no-edit case persisted
    the DEFAULT candidate's values, so the SELECTED candidate's order is
    STILL unrecorded and must remain surfaceable in future exits.

    The fill whose envelope carries only ``selected_candidate_order_id``
    therefore falls into the R2 M#4 fallback dedupe set
    (``existing_fill_value_tuples``) instead.
    """
    import json as _json

    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)

    # Plant 2 recorded exit fills:
    # - first carries the top-level ``schwab_order_id`` key (the value
    #   that was actually persisted to Schwab order's id) → contributes
    #   to existing_fill_order_ids.
    # - second carries ONLY ``selected_candidate_order_id`` (no top-
    #   level schwab_order_id) → represents the M#3 non-default-radio-
    #   no-edit case. Must contribute to existing_fill_value_tuples
    #   (fallback), NOT existing_fill_order_ids.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            env_topkey = _json.dumps({
                "exit_date": "2026-05-15", "exit_price": 110.0,
                "closed_shares": 3, "schwab_order_id": "ORDER-TOPKEY-1",
                "schwab_instrument_symbol": "NVDA",
            })
            env_selected = _json.dumps({
                "exit_date": "2026-05-17", "exit_price": 115.0,
                "closed_shares": 3,
                "selected_candidate_order_id": "ORDER-SELECTED-2",
                "schwab_instrument_symbol": "NVDA",
            })
            for fill_dt, qty, price, env in (
                ("2026-05-15T15:30:00", 3, 110.0, env_topkey),
                ("2026-05-17T15:30:00", 3, 115.0, env_selected),
            ):
                conn.execute(
                    "INSERT INTO fills "
                    "(trade_id, fill_datetime, action, quantity, price, "
                    "reason, rule_based, fees, manual_entry_confidence, "
                    "reconciliation_status, tos_match_id, "
                    "fill_origin, schwab_source_value_json, "
                    "operator_corrected_value_json, auto_fill_audit_at) "
                    "VALUES (?, ?, 'trim', ?, ?, 'manual', 0, 0.0, NULL, "
                    "'unreconciled', NULL, 'schwab_auto', ?, NULL, "
                    "'2026-05-19T14:30:00.000000+00:00')",
                    (trade_id, fill_dt, qty, price, env),
                )
    finally:
        conn.close()

    calls = _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="no matches",
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
    excluded = calls[0]["existing_fill_order_ids"]
    assert excluded is not None, (
        "M#4: resolver must receive a non-None exclusion set when trade "
        "has recorded fills with schwab provenance envelopes"
    )
    assert isinstance(excluded, set)
    # R2 M#3: only top-level schwab_order_id contributes; the
    # selected_candidate_order_id-only envelope does NOT.
    assert excluded == {"ORDER-TOPKEY-1"}, (
        f"R2 M#3: only top-level ``schwab_order_id`` should dedupe; the "
        f"selected_candidate_order_id-only envelope must fall through to "
        f"the R2 M#4 fallback. Got {excluded!r}"
    )
    # R2 M#4: the selected-candidate-only envelope falls into the
    # fallback dedupe set keyed by (date, round(price, 2), int(qty)).
    fallback = calls[0]["existing_fill_value_tuples"]
    assert fallback is not None, (
        "R2 M#4: envelopes without a top-level schwab_order_id MUST "
        "contribute to existing_fill_value_tuples fallback"
    )
    assert isinstance(fallback, set)
    assert ("2026-05-17", 115.00, 3) in fallback, (
        f"R2 M#4: selected-candidate-only envelope must yield fallback "
        f"tuple (date, round(price, 2), qty); got {fallback!r}"
    )


def test_major4_no_existing_fills_passes_none(seeded_db, monkeypatch):
    """Codex R1 Major #4 — when there are NO already-recorded non-entry
    fills with envelopes, resolver is called with
    ``existing_fill_order_ids=None`` (backwards-compat with the entry-
    side parity test pattern + the empty-set degenerate case).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    calls = _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="no matches",
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
    assert calls[0]["existing_fill_order_ids"] is None
    # R2 M#4: no envelopes + no non-entry fills => fallback also None.
    assert calls[0]["existing_fill_value_tuples"] is None


# ============================================================================
# Codex R2 Major #3 — dedupe ONLY on persisted schwab_order_id, NOT on
# selected_candidate_order_id (audit field for non-default radio selection).
# ============================================================================


def test_r2_major3_dedupe_only_on_persisted_schwab_order_id(
    seeded_db, monkeypatch,
):
    """Codex R2 Major #3 — when ``fill_origin = schwab_auto_then_operator_
    corrected`` from a non-default-radio-no-edit submit, the envelope
    carries:
      * ``schwab_order_id = A`` (DEFAULT candidate's order — the values
        ACTUALLY persisted because radio doesn't rebind visible inputs);
      * ``selected_candidate_order_id = B`` (the candidate the operator
        PICKED but whose values were never persisted).
    Future exit-form renders must dedupe ONLY on A — order B is STILL
    unrecorded and must remain surfaceable as a candidate.

    Discriminating test: plant a fill with envelope (schwab_order_id=A,
    selected_candidate_order_id=B). Resolver receives
    existing_fill_order_ids={A} (NOT {A, B}). With Schwab returning A+B+C,
    the candidates list excludes only A.
    """
    import json as _json

    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            env = _json.dumps({
                "exit_date": "2026-05-15", "exit_price": 110.0,
                "closed_shares": 3,
                "schwab_order_id": "ORDER-A",  # the ACTUALLY persisted
                "selected_candidate_order_id": "ORDER-B",  # picked, NOT persisted
                "schwab_instrument_symbol": "NVDA",
            })
            conn.execute(
                "INSERT INTO fills "
                "(trade_id, fill_datetime, action, quantity, price, "
                "reason, rule_based, fees, manual_entry_confidence, "
                "reconciliation_status, tos_match_id, "
                "fill_origin, schwab_source_value_json, "
                "operator_corrected_value_json, auto_fill_audit_at) "
                "VALUES (?, '2026-05-15T15:30:00', 'trim', 3, 110.0, "
                "'manual', 0, 0.0, NULL, 'unreconciled', NULL, "
                "'schwab_auto_then_operator_corrected', ?, NULL, "
                "'2026-05-19T14:30:00.000000+00:00')",
                (trade_id, env),
            )
    finally:
        conn.close()

    calls = _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="no matches",
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
    excluded = calls[0]["existing_fill_order_ids"]
    # R2 M#3: ORDER-B (selected_candidate_order_id) must NOT be excluded;
    # only ORDER-A (the actually-persisted schwab_order_id) is.
    assert excluded == {"ORDER-A"}, (
        f"R2 M#3: only schwab_order_id (actually-persisted) should "
        f"dedupe; selected_candidate_order_id MUST NOT be excluded "
        f"(it represents an UNRECORDED Schwab order). Got {excluded!r}"
    )


# ============================================================================
# Codex R2 Major #4 — fallback dedupe by (date, round(price, 2), quantity)
# for fills without a parseable schwab_order_id (pre-v20, operator_typed,
# tos_import, imported_legacy fills).
# ============================================================================


def test_r2_major4_fallback_dedupe_operator_typed_no_envelope(
    seeded_db, monkeypatch,
):
    """Codex R2 Major #4 Test A — operator_typed fill (no envelope) at
    date=2026-05-19 + price=160.50 + quantity=100 must dedupe against a
    Schwab response carrying a matching SELL order at the same
    (date, price, qty) tuple.

    Resolver receives existing_fill_value_tuples containing
    (2026-05-19, 160.50, 100); a matching candidate is excluded.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # operator_typed fill — NO schwab_source_value_json envelope.
            conn.execute(
                "INSERT INTO fills "
                "(trade_id, fill_datetime, action, quantity, price, "
                "reason, rule_based, fees, manual_entry_confidence, "
                "reconciliation_status, tos_match_id, "
                "fill_origin, schwab_source_value_json, "
                "operator_corrected_value_json, auto_fill_audit_at) "
                "VALUES (?, '2026-05-19T15:30:00', 'trim', 100, 160.50, "
                "'manual', 0, 0.0, NULL, 'unreconciled', NULL, "
                "'operator_typed', NULL, NULL, NULL)",
                (trade_id,),
            )
    finally:
        conn.close()

    calls = _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="empty", fill_origin="operator_typed",
            advisory_text="no matches",
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
    # No schwab_order_id envelope present → order_ids should be None.
    assert calls[0]["existing_fill_order_ids"] is None
    # Fallback dedupe set carries the (date, rounded-price, qty) tuple.
    fallback = calls[0]["existing_fill_value_tuples"]
    assert fallback is not None and isinstance(fallback, set)
    assert ("2026-05-19", 160.50, 100) in fallback, (
        f"R2 M#4 Test A: operator_typed fill (no envelope) must "
        f"contribute (date, round(price, 2), int(qty)) to "
        f"existing_fill_value_tuples; got {fallback!r}"
    )


def test_r2_major4_fallback_dedupe_resolver_filters_matching_tuple(
    seeded_db, monkeypatch,
):
    """Codex R2 Major #4 — direct test of resolve_exit_auto_fill's
    tuple-filtering branch. Plant 3 Schwab candidates A + B + C; pass
    excluded value tuples matching A's (date, price, qty). Assert A
    excluded from candidates list while B + C remain.

    Plus tolerance tests:
      * candidate at 160.51 (1 cent off) is NOT filtered when excluded
        tuple is (date, 160.50, 100) — drift exceeds 2-decimal rounding.
      * candidate at 160.504 (rounds to 160.50) IS filtered when excluded
        tuple is (date, 160.50, 100).
      * candidate at 160.499 (rounds to 160.50) IS filtered when excluded
        tuple is (date, 160.50, 100).
    """
    from unittest.mock import MagicMock

    from swing.trades.exit_auto_fill import resolve_exit_auto_fill

    cfg, _cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")

    # Build 4 fake Schwab orders — A matches excluded tuple exactly;
    # B differs by 1 cent (price drift > rounding tolerance);
    # C is unrelated; D matches via float-rounding tolerance (160.504).
    def _fake_order(order_id, enter_time, price, qty):
        o = MagicMock()
        o.instrument_symbol = "NVDA"
        o.instruction = "SELL"
        o.order_id = order_id
        o.enter_time = enter_time
        o.status = "FILLED"
        # Single-leg execution carrying the price + filled quantity.
        leg = MagicMock()
        leg.price = price
        leg.quantity = qty
        activity = MagicMock()
        activity.execution_legs = [leg]
        o.order_activity_collection = [activity]
        o.executions = [leg]
        o.filled_quantity = qty
        o.price = price
        return o

    # The resolver uses _compute_execution_price / _resolve_match_quantity
    # which read order activity collection; let's monkeypatch them to
    # produce deterministic values keyed off the mock attributes for
    # this discriminating test.
    monkeypatch_obj = pytest.MonkeyPatch()
    try:
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill._compute_execution_price",
            lambda o: getattr(o, "price", None),
        )
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill._resolve_match_quantity",
            lambda o: getattr(o, "filled_quantity", None),
        )
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill._is_execution_bearing_candidate",
            lambda o: True,
        )
        # Patch the Schwab fetch entirely.
        order_a = _fake_order("ORD-A", "2026-05-19T15:30:00", 160.50, 100)
        order_b = _fake_order("ORD-B", "2026-05-19T15:35:00", 160.51, 100)
        order_c = _fake_order("ORD-C", "2026-05-20T10:00:00", 170.25, 50)
        order_d = _fake_order("ORD-D", "2026-05-19T15:40:00", 160.504, 100)
        order_e = _fake_order("ORD-E", "2026-05-19T15:45:00", 160.499, 100)
        all_orders = [order_a, order_b, order_c, order_d, order_e]
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill.trader.get_account_orders",
            lambda *a, **kw: all_orders,
        )
        # Short-circuit all the auth + degraded-state machinery to LIVE.
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill._compute_degraded_state",
            lambda *a, **kw: ("LIVE", None),
        )
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill.resolve_credentials_env_or_prompt",
            lambda *a, **kw: ("client-id", "client-secret"),
        )
        monkeypatch_obj.setattr(
            "swing.trades.exit_auto_fill.construct_authenticated_client",
            lambda *a, **kw: MagicMock(),
        )
        # cfg with production environment + account_hash.
        fake_cfg = MagicMock()
        fake_cfg.integrations.schwab.environment = "production"
        fake_cfg.integrations.schwab.account_hash = "fake-hash"
        fake_conn = MagicMock()
        result = resolve_exit_auto_fill(
            trade_id=trade_id,
            ticker="NVDA",
            entry_date="2026-04-15",
            cfg=fake_cfg,
            conn=fake_conn,
            existing_fill_value_tuples={("2026-05-19", 160.50, 100)},
        )
    finally:
        monkeypatch_obj.undo()

    assert result.kind == "populated", (
        f"expected populated result with B+C surviving; got {result!r}"
    )
    cand_order_ids = {c.order_id for c in (result.candidates or ())}
    # A excluded by exact tuple match; D + E excluded by rounding match.
    assert "ORD-A" not in cand_order_ids, (
        "Test A: exact (date, 160.50, 100) match must be excluded"
    )
    assert "ORD-D" not in cand_order_ids, (
        "Test C: 160.504 rounds to 160.50; must be excluded"
    )
    assert "ORD-E" not in cand_order_ids, (
        "Test C bis: 160.499 rounds to 160.50; must be excluded"
    )
    # B + C survive — drift > rounding + unrelated qty/date.
    assert "ORD-B" in cand_order_ids, (
        "Test B: 160.51 (1 cent off) exceeds 2-decimal rounding "
        "tolerance; MUST NOT be excluded"
    )
    assert "ORD-C" in cand_order_ids, (
        "Unrelated candidate (different date + qty) MUST survive"
    )


# ============================================================================
# Codex R2 Minor #1 — operator-instruction text inside multi-partial radio
# fieldset.
# ============================================================================


def test_r2_minor1_operator_instruction_text_present_in_multi_partial_fieldset(
    seeded_db, monkeypatch,
):
    """Codex R2 Minor #1 — when 2+ candidates render, the fieldset
    contains operator-instruction text telling the operator that radio
    selection does NOT auto-update visible inputs.

    Rationale: the template does not rebind visible inputs client-side
    when a radio is picked; without this hint, operator may submit
    default-input values while believing the selection drove them.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    candidates = (
        _single_candidate(
            date="2026-05-15", price=110.0, quantity=3,
            signature_hash="sig-0", order_id="ord-0",
        ),
        _single_candidate(
            date="2026-05-17", price=115.5, quantity=4,
            signature_hash="sig-1", order_id="ord-1",
        ),
    )
    _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="populated", fill_origin="schwab_auto",
            exit_date="2026-05-17", exit_price=115.5, closed_shares=4,
            candidates=candidates,
            schwab_source_value_json="{}",
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
    body = resp.text
    # The instruction text must appear inside the multi-partial fieldset.
    assert "auto-fill-candidates" in body, (
        "fieldset class auto-fill-candidates must render when N>=2"
    )
    assert "manually edit the inputs" in body, (
        "Codex R2 Minor #1: operator-instruction text missing from "
        "multi-partial radio fieldset"
    )
    # Defensive: also assert phrase about radio not updating inputs.
    assert "does NOT update" in body, (
        "Codex R2 Minor #1: instruction text should clearly state "
        "selection does NOT update visible inputs"
    )


def test_r2_minor1_no_instruction_text_on_single_fill_case(
    seeded_db, monkeypatch,
):
    """Codex R2 Minor #1 — single-fill case (N=1) does NOT render the
    radio fieldset, so the operator-instruction text MUST NOT appear.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "NVDA")
    _patch_price_cache(monkeypatch)
    _patch_auto_fill(
        monkeypatch,
        ExitAutoFillResult(
            kind="populated", fill_origin="schwab_auto",
            exit_date="2026-05-17", exit_price=115.5, closed_shares=4,
            candidates=(_single_candidate(
                date="2026-05-17", price=115.5, quantity=4,
                signature_hash="sig-0", order_id="ord-0",
            ),),
            schwab_source_value_json="{}",
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
    body = resp.text
    assert "auto-fill-candidates" not in body
    assert "manually edit the inputs" not in body


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
