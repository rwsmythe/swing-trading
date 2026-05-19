"""Phase 13 T3.SB1 T-B.1.2 — entry auto-fill via Schwab Trader API.

``resolve_entry_auto_fill(*, ticker, cfg, conn, now=None, lookback_days=7)``
is called from the ``/trades/entry/form`` route handler at form-render
time. It resolves recent BUY-side fills for ``ticker`` via the Schwab
Trader API and returns an ``EntryAutoFillResult`` that the route handler
maps to ``TradeEntryFormVM`` fields.

Schwab integration discipline (4-step chain BINDING per spec §6.1 + plan
§A.11 + CLAUDE.md gotcha "Schwab integration discipline" + dispatch brief
§5 watch items 3, 4, 5):

  1. Caller has run ``apply_overrides(cfg)`` at handler entry. The service
     consumes the already-merged ``cfg``; it does NOT re-apply overrides.
  2. ``resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)``
     — ``allow_prompt=False`` BINDING per CLAUDE.md gotcha "form-render-time
     prompts would block HTTP handler".
  3. ``construct_authenticated_client(cfg, environment, client_id, client_secret)``
     — 4-arg signature per post-Phase-12 Sub-bundle 1 + forward-binding
     lesson #10.
  4. ``trader.get_account_orders(client, conn, account_hash, from_dt, to_dt,
     surface='trade_entry', environment=environment, ...)`` — emits the
     ``schwab_api_calls`` audit row internally via ``audit_service`` per
     CHECK widening at v20 migration.

Short-circuits (any of which skip steps 2-4):

  - Sandbox: ``cfg.integrations.schwab.environment == 'sandbox'`` →
    ``kind='sandbox_short_circuit'`` per CLAUDE.md "Schwab API integration
    writes domain rows ONLY when environment='production'".
  - DEGRADED / PROVISIONAL: ``cli_schwab._compute_degraded_state`` returns
    non-``LIVE`` → ``kind='degraded'``. Mirrors the ``swing schwab status``
    predicate so operator sees consistent state across surfaces.
  - account_hash missing: ``cfg.integrations.schwab.account_hash`` absent
    or non-string → ``kind='degraded'``.
  - Credentials absent under ``allow_prompt=False``: returns ``(None, None)``
    → ``kind='degraded'``.

Execution-grain helpers consumed verbatim from post-Phase-12 Sub-bundle 1
(``swing/trades/schwab_reconciliation.py``):

  - ``_compute_execution_price`` — single-leg / multi-leg VWAP.
  - ``_resolve_match_quantity`` — execution-grain quantity (or fallback to
    ``so.quantity`` for legacy V1 mapper paths).
  - ``_is_execution_bearing_candidate`` — FILLED with executions OR price
    set, CANCELED with executions (partial-then-canceled), REPLACED with
    executions (partial-then-replaced).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

# NOTE: _compute_degraded_state is imported here so it can be monkeypatched
# in tests via ``swing.trades.entry_auto_fill._compute_degraded_state``.
# Same applies to ``resolve_credentials_env_or_prompt``,
# ``construct_authenticated_client``, and the ``trader`` submodule below —
# the form ``from X import Y`` copies the reference into this module's
# namespace, so monkeypatching at the test-import site works correctly.
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


# Per spec §6.1 + plan §G.2 T-B.1.2 — V1 lookback window for fill candidates.
DEFAULT_LOOKBACK_DAYS: int = 7


# BUY-side instructions that signal an opening fill on the entry side.
# Mirrors swing/integrations/schwab/models.py _SCHWAB_ORDER_INSTRUCTIONS
# BUY family. SELL family is the symmetric set consumed at T3.SB2 exit
# auto-fill.
_BUY_INSTRUCTIONS: frozenset[str] = frozenset({
    "BUY", "BUY_TO_OPEN", "BUY_TO_COVER",
})


EntryAutoFillKind = Literal[
    "populated", "empty", "sandbox_short_circuit", "degraded", "error",
]


EntryFillOrigin = Literal[
    "operator_typed",
    "schwab_auto",
    "schwab_auto_then_operator_corrected",
    "tos_import",
    "imported_legacy",
]


@dataclass(frozen=True)
class EntryAutoFillResult:
    """Result of ``resolve_entry_auto_fill`` (form-render-time fetch).

    Five disjoint ``kind`` values:

      - ``'populated'``: Schwab returned a matching BUY fill. Fields carry
        execution-grain values; ``fill_origin='schwab_auto'``.
      - ``'empty'``: Schwab returned no matching BUY fill. Fields are None;
        ``fill_origin='operator_typed'``; ``advisory_text`` non-None.
      - ``'sandbox_short_circuit'``: ``cfg.integrations.schwab.environment
        == 'sandbox'``. NO Schwab call fired. Fields are None;
        ``fill_origin='operator_typed'``; ``advisory_text`` non-None.
      - ``'degraded'``: DEGRADED / PROVISIONAL state OR account_hash
        unresolvable OR credential resolution returned None. NO Schwab call
        fired. Fields are None; ``fill_origin='operator_typed'``;
        ``advisory_text`` non-None.
      - ``'error'``: Schwab call fired but raised a typed exception
        (``SchwabApiError`` / ``SchwabAuthError`` / ``SchwabRateLimitError``).
        Audit row records the failure outcome via the existing
        ``audit_service`` plumbing. Fields are None;
        ``fill_origin='operator_typed'``; ``advisory_text`` non-None.

    Hidden audit anchors ``schwab_source_value_json`` + ``auto_fill_audit_at``
    are server-stamped at form render (per CLAUDE.md "For any V1 single-
    operator form with hidden audit fields, default to SERVER-STAMPING at
    handler entry; hidden inputs are tampering surfaces"):

      - ``schwab_source_value_json``: JSON-encoded original auto-populated
        values. Set on ``'populated'`` only; None for other kinds.
      - ``auto_fill_audit_at``: ISO timestamp at form-render time. Set on
        ALL kinds (even short-circuit kinds — the audit anchor records
        that an auto-fill ATTEMPT happened at this time).
    """

    kind: EntryAutoFillKind
    fill_origin: EntryFillOrigin = "operator_typed"
    entry_date: str | None = None
    entry_price: float | None = None
    shares: int | None = None
    advisory_text: str | None = None
    schwab_source_value_json: str | None = None
    auto_fill_audit_at: str | None = None
    schwab_api_call_id: int | None = None

    def __post_init__(self) -> None:
        if self.kind == "populated":
            if self.entry_date is None:
                raise ValueError(
                    "populated EntryAutoFillResult requires entry_date"
                )
            if self.entry_price is None:
                raise ValueError(
                    "populated EntryAutoFillResult requires entry_price"
                )
            if self.shares is None:
                raise ValueError(
                    "populated EntryAutoFillResult requires shares"
                )
            if self.fill_origin != "schwab_auto":
                raise ValueError(
                    "populated EntryAutoFillResult must have "
                    f"fill_origin='schwab_auto'; got {self.fill_origin!r}"
                )
        else:
            if self.entry_date is not None:
                raise ValueError(
                    f"{self.kind!r} EntryAutoFillResult must not carry "
                    f"entry_date; got {self.entry_date!r}"
                )
            if self.entry_price is not None:
                raise ValueError(
                    f"{self.kind!r} EntryAutoFillResult must not carry "
                    f"entry_price; got {self.entry_price!r}"
                )
            if self.shares is not None:
                raise ValueError(
                    f"{self.kind!r} EntryAutoFillResult must not carry "
                    f"shares; got {self.shares!r}"
                )
            if self.fill_origin != "operator_typed":
                raise ValueError(
                    f"{self.kind!r} EntryAutoFillResult must have "
                    f"fill_origin='operator_typed'; got {self.fill_origin!r}"
                )


def resolve_entry_auto_fill(
    *,
    ticker: str,
    cfg: Any,
    conn: Any,
    now: datetime | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> EntryAutoFillResult:
    """Resolve form-render-time entry auto-fill via Schwab Trader API.

    See module docstring for the 4-step Schwab integration chain + short-
    circuit semantics.

    Args:
        ticker: ticker to query (case-normalized to uppercase).
        cfg: Config object; caller has already run apply_overrides(cfg)
            at the handler entry (per spec §6.1 + plan §A.11).
        conn: open DB connection (used for the DEGRADED predicate's
            ``schwab_api_calls`` query + the ``trader.get_account_orders``
            audit-row writes).
        now: server-stamped 'now' for the lookback window + audit_at;
            defaults to ``datetime.now(timezone.utc)``.
        lookback_days: window for fill candidates; defaults to
            ``DEFAULT_LOOKBACK_DAYS`` (7 days).

    Returns:
        ``EntryAutoFillResult`` — see dataclass docstring for the 5 kinds.
    """
    if not isinstance(ticker, str) or not ticker:
        raise ValueError(
            f"ticker must be non-empty str; got {ticker!r}"
        )
    ticker = ticker.upper()
    if now is None:
        now = datetime.now(UTC)
    auto_fill_audit_at = now.isoformat(timespec="microseconds")

    # ----------------------------------------------------------------------
    # Sandbox short-circuit per CLAUDE.md "Schwab sandbox-gating" gotcha.
    # Fires BEFORE any Schwab client construction to keep the sandbox path
    # provably side-effect-free.
    # ----------------------------------------------------------------------
    schwab_cfg = getattr(getattr(cfg, "integrations", None), "schwab", None)
    environment = getattr(schwab_cfg, "environment", None)
    if environment == "sandbox":
        return EntryAutoFillResult(
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
        # No Schwab cfg sub-namespace OR environment value not in V1 enum.
        # Treat as DEGRADED for operator-facing consistency (the advisory
        # text mentions cfg, not "sandbox" — operator can't enable
        # auto-fill via sandbox mode).
        return EntryAutoFillResult(
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
    # DEGRADED / PROVISIONAL short-circuit (mirrors `swing schwab status`
    # predicate at cli_schwab._compute_degraded_state). LIVE proceeds;
    # PROVISIONAL + DEGRADED both short-circuit with advisory.
    # ----------------------------------------------------------------------
    tokens_path = _resolve_tokens_db_path(environment)
    state, reason = _compute_degraded_state(
        conn, env=environment, tokens_path=tokens_path, now=now,
    )
    if state != "LIVE":
        return EntryAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab integration {state.lower()}: "
                f"{reason or 'unavailable'}. Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # account_hash resolution from cfg (V1: single linked account; per
    # CLAUDE.md "Schwab CLIENT_ID + CLIENT_SECRET storage" + Sub-bundle B
    # T-B.2 storage pattern).
    # ----------------------------------------------------------------------
    account_hash = getattr(schwab_cfg, "account_hash", None)
    if not account_hash or not isinstance(account_hash, str):
        return EntryAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                "Schwab account_hash not set; complete `swing schwab setup` "
                "to link your account. Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Credential resolution per CLAUDE.md gotcha "form-render-time prompts
    # would block HTTP handler" — allow_prompt=False BINDING (BINDING per
    # dispatch brief §5 watch item 4 + plan §A.11).
    # ----------------------------------------------------------------------
    try:
        client_id, client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=False,
        )
    except SchwabConfigMissingError as exc:
        return EntryAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab credential resolution failed: {exc}. "
                "Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )
    if client_id is None or client_secret is None:
        return EntryAutoFillResult(
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
    # Construct authenticated client (4-arg signature per post-Phase-12
    # Sub-bundle 1 + forward-binding lesson #10).
    # ----------------------------------------------------------------------
    try:
        client = construct_authenticated_client(
            cfg, environment, client_id, client_secret,
        )
    except (SchwabAuthError, SchwabConfigMissingError) as exc:
        return EntryAutoFillResult(
            kind="degraded",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab client construction failed: {exc}. "
                "Auto-fill unavailable."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # trader.get_account_orders — emits schwab_api_calls audit row
    # internally via audit_service. Wrap in try/except for typed failures
    # (typed exceptions are already closed via record_call_finish per
    # CLAUDE.md "Typed SchwabApiError audit-row close discipline").
    # ----------------------------------------------------------------------
    from_dt = now - timedelta(days=lookback_days)
    try:
        orders = trader.get_account_orders(
            client, conn, account_hash, from_dt, now,
            surface="trade_entry",
            environment=environment,
            pipeline_run_id=None,
            status=None,
            max_results=None,
        )
    except (SchwabAuthError, SchwabRateLimitError, SchwabApiError) as exc:
        log.warning(
            "schwab entry auto-fill: get_account_orders failed for %s: %s",
            ticker, type(exc).__name__,
        )
        return EntryAutoFillResult(
            kind="error",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab fetch failed ({type(exc).__name__}); auto-fill "
                "unavailable. Please enter manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # ----------------------------------------------------------------------
    # Candidate selection — production-shape filter mirrors
    # _is_execution_bearing_candidate from post-Phase-12 Sub-bundle 1.
    # ----------------------------------------------------------------------
    candidates = [
        o for o in orders
        if (
            getattr(o, "instrument_symbol", "") == ticker
            and getattr(o, "instruction", "") in _BUY_INSTRUCTIONS
            and _is_execution_bearing_candidate(o)
        )
    ]
    if not candidates:
        return EntryAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            advisory_text=(
                f"No matching Schwab BUY fills for {ticker} in last "
                f"{lookback_days} days; please enter manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # Pick most-recent candidate by enter_time. Schwab returns ISO
    # timestamps in `yyyy-MM-dd'T'HH:mm:ss.SSSZ` shape; lexicographic max
    # matches chronological for valid ISO-Z strings.
    chosen = max(candidates, key=lambda o: getattr(o, "enter_time", ""))

    # Execution-grain extraction via post-Phase-12 Sub-bundle 1 helpers.
    entry_price = _compute_execution_price(chosen)
    if entry_price is None:
        # Belt-and-suspenders: _is_execution_bearing_candidate admitted
        # this row so executions OR so.price is present. entry_price-None
        # implies a transient mapper edge case (FILLED with price set but
        # executions=None — covered by the candidate filter; helper still
        # short-circuits at executions is None / empty). Treat as empty
        # so the operator gets a clear advisory + manual fallback path
        # instead of a NULL-price form-default.
        return EntryAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            advisory_text=(
                f"Schwab BUY fill for {ticker} lacks execution-grain price; "
                "please enter manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )
    quantity = _resolve_match_quantity(chosen)
    shares = int(quantity)
    entry_date = _extract_iso_date(getattr(chosen, "enter_time", ""))

    schwab_source_value_json = json.dumps(
        {
            "entry_date": entry_date,
            "entry_price": entry_price,
            "shares": shares,
            "schwab_order_id": getattr(chosen, "order_id", None),
            "schwab_instrument_symbol": getattr(
                chosen, "instrument_symbol", None,
            ),
        },
        sort_keys=True,
    )

    return EntryAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        advisory_text=None,
        schwab_source_value_json=schwab_source_value_json,
        auto_fill_audit_at=auto_fill_audit_at,
        # V1: trader.get_account_orders does not return the call_id; the
        # audited variant (get_account_orders_audited) is reserved for the
        # Phase 12 backfill path. V2 candidate: thread call_id through here
        # so the auto-fill audit chain can link the fills row's
        # schwab_source_value_json to the originating schwab_api_calls row.
        schwab_api_call_id=None,
    )


def _extract_iso_date(iso_string: str) -> str:
    """Extract ``YYYY-MM-DD`` from an ISO timestamp string.

    Schwab Trader API returns timestamps like ``2026-05-19T14:30:00.000Z``;
    the entry-form template expects an ISO date for the ``entry_date``
    input. Tolerant of missing ``T`` separator (date-only inputs).
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
    "EntryAutoFillKind",
    "EntryAutoFillResult",
    "EntryFillOrigin",
    "resolve_entry_auto_fill",
]
