"""Phase 13 T3.SB1 T-B.1.2 — entry_auto_fill module tests.

Per plan §G.2 T-B.1.2 step 1 + dispatch brief §5 watch items 3, 4, 12-15:

  (a) matching Schwab BUY fill returns AutoFillResult with populated
      values + fill_origin='schwab_auto'
  (b) empty Schwab response → empty result + fill_origin='operator_typed'
  (c) sandbox short-circuits
  (d) DEGRADED short-circuits with advisory
  (e) trace test: resolve_credentials_env_or_prompt invoked with
      allow_prompt=False (mock-verified per Codex R1 Major #5 closure
      pattern + CLAUDE.md gotcha "form-render-time prompts would block
      HTTP handler")
  (f) trace test: construct_authenticated_client invoked with 4-arg
      signature (cfg, environment, client_id, client_secret) per post-
      Phase-12 Sub-bundle 1 + forward-binding lesson #10

Additional defensive tests:
  (g) account_hash missing → degraded
  (h) credentials None under allow_prompt=False → degraded
  (i) Schwab call raises SchwabApiError → error kind
  (j) production-emitter-shape SchwabOrderResponse (NOT synthetic) used
      throughout (per CLAUDE.md "Synthetic-fixture-vs-production-emitter
      shape drift" gotcha)
  (k) BUY-side instruction filter (rejects SELL fills for entry auto-fill)
  (l) most-recent-by-enter_time tiebreaker when multiple BUY candidates
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from swing.trades.entry_auto_fill import (
    DEFAULT_LOOKBACK_DAYS,
    EntryAutoFillResult,
    resolve_entry_auto_fill,
)

# ============================================================================
# Shared fixtures
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


def _make_buy_order(
    *,
    ticker: str = "AAPL",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    price: float = 123.45,
    quantity: float = 100,
    order_type: str = "LIMIT",
    instruction: str = "BUY",
    status: str = "FILLED",
    order_id: str | None = None,
) -> SchwabOrderResponse:
    """Build a production-emitter-shape SchwabOrderResponse with one execution
    leg at price * quantity. Per CLAUDE.md "Synthetic-fixture-vs-production-
    emitter shape drift" gotcha — tests use the real dataclass, not a stub.
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


def _make_multileg_buy_order(
    *,
    ticker: str = "AAPL",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    legs: tuple[tuple[float, float], ...] = ((100.0, 50.0), (102.0, 50.0)),
) -> SchwabOrderResponse:
    """Multi-leg fill: ``legs`` is a tuple of ``(price, quantity)`` pairs.

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
        instruction="BUY",
        quantity=total_qty,
        order_type="MARKET",
        price=None,  # MARKET orders may have price=None
        executions=execution_legs,
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Schema-initialized in-memory connection (v20)."""
    db_path = tmp_path / "eaf_test.db"
    c = ensure_schema(db_path)
    yield c
    c.close()


@pytest.fixture
def fake_now() -> datetime:
    """Fixed 'now' for deterministic lookback windows."""
    return datetime(2026, 5, 19, 14, 30, 0, tzinfo=UTC)


@pytest.fixture
def patch_live_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force _compute_degraded_state to return ('LIVE', None) so production-
    path tests don't trip on missing tokens DB / empty `schwab_api_calls`.

    Tests that exercise DEGRADED branch monkeypatch this differently.
    """
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: ("LIVE", None),
    )


@pytest.fixture
def patch_credentials(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch resolve_credentials_env_or_prompt to record call kwargs +
    return canned credentials. Returns a list the test can inspect.
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
        "swing.trades.entry_auto_fill.resolve_credentials_env_or_prompt",
        fake_resolver,
    )
    return calls


@pytest.fixture
def patch_client_factory(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch construct_authenticated_client to record positional args +
    return a sentinel client object.
    """
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
        "swing.trades.entry_auto_fill.construct_authenticated_client",
        fake_factory,
    )
    return calls


class _OrdersCallRecorder(list):
    """List subclass that also carries a ``state`` dict for fixture
    seam mutation. Plain ``list`` rejects __dict__ attribute setting on
    CPython 3.14; subclass adds __slots__-compatible storage."""

    def __init__(self) -> None:
        super().__init__()
        self.state: dict[str, Any] = {"orders": [], "raises": None}


@pytest.fixture
def patch_get_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> _OrdersCallRecorder:
    """Patch trader.get_account_orders. Returns a recorder whose
    ``.state`` dict the test mutates to set orders / raises behavior.
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
        "swing.trades.entry_auto_fill.trader.get_account_orders",
        fake_get,
    )
    return recorder


# ============================================================================
# Tests
# ============================================================================


def test_a_matching_buy_fill_returns_populated(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(a) matching Schwab BUY fill → populated result + fill_origin='schwab_auto'."""
    order = _make_buy_order(
        ticker="AAPL", price=150.25, quantity=100,
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [order]
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert isinstance(result, EntryAutoFillResult)
    assert result.kind == "populated"
    assert result.fill_origin == "schwab_auto"
    assert result.entry_price == 150.25
    assert result.shares == 100
    assert result.entry_date == "2026-05-19"
    assert result.auto_fill_audit_at is not None
    assert result.schwab_source_value_json is not None
    assert "150.25" in result.schwab_source_value_json
    assert "AAPL" in result.schwab_source_value_json or "150.25" in result.schwab_source_value_json


def test_a_multileg_buy_fill_uses_vwap(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Multi-leg BUY fill computes VWAP via _compute_execution_price."""
    order = _make_multileg_buy_order(
        ticker="AAPL", legs=((100.0, 50.0), (102.0, 50.0)),
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [order]
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "populated"
    # VWAP = (100*50 + 102*50) / 100 = 101.0
    assert result.entry_price == 101.0
    assert result.shares == 100


def test_b_empty_schwab_response_returns_empty(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(b) Schwab returns no orders → empty + fill_origin='operator_typed'."""
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty"
    assert result.fill_origin == "operator_typed"
    assert result.entry_price is None
    assert result.shares is None
    assert result.entry_date is None
    assert result.advisory_text is not None
    assert "no matching" in result.advisory_text.lower()


def test_c_sandbox_short_circuits(conn, fake_now):
    """(c) cfg.integrations.schwab.environment == 'sandbox' short-circuits.

    Verifies (1) result.kind='sandbox_short_circuit',
    (2) result.fill_origin='operator_typed',
    (3) NO Schwab call fires — monkeypatch verifies via raise.
    """
    cfg = _make_cfg(environment="sandbox")
    # Sandbox short-circuit must fire BEFORE any Schwab dependency call.
    # We do NOT install the patch_credentials/patch_client_factory/
    # patch_get_orders fixtures — if the service reached them, it would
    # try to import schwabdev (via real construct_authenticated_client)
    # and the test would fail with a different error. Sandbox short-
    # circuit is the only correct path.
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "sandbox_short_circuit"
    assert result.fill_origin == "operator_typed"
    assert result.entry_price is None
    assert result.shares is None
    assert result.advisory_text is not None
    assert "sandbox" in result.advisory_text.lower()


def test_d_degraded_short_circuits(
    conn, fake_now, monkeypatch,
):
    """(d) _compute_degraded_state returns 'DEGRADED' → degraded result."""
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: (
            "DEGRADED", "refresh_token expired"
        ),
    )
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"
    assert result.advisory_text is not None
    assert "refresh_token expired" in result.advisory_text


def test_d_provisional_treated_as_degraded(
    conn, fake_now, monkeypatch,
):
    """PROVISIONAL state (not yet configured) also short-circuits as degraded."""
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: (
            "PROVISIONAL", "tokens DB missing — not configured yet"
        ),
    )
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"
    assert "tokens DB missing" in (result.advisory_text or "")


def test_e_credential_resolver_invoked_with_allow_prompt_false(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(e) TRACE: resolve_credentials_env_or_prompt called with allow_prompt=False.

    Per CLAUDE.md gotcha "form-render-time prompts would block HTTP handler"
    + dispatch brief §5 watch item 4 + plan §A.11 BINDING.
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    # Verify resolve_credentials_env_or_prompt was called exactly once
    # with allow_prompt=False keyword.
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


def test_f_client_factory_invoked_with_4_arg_signature(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(f) TRACE: construct_authenticated_client called with 4-arg signature.

    Per post-Phase-12 Sub-bundle 1 + forward-binding lesson #10 + dispatch
    brief §5 watch item 3 + plan §A.11 BINDING.
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert len(patch_client_factory) == 1, (
        f"expected 1 call to construct_authenticated_client; "
        f"got {len(patch_client_factory)}"
    )
    call = patch_client_factory[0]
    # 4-arg signature: (cfg, environment, client_id, client_secret).
    assert call["cfg"] is cfg
    assert call["environment"] == "production"
    assert call["client_id"] == "sentinel-client-id"
    assert call["client_secret"] == "sentinel-client-secret"


def test_f_audit_surface_is_trade_entry(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """trader.get_account_orders called with surface='trade_entry'.

    Per spec §6.1 audit-row emit + dispatch brief §5 watch item 11 +
    schwab_api_calls.surface CHECK widening at v20.
    """
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert len(patch_get_orders) == 1
    call = patch_get_orders[0]
    assert call["surface"] == "trade_entry", (
        f"BINDING: surface MUST be 'trade_entry' at entry auto-fill path; "
        f"got {call['surface']!r}"
    )
    assert call["environment"] == "production"
    assert call["pipeline_run_id"] is None, (
        "form-render fetch is NOT pipeline-bound"
    )


def test_g_account_hash_missing_returns_degraded(
    conn, fake_now, patch_live_state,
):
    """(g) cfg.integrations.schwab.account_hash missing → degraded."""
    cfg = _make_cfg(environment="production", account_hash=None)
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"
    assert "account_hash" in (result.advisory_text or "")


def test_h_credentials_none_returns_degraded(
    conn, fake_now, patch_live_state, monkeypatch,
):
    """(h) resolve_credentials_env_or_prompt returns (None, None) → degraded."""
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.resolve_credentials_env_or_prompt",
        lambda cfg, env, **kw: (None, None),
    )
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert result.fill_origin == "operator_typed"


def test_h_credentials_partial_env_raises_returns_degraded(
    conn, fake_now, patch_live_state, monkeypatch,
):
    """SchwabConfigMissingError from resolve_credentials → degraded (not crash)."""
    def raiser(cfg, env, **kw):
        raise SchwabConfigMissingError("partial env-tier credentials")
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.resolve_credentials_env_or_prompt",
        raiser,
    )
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "degraded"
    assert "partial env-tier" in (result.advisory_text or "")


def test_i_schwab_api_error_returns_error_kind(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(i) trader.get_account_orders raises → result.kind='error'."""
    patch_get_orders.state["raises"] = SchwabApiError(
        500, "fake server error",
    )
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "error"
    assert result.fill_origin == "operator_typed"
    assert result.entry_price is None
    assert "fetch failed" in (result.advisory_text or "").lower()


def test_k_sell_fills_filtered_out(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(k) SELL-side fills are NOT consumed by entry auto-fill (BUY-only)."""
    sell_order = _make_buy_order(
        ticker="AAPL", instruction="SELL_TO_CLOSE",
        enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [sell_order]
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty", (
        "SELL fills must be filtered; entry auto-fill is BUY-only"
    )


def test_k_wrong_ticker_filtered_out(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """Orders for a different ticker filtered out by instrument_symbol."""
    other_ticker = _make_buy_order(
        ticker="MSFT", enter_time="2026-05-19T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [other_ticker]
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "empty"


def test_l_most_recent_by_enter_time_wins(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """(l) Multiple matching BUY candidates → most-recent enter_time wins."""
    older = _make_buy_order(
        ticker="AAPL", price=100.0, quantity=50,
        enter_time="2026-05-15T14:30:00.000Z",
    )
    newer = _make_buy_order(
        ticker="AAPL", price=150.0, quantity=75,
        enter_time="2026-05-18T14:30:00.000Z",
    )
    patch_get_orders.state["orders"] = [older, newer]
    cfg = _make_cfg(environment="production")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    assert result.kind == "populated"
    assert result.entry_price == 150.0
    assert result.shares == 75
    assert result.entry_date == "2026-05-18"


def test_lookback_window_default_is_7_days(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """DEFAULT_LOOKBACK_DAYS=7 per spec §6.1."""
    assert DEFAULT_LOOKBACK_DAYS == 7
    patch_get_orders.state["orders"] = []
    cfg = _make_cfg(environment="production")
    resolve_entry_auto_fill(
        ticker="AAPL", cfg=cfg, conn=conn, now=fake_now,
    )
    call = patch_get_orders[0]
    expected_from = fake_now - timedelta(days=7)
    assert call["from_dt"] == expected_from
    assert call["to_dt"] == fake_now


def test_entry_auto_fill_result_populated_requires_fill_origin_schwab_auto():
    """EntryAutoFillResult __post_init__: populated kind requires fill_origin='schwab_auto'."""
    with pytest.raises(ValueError, match="populated"):
        EntryAutoFillResult(
            kind="populated",
            fill_origin="operator_typed",  # wrong
            entry_date="2026-05-19",
            entry_price=100.0,
            shares=100,
        )


def test_entry_auto_fill_result_non_populated_requires_no_values():
    """Non-populated kinds must NOT carry entry_date/entry_price/shares."""
    with pytest.raises(ValueError, match="must not carry"):
        EntryAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            entry_price=100.0,  # forbidden on non-populated
        )


def test_entry_auto_fill_result_non_populated_must_be_operator_typed():
    """Non-populated kinds must have fill_origin='operator_typed'."""
    with pytest.raises(ValueError, match="operator_typed"):
        EntryAutoFillResult(
            kind="empty",
            fill_origin="schwab_auto",  # wrong
        )
