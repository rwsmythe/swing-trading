"""Phase 13 T3.SB2 T-B.2.1 — exit auto-fill via Schwab Trader API.

``resolve_exit_auto_fill(*, trade_id, ticker, entry_date, cfg, conn, now=None)``
is called from the ``/trades/{id}/exit`` route handler at form-render time.
It resolves recent SELL-side fills for ``ticker`` (since ``entry_date``) via
the Schwab Trader API and returns an ``ExitAutoFillResult`` that the route
handler maps to the trade-exit form view-model.

SELL-side mirror of ``swing.trades.entry_auto_fill`` with one architectural
addition: **multi-partial-exit handling**. Per spec §6.2 paragraph 2, if
Schwab returns multiple SELL fills since ``entry_date`` (operator scaled
out via multiple partial sells), the result surfaces a list of
``ExitAutoFillCandidate`` for operator selection at form render. The
single-fill case still returns a length-1 ``candidates`` list for UX
consistency.

Schwab integration discipline (4-step chain BINDING per spec §6.2 + plan
§A.11 + CLAUDE.md gotcha "Schwab integration discipline"):

  1. Caller has run ``apply_overrides(cfg)`` at handler entry. The service
     consumes the already-merged ``cfg``; it does NOT re-apply overrides.
  2. ``resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)``
     — ``allow_prompt=False`` BINDING per CLAUDE.md gotcha "form-render-time
     prompts would block HTTP handler".
  3. ``construct_authenticated_client(cfg, environment, client_id, client_secret)``
     — 4-arg signature per post-Phase-12 Sub-bundle 1 + forward-binding
     lesson #10.
  4. ``trader.get_account_orders(client, conn, account_hash, from_dt, to_dt,
     surface='trade_exit', environment=environment, ...)`` — emits the
     ``schwab_api_calls`` audit row internally via ``audit_service`` per
     CHECK widening at v20 migration. ``surface='trade_exit'`` is the
     SELL-side counterpart to T3.SB1's ``surface='trade_entry'``.

Short-circuits (any of which skip steps 2-4):

  - Sandbox: ``cfg.integrations.schwab.environment == 'sandbox'`` →
    ``kind='sandbox_short_circuit'`` per CLAUDE.md "Schwab API integration
    writes domain rows ONLY when environment='production'".
  - DEGRADED / PROVISIONAL: ``cli_schwab._compute_degraded_state`` returns
    non-``LIVE`` → ``kind='degraded'``.
  - account_hash missing: ``cfg.integrations.schwab.account_hash`` absent
    or non-string → ``kind='degraded'``.
  - Credentials absent under ``allow_prompt=False``: returns ``(None, None)``
    → ``kind='degraded'``.

Execution-grain helpers consumed verbatim from post-Phase-12 Sub-bundle 1
(``swing/trades/schwab_reconciliation.py``):

  - ``_compute_execution_price`` — single-leg / multi-leg VWAP. Do NOT
    use raw ``so.price`` (would re-introduce the limit-vs-fill defect
    closed at Sub-bundle 1).
  - ``_resolve_match_quantity`` — execution-grain quantity.
  - ``_is_execution_bearing_candidate`` — FILLED with executions OR price
    set, CANCELED with executions, REPLACED with executions.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

# NOTE: _compute_degraded_state is imported here so it can be monkeypatched
# in tests via ``swing.trades.exit_auto_fill._compute_degraded_state``.
# Same applies to ``resolve_credentials_env_or_prompt``,
# ``construct_authenticated_client``, and the ``trader`` submodule.
from swing.cli_schwab import _compute_degraded_state
from swing.integrations.schwab import trader
from swing.integrations.schwab.auth import (
    _resolve_tokens_db_path,
    construct_authenticated_client,
    resolve_credentials_env_or_prompt,
)
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabRateLimitError,
)
from swing.trades.schwab_reconciliation import (
    _compute_execution_price,
    _is_execution_bearing_candidate,
    _resolve_match_quantity,
)

log = logging.getLogger(__name__)


# Per spec §6.2 + plan §G.5 T-B.2.1 — V1 lookback discipline. The lookback
# is bounded by ``entry_date`` (passed by caller); the service does NOT
# apply an additional 7-day cap because operator may exit weeks after
# entry. ``DEFAULT_LOOKBACK_DAYS`` is retained for parity with the entry
# auto-fill module + V2 use cases.
DEFAULT_LOOKBACK_DAYS: int = 7


# SELL-side instructions that signal a closing fill on the exit side.
# Mirrors swing/integrations/schwab/models.py _SCHWAB_ORDER_INSTRUCTIONS
# SELL family. Symmetric counterpart of the BUY family consumed at T3.SB1
# entry auto-fill.
_SELL_INSTRUCTIONS: frozenset[str] = frozenset({
    "SELL", "SELL_TO_CLOSE", "SELL_TO_OPEN", "SELL_SHORT",
})


# Literal-validating frozensets per L6 + CLAUDE.md gotcha "Literal[...] type
# hints are NOT runtime-enforced" — every Literal-typed field on the data-
# integrity path must validate against an explicit frozenset at
# __post_init__ time.
_EXIT_AUTO_FILL_KIND_VALUES: frozenset[str] = frozenset({
    "populated", "empty", "sandbox_short_circuit", "degraded", "error",
})


_EXIT_FILL_ORIGIN_VALUES: frozenset[str] = frozenset({
    "operator_typed",
    "schwab_auto",
    "schwab_auto_then_operator_corrected",
    "tos_import",
    "imported_legacy",
})


ExitAutoFillKind = Literal[
    "populated", "empty", "sandbox_short_circuit", "degraded", "error",
]


ExitFillOrigin = Literal[
    "operator_typed",
    "schwab_auto",
    "schwab_auto_then_operator_corrected",
    "tos_import",
    "imported_legacy",
]


@dataclass(frozen=True)
class ExitAutoFillCandidate:
    """One SELL-side fill candidate surfaced to the operator at form
    render. Multiple instances form the ``candidates`` list on a
    ``populated`` ``ExitAutoFillResult`` when the operator scaled out via
    multiple partial sells (per spec §6.2 paragraph 2).

    Fields:

      - ``date``: ISO ``YYYY-MM-DD`` date of the fill.
      - ``price``: execution-grain price (VWAP across legs for multi-leg
        single-order fills).
      - ``quantity``: execution-grain quantity (sum of leg quantities for
        multi-leg single-order fills).
      - ``signature_hash``: stable hash of the broker-emitted fill
        identity (per-candidate distinct; used downstream for operator-
        selection round-trip + idempotency).
      - ``order_id``: Schwab order id (for audit / debugging).
    """

    date: str
    price: float
    quantity: int
    signature_hash: str
    order_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.date, str) or not self.date:
            raise ValueError(
                f"ExitAutoFillCandidate.date must be non-empty str; "
                f"got {self.date!r}"
            )
        if not isinstance(self.signature_hash, str) or not self.signature_hash:
            raise ValueError(
                "ExitAutoFillCandidate.signature_hash must be non-empty "
                f"str; got {self.signature_hash!r}"
            )
        if not isinstance(self.price, int | float) or self.price <= 0:
            raise ValueError(
                f"ExitAutoFillCandidate.price must be > 0; "
                f"got {self.price!r}"
            )
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError(
                f"ExitAutoFillCandidate.quantity must be int > 0; "
                f"got {self.quantity!r}"
            )


@dataclass(frozen=True)
class ExitAutoFillResult:
    """Result of ``resolve_exit_auto_fill`` (form-render-time SELL fetch).

    Five disjoint ``kind`` values (mirrors T3.SB1 entry):

      - ``'populated'``: Schwab returned at least one matching SELL fill.
        ``exit_date`` / ``exit_price`` / ``closed_shares`` carry the
        most-recent candidate's execution-grain values; ``candidates``
        carries the full list (length >= 1) for operator selection;
        ``fill_origin='schwab_auto'``.
      - ``'empty'``: Schwab returned no matching SELL fill. Fields are
        None; ``candidates=None``; ``fill_origin='operator_typed'``;
        ``advisory_text`` non-None.
      - ``'sandbox_short_circuit'``: sandbox mode. NO Schwab call fired.
      - ``'degraded'``: DEGRADED / PROVISIONAL state OR account_hash
        unresolvable OR credential resolution returned None. NO Schwab
        call fired.
      - ``'error'``: Schwab call fired but raised a typed exception.

    ``schwab_source_value_json`` + ``auto_fill_audit_at`` are hidden audit
    anchors server-stamped at form render (per CLAUDE.md "For any V1
    single-operator form with hidden audit fields, default to SERVER-
    STAMPING at handler entry; hidden inputs are tampering surfaces").
    """

    kind: ExitAutoFillKind
    fill_origin: ExitFillOrigin = "operator_typed"
    exit_date: str | None = None
    exit_price: float | None = None
    closed_shares: int | None = None
    candidates: list[ExitAutoFillCandidate] | None = None
    advisory_text: str | None = None
    schwab_source_value_json: str | None = None
    auto_fill_audit_at: str | None = None
    schwab_api_call_id: int | None = None

    def __post_init__(self) -> None:
        # L6 + CLAUDE.md gotcha: Literal[...] not runtime-enforced — validate
        # explicit frozenset membership for kind + fill_origin.
        if self.kind not in _EXIT_AUTO_FILL_KIND_VALUES:
            raise ValueError(
                f"ExitAutoFillResult.kind must be one of "
                f"{sorted(_EXIT_AUTO_FILL_KIND_VALUES)}; got {self.kind!r}"
            )
        if self.fill_origin not in _EXIT_FILL_ORIGIN_VALUES:
            raise ValueError(
                f"ExitAutoFillResult.fill_origin must be one of "
                f"{sorted(_EXIT_FILL_ORIGIN_VALUES)}; "
                f"got {self.fill_origin!r}"
            )
        if self.kind == "populated":
            if self.exit_date is None:
                raise ValueError(
                    "populated ExitAutoFillResult requires exit_date"
                )
            if self.exit_price is None:
                raise ValueError(
                    "populated ExitAutoFillResult requires exit_price"
                )
            if self.closed_shares is None:
                raise ValueError(
                    "populated ExitAutoFillResult requires closed_shares"
                )
            if self.candidates is None or len(self.candidates) == 0:
                raise ValueError(
                    "populated ExitAutoFillResult requires non-empty "
                    "candidates list (length >= 1; single-fill case is a "
                    "length-1 list per spec §6.2 paragraph 2)"
                )
            if self.fill_origin != "schwab_auto":
                raise ValueError(
                    "populated ExitAutoFillResult must have "
                    f"fill_origin='schwab_auto'; got {self.fill_origin!r}"
                )
        else:
            if self.exit_date is not None:
                raise ValueError(
                    f"{self.kind!r} ExitAutoFillResult must not carry "
                    f"exit_date; got {self.exit_date!r}"
                )
            if self.exit_price is not None:
                raise ValueError(
                    f"{self.kind!r} ExitAutoFillResult must not carry "
                    f"exit_price; got {self.exit_price!r}"
                )
            if self.closed_shares is not None:
                raise ValueError(
                    f"{self.kind!r} ExitAutoFillResult must not carry "
                    f"closed_shares; got {self.closed_shares!r}"
                )
            if self.candidates is not None:
                raise ValueError(
                    f"{self.kind!r} ExitAutoFillResult must not carry "
                    f"candidates; got {self.candidates!r}"
                )
            if self.fill_origin != "operator_typed":
                raise ValueError(
                    f"{self.kind!r} ExitAutoFillResult must have "
                    f"fill_origin='operator_typed'; got {self.fill_origin!r}"
                )


def resolve_exit_auto_fill(
    *,
    trade_id: int,
    ticker: str,
    entry_date: str,
    cfg: Any,
    conn: Any,
    now: datetime | None = None,
) -> ExitAutoFillResult:
    """Resolve form-render-time exit auto-fill via Schwab Trader API.

    Args:
        trade_id: trades.id of the trade being exited (used for audit /
            future signature_hash augmentation).
        ticker: ticker to query (case-normalized to uppercase).
        entry_date: ISO ``YYYY-MM-DD`` date of the trade entry; bounds
            the Schwab account_orders lookback window.
        cfg: Config object; caller has already run apply_overrides(cfg)
            at the handler entry (per spec §6.2 + plan §A.11).
        conn: open DB connection (used for the DEGRADED predicate's
            ``schwab_api_calls`` query + the ``trader.get_account_orders``
            audit-row writes).
        now: server-stamped 'now' for the lookback upper bound + audit_at;
            defaults to ``datetime.now(UTC)``.

    Returns:
        ``ExitAutoFillResult`` — see dataclass docstring for the 5 kinds.
    """
    if not isinstance(trade_id, int):
        raise ValueError(
            f"trade_id must be int; got {trade_id!r}"
        )
    if not isinstance(ticker, str) or not ticker:
        raise ValueError(
            f"ticker must be non-empty str; got {ticker!r}"
        )
    if not isinstance(entry_date, str) or not entry_date:
        raise ValueError(
            f"entry_date must be non-empty ISO YYYY-MM-DD str; "
            f"got {entry_date!r}"
        )
    ticker = ticker.upper()
    if now is None:
        now = datetime.now(UTC)
    auto_fill_audit_at = now.isoformat(timespec="microseconds")

    # ----------------------------------------------------------------------
    # Sandbox short-circuit per CLAUDE.md "Schwab sandbox-gating" gotcha.
    # Fires BEFORE any Schwab client construction.
    # ----------------------------------------------------------------------
    schwab_cfg = getattr(getattr(cfg, "integrations", None), "schwab", None)
    environment = getattr(schwab_cfg, "environment", None)
    if environment == "sandbox":
        return ExitAutoFillResult(
            kind="sandbox_short_circuit",
            fill_origin="operator_typed",
            advisory_text=(
                "Schwab integration in sandbox mode; auto-fill disabled. "
                "Switch cfg.integrations.schwab.environment to 'production' "
                "to enable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )
    if environment != "production":
        return ExitAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                "Schwab integration not configured "
                "(cfg.integrations.schwab.environment missing or invalid). "
                "Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # DEGRADED / PROVISIONAL short-circuit (mirrors `swing schwab status`).
    # ----------------------------------------------------------------------
    tokens_path = _resolve_tokens_db_path(environment)
    state, reason = _compute_degraded_state(
        conn, env=environment, tokens_path=tokens_path, now=now,
    )
    if state != "LIVE":
        return ExitAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab integration {state.lower()}: "
                f"{reason or 'unavailable'}. Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # account_hash resolution (V1: single linked account).
    # ----------------------------------------------------------------------
    account_hash = getattr(schwab_cfg, "account_hash", None)
    if not account_hash or not isinstance(account_hash, str):
        return ExitAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                "Schwab account_hash not set; complete `swing schwab setup` "
                "to link your account. Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Credential resolution — allow_prompt=False BINDING (form-render-time
    # prompts would block the HTTP handler per CLAUDE.md gotcha).
    # ----------------------------------------------------------------------
    try:
        client_id, client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=False,
        )
    except SchwabConfigMissingError as exc:
        return ExitAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab credential resolution failed: {exc}. "
                "Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )
    if client_id is None or client_secret is None:
        return ExitAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                "Schwab credentials missing (env vars + cfg both absent "
                "under allow_prompt=False). Set SCHWAB_CLIENT_ID + "
                "SCHWAB_CLIENT_SECRET env vars or populate "
                "cfg.integrations.schwab. Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Construct authenticated client (4-arg signature).
    # ----------------------------------------------------------------------
    try:
        client = construct_authenticated_client(
            cfg, environment, client_id, client_secret,
        )
    except (SchwabAuthError, SchwabConfigMissingError) as exc:
        return ExitAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab client construction failed: {exc}. "
                "Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Lookback bounds — from = entry_date (start-of-day UTC); to = now.
    # Per dispatch brief: "for SELL fills matching ticker since entry_date".
    # ----------------------------------------------------------------------
    from_dt = _parse_entry_date_to_utc(entry_date)

    # ----------------------------------------------------------------------
    # trader.get_account_orders — emits schwab_api_calls audit row
    # internally via audit_service. surface='trade_exit' per CHECK widening
    # at v20.
    # ----------------------------------------------------------------------
    try:
        orders = trader.get_account_orders(
            client, conn, account_hash, from_dt, now,
            surface="trade_exit",
            environment=environment,
            pipeline_run_id=None,
            status=None,
            max_results=None,
        )
    except (SchwabAuthError, SchwabRateLimitError, SchwabApiError) as exc:
        log.warning(
            "schwab exit auto-fill: get_account_orders failed for %s: %s",
            ticker, type(exc).__name__,
        )
        return ExitAutoFillResult(
            kind="error",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab fetch failed ({type(exc).__name__}); auto-fill "
                "unavailable. Please enter manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Candidate selection — production-shape filter (SELL-side mirror).
    # ----------------------------------------------------------------------
    matches = [
        o for o in orders
        if (
            getattr(o, "instrument_symbol", "") == ticker
            and getattr(o, "instruction", "") in _SELL_INSTRUCTIONS
            and _is_execution_bearing_candidate(o)
        )
    ]
    if not matches:
        return ExitAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            advisory_text=(
                f"No matching Schwab SELL fills for {ticker} since "
                f"{entry_date}; please enter manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Build per-fill candidates. NEW vs T3.SB1: every matching SELL fill
    # becomes an ExitAutoFillCandidate. Single-fill case = length-1 list
    # per spec §6.2 paragraph 2. Multi-partial case = length-N list for
    # operator selection.
    # ----------------------------------------------------------------------
    candidates: list[ExitAutoFillCandidate] = []
    for o in matches:
        cand = _build_candidate(o)
        if cand is not None:
            candidates.append(cand)
    if not candidates:
        # All matches lacked execution-grain price (mapper edge case).
        return ExitAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab SELL fills for {ticker} lacked execution-grain "
                "price; please enter manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # Most-recent candidate by enter_time drives the default form values;
    # the full candidates list lets operator select another fill if scaled
    # out. Lexicographic max matches chronological for valid ISO-Z strings.
    chosen_order = max(matches, key=lambda o: getattr(o, "enter_time", ""))
    chosen_price = _compute_execution_price(chosen_order)
    chosen_quantity = _resolve_match_quantity(chosen_order)
    chosen_date = _extract_iso_date(
        getattr(chosen_order, "enter_time", "")
    )

    # Build a stable signature for the most-recent fill so the
    # schwab_source_value_json carries provenance equivalent to the
    # candidate the operator sees defaulted.
    schwab_source_value_json = json.dumps(
        {
            "exit_date": chosen_date,
            "exit_price": chosen_price,
            "closed_shares": int(chosen_quantity),
            "schwab_order_id": getattr(chosen_order, "order_id", None),
            "schwab_instrument_symbol": getattr(
                chosen_order, "instrument_symbol", None,
            ),
            "candidate_count": len(candidates),
        },
        sort_keys=True,
    )

    return ExitAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        exit_date=chosen_date,
        exit_price=chosen_price,
        closed_shares=int(chosen_quantity),
        candidates=candidates,
        advisory_text=None,
        schwab_source_value_json=schwab_source_value_json,
        auto_fill_audit_at=auto_fill_audit_at,
        schwab_api_call_id=None,
    )


def _build_candidate(o: Any) -> ExitAutoFillCandidate | None:
    """Build an ExitAutoFillCandidate from a SchwabOrderResponse.

    Uses execution-grain helpers per CLAUDE.md "Pass-1-tier-1 Sub-bundle 1"
    discipline — do NOT consume raw ``so.price``.

    Returns None if the order lacks execution-grain price (mapper edge
    case; caller falls back to empty result if ALL candidates are None).
    """
    price = _compute_execution_price(o)
    if price is None:
        return None
    quantity = _resolve_match_quantity(o)
    if quantity is None or quantity <= 0:
        return None
    date = _extract_iso_date(getattr(o, "enter_time", ""))
    if not date:
        return None
    order_id = getattr(o, "order_id", None)
    sig = _compute_signature_hash(
        order_id=order_id,
        date=date,
        price=price,
        quantity=quantity,
        enter_time=getattr(o, "enter_time", ""),
    )
    return ExitAutoFillCandidate(
        date=date,
        price=float(price),
        quantity=int(quantity),
        signature_hash=sig,
        order_id=order_id,
    )


def _compute_signature_hash(
    *,
    order_id: str | None,
    date: str,
    price: float,
    quantity: float,
    enter_time: str,
) -> str:
    """Compute a stable signature hash for a candidate.

    Includes the broker order_id (when present) plus a tuple of fill
    identity fields so candidates with the same shape but different
    underlying Schwab orders get distinct hashes. Used downstream for
    operator-selection round-trip + idempotency.
    """
    payload = json.dumps(
        {
            "order_id": order_id or "",
            "date": date,
            "price": float(price),
            "quantity": float(quantity),
            "enter_time": enter_time or "",
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _parse_entry_date_to_utc(entry_date: str) -> datetime:
    """Parse ISO ``YYYY-MM-DD`` to a UTC datetime at start-of-day.

    Schwab account_orders accepts datetime or ISO string lower bounds; we
    pass a datetime for parity with the entry auto-fill path.
    """
    try:
        d = datetime.strptime(entry_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"entry_date must be ISO YYYY-MM-DD; got {entry_date!r}"
        ) from exc
    return d.replace(tzinfo=UTC)


def _extract_iso_date(iso_string: str) -> str:
    """Extract ``YYYY-MM-DD`` from an ISO timestamp string.

    Tolerant of missing ``T`` separator (date-only inputs) + missing
    suffix (date-only).
    """
    if not isinstance(iso_string, str) or not iso_string:
        return ""
    if "T" in iso_string:
        return iso_string.split("T", 1)[0]
    if " " in iso_string:
        return iso_string.split(" ", 1)[0]
    return iso_string[:10] if len(iso_string) >= 10 else ""


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "ExitAutoFillCandidate",
    "ExitAutoFillKind",
    "ExitAutoFillResult",
    "ExitFillOrigin",
    "resolve_exit_auto_fill",
]
