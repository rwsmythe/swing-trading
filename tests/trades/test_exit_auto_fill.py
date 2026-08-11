"""Phase 13 T3.SB2 T-B.2.1 — exit_auto_fill module tests.

Per plan §G.5 T-B.2.1 step 1 (7 failing tests) + dispatch brief §5 watch
items + SELL-side mirror of T3.SB1 entry_auto_fill tests:

  (a) matching Schwab SELL fill returns ExitAutoFillResult with populated
      values + fill_origin='schwab_auto'
  (b) empty Schwab response → empty result + fill_origin='operator_typed'
  (c) sandbox short-circuits per §A.11
  (d) DEGRADED short-circuits with advisory per §A.11
  (e) multi-partial-exit handling — if Schwab returns multiple SELL fills
      since entry_date, returns list of ExitAutoFillCandidate for operator
      selection (per spec §6.2 paragraph 2)
  (f) trace test: resolve_exit_auto_fill invokes
      resolve_credentials_env_or_prompt(allow_prompt=False) (mock-verified)
  (g) trace test: invokes construct_authenticated_client with 4-arg
      signature

Additional defensive tests cover audit surface, BUY-side filter rejection,
account_hash missing, credentials None, SchwabApiError, dataclass
__post_init__ Literal validation, and lookback semantics (since
entry_date).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabConfigMissingError,
)
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.exit import _normalize_trade_event_date_to_iso
from swing.trades.exit_auto_fill import (
    ExitAutoFillCandidate,
    ExitAutoFillResult,
    resolve_exit_auto_fill,
)
from swing.trades.schwab_reconciliation import _fill_execution_session_distance

# ============================================================================
# Shared fixtures (mirror T3.SB1 test pattern verbatim)
# ============================================================================


@dataclass
class _SchwabCfg:
    environment: str = "production"
    client_id: str | None = None
    client_secret: str | None = None
    account_hash: str | None = "deadbeef-account-hash"


@dataclass
class _IntegrationsCfg:
    schwab: _SchwabCfg


@dataclass
class _Cfg:
    integrations: _IntegrationsCfg


def _make_cfg(
    *,
    environment: str = "production",
    account_hash: str | None = "deadbeef-account-hash",
) -> _Cfg:
    return _Cfg(
        integrations=_IntegrationsCfg(
            schwab=_SchwabCfg(
                environment=environment,
                account_hash=account_hash,
            ),
        ),
    )


def _make_sell_order(
    *,
    ticker: str = "AAPL",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    price: float = 150.25,
    quantity: float = 100,
    order_type: str = "LIMIT",
    instruction: str = "SELL",
    status: str = "FILLED",
    order_id: str | None = None,
    execution_time: str | None = None,
) -> SchwabOrderResponse:
    """Build a production-emitter-shape SchwabOrderResponse representing a
    SELL fill with one execution leg. Per CLAUDE.md "Synthetic-fixture-vs-
    production-emitter shape drift" gotcha — tests use the real dataclass,
    not a stub.

    ``execution_time`` defaults to ``enter_time`` (the same-session fill that
    every pre-D31 test assumed). Pass it explicitly to build the STRADDLING
    shape: an order ENTERED on one session and EXECUTED on another, which is
    what a resting stop does and what the D31 exit-side defect mis-dated.
    """
    leg = SchwabExecutionLeg(
        leg_id=1,
        price=price,
        quantity=quantity,
        mismarked_quantity=None,
        instrument_id=12345,
        time=execution_time if execution_time is not None else enter_time,
    )
    return SchwabOrderResponse(
        order_id=order_id or f"order-{ticker}-{enter_time}",
        status=status,
        enter_time=enter_time,
        instrument_symbol=ticker,
        instruction=instruction,
        quantity=quantity,
        order_type=order_type,
        price=price,
        executions=[leg],
    )


def _make_multileg_sell_order(
    *,
    ticker: str = "AAPL",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    legs: tuple[tuple[float, float], ...] = ((100.0, 50.0), (102.0, 50.0)),
) -> SchwabOrderResponse:
    """Multi-leg SELL fill: ``legs`` = tuple of ``(price, quantity)`` pairs.
    VWAP via _compute_execution_price = sum(p*q)/sum(q).
    """
    execution_legs = [
        SchwabExecutionLeg(
            leg_id=i + 1,
            price=p,
            quantity=q,
            mismarked_quantity=None,
            instrument_id=12345,
            time=enter_time,
        )
        for i, (p, q) in enumerate(legs)
    ]
    total_qty = sum(q for _, q in legs)
    return SchwabOrderResponse(
        order_id=f"order-{ticker}-{enter_time}-multileg",
        status="FILLED",
        enter_time=enter_time,
        instrument_symbol=ticker,
        instruction="SELL",
        quantity=total_qty,
        order_type="MARKET",
        price=None,  # MARKET orders may have price=None
        executions=execution_legs,
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Schema-initialized in-memory connection (v20)."""
    db_path = tmp_path / "xaf_test.db"
    c = ensure_schema(db_path)
    yield c
    c.close()


@pytest.fixture
def fake_now() -> datetime:
    """Fixed 'now' for deterministic lookback windows."""
    return datetime(2026, 5, 19, 14, 30, 0, tzinfo=UTC)


@pytest.fixture
def patch_live_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force _compute_degraded_state → ('LIVE', None) so production-path
    tests don't trip on missing tokens DB / empty `schwab_api_calls`.
    """
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: ("LIVE", None),
    )


@pytest.fixture
def patch_credentials(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch resolve_credentials_env_or_prompt to record call kwargs +
    return canned credentials.
    """
    calls: list = []

    def fake_resolver(
        cfg: Any,
        environment: str,
        *,
        allow_prompt: bool = True,
        prompter: Any = None,
    ) -> tuple[str | None, str | None]:
        calls.append({
            "cfg": cfg,
            "environment": environment,
            "allow_prompt": allow_prompt,
        })
        return ("sentinel-client-id", "sentinel-client-secret")

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.resolve_credentials_env_or_prompt",
        fake_resolver,
    )
    return calls


@pytest.fixture
def patch_client_factory(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch construct_authenticated_client to record positional args."""
    calls: list = []
    sentinel_client = object()

    def fake_factory(
        cfg: Any, environment: str, client_id: str, client_secret: str,
    ) -> Any:
        calls.append({
            "cfg": cfg,
            "environment": environment,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        return sentinel_client

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.construct_authenticated_client",
        fake_factory,
    )
    return calls


class _OrdersCallRecorder(list):
    """List subclass that also carries a ``state`` dict for fixture
    seam mutation. Plain ``list`` rejects __dict__ attribute setting on
    CPython 3.14; subclass adds __slots__-compatible storage.
    """

    def __init__(self) -> None:
        super().__init__()
        self.state: dict[str, Any] = {"orders": [], "raises": None}


@pytest.fixture
def patch_get_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> _OrdersCallRecorder:
    """Patch trader.get_account_orders. Returns a recorder whose ``.state``
    dict the test mutates to set orders / raises behavior.
    """
    recorder = _OrdersCallRecorder()

    def fake_get(client, conn, account_hash, from_dt, to_dt, **kwargs):
        recorder.append({
            "client": client,
            "conn": conn,
            "account_hash": account_hash,
            "from_dt": from_dt,
            "to_dt": to_dt,
            **kwargs,
        })
        if recorder.state["raises"] is not None:
            raise recorder.state["raises"]
        return list(recorder.state["orders"])

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.trader.get_account_orders",
        fake_get,
    )
    return recorder


# ============================================================================
# Tests — 7 plan-§G.5-listed tests
# ============================================================================


def test_a_matching_sell_fill_returns_populated(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(a) matching Schwab SELL fill → populated + fill_origin='schwab_auto'.

    Single-fill case: ``candidates`` is a length-1 list per spec §6.2
    paragraph 2 ("single-fill case = length-1 list").
    """
    order = _make_sell_order(
        ticker="AAPL", price=160.50, quantity=100,
        enter_time="2026-05-19T15:30:00.000Z",
        instruction="SELL_TO_CLOSE",
    )
    patch_get_orders.state["orders"] = [order]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert isinstance(result, ExitAutoFillResult)
    assert result.kind == "populated"
    assert result.fill_origin == "schwab_auto"
    assert result.exit_price == 160.50
    assert result.closed_shares == 100
    assert result.exit_date == "2026-05-19"
    assert result.auto_fill_audit_at is not None
    assert result.schwab_source_value_json is not None
    assert "160.5" in result.schwab_source_value_json
    # Single-fill case still surfaces a length-1 candidates list per
    # spec §6.2 paragraph 2 ("single-fill case = length-1 list").
    assert result.candidates is not None
    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert isinstance(cand, ExitAutoFillCandidate)
    assert cand.price == 160.50
    assert cand.quantity == 100
    assert cand.date == "2026-05-19"


def test_b_empty_schwab_response_returns_empty(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(b) Schwab returns no SELL orders → empty + fill_origin='operator_typed'."""
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty"
    assert result.fill_origin == "operator_typed"
    assert result.exit_price is None
    assert result.closed_shares is None
    assert result.exit_date is None
    assert result.candidates is None
    assert result.advisory_text is not None
    assert "no matching" in result.advisory_text.lower()


def test_c_sandbox_short_circuits(conn, fake_now):
    """(c) cfg.integrations.schwab.environment == 'sandbox' short-circuits.

    Sandbox short-circuit must fire BEFORE any Schwab dependency call.
    No credentials / factory / orders fixtures are installed — if the
    service reached them, it would try real schwabdev import.
    """
    cfg = _make_cfg(environment="sandbox")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "sandbox_short_circuit"
    assert result.fill_origin == "operator_typed"
    assert result.exit_price is None
    assert result.closed_shares is None
    assert result.candidates is None
    assert result.advisory_text is not None
    assert "sandbox" in result.advisory_text.lower()


def test_d_degraded_short_circuits(conn, fake_now, monkeypatch):
    """(d) _compute_degraded_state returns 'DEGRADED' → degraded result."""
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: (
            "DEGRADED", "refresh_token expired"
        ),
    )
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"
    assert result.advisory_text is not None
    assert "refresh_token expired" in result.advisory_text


def test_e_multi_partial_exit_returns_candidate_list(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(e) NEW vs T3.SB1: multiple SELL fills → list[ExitAutoFillCandidate].

    Per spec §6.2 paragraph 2: "if Schwab returns multiple SELL fills since
    entry_date (partial exits over time), form lists each as a candidate;
    operator picks one OR enters consolidated value."

    Each candidate carries date / price / quantity / signature_hash.
    """
    part1 = _make_sell_order(
        ticker="AAPL", price=160.00, quantity=33,
        enter_time="2026-05-16T15:30:00.000Z",
        instruction="SELL_TO_CLOSE", order_id="order-AAPL-part1",
    )
    part2 = _make_sell_order(
        ticker="AAPL", price=162.50, quantity=33,
        enter_time="2026-05-17T15:30:00.000Z",
        instruction="SELL_TO_CLOSE", order_id="order-AAPL-part2",
    )
    part3 = _make_sell_order(
        ticker="AAPL", price=165.00, quantity=34,
        enter_time="2026-05-18T15:30:00.000Z",
        instruction="SELL_TO_CLOSE", order_id="order-AAPL-part3",
    )
    patch_get_orders.state["orders"] = [part1, part2, part3]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "populated"
    assert result.candidates is not None
    assert len(result.candidates) == 3
    # Each candidate carries date / price / quantity / signature_hash.
    for cand in result.candidates:
        assert isinstance(cand, ExitAutoFillCandidate)
        assert cand.date is not None
        assert cand.price is not None
        assert cand.quantity is not None
        assert cand.signature_hash is not None
        assert isinstance(cand.signature_hash, str)
        assert len(cand.signature_hash) > 0
    # Per-candidate field values present (date sortable check ensures
    # all 3 partial dates surface).
    dates = sorted(c.date for c in result.candidates)
    assert dates == ["2026-05-16", "2026-05-17", "2026-05-18"]
    prices = sorted(c.price for c in result.candidates)
    assert prices == [160.00, 162.50, 165.00]
    # signature_hash values must be distinct per candidate (each fill is
    # a distinct broker-emitted event).
    sig_hashes = {c.signature_hash for c in result.candidates}
    assert len(sig_hashes) == 3, (
        "each candidate must have a distinct signature_hash"
    )


def test_f_credential_resolver_invoked_with_allow_prompt_false(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(f) TRACE: resolve_credentials_env_or_prompt called with
    allow_prompt=False.

    Per CLAUDE.md gotcha "form-render-time prompts would block HTTP
    handler" + dispatch brief §5 watch item 4 + plan §A.11 BINDING.
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert len(patch_credentials) == 1, (
        f"expected 1 call to resolve_credentials_env_or_prompt; "
        f"got {len(patch_credentials)}"
    )
    call = patch_credentials[0]
    assert call["allow_prompt"] is False, (
        f"BINDING: allow_prompt MUST be False at form-render path; "
        f"got {call['allow_prompt']!r}"
    )
    assert call["environment"] == "production"
    assert call["cfg"] is cfg


def test_g_client_factory_invoked_with_4_arg_signature(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(g) TRACE: construct_authenticated_client called with 4-arg
    signature (cfg, environment, client_id, client_secret) per post-
    Phase-12 Sub-bundle 1 + forward-binding lesson #10.
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert len(patch_client_factory) == 1, (
        f"expected 1 call to construct_authenticated_client; "
        f"got {len(patch_client_factory)}"
    )
    call = patch_client_factory[0]
    assert call["cfg"] is cfg
    assert call["environment"] == "production"
    assert call["client_id"] == "sentinel-client-id"
    assert call["client_secret"] == "sentinel-client-secret"


# ============================================================================
# Additional defensive tests (mirror T3.SB1 entry coverage)
# ============================================================================


def test_audit_surface_is_trade_exit(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """trader.get_account_orders called with surface='trade_exit' per
    spec §6.2 + schwab_api_calls.surface CHECK widening at v20.
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert len(patch_get_orders) == 1
    call = patch_get_orders[0]
    assert call["surface"] == "trade_exit", (
        f"BINDING: surface MUST be 'trade_exit' at exit auto-fill path; "
        f"got {call['surface']!r}"
    )
    assert call["environment"] == "production"
    assert call["pipeline_run_id"] is None


def test_buy_fills_filtered_out(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """BUY-side fills are NOT consumed by exit auto-fill (SELL-only)."""
    buy_order = _make_sell_order(
        ticker="AAPL", instruction="BUY",
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [buy_order]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty", (
        "BUY fills must be filtered; exit auto-fill is SELL-only"
    )


def test_sell_to_open_filtered_out(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R1 Major #6 — SELL_TO_OPEN is a short-OPENING instruction
    (entering a short position), NOT a close of a long position. Exit
    auto-fill MUST NOT surface it as a candidate fill for a long-position
    exit. Pre-fix: ``_SELL_INSTRUCTIONS`` included SELL_TO_OPEN +
    SELL_SHORT; this test would have returned 'populated'. Post-fix: only
    {SELL, SELL_TO_CLOSE} are recognised; SELL_TO_OPEN yields 'empty'.
    """
    sto_order = _make_sell_order(
        ticker="AAPL", instruction="SELL_TO_OPEN",
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [sto_order]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty", (
        "SELL_TO_OPEN is short-opening, NOT a long-exit; must be filtered"
    )


def test_sell_short_filtered_out(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R1 Major #6 — SELL_SHORT is a short-OPENING instruction;
    must NOT surface as a candidate fill for a long-position exit.
    Companion to test_sell_to_open_filtered_out.
    """
    ss_order = _make_sell_order(
        ticker="AAPL", instruction="SELL_SHORT",
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [ss_order]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty", (
        "SELL_SHORT is short-opening, NOT a long-exit; must be filtered"
    )


def test_wrong_ticker_filtered_out(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Orders for a different ticker filtered out by instrument_symbol."""
    other_ticker = _make_sell_order(
        ticker="MSFT", enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [other_ticker]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty"


def test_multileg_sell_fill_uses_vwap(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Multi-leg SELL fill computes VWAP via _compute_execution_price.

    Single multi-leg ORDER (one Schwab response) = one candidate, with
    execution-grain VWAP price + sum-of-leg-quantities quantity.
    """
    order = _make_multileg_sell_order(
        ticker="AAPL", legs=((160.0, 50.0), (162.0, 50.0)),
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [order]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "populated"
    # VWAP = (160*50 + 162*50) / 100 = 161.0
    assert result.exit_price == 161.0
    assert result.closed_shares == 100
    assert result.candidates is not None
    assert len(result.candidates) == 1


def test_account_hash_missing_returns_degraded(
    conn, fake_now, patch_live_state,
):
    """cfg.integrations.schwab.account_hash missing → degraded."""
    cfg = _make_cfg(environment="production", account_hash=None)
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"
    assert "account_hash" in (result.advisory_text or "")


def test_credentials_none_returns_degraded(
    conn, fake_now, patch_live_state, monkeypatch,
):
    """resolve_credentials_env_or_prompt returns (None, None) → degraded."""
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.resolve_credentials_env_or_prompt",
        lambda cfg, env, **kw: (None, None),
    )
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"


def test_credentials_partial_env_raises_returns_degraded(
    conn, fake_now, patch_live_state, monkeypatch,
):
    """SchwabConfigMissingError → degraded (not crash)."""
    def raiser(cfg, env, **kw):
        raise SchwabConfigMissingError("partial env-tier credentials")
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.resolve_credentials_env_or_prompt",
        raiser,
    )
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert "partial env-tier" in (result.advisory_text or "")


def test_schwab_api_error_returns_error_kind(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """trader.get_account_orders raises → result.kind='error'."""
    patch_get_orders.state["raises"] = SchwabApiError(
        500, "fake server error",
    )
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "error"
    assert result.fill_origin == "operator_typed"
    assert result.exit_price is None
    assert "fetch failed" in (result.advisory_text or "").lower()


def test_lookback_starts_at_entry_date(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The Schwab account_orders query lower bound is entry_date.

    Per dispatch brief: "Schwab account_orders ... for SELL fills matching
    ticker since entry_date".
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    call = patch_get_orders[0]
    # entry_date '2026-05-15' parsed to a UTC datetime at start-of-day.
    expected_from = datetime(2026, 5, 15, 0, 0, 0, tzinfo=UTC)
    assert call["from_dt"] == expected_from
    assert call["to_dt"] == fake_now


def test_existing_fill_order_ids_excludes_already_recorded_fills(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R1 Major #4 — already-recorded fills excluded from candidates.

    Plant 2 SELL orders from Schwab (ABC123 + DEF456). Pass
    ``existing_fill_order_ids={'ABC123'}`` to the resolver to simulate
    a partial_exited trade with an already-recorded SELL fill whose
    schwab_source_value_json envelope referenced order_id='ABC123'.

    Pre-fix: candidates list has length 2 (both orders surfaced; operator
    could pick ABC123 and create a duplicate fill row).
    Post-fix: candidates list has length 1 (only DEF456 — the new fill).
    """
    order_abc = _make_sell_order(
        ticker="AAPL", order_id="ABC123", price=150.0, quantity=50,
        enter_time="2026-05-17T14:30:00.000Z",
        instruction="SELL_TO_CLOSE",
    )
    order_def = _make_sell_order(
        ticker="AAPL", order_id="DEF456", price=155.0, quantity=50,
        enter_time="2026-05-19T14:30:00.000Z",
        instruction="SELL_TO_CLOSE",
    )
    patch_get_orders.state["orders"] = [order_abc, order_def]
    cfg = _make_cfg(environment="production")

    # WITHOUT exclusion: both candidates surface.
    result_all = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result_all.kind == "populated"
    assert result_all.candidates is not None
    assert len(result_all.candidates) == 2

    # WITH exclusion: only DEF456 (the new one) surfaces.
    result_filtered = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
        existing_fill_order_ids={"ABC123"},
    )
    assert result_filtered.kind == "populated"
    assert result_filtered.candidates is not None
    assert len(result_filtered.candidates) == 1
    assert result_filtered.candidates[0].order_id == "DEF456"


def test_existing_fill_order_ids_all_excluded_returns_empty(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R1 Major #4 — when ALL Schwab fills are already-recorded,
    candidate list collapses to empty (no new fills to surface)."""
    order_abc = _make_sell_order(
        ticker="AAPL", order_id="ABC123", price=150.0, quantity=50,
        enter_time="2026-05-17T14:30:00.000Z",
        instruction="SELL_TO_CLOSE",
    )
    patch_get_orders.state["orders"] = [order_abc]
    cfg = _make_cfg(environment="production")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
        existing_fill_order_ids={"ABC123"},
    )
    assert result.kind == "empty"


def test_exit_auto_fill_result_populated_requires_fill_origin_schwab_auto():
    """ExitAutoFillResult __post_init__: populated kind requires
    fill_origin='schwab_auto' (Literal validation per L6 + CLAUDE.md
    'Literal[...] type hints are NOT runtime-enforced' gotcha).
    """
    cand = ExitAutoFillCandidate(
        date="2026-05-19", price=100.0, quantity=100,
        signature_hash="abc123", order_id="o-1",
    )
    with pytest.raises(ValueError, match="populated"):
        ExitAutoFillResult(
            kind="populated",
            fill_origin="operator_typed",  # wrong
            exit_date="2026-05-19",
            exit_price=100.0,
            closed_shares=100,
            candidates=[cand],
        )


def test_exit_auto_fill_result_non_populated_requires_no_values():
    """Non-populated kinds must NOT carry exit_date/exit_price/closed_shares."""
    with pytest.raises(ValueError, match="must not carry"):
        ExitAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            exit_price=100.0,  # forbidden on non-populated
        )


def test_exit_auto_fill_result_invalid_kind_rejected():
    """__post_init__: kind not in frozenset rejected (Literal runtime guard)."""
    with pytest.raises(ValueError, match="kind"):
        ExitAutoFillResult(
            kind="bogus",  # type: ignore[arg-type]
            fill_origin="operator_typed",
        )


def test_exit_auto_fill_result_invalid_fill_origin_rejected():
    """__post_init__: fill_origin not in frozenset rejected (Literal runtime guard)."""
    with pytest.raises(ValueError, match="fill_origin"):
        ExitAutoFillResult(
            kind="empty",
            fill_origin="bogus",  # type: ignore[arg-type]
        )


def test_unresolvable_match_falls_through_to_empty_not_typeerror(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """T-B.2.1 reviewer fix — chosen-candidate from candidates list.

    Discriminating test: when a matching SELL order passes
    ``_is_execution_bearing_candidate`` (FILLED with price set) but
    LACKS executions (``executions=None``), the order-grain helpers
    ``_compute_execution_price`` and ``_resolve_match_quantity`` cannot
    surface execution-grain price; ``_build_candidate`` returns
    ``(None, 'no_execution_price')``; candidates list is empty; the service
    returns ``kind='empty'``. The refusal reason matters: only a
    ``'no_usable_date'`` refusal raises the D31 omission advisory, and this
    order is refused for a different reason, so no advisory is due.

    Pre-fix code path invoked ``int(_resolve_match_quantity(chosen_order))``
    on the raw order AFTER the candidates list was built. For analogous
    partial-then-canceled MARKET orders where quantity resolution yields
    None, this would have raised ``TypeError: int() argument must be ...
    not 'NoneType'``. Post-fix uses ``chosen = candidates[-1]`` so the
    chosen values come from the already-validated candidates list and
    such orders fall through to ``kind='empty'`` cleanly.
    """
    # FILLED + price set passes _is_execution_bearing_candidate, but
    # executions=None makes _compute_execution_price return None →
    # _build_candidate refuses with 'no_execution_price' → candidates empty.
    no_exec_order = SchwabOrderResponse(
        order_id="order-no-executions",
        status="FILLED",
        enter_time="2026-05-19T15:30:00.000Z",
        instrument_symbol="AAPL",
        instruction="SELL_TO_CLOSE",
        quantity=100,
        order_type="LIMIT",
        price=160.0,
        executions=None,  # legacy mapper path / sandbox / coherence-collapse
    )
    patch_get_orders.state["orders"] = [no_exec_order]
    cfg = _make_cfg(environment="production")
    # Must NOT raise TypeError; must return kind='empty' gracefully.
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty"
    assert result.fill_origin == "operator_typed"
    assert result.exit_price is None
    assert result.closed_shares is None
    assert result.candidates is None
    assert result.advisory_text is not None
    assert "execution-grain" in result.advisory_text.lower()


def test_exit_auto_fill_candidate_validates_fields():
    """ExitAutoFillCandidate.__post_init__: empty date/sig rejected."""
    with pytest.raises(ValueError, match="date"):
        ExitAutoFillCandidate(
            date="", price=100.0, quantity=100,
            signature_hash="abc", order_id="o-1",
        )
    with pytest.raises(ValueError, match="signature_hash"):
        ExitAutoFillCandidate(
            date="2026-05-19", price=100.0, quantity=100,
            signature_hash="", order_id="o-1",
        )
    with pytest.raises(ValueError, match="price"):
        ExitAutoFillCandidate(
            date="2026-05-19", price=-1.0, quantity=100,
            signature_hash="abc", order_id="o-1",
        )
    with pytest.raises(ValueError, match="quantity"):
        ExitAutoFillCandidate(
            date="2026-05-19", price=100.0, quantity=0,
            signature_hash="abc", order_id="o-1",
        )


# ============================================================================
# D31 exit-side follow-on — the exit date is the EXECUTION date
#
# Frozen clocks throughout: this whole section is about dates, so a live clock
# here would be a false green waiting for a session boundary.
# ============================================================================

# The live founding case: fill 40 (trade 19, FTRE, action='stop'). The stop
# rested from 2026-08-03 and executed 2026-08-04; the framework proposed
# 2026-08-03 and the operator corrected it by hand.
_FTRE_ENTERED = "2026-08-03T13:45:00.000Z"
_FTRE_EXECUTED = "2026-08-04T13:30:05.000Z"


@pytest.fixture
def d31_now() -> datetime:
    """Frozen 'now' for the D31 cases (the live FTRE window)."""
    return datetime(2026, 8, 4, 20, 0, 0, tzinfo=UTC)


def _resolve_ftre(conn, now, orders, **kwargs):
    """Run the resolver over ``orders`` with the FTRE trade's real anchors."""
    return resolve_exit_auto_fill(
        trade_id=19, ticker="FTRE", entry_date="2026-07-23",
        cfg=_make_cfg(environment="production"), conn=conn, now=now,
        **kwargs,
    )


def test_d31_candidate_date_is_the_execution_date_not_the_entered_date(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The founding case. Pre-fix this resolves 2026-08-03 and fails.

    ``_extract_iso_date(o.enter_time)`` read when the ORDER WAS PLACED. The
    fill happened the next session, and `fills.fill_datetime` is defined as
    when the EXIT happened (`swing/trades/exit.py`), so the entered date was
    never the value this form should default to.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time=_FTRE_ENTERED, execution_time=_FTRE_EXECUTED,
        instruction="SELL", order_id="order-FTRE-stop",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    assert result.kind == "populated"
    assert result.exit_date == "2026-08-04"
    assert result.candidates is not None
    chosen = result.candidates[-1]
    assert chosen.date == "2026-08-04"

    envelope = json.loads(result.schwab_source_value_json)
    assert envelope["exit_date"] == "2026-08-04"
    assert envelope["exit_date_source"] == "execution_leg"
    entry = envelope["candidates_map"][chosen.signature_hash]
    assert entry["date"] == "2026-08-04"
    assert entry["date_source"] == "execution_leg"


def test_d31_date_source_is_per_candidate_not_one_stamp_for_the_list(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Per-row provenance (gotcha #30), on the surface that has N rows.

    Two candidates whose dates come from DIFFERENT grains: the first from its
    execution leg, the second falling back to the entered date because its leg
    time is unusable. A single top-level stamp would label one of them wrongly,
    and the operator can SELECT either -- the POST handler reads
    ``candidates_map[submitted_hash]`` as authoritative, not the top level.

    Also locks the agreement the POST handler depends on: the envelope's top
    level, the chosen candidate, and that candidate's map entry carry ONE date.
    A disagreement there would flip ``fill_origin`` to
    ``schwab_auto_then_operator_corrected`` for an operator who edited nothing.
    """
    from_leg = _make_sell_order(
        ticker="FTRE", price=18.10, quantity=4,
        enter_time="2026-08-01T13:45:00.000Z",
        execution_time="2026-08-03T17:00:00.000Z",
        instruction="SELL", order_id="order-FTRE-part1",
    )
    from_entered = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=6,
        enter_time="2026-08-04T13:45:00.000Z",
        execution_time="not-a-timestamp",
        instruction="SELL", order_id="order-FTRE-part2",
    )
    patch_get_orders.state["orders"] = [from_leg, from_entered]
    result = _resolve_ftre(conn, d31_now, [from_leg, from_entered])

    assert result.kind == "populated"
    assert result.candidates is not None
    assert len(result.candidates) == 2
    envelope = json.loads(result.schwab_source_value_json)
    by_order = {
        cand.order_id: envelope["candidates_map"][cand.signature_hash]
        for cand in result.candidates
    }
    assert by_order["order-FTRE-part1"]["date"] == "2026-08-03"
    assert by_order["order-FTRE-part1"]["date_source"] == "execution_leg"
    assert by_order["order-FTRE-part2"]["date"] == "2026-08-04"
    assert by_order["order-FTRE-part2"]["date_source"] == "enter_time"

    chosen = result.candidates[-1]
    assert result.exit_date == chosen.date
    assert envelope["exit_date"] == chosen.date
    assert envelope["candidates_map"][chosen.signature_hash]["date"] == chosen.date
    assert envelope["exit_date_source"] == (
        envelope["candidates_map"][chosen.signature_hash]["date_source"]
    )
    for cand in result.candidates:
        cand_entry = envelope["candidates_map"][cand.signature_hash]
        assert cand_entry["date"] == cand.date
        assert cand_entry["price"] == cand.price
        assert cand_entry["quantity"] == cand.quantity


def test_d31_entered_time_fallback_is_reachable_and_stamped(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The fallback's REACHABILITY, pinned in a test rather than a comment.

    The reachable fallback for a real CANDIDATE is a PRESENT-but-unusable leg
    TIME: ``SchwabExecutionLeg.__post_init__`` validates ``time`` as NON-EMPTY,
    never as parseable, so any non-empty string arrives at the derivation.

    (An EMPTY execution list also reaches the derivation -- via
    ``_candidate_sort_key`` during ``sorted()`` -- but such an order is refused
    for ``'no_execution_price'`` and never becomes a candidate. That half is
    pinned separately by
    ``test_d31_execution_date_helper_falls_back_when_executions_absent``.)
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time=_FTRE_ENTERED, execution_time="not-a-timestamp",
        instruction="SELL", order_id="order-FTRE-badleg",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    assert result.kind == "populated"
    assert result.exit_date == "2026-08-03"
    envelope = json.loads(result.schwab_source_value_json)
    assert envelope["exit_date_source"] == "enter_time"


def test_d31_sort_key_reaches_the_date_derivation_before_price_resolution(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders, monkeypatch,
):
    """The CONTROL FLOW claim, pinned where it actually lives (Codex R4 Minor).

    The unit test below pins what ``_execution_date`` DOES with an absent leg
    list. It does NOT pin that the resolver ever calls it with one -- delete
    the call from ``_candidate_sort_key`` and that test stays green while its
    docstring's claim quietly becomes false, which is the fixture-routes-around
    -the-branch shape.

    So: spy on the module-global derivation and resolve a no-legs order.
    ``_build_candidate`` refuses it for ``no_execution_price`` before deriving
    any date (verified: it makes zero derivation calls for such an order).

    ``_warn_on_mixed_candidate_offsets`` IS STUBBED OUT, and that is the point
    of this fix (Codex R5 Minor). It also calls ``_execution_date``, and it was
    added by the same round that added this test -- so the round's own canary
    silently gave the round's own test a second way to pass, and removing the
    sort-key call would have left it green. A spy test is only evidence while
    exactly one caller can satisfy it, so the other one is removed rather than
    assumed harmless.
    """
    import swing.trades.exit_auto_fill as module
    seen: list[str | None] = []
    real = module._execution_date

    def spy(order):
        seen.append(getattr(order, "order_id", None))
        return real(order)

    monkeypatch.setattr(module, "_execution_date", spy)
    monkeypatch.setattr(
        module, "_warn_on_mixed_candidate_offsets",
        lambda ticker, matches: None,
    )
    no_legs = SchwabOrderResponse(
        order_id="order-no-legs", status="FILLED",
        enter_time="2026-08-03T13:45:00.000Z", instrument_symbol="FTRE",
        instruction="SELL", quantity=10, order_type="LIMIT", price=18.40,
        executions=None,
    )
    patch_get_orders.state["orders"] = [no_legs]
    result = _resolve_ftre(conn, d31_now, [no_legs])

    assert result.kind == "empty", "a no-legs order must not become a candidate"
    assert "order-no-legs" in seen, (
        "the sort key must reach the date derivation for an order whose "
        "price check will later refuse it"
    )


def test_d31_execution_date_helper_falls_back_when_executions_absent():
    """Direct unit pin of ``_execution_date``'s absent-executions branch.

    Codex R3 Minor -- a docstring claimed this branch was unreachable because
    ``_compute_execution_price`` refuses an empty leg list first. It is
    reachable through the sort key. This test pins the helper's own behaviour;
    the test above pins that the resolver reaches it.
    """
    from swing.trades.exit_auto_fill import _execution_date
    order = SchwabOrderResponse(
        order_id="order-no-legs",
        status="FILLED",
        enter_time="2026-08-03T13:45:00.000Z",
        instrument_symbol="FTRE",
        instruction="SELL",
        quantity=10,
        order_type="LIMIT",
        price=18.40,
        executions=None,
    )
    assert _execution_date(order) == ("2026-08-03", "enter_time")
    order_empty_legs = SchwabOrderResponse(
        order_id="order-empty-legs",
        status="FILLED",
        enter_time="2026-08-03T13:45:00.000Z",
        instrument_symbol="FTRE",
        instruction="SELL",
        quantity=10,
        order_type="LIMIT",
        price=18.40,
        executions=[],
    )
    assert _execution_date(order_empty_legs) == ("2026-08-03", "enter_time")


def test_d31_execution_before_the_order_falls_back_visibly(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """An execution cannot precede its own order; the shared rule refuses it.

    The RESPONSE is this consumer's own -- a VISIBLE fallback to the entered
    date, because this is a form default the operator sees and can override,
    not a ledger rewrite.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time="2026-08-04T13:45:00.000Z",
        execution_time="2026-08-03T13:30:05.000Z",
        instruction="SELL", order_id="order-FTRE-backwards",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    assert result.kind == "populated"
    assert result.exit_date == "2026-08-04"
    envelope = json.loads(result.schwab_source_value_json)
    assert envelope["exit_date_source"] == "enter_time"


def test_d31_malformed_entered_time_does_not_discard_a_good_execution_date(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R4 Minor -- the chronology rule compares CANONICAL values only.

    An earlier draft fed the raw ``_extract_iso_date`` SLICE of ``enter_time``
    to ``execution_precedes_order``. That slice is not a date: ``9999-99-99``
    (verified: ``_extract_iso_date('9999-99-99Tjunk')`` returns exactly that)
    sorts lexically after every real execution date, so the chronology rule
    fired, the good execution-grain date was thrown away, and the fallback then
    refused the same garbage -- losing the whole candidate on the evidence of
    an unrelated malformed field.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time="9999-99-99Tjunk", execution_time=_FTRE_EXECUTED,
        instruction="SELL", order_id="order-FTRE-bad-enter-time",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    assert result.kind == "populated"
    assert result.exit_date == "2026-08-04"
    envelope = json.loads(result.schwab_source_value_json)
    assert envelope["exit_date_source"] == "execution_leg"


def test_d31_mixed_offsets_across_candidates_order_by_local_date_and_warn(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders, caplog,
):
    """Codex R4 Major -- the residue, RECORDED with its canary.

    Two orders whose offset-local dates and absolute instants disagree: A
    executed 2026-08-04T23:00-10:00 (absolute 08-05T09:00Z) and B executed
    2026-08-05T01:00+14:00 (absolute 08-04T11:00Z). Ordering by local date puts
    A first and defaults to B; ordering by absolute instant would reverse them.

    The list is ordered by LOCAL DATE, deliberately: it is the value displayed
    to the operator and the value recorded when he accepts, so an
    instant-primary order would show 2026-08-05 above 2026-08-04 and default to
    the row reading earlier. `latest_execution_leg_date` refuses this same
    ambiguity WITHIN one order and cannot see across orders, so the condition
    is logged. Schwab emits +0000 on every leg, making this a canary rather
    than a live path -- which is exactly why it is pinned rather than trusted
    to stay unreachable.
    """
    west = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=6,
        enter_time="2026-08-03T13:00:00+00:00",
        execution_time="2026-08-04T23:00:00-10:00",
        instruction="SELL", order_id="order-FTRE-west",
    )
    east = _make_sell_order(
        ticker="FTRE", price=18.10, quantity=4,
        enter_time="2026-08-03T13:00:00+00:00",
        execution_time="2026-08-05T01:00:00+14:00",
        instruction="SELL", order_id="order-FTRE-east",
    )
    patch_get_orders.state["orders"] = [west, east]
    with caplog.at_level(logging.WARNING, logger="swing.trades.exit_auto_fill"):
        result = _resolve_ftre(conn, d31_now, [west, east])

    assert result.kind == "populated"
    assert result.candidates is not None
    assert [c.date for c in result.candidates] == ["2026-08-04", "2026-08-05"]
    assert result.exit_date == "2026-08-05"
    assert any(
        "different utc offsets" in rec.message for rec in caplog.records
    ), "the mixed-offset canary must fire"


def test_d31_non_canonical_entered_time_declines_the_candidate(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A basic-format ``enter_time`` must not become a form default.

    ``_extract_iso_date`` only splits on ``T``/space and slices, so
    ``20260803T134500`` reduced to ``"20260803"`` -- not a date, and one that
    every downstream ``[:10]`` prefix and LEXICAL date comparison in the
    project would then mis-order. ``fills.fill_datetime`` is a bare
    ``TEXT NOT NULL`` and ``record_exit`` normalizes rather than refuses, so
    nothing further down catches it. The candidate is declined instead.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time="20260803T134500", execution_time="not-a-timestamp",
        instruction="SELL", order_id="order-FTRE-basicformat",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    assert result.kind == "empty"
    assert result.exit_date is None
    assert result.candidates is None
    assert result.advisory_text is not None


def test_d31_derived_exit_date_satisfies_the_reconciliation_session_guard(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """THE EXIT-SIDE INVARIANT, cross-checked against its actual consumer.

    There is no ``trades.exit_date``. The exit date is SINGLE-HOMED in
    ``fills.fill_datetime``, derives into ``trades.last_fill_at``
    (``MAX(fill_datetime)``), and is CHECKED against the broker by
    ``_fill_execution_session_distance``, which measures the NYSE-session
    distance between ``fill_datetime[:10]`` and the order's execution legs.
    That guard already reads the fill as carrying the EXECUTION date.

    The second assertion is what makes this test distinguish: under the
    pre-fix derivation the proposed date sat one session away from the
    execution it claims to record. It also shows why the defect was not loud
    -- the classifier admits tier-1 through
    ``_MAX_TIER1_SESSION_DISTANCE == 1``, so this one-session error passed the
    guard silently and had to be caught by hand.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time=_FTRE_ENTERED, execution_time=_FTRE_EXECUTED,
        instruction="SELL", order_id="order-FTRE-stop",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    derived = _normalize_trade_event_date_to_iso(
        result.exit_date, field_name="exit_date",
    )
    assert _fill_execution_session_distance(derived, order) == 0

    entered = _normalize_trade_event_date_to_iso(
        "2026-08-03", field_name="exit_date",
    )
    assert _fill_execution_session_distance(entered, order) == 1


def test_d31_dedupe_tuple_matches_the_recorded_execution_date(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The fallback dedupe compares like with like.

    ``build_exit_form_vm`` builds each existing tuple from the stored fill's
    OWN ``fill_datetime`` -- an EXECUTION date. Pre-fix the candidate side
    contributed the ORDER-ENTERED date, so an already-recorded resting-stop
    fill failed to match its own candidate and the form re-offered it. That
    is the live shape: fill 40 is stored at 2026-08-04 while the candidate
    dated itself 2026-08-03.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time=_FTRE_ENTERED, execution_time=_FTRE_EXECUTED,
        instruction="SELL", order_id="order-FTRE-stop",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(
        conn, d31_now, [order],
        existing_fill_value_tuples={("2026-08-04", 18.40, 10)},
    )
    assert result.kind == "empty"


def test_d31_dedupe_tuple_no_longer_matches_the_entered_date(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The other direction of the same correction, stated explicitly.

    A recorded fill dated 2026-08-03 is a DIFFERENT fill from an order that
    executed on 2026-08-04, and pre-fix the candidate collapsed onto it --
    the over-merge direction, where the surface goes quiet instead of
    offering a real unrecorded fill.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time=_FTRE_ENTERED, execution_time=_FTRE_EXECUTED,
        instruction="SELL", order_id="order-FTRE-stop",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(
        conn, d31_now, [order],
        existing_fill_value_tuples={("2026-08-03", 18.40, 10)},
    )
    assert result.kind == "populated"
    assert result.exit_date == "2026-08-04"


def test_d31_dedupe_tuple_set_still_over_merges_ambiguous_candidates(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The FLAGGED residue, pinned as it actually behaves (Codex R1 Major 1).

    ``existing_fill_value_tuples`` is a SET with no multiplicity, so ONE
    recorded fill excludes EVERY candidate sharing its (date, price, quantity)
    tuple. Two equal clips at one price on one session -- an ordinary
    scale-out -- therefore both vanish once either is recorded.

    This test EXISTS TO RECORD THAT, not to bless it. It is a pre-existing
    property of the lossy fallback key, not of the date grain this arc
    corrected: before D31 the same collision happened on a shared
    ORDER-ENTERED date. Changing it is an operator-facing call (a silent
    omission versus a visible duplicate-record invitation) against a shipped,
    separately-tested contract, so it is routed up rather than decided here.
    If a later arc changes the behaviour, this test is the thing it must
    deliberately rewrite -- which is the point of pinning it.
    """
    twin_a = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=5,
        enter_time="2026-08-03T13:45:00.000Z",
        execution_time="2026-08-04T13:30:05.000Z",
        instruction="SELL", order_id="order-FTRE-twin-a",
    )
    twin_b = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=5,
        enter_time="2026-08-03T14:45:00.000Z",
        execution_time="2026-08-04T15:30:05.000Z",
        instruction="SELL", order_id="order-FTRE-twin-b",
    )
    patch_get_orders.state["orders"] = [twin_a, twin_b]
    result = _resolve_ftre(
        conn, d31_now, [twin_a, twin_b],
        existing_fill_value_tuples={("2026-08-04", 18.40, 5)},
    )
    assert result.kind == "empty"


def test_d31_undated_fill_omitted_from_a_populated_list_is_announced(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R1 Major 2 -- a short list must not look complete.

    One order has a real price and quantity but no usable date at EITHER grain
    (unusable leg time AND a basic-format `enter_time`), so it cannot become a
    candidate. Another order is fine. Dropping the first silently would show
    the operator a list that omits a fill he actually made; the populated
    result carries an advisory naming the omission instead, and the template
    renders `auto_fill_advisory_text` whenever it is set.
    """
    good = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=6,
        enter_time="2026-08-03T13:45:00.000Z",
        execution_time="2026-08-04T13:30:05.000Z",
        instruction="SELL", order_id="order-FTRE-good",
    )
    undated = _make_sell_order(
        ticker="FTRE", price=18.10, quantity=4,
        enter_time="20260803T134500", execution_time="not-a-timestamp",
        instruction="SELL", order_id="order-FTRE-undated",
    )
    patch_get_orders.state["orders"] = [good, undated]
    result = _resolve_ftre(conn, d31_now, [good, undated])

    assert result.kind == "populated"
    assert result.candidates is not None
    assert [c.order_id for c in result.candidates] == ["order-FTRE-good"]
    assert result.advisory_text is not None
    assert "1 Schwab SELL fill(s)" in result.advisory_text
    assert "not listed" in result.advisory_text.lower()
    assert result.advisory_text.isascii()


def test_d31_populated_without_omissions_carries_no_advisory(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """The omission advisory must not become standing noise.

    An advisory on every populated result would train the operator to ignore
    the one case where it means something.
    """
    order = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=10,
        enter_time=_FTRE_ENTERED, execution_time=_FTRE_EXECUTED,
        instruction="SELL", order_id="order-FTRE-stop",
    )
    patch_get_orders.state["orders"] = [order]
    result = _resolve_ftre(conn, d31_now, [order])

    assert result.kind == "populated"
    assert result.advisory_text is None


def test_d31_same_day_default_is_the_latest_execution_instant(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Codex R1 Major 3 -- the same-date tiebreak is the EXECUTION instant.

    Both fills executed on 2026-08-04, so the date cannot separate them. The
    one ENTERED later executed EARLIER; ranking the tie on `enter_time` would
    default the form to the 10:01 fill because its order was typed second.
    Exact execution timestamps exist, so the ranking uses them.
    """
    entered_first = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=6,
        enter_time="2026-08-04T13:00:00.000Z",
        execution_time="2026-08-04T19:59:00.000Z",
        instruction="SELL", order_id="order-FTRE-late-exec",
    )
    entered_second = _make_sell_order(
        ticker="FTRE", price=18.10, quantity=4,
        enter_time="2026-08-04T14:00:00.000Z",
        execution_time="2026-08-04T14:01:00.000Z",
        instruction="SELL", order_id="order-FTRE-early-exec",
    )
    patch_get_orders.state["orders"] = [entered_first, entered_second]
    result = _resolve_ftre(conn, d31_now, [entered_first, entered_second])

    assert result.kind == "populated"
    assert result.candidates is not None
    assert [c.order_id for c in result.candidates] == [
        "order-FTRE-early-exec", "order-FTRE-late-exec",
    ]
    assert result.closed_shares == 6


def test_d31_entered_time_fallback_never_ranks_as_a_known_instant(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A fallback-dated candidate is not ranked as though we knew its instant.

    Both land on 2026-08-04; one from its execution leg, one from a bare
    `enter_time` with an unusable leg. The genuinely-dated fill is preferred
    as the default no matter what hour the fallback's entered timestamp
    carries -- there is no execution instant to compare it against.
    """
    from_leg = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=6,
        enter_time="2026-08-03T13:00:00.000Z",
        execution_time="2026-08-04T14:00:00.000Z",
        instruction="SELL", order_id="order-FTRE-from-leg",
    )
    from_entered = _make_sell_order(
        ticker="FTRE", price=18.10, quantity=4,
        enter_time="2026-08-04T19:59:00.000Z",
        execution_time="not-a-timestamp",
        instruction="SELL", order_id="order-FTRE-from-entered",
    )
    patch_get_orders.state["orders"] = [from_leg, from_entered]
    result = _resolve_ftre(conn, d31_now, [from_leg, from_entered])

    assert result.kind == "populated"
    assert result.candidates is not None
    assert [c.order_id for c in result.candidates] == [
        "order-FTRE-from-entered", "order-FTRE-from-leg",
    ]
    assert result.closed_shares == 6


def test_d31_default_candidate_is_the_latest_execution_not_the_latest_entry(
    conn, d31_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """"Most recent" means most recently EXECUTED.

    ``early_entry`` was placed first and filled LAST (a resting stop);
    ``late_entry`` was placed second and filled the SAME day. Sorting the
    candidate list by ``enter_time`` defaults the form to the order the
    operator TYPED last, which is not the fill he is recording.
    """
    early_entry = _make_sell_order(
        ticker="FTRE", price=18.40, quantity=6,
        enter_time="2026-08-03T13:45:00.000Z",
        execution_time="2026-08-06T13:30:05.000Z",
        instruction="SELL", order_id="order-FTRE-resting",
    )
    late_entry = _make_sell_order(
        ticker="FTRE", price=18.10, quantity=4,
        enter_time="2026-08-04T13:45:00.000Z",
        execution_time="2026-08-05T13:30:05.000Z",
        instruction="SELL", order_id="order-FTRE-sameday",
    )
    patch_get_orders.state["orders"] = [early_entry, late_entry]
    result = resolve_exit_auto_fill(
        trade_id=19, ticker="FTRE", entry_date="2026-07-23",
        cfg=_make_cfg(environment="production"), conn=conn,
        now=datetime(2026, 8, 6, 20, 0, 0, tzinfo=UTC),
    )

    assert result.kind == "populated"
    assert result.candidates is not None
    assert [c.date for c in result.candidates] == ["2026-08-05", "2026-08-06"]
    assert result.exit_date == "2026-08-06"
    assert result.closed_shares == 6
