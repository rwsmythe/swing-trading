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
import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
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
from swing.trades.execution_dates import (
    execution_precedes_order,
    latest_execution_leg_date,
    latest_execution_leg_instant,
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
# entry. ``DEFAULT_LOOKBACK_DAYS`` documents the V2 wiring point if a
# cap is ever added; intentionally NOT in ``__all__`` because the V1
# function does not consume it (no false-configurability surface).
DEFAULT_LOOKBACK_DAYS: int = 7


# SELL-side instructions that signal a CLOSING fill on the exit side.
# Codex R1 Major #6 fix — restricted to {SELL, SELL_TO_CLOSE} only.
# ``SELL_TO_OPEN`` and ``SELL_SHORT`` are short-OPENING instructions
# (entering a short position) — NOT closes of a long position. Including
# them on the exit form would surface unrelated short-entry orders as
# candidate fills for a long-position exit, which is semantically wrong.
# The companion BUY-side mirror at T3.SB1 entry auto-fill uses ``BUY``
# and ``BUY_TO_OPEN`` (long-opening); the symmetric closing pair is
# ``SELL`` and ``SELL_TO_CLOSE``.
_SELL_INSTRUCTIONS: frozenset[str] = frozenset({
    "SELL", "SELL_TO_CLOSE",
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


# D31 (exit half) — which grain produced a candidate's date. Stamped
# per-candidate into the audit envelope; see ``_execution_date``.
_EXIT_DATE_SOURCE_VALUES: frozenset[str] = frozenset({
    "execution_leg", "enter_time",
})


# Operator-facing text for each ``_build_candidate`` refusal reason. Every
# reason is announced, not just the one D31 introduced (cold audit) — a fill
# omitted for an unresolvable price is exactly as absent as one omitted for an
# unusable date. An unknown key falls through to the raw reason rather than
# being swallowed, so a future reason cannot go quiet by forgetting this map.
_OMISSION_REASON_TEXT: dict[str, str] = {
    "no_usable_date": (
        "no usable execution date (unusable execution leg times and a "
        "non-calendar order-entered timestamp)"
    ),
    "no_execution_price": "no execution-grain price",
    "no_quantity": "no resolvable execution quantity",
    "sub_one_share_quantity": (
        "an execution quantity below one whole share, which this form "
        "cannot represent"
    ),
}


def _omission_reason_summary(omitted: dict[str, int]) -> str:
    """``'<n> for <reason>; <n> for <reason>'`` over every refusal counted.

    Spelled ONCE because both operator-facing exits announce omissions: the
    populated result's advisory, and the empty result the caller reaches when
    every match was refused. The empty branch used to state a fixed sentence
    naming price/quantity/date, which is a false description of a fill refused
    for anything else -- a reason reaching the counter and then a message
    contradicting it (orchestrator B review round 2, MAJOR B).
    """
    return "; ".join(
        f"{count} for {_OMISSION_REASON_TEXT.get(reason, reason)}"
        for reason, count in sorted(omitted.items())
    )


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
class PossibleDuplicateFill:
    """An ALREADY-RECORDED fill a candidate MIGHT duplicate, named in full.

    Emitted when identity is UNDECIDABLE: a recorded fill carrying no
    ``schwab_order_id`` whose stored date matches EITHER of the two dates in
    play for a candidate -- the date the candidate carries, or the date this
    module would have recorded for the same order before the D31 grain
    cutover -- with the same price and quantity. The rows may be one broker
    fill or two different ones, and nothing available can tell them apart:
    BY DEFINITION these rows carry no usable ``schwab_order_id`` bound to their
    recorded values, and that id is the only proof of identity this system has.
    On the live ledger today they are additionally ALL ``operator_typed`` --
    hand-typed dates whose grain is unknowable in principle -- which is the
    observation RD's 2026-08-11 ruling rests on. That is a fact about the
    CURRENT POPULATION, not the definition of this channel, which also admits
    imported fills and ``selected_candidate_order_id``-only envelopes.

    The row is NAMED rather than merely counted -- ``fill_id``, stored date,
    price, quantity -- because the operator adjudicates this, and "one of your
    recorded fills might be this" is not an actionable sentence.
    """

    fill_id: int
    date: str
    price: float
    # FLOAT, NOT INT (Codex R16 major). `fills.quantity` is
    # `REAL NOT NULL CHECK (quantity > 0)` (migration 0014) and the
    # split-partial correction path writes fractional values, so truncating a
    # stored 5.9 to 5 would make it falsely equal a 5-share candidate and
    # name the wrong row. The live ledger happens to hold no fractional
    # quantity today; the schema has always permitted one.
    quantity: float

    def __post_init__(self) -> None:
        if isinstance(self.fill_id, bool) or not isinstance(self.fill_id, int):
            raise ValueError(
                f"PossibleDuplicateFill.fill_id must be int (not bool); "
                f"got {self.fill_id!r}"
            )
        if not isinstance(self.date, str) or not self.date:
            raise ValueError(
                f"PossibleDuplicateFill.date must be non-empty str; "
                f"got {self.date!r}"
            )


@dataclass(frozen=True)
class ExitAutoFillCandidate:
    """One SELL-side fill candidate surfaced to the operator at form
    render. Multiple instances form the ``candidates`` list on a
    ``populated`` ``ExitAutoFillResult`` when the operator scaled out via
    multiple partial sells (per spec §6.2 paragraph 2).

    Fields:

      - ``date``: ISO ``YYYY-MM-DD`` date of the fill. VALIDATED as such
        below, because this docstring used to promise the format while
        ``__post_init__`` checked only non-emptiness (orchestrator B review) --
        a documented contract nothing enforced.
      - ``price``: execution-grain price (VWAP across legs for multi-leg
        single-order fills).
      - ``quantity``: execution-grain quantity (sum of leg quantities for
        multi-leg single-order fills).
      - ``signature_hash``: stable hash of the broker-emitted fill
        identity (per-candidate distinct; used downstream for the
        operator-selection round-trip + audit provenance -- NOT for
        idempotency, see ``_compute_signature_hash``).
      - ``order_id``: Schwab order id (for audit / debugging).
      - ``date_source``: which grain produced ``date`` -- ``'execution_leg'``
        or ``'enter_time'``. ``None`` means UNSTATED, which is what a
        hand-constructed candidate gets; the resolver always states it. A
        default of ``'execution_leg'`` would let a construction that never
        thought about provenance silently claim the good grain.
      - ``possible_duplicates``: EVERY anonymous recorded fill this candidate
        might duplicate (see ``PossibleDuplicateFill``); empty tuple when none.
        The candidate is still OFFERED -- the affordance to record is never
        gated on the alarm -- but never offered clean. ALL matches are named,
        not just the first: nothing is excluded any more, so if the operator
        rules out the one row he was shown he would duplicate the one he was
        not (Codex R16 major).
    """

    date: str
    price: float
    quantity: int
    signature_hash: str
    order_id: str | None = None
    date_source: str | None = None
    possible_duplicates: tuple[PossibleDuplicateFill, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.date, str) or not self.date:
            raise ValueError(
                f"ExitAutoFillCandidate.date must be non-empty str; "
                f"got {self.date!r}"
            )
        if _canonical_date(self.date) != self.date:
            raise ValueError(
                f"ExitAutoFillCandidate.date must be an EXTENDED-format ISO "
                f"YYYY-MM-DD calendar date; got {self.date!r}"
            )
        # `isinstance` BEFORE membership: `[] in frozenset(...)` raises
        # TypeError, not the ValueError this contract promises (Codex R14).
        # Same shape as the POST tier's unhashable-value defect two rounds
        # earlier -- a set-membership test is only safe once the value is known
        # to be hashable.
        if self.date_source is not None and not (
            isinstance(self.date_source, str)
            and self.date_source in _EXIT_DATE_SOURCE_VALUES
        ):
            raise ValueError(
                f"ExitAutoFillCandidate.date_source must be one of "
                f"{sorted(_EXIT_DATE_SOURCE_VALUES)} or None; "
                f"got {self.date_source!r}"
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
        most-recent candidate's values; ``candidates`` carries the full list
        (length >= 1) for operator selection; ``fill_origin='schwab_auto'``.
        PRICE AND QUANTITY ARE ALWAYS EXECUTION-GRAIN; **THE DATE IS NOT
        ALWAYS** (orchestrator B review). An earlier version of this line said
        "execution-grain values" of all three, which the module's own
        supported fallback contradicts: when an order's execution leg times
        are unusable the date comes from ``enter_time`` and the result is
        still ``populated``. Per-candidate ``date_source`` says which grain
        each one used, and the operator is told on the form.
      - ``'empty'``: Schwab returned no matching SELL fill. Fields are
        None; ``candidates=None``; ``fill_origin='operator_typed'``;
        ``advisory_text`` non-None.
      - ``'sandbox_short_circuit'``: sandbox mode. NO Schwab call fired.
      - ``'degraded'``: DEGRADED / PROVISIONAL state OR account_hash
        unresolvable OR credential resolution returned None. NO Schwab
        call fired.
      - ``'error'``: Schwab call fired but raised a typed exception.

    ``schwab_source_value_json`` + ``auto_fill_audit_at`` are GET-GENERATED,
    CLIENT-ROUND-TRIPPED audit anchors: this resolver computes them at form
    render, they travel to the browser as hidden inputs, and the POST accepts
    them back.

    THEY ARE NOT "SERVER-STAMPED" IN THIS PROJECT'S SENSE, and calling them
    that WHILE CITING THE CONVENTION THAT FORBIDS IT is the falsified-claim
    shape (Codex R11). CLAUDE.md defines the term precisely: server-stamping
    means the POST handler RE-COMPUTES from canonical state at POST time, NOT
    that a GET-rendered value is trusted on resubmit -- and `auto_fill_audit_at`
    is read straight off the submitted form and persisted. The anchors are
    therefore a tampering surface, which is exactly why the POST carries a
    rejection ladder over them rather than trusting them.
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
    existing_fill_order_ids: set[str] | None = None,
    existing_anonymous_fills: tuple[PossibleDuplicateFill, ...] | None = None,
) -> ExitAutoFillResult:
    """Resolve form-render-time exit auto-fill via Schwab Trader API.

    SILENT EXCLUSION REQUIRES PROVEN IDENTITY. VALUE-TUPLE EQUALITY IS NEVER
    PROOF (RD ruling, 2026-08-11, superseding his own earlier three-state
    formulation). Two evidence states govern whether an already-recorded fill
    suppresses a candidate:

      1. ``schwab_order_id`` present on BOTH sides -> identity is PROVEN or
         REFUTED. Exclusion by id is exact; ``existing_fill_order_ids`` does
         exactly that and is UNCHANGED.
      2. ANONYMOUS recorded fill (no ``schwab_order_id``), value-tuple match at
         EITHER grain -- its stored date equals the candidate's EXECUTION date,
         OR the candidate's ORDER-ENTERED date, same price and quantity ->
         the candidate is OFFERED carrying ``possible_duplicates`` naming
         EVERY such row. NEVER silently excluded. NEVER offered clean.

    THE LINE IS PROVENANCE, NOT GRAIN, and the fact that moved it is this: all
    ten anonymous non-entry fills on the live ledger are ``operator_typed`` --
    hand-typed dates. Which grain a human had in mind when typing is not merely
    unknown pending some migration, it is **unknowable in principle, forever**.
    No epoch, backfill or provenance column recovers it. An earlier version of
    this rule drew a bright line between a "same-grain" and an "other-grain"
    match and silently excluded the first; that line ran through a variable
    which does not exist, so the exclusion it authorised rested on nothing.

    The one-sidedness is deliberate and is the operator's own call: he accepts
    flagged re-offers of manually-typed exits rather than ever silently hiding
    a real fill. A visible duplicate invitation is adjudicable; a silent
    omission is not. Alarm, never assert -- and the affordance to record is
    never gated on the alarm.

    A COUNT-AND-SURFACE HALFWAY HOUSE (exclude when unambiguous, flag when
    several candidates share a tuple) was offered as a fallback floor and
    DECLINED. It is not the shipped behaviour and must not be reintroduced as
    an optimisation.

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
        now: the GET-generated render-time clock for the lookback upper
            bound + ``auto_fill_audit_at``; defaults to ``datetime.now(UTC)``.
            NOT "server-stamped" in the CLAUDE.md sense -- the resulting
            timestamp travels to the browser as a hidden input and the POST
            accepts it back (Codex R12). Tests that assert anything derived
            from it MUST pass a fixed value or freeze this module's clock.
        existing_fill_order_ids: optional set of Schwab order_ids that
            have ALREADY been persisted as fills for this trade (for
            partial_exited trades with one or more recorded SELL fills).
            Codex R1 Major #4 fix — without this exclusion, a partial-
            exited trade's auto-fill resolver would re-surface
            already-recorded SELL fills as candidates, letting the
            operator inadvertently double-record a fill. When supplied,
            candidates whose ``order_id`` is in the set are filtered out
            BEFORE the candidates list is built. Default ``None`` =
            no exclusion (backwards-compat for entry-side parity tests
            + the empty-set degenerate case).
        existing_anonymous_fills: the already-recorded non-entry fills for
            this trade that carry NO usable ``schwab_order_id`` — pre-v20
            fills, ``operator_typed`` fills, ``tos_import`` and
            ``imported_legacy`` fills, and envelopes whose only order-id key
            is ``selected_candidate_order_id``. Each is carried WITH its
            identity (``fill_id`` + stored date/price/quantity) so a match can
            NAME the row rather than merely suppress a candidate.

            THIS IS THE ONLY CHANNEL FOR ANONYMOUS ROWS AND IT CANNOT EXCLUDE.
            A prior ``existing_fill_value_tuples`` parameter carried the same
            population as bare tuples and silently filtered candidates that
            matched one; it was REMOVED rather than left dormant, because a
            parameter whose sole effect is the behaviour a ruling forbids is an
            invitation to reinstate it. Default ``None`` = no flagging.

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
    # Codex R1 Major #4 fix — when ``existing_fill_order_ids`` is
    # supplied (partial_exited trade with one or more recorded SELL
    # fills), filter out orders whose ``order_id`` is already a recorded
    # fill. Without this exclusion, operator could pick a candidate
    # corresponding to an already-persisted fill, creating a duplicate.
    # ----------------------------------------------------------------------
    excluded_ids: set[str] = (
        existing_fill_order_ids
        if isinstance(existing_fill_order_ids, set)
        else set()
    )

    def _passes_filters(o: Any) -> bool:
        if getattr(o, "instrument_symbol", "") != ticker:
            return False
        if getattr(o, "instruction", "") not in _SELL_INSTRUCTIONS:
            return False
        if not _is_execution_bearing_candidate(o):
            return False
        return not (
            excluded_ids and getattr(o, "order_id", None) in excluded_ids
        )

    # ONLY A PROVEN IDENTITY EXCLUDES (RD, 2026-08-11). The value-tuple
    # exclusion that used to sit here is GONE, and with it the multiplicity
    # problem it carried: a SET cannot say "one of these two", so one recorded
    # fill silently dropped every candidate sharing its tuple. That was flagged
    # rather than fixed while the rule still authorised value-equality
    # exclusion; the ruling removed the authority, and the defect dissolved
    # with it rather than being patched. Equal-clip scale-out candidates are
    # now all OFFERED, each flagged against the recorded row, so the silent
    # omission became visible adjudication.
    matches = [o for o in orders if _passes_filters(o)]
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
    #
    # Sort matches by EXECUTION date ASCENDING so the candidates list carries
    # chronological order (oldest first; most-recent last). Then build
    # candidates from the sorted matches; _build_candidate returns
    # ``(None, <refusal reason>, None)`` for orders lacking an execution-grain
    # price/quantity (mapper edge case) or a usable date, so candidates may
    # have fewer entries than matches — and the ``no_usable_date`` refusals are
    # COUNTED below rather than dropped on the floor.
    #
    # D31 — the sort key was ``enter_time``, which makes "most recent" mean
    # "the order the operator TYPED last". Two resting orders can be entered
    # in one order and fill in the other, so the default candidate could be a
    # fill that happened BEFORE the one it was preferred over. Correcting the
    # DATE without correcting the RANKING would have left "most recent"
    # measured on the clock the fix just retired.
    #
    # Per reviewer fix (T-B.2.1 follow-up): the chosen (default) candidate
    # is the LAST entry in the candidates list (most recent by execution
    # date) — NOT a second invocation of _compute_execution_price /
    # _resolve_match_quantity against the raw order. This guarantees the
    # chosen values are consistent with what _build_candidate validated +
    # avoids a TypeError when _resolve_match_quantity returns None for
    # partial-then-canceled MARKET orders.
    # ----------------------------------------------------------------------
    sorted_matches = sorted(matches, key=_candidate_sort_key)
    _warn_on_mixed_candidate_offsets(ticker, sorted_matches)
    anonymous_fills: tuple[PossibleDuplicateFill, ...] = (
        tuple(existing_anonymous_fills) if existing_anonymous_fills else ()
    )
    candidates: list[ExitAutoFillCandidate] = []
    date_sources: dict[str, str] = {}
    # EVERY refusal is counted, not just the date one (cold audit). A fill
    # dropped for an unresolvable price or quantity is exactly as absent from
    # the operator's list as one dropped for an unusable date, and the list
    # looks equally complete either way. Counting only the reason this arc
    # happened to introduce would have announced one third of the omissions
    # while the mechanism to announce all of them was already built.
    #
    # Declining the WHOLE auto-fill -- the entry-side posture -- would be wrong
    # here: the entry side has one order, this surface has N, and hiding N-1
    # good candidates to protest one bad one is a worse trade for the operator.
    omitted: dict[str, int] = {}
    for o in sorted_matches:
        cand, outcome, match_quantity = _build_candidate(o)
        if cand is not None:
            cand = replace(
                cand,
                date_source=outcome,
                # ``match_quantity`` is non-None exactly when ``cand`` is
                # non-None -- the builder returns them together and refuses
                # both when the quantity is unresolvable, which is why this
                # branch can pass it straight through. It is the untruncated
                # quantity, threaded so the alarm compares Schwab's number
                # rather than the dataclass's truncation of it (B review
                # MAJOR 3).
                possible_duplicates=_undecidable_duplicates(
                    o, cand, anonymous_fills,
                    match_quantity=match_quantity,
                ),
            )
            candidates.append(cand)
            date_sources[cand.signature_hash] = outcome
        else:
            omitted[outcome] = omitted.get(outcome, 0) + 1
    if not candidates:
        # EVERY match was refused, and the operator is told WHICH reasons
        # (orchestrator B review round 2, MAJOR B). This branch used to state a
        # fixed sentence -- "lacked an execution-grain price/quantity or a
        # usable execution date" -- which enumerated the reasons that existed
        # when it was written and read as a complete account of why the list is
        # empty. It is false for a fill refused for anything else: a
        # sub-one-share execution has a price, a quantity and a date. The
        # reasons are now rendered from the same map the populated advisory
        # uses, so a reason cannot be announced on one exit and denied on the
        # other. ``omitted`` is necessarily non-empty here: reaching this line
        # means ``matches`` was non-empty (the no-matches case returned above)
        # and every one of them incremented a counter.
        return ExitAutoFillResult(
            kind="empty",
            fill_origin="operator_typed",
            advisory_text=(
                f"No Schwab SELL fill for {ticker} could be listed "
                f"({_omission_reason_summary(omitted)}); please enter "
                "manually."
            ),
            auto_fill_audit_at=auto_fill_audit_at,
        )

    # Most-recent candidate (last in chronological list) drives the
    # default form values; the full candidates list lets operator select
    # another fill if scaled out.
    chosen = candidates[-1]

    # Build a stable signature for the chosen fill so the
    # schwab_source_value_json carries provenance equivalent to the
    # candidate the operator sees defaulted. Use chosen.* directly to
    # guarantee envelope-vs-candidate value consistency.
    #
    # Codex R1 Critical #1 + Major #1 fix — add ``candidates_map``, keyed by
    # signature_hash, as the truth source the POST handler prefers OVER THE
    # VISIBLE INPUT BOXES.
    #
    # IT IS NOT A SERVER-SIDE TRUTH SOURCE AND THE POST CANNOT PROVE
    # PROVENANCE (cold audit + Codex R8). The whole envelope round-trips
    # through a hidden form field, so a client can alter the map and the
    # signature TOGETHER; what the handler establishes is CONSISTENCY WITHIN
    # THE SUBMITTED ENVELOPE, and only when that envelope carries a non-empty
    # map (its check is `if candidates_map and submitted_hash not in
    # candidates_map`, so a legacy envelope with no map skips it entirely).
    # Making this unforgeable needs a SIGNED envelope, which is a design
    # decision outside this arc and is flagged rather than improvised.
    #
    # The POST handler uses this map to:
    #   (a) reject a submitted signature_hash that does not appear in its own
    #       submitted map (400) — a consistency gate, not a forgery gate;
    #   (b) look up the authoritative price/date/quantity for the selected
    #       candidate so multi-partial radio selection actually drives
    #       persisted values (closes Critical #1 — the template's radio
    #       inputs did not rebind visible form fields, so without the
    #       authoritative map, the operator's selection was semantically
    #       meaningless).
    # Sort_keys=True makes the JSON stable across runs for test parity.
    #
    # D31 — ``date_source`` rides on EACH map entry, not once at the top
    # level. The operator can select any candidate and the POST handler reads
    # ``candidates_map[submitted_hash]`` as authoritative, so a single stamp
    # would label whichever candidate he picked with the DEFAULT's provenance
    # (gotcha #30). The top-level ``exit_date_source`` describes the top-level
    # ``exit_date``, i.e. the default, and nothing else.
    candidates_map = {
        cand.signature_hash: {
            "date": cand.date,
            "date_source": date_sources[cand.signature_hash],
            "price": cand.price,
            "quantity": cand.quantity,
            "order_id": cand.order_id,
            # The PERSISTED envelope records that this candidate was offered
            # under an undecidable-identity alarm, so if a double-record ever
            # happens the fill's own audit trail shows EVERY row it might
            # duplicate -- the same list the operator was shown.
            "possible_duplicates": [
                {
                    "fill_id": dup.fill_id,
                    "date": dup.date,
                    "price": dup.price,
                    "quantity": dup.quantity,
                }
                for dup in cand.possible_duplicates
            ],
        }
        for cand in candidates
    }
    schwab_source_value_json = json.dumps(
        {
            "exit_date": chosen.date,
            "exit_date_source": date_sources[chosen.signature_hash],
            "exit_price": chosen.price,
            "closed_shares": chosen.quantity,
            "schwab_order_id": chosen.order_id,
            "schwab_instrument_symbol": ticker,
            "candidate_count": len(candidates),
            "candidates_map": candidates_map,
        },
        sort_keys=True,
    )

    # An omission the operator cannot see is worse than one he can (Codex R1
    # Major 2). A populated result carried ``advisory_text=None`` before D31
    # and still does whenever nothing was omitted AND every listed candidate was
    # dated from its executions -- the template renders this text whenever it is
    # set, so a standing advisory on every populated result would train the
    # operator to ignore it.
    #
    # THE FALLBACK IS ANNOUNCED TOO (cold audit). The derivation calls its
    # ``enter_time`` fallback "visible", and it is -- in the audit envelope. The
    # TEMPLATE renders no provenance, so an operator looking at the form saw an
    # ORDER-ENTERED date presented exactly like an execution date, which is the
    # defect this whole arc exists to stop. A stamp in hidden JSON is audit
    # data, not disclosure.
    #
    # THE DUPLICATE ALARM LEADS, and it is in the ADVISORY as well as on the
    # candidate. The template renders the per-candidate list only at length
    # >= 2, so a single-fill render would otherwise carry the flag in an
    # envelope nobody reads. It is stated first because it is the only one of
    # these messages that can cost the operator a wrong ledger row.
    advisory_parts: list[str] = []
    flagged = [c for c in candidates if c.possible_duplicates]
    if flagged:
        # NEUTRAL WORDING (Codex R16 minor). An earlier draft told the operator
        # the matching row was "recorded under the OLD date convention" and was
        # "dated when the ORDER WAS PLACED". That is an assertion about which
        # grain a HAND-TYPED date used -- the very thing ruled unknowable, and
        # false on its face for a row matching the candidate's own execution
        # date. The message states the EVIDENCE and leaves the conclusion to
        # the operator, which is the whole point of alarming instead of
        # asserting.
        named = "; ".join(
            f"fill #{dup.fill_id} recorded {dup.date} at {dup.price:.2f} x "
            f"{dup.quantity:g} (offered here as {c.date} at {c.price:.2f} x "
            f"{c.quantity})"
            for c in flagged
            for dup in c.possible_duplicates
        )
        # NUMBER-NEUTRAL (Codex R20). The single-candidate/single-row case
        # is the COMMON one, and the previous phrasing read "1 offered fill
        # match already-recorded fills" -- ungrammatical, and implying several
        # recorded rows where there is one. "has one or more matches" and
        # "Each matching recorded fill" are true at every cardinality without
        # branching the sentence three ways.
        noun = "fill has" if len(flagged) == 1 else "fills have"
        advisory_parts.append(
            f"POSSIBLE DUPLICATE: {len(flagged)} offered {noun} one or more "
            f"matches among already-recorded fills on price and quantity, "
            f"with each recorded date equal to the offered date or to the "
            f"date its order was entered -- {named}. Each matching recorded "
            "fill carries no usable broker order id for the values that were "
            "recorded, so nothing here can tell whether it is the same fill "
            "or a different one. Check the trade's recorded fills before "
            "submitting."
        )
        log.warning(
            "schwab exit auto-fill: %s -- %d candidate(s) match an anonymous "
            "recorded fill on value and date with no id to decide identity "
            "(fill_ids %s); offered WITH the alarm, not suppressed",
            ticker, len(flagged),
            ", ".join(
                str(dup.fill_id)
                for c in flagged
                for dup in c.possible_duplicates
            ),
        )
    fallback_dates = sorted(
        cand.date for cand in candidates
        if date_sources.get(cand.signature_hash) == "enter_time"
    )
    if fallback_dates:
        n = len(fallback_dates)
        advisory_parts.append(
            (
                f"{n} listed fill could not be dated from its Schwab "
                "execution times, so the date shown is when the ORDER WAS "
                if n == 1 else
                f"{n} listed fills could not be dated from their Schwab "
                "execution times, so each date shown is when the ORDER WAS "
            )
            + f"PLACED, not when it filled ({', '.join(fallback_dates)}). "
            + "Check against the broker before submitting."
        )
        log.warning(
            "schwab exit auto-fill: %d %s candidate(s) fell back to the "
            "order-entered date (%s)",
            n, ticker, ", ".join(fallback_dates),
        )
    omitted_total = sum(omitted.values())
    if omitted_total:
        reasons = _omission_reason_summary(omitted)
        noun = "fill is" if omitted_total == 1 else "fills are"
        advisory_parts.append(
            f"{omitted_total} Schwab SELL {noun} NOT listed here "
            f"({reasons}). Check the broker and record manually."
        )
        log.warning(
            "schwab exit auto-fill: %d %s SELL fill(s) omitted from the "
            "candidate list (%s)",
            omitted_total, ticker,
            ", ".join(f"{r}={c}" for r, c in sorted(omitted.items())),
        )
    omission_advisory: str | None = " ".join(advisory_parts) or None

    return ExitAutoFillResult(
        kind="populated",
        fill_origin="schwab_auto",
        exit_date=chosen.date,
        exit_price=chosen.price,
        closed_shares=chosen.quantity,
        candidates=candidates,
        advisory_text=omission_advisory,
        schwab_source_value_json=schwab_source_value_json,
        auto_fill_audit_at=auto_fill_audit_at,
        schwab_api_call_id=None,
    )


def _build_candidate(
    o: Any,
) -> tuple[ExitAutoFillCandidate | None, str, float | None]:
    """Build an ExitAutoFillCandidate from a SchwabOrderResponse.

    Returns ``(candidate, date_source, match_quantity)`` on success, where
    ``date_source`` is the grain that produced the candidate's date (see
    ``_execution_date``). The source rides OUT here rather than on the dataclass
    because it is provenance about the derivation, not part of the fill's
    identity — the audit envelope carries it PER CANDIDATE (gotcha #30: a single
    stamp is not provenance for N rows, and this surface has N rows the operator
    can select between).

    ``match_quantity`` IS THE UNTRUNCATED EXECUTION-GRAIN QUANTITY, and it rides
    out for the same reason (orchestrator B review MAJOR 3). The dataclass field
    is typed ``int`` and this function truncates into it; widening that field
    touches the persisted envelope, the form and the signature input, so it is a
    separate arc. Meanwhile the duplicate-flag comparison MUST see the real
    number: ``PossibleDuplicateFill.quantity`` is a float precisely because
    truncating a stored 5.9 to 5 names the wrong row, and the OFFERED side was
    still truncating. Threaded rather than re-derived: re-invoking
    ``_resolve_match_quantity`` against the raw order is what the note above
    ``sorted_matches`` warns against, and a second derivation can drift from the
    one this function validated and hashed. ``None`` exactly when the candidate
    is ``None``.

    THE BANKED ``int`` -> ``float`` MIGRATION OF THAT FIELD CARRIES A SECOND
    COST, RECORDED HERE SO THE NEXT SCOPING SEES IT WHOLE (RD, 2026-08-11,
    re-deciding on the orchestrator's B review round 2). While the field stays
    an ``int``:

      - a sub-one-share execution CANNOT BE OFFERED AT ALL. It is refused below
        as ``'sub_one_share_quantity'`` and announced, so the operator records
        it by hand rather than losing the page -- visible degradation, the
        standard every ruling on this surface has taken, but a real capability
        gap and not merely a display artefact.
      - for any fractional quantity >= 1 the value HASHED, the value COMPARED
        and the value PERSISTED disagree: a 10.9-share execution is hashed and
        duplicate-compared as 10.9 (via ``match_quantity``) while being
        displayed, submitted and persisted as 10, linked to that order's id.

    RD's live query over the ledger found 43 fills and ZERO fractional
    quantities, so neither has a live instance today. Neither is
    schema-prevented: ``fills.quantity`` is ``REAL`` (migration 0014) and
    ``SchwabExecutionLeg.__post_init__`` admits any finite ``> 0``.

    Returns ``(None, <refusal reason>, None)`` when the order cannot become a
    candidate. THE REASON IS RETURNED, not swallowed (Codex R1 Major 2): a
    refusal that leaves OTHER candidates standing produces a list that looks
    complete while omitting a real fill, and the caller can only say so out
    loud if it knows why the omission happened. The reasons are
    ``'no_execution_price'``, ``'no_quantity'``, ``'sub_one_share_quantity'``
    and ``'no_usable_date'``, and EVERY one of them is announced -- see
    ``_OMISSION_REASON_TEXT``, which the caller renders into the operator's
    advisory on both the populated and the all-refused exit.

    Uses execution-grain helpers per CLAUDE.md "Pass-1-tier-1 Sub-bundle 1"
    discipline — do NOT consume raw ``so.price``.
    """
    price = _compute_execution_price(o)
    if price is None:
        return None, "no_execution_price", None
    quantity = _resolve_match_quantity(o)
    if quantity is None or quantity <= 0:
        return None, "no_quantity", None
    # THE TRUNCATION IS SPELLED, NOT A THRESHOLD RE-DERIVED FROM IT
    # (orchestrator B review round 2, MAJOR B). ``int(quantity) <= 0`` is the
    # exact expression the constructor call below performs, checked against the
    # exact test ``__post_init__`` applies to the result; writing ``< 1``
    # instead would state the same boundary in a second place, free to drift
    # from the truncation it is guarding. A cleanly-resolved 0.9 otherwise
    # became ``0``, the validator raised, and -- with no ``try/except`` in the
    # build loop and a ``try/FINALLY`` in the VM caller -- the exception
    # reached the route and took the whole trade-detail page down.
    if int(quantity) <= 0:
        return None, "sub_one_share_quantity", None
    date, date_source = _execution_date(o)
    if not date:
        return None, "no_usable_date", None
    order_id = getattr(o, "order_id", None)
    sig = _compute_signature_hash(
        order_id=order_id,
        date=date,
        price=price,
        quantity=quantity,
        enter_time=getattr(o, "enter_time", ""),
    )
    return (
        ExitAutoFillCandidate(
            date=date,
            price=float(price),
            quantity=int(quantity),
            signature_hash=sig,
            order_id=order_id,
        ),
        date_source,
        float(quantity),
    )


def _candidate_sort_key(o: Any) -> tuple[str, float, str]:
    """Chronological ordering key for the candidate list (D31).

    PRIMARY is the derived EXECUTION date — "most recent" on this surface
    means most recently EXECUTED, since that is the fill the operator is
    recording.

    SECONDARY is the winning leg's absolute INSTANT, which is what orders two
    fills that executed on the SAME date. An earlier draft used ``enter_time``
    here and claimed the derivation had "nothing finer" to rank on; that was
    false about the DATA (``executions[*].time`` carries full timestamps) and
    would have defaulted the form to whichever same-day fill was ORDERED last
    rather than EXECUTED last (Codex R1 Major 3). The instant comes from
    ``latest_execution_leg_instant``, which shares one ranking pass with the
    date reader, so the two cannot disagree about which leg won.

    A candidate whose date came from the ``enter_time`` FALLBACK has no known
    execution instant, and is NOT ranked as though it did: it takes ``-inf``
    and therefore sorts before any same-date candidate we actually dated from
    its execution. Preferring a genuinely-dated fill as the default is the
    conservative choice, and TERTIARY ``enter_time`` keeps that group's order
    stable.

    A candidate whose date is unresolvable sorts first; ``_build_candidate``
    drops it immediately afterwards, so its position never reaches the
    operator.

    THE DATE STAYS PRIMARY, AND THE RESIDUE IS NAMED RATHER THAN TRADED AWAY
    (Codex R4 Major). The date is the leg's OWN offset-local calendar prefix,
    so across two orders carrying DIFFERENT utc offsets the local-date order
    and the absolute-instant order can disagree, and this key would then rank
    by local date. The shared helper refuses mixed offsets WITHIN one order for
    exactly that reason, but it cannot see across orders. Promoting the instant
    to primary was rejected: the operator picks from a list that DISPLAYS these
    dates and the chosen one is what gets recorded, so an instant-primary order
    would show him 2026-08-05 above 2026-08-04 and default to the row reading
    earlier — incoherent on the surface it exists to serve — and it would
    introduce exactly the offset-arithmetic divergence from the reconciliation
    guard that ``execution_dates`` was written to prevent. The condition is
    LOGGED instead, so a mis-ordering is observable rather than silent, and it
    is not a live path: Schwab emits ``+0000`` on every execution leg (checked
    against the live DB — every stored leg time, all ``+0000``).
    """
    date, source = _execution_date(o)
    instant = _execution_instant(o) if source == "execution_leg" else None
    return (
        date or "",
        instant.timestamp() if instant is not None else float("-inf"),
        str(getattr(o, "enter_time", "") or ""),
    )


def _undecidable_duplicates(
    order: Any,
    candidate: ExitAutoFillCandidate,
    anonymous_fills: tuple[PossibleDuplicateFill, ...],
    *,
    match_quantity: float,
) -> tuple[PossibleDuplicateFill, ...]:
    """Every anonymous recorded fill this candidate MIGHT duplicate.

    Returns an empty tuple when nothing matches.

    BOTH SIDES OF THE QUANTITY COMPARISON ARE UNTRUNCATED (orchestrator B
    review MAJOR 3). ``match_quantity`` is the execution-grain quantity
    ``_build_candidate`` resolved, validated (``not None and > 0``) and hashed
    for THIS order; the candidate's own ``quantity`` field is an ``int`` that
    truncated it. Reading the field made a 10.9-share execution compare as
    10.0, which stayed SILENT against a recorded 10.9 and FIRED against a
    recorded 10.0 -- the same defect ``PossibleDuplicateFill.quantity`` was
    made a float to prevent, surviving on the other side of the equality.

    ALL MATCHES ARE RETURNED, NOT THE FIRST (Codex R16 major). An earlier
    version named one and argued that pointing the operator at the ledger was
    enough. It is not, now that nothing is excluded: shown one row, he can
    rule it out and record a fill that duplicates the OTHER one he was never
    told about. Naming a subset of the ambiguity is its own quiet failure.

    BOTH GRAINS MATCH (RD, 2026-08-11). The candidate's price and quantity are
    compared against each anonymous row's, and its date is compared at EITHER
    grain: the date the candidate carries (its EXECUTION date, or its entered
    date when the execution legs were unusable), and the date this module would
    have recorded for the same order BEFORE the grain cutover.

    The earlier version matched only the pre-cutover grain, on the theory that
    a same-grain match was decidable and could keep excluding. It is not:
    every anonymous row on this ledger is ``operator_typed``, a hand-typed
    date, so which grain the human had in mind is unknowable in principle. A
    match at either grain therefore carries exactly the same evidentiary
    weight -- some -- and the same response.

    IT USES THE RETIRED, TOLERANT ``_extract_iso_date`` ON PURPOSE, and that is
    the one place in this module that still should (Codex R14 major). This
    function's job is to reproduce WHAT THE OLD CODE WOULD HAVE STORED, and the
    old code took whatever ``_extract_iso_date`` returned -- a split on ``T``,
    no canonical check. So ``enter_time="2026-08-03Tjunk"`` really did propose,
    and the operator really did record, ``2026-08-03``. Reconstructing that with
    the NEW strict ``_canonical_date`` yields ``None``, the alarm stays silent,
    and the candidate is offered clean -- recreating the exact double-record the
    compatibility path exists to prevent. Modelling a retired behaviour requires
    the retired rule; the strict rule governs what this module WRITES, which is
    a different question.

    NOTHING IS REMOVED BEFORE THIS RUNS. ``_passes_filters`` no longer excludes
    on value tuples at all, so every candidate an anonymous row could match is
    still in the list when this is called. Under the previous rule the
    same-grain matches were filtered upstream and could never be seen here --
    the alarm could not have fired on them even had it looked.

    The alarm's job is to send the operator to the ledger, not to resolve the
    ambiguity for him -- but it must send him to ALL of it, which is why every
    match is returned rather than the first.
    """
    if not anonymous_fills:
        return ()
    try:
        price = round(float(candidate.price), 2)
        quantity = float(match_quantity)
    except (TypeError, ValueError):
        return ()
    dates = {candidate.date}
    entered_date = _extract_iso_date(getattr(order, "enter_time", "") or "")
    if entered_date:
        dates.add(entered_date)
    matches: list[PossibleDuplicateFill] = []
    for row in anonymous_fills:
        try:
            row_price = round(float(row.price), 2)
            row_quantity = float(row.quantity)
        except (TypeError, ValueError):
            continue
        if (
            row_price == price
            # NOT `==` (Codex R1 major on the B-review fix). The offered
            # quantity is a SUM over execution legs, and binary floating point
            # does not sum exactly: 10.1 + 0.2 is 10.299999999999999, which is
            # not equal to a ledger row's 10.3. Exact equality would therefore
            # offer a genuine duplicate CLEAN -- the silent miss this whole
            # surface exists to prevent, re-introduced by the fix that made the
            # comparison fractional-precise.
            #
            # THE TOLERANCE IS SIZED AGAINST THE ERROR IT ABSORBS, NOT AGAINST
            # A SHARE GRAIN (orchestrator B review round 2, MINOR C). An
            # earlier version of this comment justified 1e-9 as "five orders of
            # magnitude below the smallest meaningful share difference (1e-4)".
            # No such grain exists: `fills.quantity` is `REAL NOT NULL CHECK
            # (quantity > 0)` with no quantisation, the repo writer rounds
            # nothing, and `SchwabExecutionLeg.__post_init__` admits any finite
            # `> 0`. The tolerance was defensible; the reason given for it was a
            # claim the code does not support.
            #
            # What 1e-9 actually covers is IEEE-754 double summation error over
            # the execution legs -- relative error on the order of 1e-16, so an
            # absolute 1e-9 stays ample across any share count this ledger will
            # see while remaining tiny next to the differences the comparison is
            # meant to resolve. It is ABSOLUTE and `rel_tol=0` deliberately: a
            # relative slack would widen with the quantity, so a large position
            # would get a looser test than a small one for no stated reason.
            # The asymmetry is the point -- being slightly loose costs a
            # spurious flag the operator adjudicates, being exact costs a
            # silent miss, so this errs toward the ALARM.
            and math.isclose(row_quantity, quantity, rel_tol=0.0, abs_tol=1e-9)
            and row.date in dates
        ):
            matches.append(row)
    return tuple(matches)


def _execution_instant(order: Any) -> datetime | None:
    """The winning execution leg's absolute instant, or ``None``.

    A thin adapter over the shared ranking token so the two callers below spell
    the leg-time extraction once. Returns ``None`` for any order whose legs the
    shared helper refuses.
    """
    return latest_execution_leg_instant(
        getattr(leg, "time", None)
        for leg in (getattr(order, "executions", None) or [])
    )


def _warn_on_mixed_candidate_offsets(ticker: str, matches: list[Any]) -> None:
    """Log when the candidate SET spans more than one utc offset (D31, Codex
    R4 Major).

    ``latest_execution_leg_date`` refuses mixed offsets WITHIN one order,
    because "the latest leg's date" stops having one answer; it cannot see
    ACROSS orders, where the same ambiguity reappears between the offset-local
    date this list is ordered and displayed by and the absolute instant the
    fills actually happened at. ``_candidate_sort_key`` explains why the date
    stays primary. This makes the condition observable rather than silent.
    Schwab emits ``+0000`` on every leg, so it is a canary, not a live path.
    """
    offsets: set[timedelta] = set()
    for o in matches:
        _, source = _execution_date(o)
        if source != "execution_leg":
            continue
        instant = _execution_instant(o)
        if instant is not None:
            offsets.add(instant.utcoffset() or timedelta(0))
    if len(offsets) > 1:
        log.warning(
            "schwab exit auto-fill: %s candidate fills span %d different utc "
            "offsets (%s); the candidate list is ordered by each leg's own "
            "offset-local date, which can differ from absolute execution "
            "order -- verify the default fill against the broker",
            ticker, len(offsets),
            ", ".join(sorted(str(off) for off in offsets)),
        )


def _execution_date(order: Any) -> tuple[str | None, str]:
    """D31 (exit half) — the exit date, taken from the EXECUTION grain.

    Returns ``(iso_date, source)`` where ``source`` is ``'execution_leg'`` or
    ``'enter_time'``. ``(None, 'enter_time')`` means "no usable date at either
    grain"; the caller MUST treat that as "no candidate", never as a value.

    The order carries BOTH facts: ``enter_time`` is when the order was ENTERED
    and ``executions[*].time`` is when it EXECUTED. For a resting order those
    differ — live evidence: fill 40 (trade 19, FTRE, ``action='stop'``) was
    entered 2026-08-03, executed 2026-08-04, and the framework proposed
    2026-08-03 for the operator to correct by hand. This module was already
    execution-grain for PRICE (``_compute_execution_price``); this makes it
    execution-grain for the DATE too.

    THE EXIT-SIDE INVARIANT, stated where the grain is chosen. It is NOT the
    entry side's three-row coupling and must not be read as one: **there is no
    ``trades.exit_date`` column.** The exit date is SINGLE-HOMED in
    ``fills.fill_datetime`` (written by ``record_exit`` from the submitted
    ``exit_date``), it DERIVES into ``trades.last_fill_at``
    (``MAX(fill_datetime)``, recomputed by ``_recompute_aggregates`` in the
    same transaction as every fill insert), and it is CHECKED — not mirrored —
    against the broker by ``schwab_reconciliation._fill_execution_session_
    distance``. So one home, one derived denorm, one external cross-check, and
    nothing to keep in step at write time.

    That third fact is why the execution grain is not a preference here: the
    guard ALREADY reads ``fills.fill_datetime`` as an execution date, so an
    auto-fill defaulting to the ORDER-ENTERED date was feeding it a value of a
    different KIND.

    THE GUARD IS A TOLERANCE, NOT AN EQUALITY, and overstating it would be the
    same defect this arc exists to fix (Codex R1 Minor). It returns the MAX
    NYSE-session distance across ALL legs of the matched order, and the
    classifier admits tier-1 while that distance is ``<=
    _MAX_TIER1_SESSION_DISTANCE``, which is **1**. So a one-session straddle —
    the ordinary overnight rest, and the live fill-40 shape — was recorded on
    the wrong date and passed the guard SILENTLY. Distance is counted in NYSE
    SESSIONS, not calendar days, so a Friday-entered order filling Monday is
    also distance 1 and also passes; raising anything requires at least one
    intervening TRADING session (verified by execution: Fri 2026-08-07 to Mon
    2026-08-10 is 1, Mon 2026-08-03 to Wed 2026-08-05 is 2 — Codex R2 Minor
    corrected an earlier draft that said a weekend was enough). The defect was
    therefore mostly invisible to reconciliation rather than loudly flagged by
    it, which is the worse of the two and the reason it survived to be caught
    by hand.

    Rules, and the response to each:

    - Parse EVERY leg's ``time`` and take the LATEST. Never index the list:
      ``_extract_executions_from_order_raw`` builds it with a plain ``append``
      in API order and never sorts.
    - If ANY leg's ``time`` is unparseable, or the legs do not share one utc
      offset, the shared helper REFUSES the whole collection and this falls
      back to the entered date — a partial view of an order's own fills must
      not silently date the exit. The fallback is stamped in the returned
      source, which reaches the audit envelope AND (cold audit) an
      operator-facing advisory on the form: a stamp in hidden JSON is audit
      data, not disclosure, and an unannounced fallback shows the operator an
      order-entered date presented exactly like an execution date — the defect
      this module was changed to stop.
    - An execution cannot precede its own order. The RULE is shared; the
      RESPONSE here is a visible fallback to the entered date, because this is
      a form default the operator sees and can override, not a ledger rewrite.

    The ranking, the canonical-date standard and the chronology rule all live
    in ``swing/trades/execution_dates.py`` and are NOT reimplemented here —
    two implementations of one derivation is the #24-#26 divergence class.

    REACHABILITY IS PINNED IN TESTS, NOT ASSERTED HERE — and the rule earned
    itself inside this very arc (Codex R3 Minor). An earlier draft of this
    paragraph said an EMPTY ``executions`` list "never reaches this function"
    because ``_compute_execution_price`` refuses first. That was FALSE THE
    MOMENT IT WAS WRITTEN: ``_candidate_sort_key`` calls this function for
    every match during ``sorted()``, which runs BEFORE ``_build_candidate``
    checks the price. The claim was voided by a change made 200 lines away in
    the same commit that wrote it, and it still read plausibly.

    What is true, and is asserted rather than described: an empty ``executions``
    list DOES reach here (through the sort key) and takes the ``enter_time``
    fallback, but such an order cannot become a candidate, because
    ``_build_candidate`` refuses it for ``'no_execution_price'`` first. The
    reachable fallback for a REAL candidate is a PRESENT-but-unusable leg time
    — ``SchwabExecutionLeg.__post_init__`` validates ``time`` as non-empty,
    never as parseable.

    THE FALLBACK IS HELD TO THE SAME CANONICAL STANDARD AS THE LEGS.
    ``_extract_iso_date`` only splits on ``T``/space and slices, so a compact
    ``20260803T134500`` ``enter_time`` becomes ``"20260803"`` — not a date.
    ``SchwabOrderResponse.__post_init__`` does not validate ``enter_time``,
    ``fills.fill_datetime`` is a bare ``TEXT NOT NULL``, and ``record_exit``
    normalizes rather than refuses, so nothing downstream catches it while
    every ``[:10]`` prefix and lexical date comparison downstream would
    mis-order it. A non-canonical fallback therefore yields ``None`` and the
    caller declines the candidate.
    """
    executions = getattr(order, "executions", None) or []
    execution_date = latest_execution_leg_date(
        getattr(leg, "time", None) for leg in executions
    )
    # CANONICALIZE THE ENTERED TIMESTAMP ONCE, BEFORE ANYTHING COMPARES AGAINST
    # IT (Codex R4 Minor). An earlier draft fed the raw ``_extract_iso_date``
    # SLICE to the chronology rule, and that slice is not a date: a malformed
    # ``9999-99-99Tjunk`` slices to ``9999-99-99``, which sorts lexically after
    # every real execution date, so a perfectly good execution-grain date was
    # discarded on the evidence of garbage in an unrelated field -- and then the
    # fallback refused the same garbage, dropping the candidate entirely. One
    # canonical value now serves both the comparison and the fallback; when it
    # is ``None`` there is nothing trustworthy to compare against, and
    # ``execution_precedes_order`` correctly declines to refuse on a ``None``.
    entered_date = _canonical_date(getattr(order, "enter_time", "") or "")
    if execution_precedes_order(execution_date, entered_date):
        execution_date = None
    if execution_date is not None:
        return execution_date, "execution_leg"
    return entered_date, "enter_time"


def _canonical_date(raw: Any) -> str | None:
    """The canonical ``YYYY-MM-DD`` of ONE timestamp string, or ``None``.

    Deliberately the SHARED leg standard applied to a single value rather than
    a second predicate spelling out the same rules: ``latest_execution_leg_
    date`` already requires a ``str`` whose first ten characters ARE the
    canonical date of what it parses to, and returns ``parsed.date()
    .isoformat()``. Restating those rules here would be the #24-#26 class in
    miniature, inside one file.
    """
    return latest_execution_leg_date((raw,))


def _compute_signature_hash(
    *,
    order_id: str | None,
    date: str,
    price: float,
    quantity: float,
    enter_time: str,
) -> str:
    """Compute a stable signature hash for a candidate.

    Includes the broker order_id (when present) plus a tuple of fill identity
    fields so candidates with the same shape but different underlying Schwab
    orders get distinct hashes.

    IT IS NOT AN IDEMPOTENCY KEY, and saying it was is what made the D31
    date-grain change look like a data-compatibility question (Codex R9). The
    hash is computed fresh at every form render, round-trips through that
    render's own hidden inputs, and is checked at POST against the SAME
    render's ``candidates_map``. Nothing recomputes a hash at POST time and
    NOTHING READS A PERSISTED ONE BACK: `selected_candidate_signature_hash`
    and `other_candidate_signature_hashes` are written into
    `fills.schwab_source_value_json` and have no reader in `swing/` at all,
    while a future render SUPPRESSES only on a matching `schwab_order_id` and
    merely FLAGS a (date, price, quantity) match against an anonymous recorded
    row -- since the 2026-08-11 ruling that channel neither dedupes nor
    excludes. So changing what `date` means changes every
    hash and invalidates NOTHING -- the correct scope is
    operator-selection round-trip + audit provenance.
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
    "ExitAutoFillCandidate",
    "ExitAutoFillKind",
    "ExitAutoFillResult",
    "ExitFillOrigin",
    "PossibleDuplicateFill",
    "resolve_exit_auto_fill",
]
