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
from swing.trades.exit_auto_fill import (
    ExitAutoFillCandidate,
    ExitAutoFillResult,
    resolve_exit_auto_fill,
)

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
) -> SchwabOrderResponse:
    """Build a production-emitter-shape SchwabOrderResponse representing a
    SELL fill with one execution leg. Per CLAUDE.md "Synthetic-fixture-vs-
    production-emitter shape drift" gotcha — tests use the real dataclass,
    not a stub.
    """
    leg = SchwabExecutionLeg(
        leg_id=1,
        price=price,
        quantity=quantity,
        mismarked_quantity=None,
        instrument_id=12345,
        time=enter_time,
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
    surface execution-grain price; ``_build_candidate`` returns None;
    candidates list is empty; the service returns ``kind='empty'``.

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
    # _build_candidate returns None → candidates list is empty.
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
