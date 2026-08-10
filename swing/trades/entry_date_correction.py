"""Item-5 T2 — the audited entry-date correction surface.

RD ruling ``20260801T145327Z`` part 2: an audited override for a recorded
``trades.entry_date``, following the D19 / ``journal cash-void`` precedent —
CLI-only, NO SCHEMA, reason-required, append-only AUDIT.

**Where this follows D19 and where it does not.** ``cash_movements`` is an
append-only ledger, so D19's fix is a REVERSING ENTRY. ``trades.entry_date``
is a mutable column with exactly one truth; there is no reversing entry that
makes an eight-day error net to zero. So the append-only property attaches to
the AUDIT TRAIL (``reconciliation_corrections``, which CLAUDE.md already pins
as APPEND-ONLY) and not to the corrected value — the same asymmetry every
existing tier-1/2/3 correction lives under.

**The correction must hang off a FINDING.** ``reconciliation_corrections``
declares ``discrepancy_id`` and ``reconciliation_run_id`` NOT NULL with FKs,
so a correction cannot float. This surface therefore REQUIRES an existing
discrepancy and inherits its run. The alternative — minting a synthetic
``source='system_audit'`` run plus a discrepancy — would have to choose a
``discrepancy_type`` for the row it mints, and none of them truthfully says
"the operator noticed a recorded entry date is wrong and there is no finding".
Buying generality by minting a MISTYPED row is the precise failure this arc
exists to stop. **The gap that leaves is named, not hidden:** an entry-date
error with NO reconciliation finding remains uncorrectable through a supported
path. That is a real, reduced-scope residue of D19.

**``entry_date`` is not one field.** ``swing/trades/entry.py``'s ``record_entry``
fans it into four values, and a correction that moved only ``trades.entry_date``
would leave the ledger MORE incoherent than it found it — and, critically,
would not close the finding, because the A2-date guard that raises these
measures against ``fills.fill_datetime`` and never against ``trades.entry_date``
(``schwab_reconciliation.py`` ``_fill_execution_session_distance``). Three of
the four move here:

  - ``trades.entry_date`` — the ruled correction;
  - ``fills.fill_datetime`` on the discrepancy's OWN bound entry fill —
    required, or the finding's cause survives the correction;
  - ``watchlist_archive.removed_date`` on the ``reason='entered'`` row —
    written from ``req.entry_date`` at ``entry.py``, so it carries the same
    defective value.

**``trades.pre_trade_locked_at`` is DELIBERATELY NOT MOVED (RD, 2026-08-09).**
It is written as ``entry_date + 'T16:00:00'`` and RD verified it equals exactly
that on 20 of 20 live trades, zero exceptions — it is a SYNTHETIC RESTATEMENT
of the very column under correction, not independent evidence about the world.
Moving it to the corrected date would manufacture a lock time for which there
is zero evidence. So it stays, and the resulting inconsistency is NAMED in the
correction reason: after the correction the row's ``pre_trade_locked_at`` is a
stale derivative of the PRE-correction ``entry_date``. A labelled inconsistency
beats an invented timestamp. For the same reason no reason text may cite it as
corroboration — that would assert an independence that does not exist.

**The target date is SERVER-DERIVED; ``--to`` only CONFIRMS it.** Every
authorization clause below establishes that date evidence EXISTS and DIFFERS
from the fill's date; none of them binds an operator-supplied date to it. So
the service derives the target from the discrepancy's own execution evidence,
using the SAME derivation the auto-fill uses
(``swing/trades/execution_dates.py``), and REFUSES unless ``--to`` equals it.
Otherwise a typo wearing an audit trail could write an unsupported date while
citing the finding as its justification — worse than the defect being closed,
because the current wrong date at least came from a real Schwab field.

Transaction contract (CLAUDE.md): the outer function ALWAYS owns
``BEGIN IMMEDIATE`` / COMMIT / ROLLBACK and REJECTS a caller-held transaction
(never auto-detects). The inner never commits, so a future reconciliation-flow
pivot can compose it under a SAVEPOINT. Every function it calls is repo-level
(``_recompute_aggregates``, ``insert_correction``) — none opens a ``with conn:``.
"""
from __future__ import annotations

import contextlib
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime
from typing import Any

from swing.data.models import ReconciliationCorrection
from swing.data.repos.fills import _recompute_aggregates, update_fill_datetime
from swing.data.repos.reconciliation import get_discrepancy
from swing.data.repos.reconciliation_corrections import insert_correction
from swing.data.repos.trades import get_trade, update_entry_date
from swing.data.repos.watchlist import (
    WatchlistArchiveMatchError,
    update_archive_removed_date,
)
from swing.evaluation.dates import is_trading_session
from swing.trades.execution_dates import (
    execution_precedes_order,
    latest_execution_leg_date,
)

__all__ = [
    "BOUND_ARCHIVE_KEY",
    "CORRECTED_FIELDS",
    "CORRECTION_ACTION",
    "CORRECTION_CHOICE",
    "ACTIVE_TRADE_CONSEQUENCES",
    "ACTIVE_TRADE_STATES",
    "TERMINAL_TRADE_STATES",
    "CallerHeldTransactionError",
    "EntryDateCorrectionError",
    "EntryDateCorrectionPreview",
    "EntryDateCorrectionResult",
    "correct_entry_date",
    "preview_entry_date_correction",
]


# ---------------------------------------------------------------------------
# The CLOSED field enum.
#
# ``_update_journal_field`` (reconciliation_auto_correct.py) interpolates a
# field name straight into SQL and its own docstring says callers MUST source
# it from a closed enum and NEVER accept raw operator input. This surface does
# not use that helper at all: every UPDATE below is a LITERAL statement in a
# narrow repo writer, and the operator supplies a DATE — never a field name.
# This tuple is the documented manifest of what one correction touches, pinned
# by a test so a silent widening is visible.
# ---------------------------------------------------------------------------
CORRECTED_FIELDS: tuple[str, ...] = (
    "trades.entry_date",
    "fills.fill_datetime",
    "watchlist_archive.removed_date",
)

# ``reconciliation_corrections.correction_action`` admits three values and only
# one of them is true here.
#
#   - ``auto_applied`` -- false; a human did this.
#   - ``operator_overridden`` -- false. ``ReconciliationCorrection``'s docstring
#     defines it as tier-3, an operator override OF A PRIOR TIER-1 CORRECTION,
#     and ``_apply_tier3_override_inner`` requires an existing ``correction_id``
#     to supersede. A discrepancy reaching this surface has no correction rows
#     to supersede, so the label would assert a supersession of nothing -- in a
#     ledger whose whole purpose here is to stop the system writing false
#     statements.
#   - ``operator_resolved_ambiguity`` -- true. The operator resolves the
#     finding by supplying the execution truth, paired with a correction row.
#
# ``models.py`` names ``operator_resolved_ambiguity`` with ``correction_choice
# IS NULL`` as an explicit LIFECYCLE CONTRADICTION -- one the schema
# deliberately does not enforce, to be caught at the service layer. So the
# action and the choice are a PAIR, and the service asserts the choice before
# INSERT. ``correct_entry_date`` is a controlled code owned by this surface; it
# is deliberately NOT a member of any ``get_choice_menu`` list, because this
# correction does not come from the tier-2 operator menu.
CORRECTION_ACTION = "operator_resolved_ambiguity"
CORRECTION_CHOICE = "correct_entry_date"

# The key under which the corrected `watchlist_archive` row's PRIMARY KEY is
# recorded in both value envelopes (and so in the trade_events payload, which
# carries the same dicts).
BOUND_ARCHIVE_KEY = "bound_watchlist_archive_id"

# ``reconciliation_discrepancies.resolution`` values from which a FRESH live
# mutation may be authorized. A terminal, already-dispositioned historical
# finding must never stand as a standing warrant to rewrite a trade's date.
AUTHORIZING_RESOLUTIONS: frozenset[str] = frozenset(
    {"unresolved", "pending_ambiguity_resolution"},
)

TERMINAL_TRADE_STATES: frozenset[str] = frozenset({"closed", "reviewed"})
ACTIVE_TRADE_STATES: frozenset[str] = frozenset(
    {"entered", "managing", "partial_exited"},
)

# The terminal ``fills.reconciliation_status`` every existing correction path
# writes for the fill it touched (reconciliation_auto_correct.py, three sites).
_FILL_RECONCILED_STATUS = "reconciled_discrepancy_resolved"

_AUTHORIZING_DISCREPANCY_TYPE = "entry_price_mismatch"

# What moving an ACTIVE trade's entry date actually does. This is the best
# inventory four adversarial review rounds produced; it is NOT a completeness
# claim. An acknowledgement flag that under-states what is being acknowledged
# is worse than no flag, so the refusal prints the whole list.
ACTIVE_TRADE_CONSEQUENCES: tuple[str, ...] = (
    "1. _recompute_aggregates WILL move trades.last_fill_at on a not-yet-"
    "exited position (the corrected entry fill is its latest fill).",
    "2. It can move trades.current_avg_cost on a multi-entry-fill trade (the "
    "ORDER BY fill_datetime ASC re-sort), and current_avg_cost feeds "
    "open-position capital heat and utilization (metrics/capital.py) -- i.e. "
    "POSITION SIZING INPUTS on a live position.",
    "3. The live advisory day-count and the day-3-5 window shift under the "
    "operator mid-position (trades/advisory.py).",
    "4. concurrent_open_positions (metrics/capital.py) re-windows.",
    "5. The MFE/MAE running anchor (trades/daily_management.py) moves for "
    "every FUTURE snapshot; past snapshots are persisted and stay.",
    "6. entry_date is the SELL-side lookback boundary for exit auto-fill "
    "(trades/exit_auto_fill.py). Moving it FORWARD narrows that window, so a "
    "partial exit executed between the old and new dates would drop out of "
    "the exit form's candidate set.",
    "7. The LATCH surface reads entry_date for eligibility, ordering AND "
    "fill-terminal ranking (latches/reader.py, latches/service.py), so the "
    "move can change whether the trade matches a latch at all and which "
    "terminal wins.",
    "8. The nightly briefing's open-position days_open (rendering/briefing.py) "
    "changes in tomorrow morning's briefing.",
    "9. Live open-R and PERSISTED future heat inputs derive from "
    "current_avg_cost (web/view_models/dashboard.py, trades/daily_management"
    ".py), and journal/tos_import.py bounds historical close-matching with "
    "the entry date, so which TOS CLOSE fills route to history versus live "
    "allocation changes.",
)

_ALLOW_ACTIVE_ACKNOWLEDGEMENT = (
    "[--allow-active acknowledged: the trade was NOT in a terminal state; the "
    "operator accepted the active-trade consequence inventory.] "
)


class EntryDateCorrectionError(ValueError):
    """Any refusal from this surface. A ``ValueError`` so the CLI boundary's
    existing ``except ValueError -> ClickException`` discipline applies."""


class CallerHeldTransactionError(EntryDateCorrectionError):
    """The outer function was called with a transaction already open."""


@dataclass(frozen=True)
class EntryDateCorrectionPreview:
    """What ``--dry-run`` knows, and what it deliberately does not.

    ``aggregates_before`` carries REAL current values; there is no
    ``aggregates_after``. Predicting them means re-implementing
    ``_recompute_aggregates`` in the preview path, and a second implementation
    of a derivation is the #24-#26 class invited into a preview. A dry run may
    show what it knows and MUST say what it does not.
    """

    trade_id: int
    ticker: str
    state: str
    discrepancy_id: int
    fill_id: int
    watchlist_archive_id: int
    target_date: str
    pre_values: dict[str, Any]
    post_values: dict[str, Any]
    aggregates_before: dict[str, Any]
    allow_active_used: bool
    active_trade_consequences: tuple[str, ...] = ()
    pre_trade_locked_at_left_stale: str | None = None


@dataclass(frozen=True)
class EntryDateCorrectionResult:
    correction_id: int
    trade_id: int
    fill_id: int
    watchlist_archive_id: int
    discrepancy_id: int
    pre_entry_date: str
    target_date: str
    correction_reason: str
    follow_up_command: str
    pre_values: dict[str, Any] = field(default_factory=dict)
    applied_values: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation + authorization (shared by the preview and the write path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Authorized:
    trade: Any
    fill_row: tuple
    discrepancy: Any
    archive_id: int
    target_date: str
    allow_active_used: bool
    prior_correction_id: int | None


def _validate_target_date(to_date: str) -> str:
    """``--to`` must be a bare ISO calendar date on an NYSE trading session."""
    if not isinstance(to_date, str) or not to_date.strip():
        raise EntryDateCorrectionError("--to must be a YYYY-MM-DD date.")
    candidate = to_date.strip()
    if "T" in candidate:
        # Mirrors entry.py's own rejection: downstream callers do
        # date.fromisoformat(trade.entry_date) directly, and a full ISO
        # datetime breaks them.
        raise EntryDateCorrectionError(
            f"--to must be a DATE, not a datetime; got {candidate!r}."
        )
    try:
        parsed = _date.fromisoformat(candidate)
    except (TypeError, ValueError) as exc:
        raise EntryDateCorrectionError(
            f"--to must be a valid YYYY-MM-DD date; got {candidate!r}."
        ) from exc
    # Codex R1 Major 2 -- `date.fromisoformat` on 3.11+ ALSO accepts basic ISO
    # forms (`20260731`, `2026-W31-5`), and writing one of those into
    # `trades.entry_date` would break every downstream `[:10]` prefix and
    # lexical date comparison. Require the canonical round-trip.
    if parsed.isoformat() != candidate:
        raise EntryDateCorrectionError(
            f"--to must be EXTENDED-format YYYY-MM-DD; got {candidate!r}, "
            f"which parses to {parsed.isoformat()}. A basic/compact/week-date "
            "form is refused rather than silently canonicalized."
        )
    if not is_trading_session(parsed):
        raise EntryDateCorrectionError(
            f"--to {candidate} is not an NYSE trading session. If this is the "
            "UTC-date residue of an after-hours execution (an execution after "
            "20:00 ET lands on the NEXT UTC date, and the auto-fill and the "
            "reconciliation guard BOTH read the naive UTC prefix by design), "
            "that case is UNSUPPORTED by this surface rather than silently "
            "mis-dated -- route it to CHARC. It is not a typo, and writing a "
            "non-session entry date would de-latch a live position."
        )
    return candidate


def _load_trade_or_refuse(conn: sqlite3.Connection, trade_id: int) -> Any:
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise EntryDateCorrectionError(f"trade {trade_id} not found.")
    return trade


def _gate_on_state(trade: Any, *, allow_active: bool) -> bool:
    """Returns True when ``--allow-active`` was REQUIRED and supplied.

    A closed-only guard was considered and REJECTED: D31's own words are
    "EVERY future latch fill hits it", and a latch fill lands on a LIVE
    position, so a terminal-states-only surface would leave the case this arc
    exists to prevent permanently uncorrectable -- the D19 gap re-created one
    field over. The flag is the same posture as ``discrepancy resolve
    --force``: not a lock, a conscious acknowledgement, recorded in the reason.
    """
    state = str(getattr(trade, "state", ""))
    if state in TERMINAL_TRADE_STATES:
        return False
    if state not in ACTIVE_TRADE_STATES:
        raise EntryDateCorrectionError(
            f"trade {trade.id} has an unrecognized state {state!r}; refusing."
        )
    if not allow_active:
        inventory = "\n  ".join(ACTIVE_TRADE_CONSEQUENCES)
        raise EntryDateCorrectionError(
            f"trade {trade.id} is in state {state!r} (not closed/reviewed). "
            "Correcting a LIVE position's entry date has consequences; pass "
            "--allow-active to acknowledge them:\n  " + inventory
        )
    return True


def _entry_fill_row(conn: sqlite3.Connection, fill_id: int) -> tuple | None:
    return conn.execute(
        "SELECT fill_id, trade_id, fill_datetime, action, "
        "reconciliation_status, quantity, fill_origin, "
        "schwab_source_value_json, operator_corrected_value_json, "
        "price "
        "FROM fills WHERE fill_id = ?",
        (fill_id,),
    ).fetchone()


def _canonical_fill_datetime_or_refuse(raw: Any, *, fill_id: int) -> str:
    """The fill's EXISTING datetime, validated WHOLE (Codex R3 Major 4).

    The agreement gate compares only ``[:10]`` and ``_corrected_fill_datetime``
    appends everything after character ten verbatim, so a schema-valid
    ``2026-07-23garbage`` -- ``fills.fill_datetime`` is a bare ``TEXT NOT
    NULL`` -- passes authorization and becomes ``2026-07-31garbage``. The
    correction would commit, recompute LEXICALLY ordered aggregates off it, and
    append an audit row asserting that value was successfully applied. Validate
    the whole string before authorizing anything.
    """
    value = str(raw)
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise EntryDateCorrectionError(
            f"fill {fill_id}'s fill_datetime {value!r} is not a parseable ISO "
            "datetime. `fills.fill_datetime` is a bare TEXT column, so a "
            "malformed value is schema-legal; this surface refuses to "
            "re-certify one by moving its date prefix."
        ) from exc
    if value[:10] != parsed.date().isoformat():
        raise EntryDateCorrectionError(
            f"fill {fill_id}'s fill_datetime {value!r} is not in EXTENDED "
            "YYYY-MM-DD... form; refusing to rewrite its date prefix."
        )
    return value


def _derive_target_date_from_discrepancy(
    disc: Any, *, fill_datetime: str, order_entered_date: str | None = None,
) -> str:
    """The date this correction will write, derived from the finding itself.

    ``execution_sessions_from_fill`` is NOT an acceptable substitute and is
    deliberately not consulted: ``_fill_execution_session_distance`` returns
    ``max(distances)`` ACROSS ALL LEGS, so a nonzero value only proves that
    SOME leg differs from the fill date. A partial fill whose first leg
    executed on an earlier session and whose LAST leg executed on the fill date
    would report a nonzero distance while the date this surface would write is
    unchanged. Authorizing a date rewrite from an aggregate that does not
    describe the value being written is gotcha #30 in its general form: a MAX
    across rows is not provenance for the row you are about to use. Compute the
    same date the correction will write, and compare THAT.
    """
    payload = _evidence_payload(disc)
    # Codex R1 Major 1 -- THE SIDE MUST BE AN ENTRY SIDE. The sole-candidate
    # Shape-D emit fires when that candidate failed price OR **SIDE** OR
    # session, and it always carries `execution_side` (= `so.instruction`). So
    # a same-ticker same-quantity SELL execution reaches this function as the
    # only evidence on an `entry_price_mismatch` for an ENTRY fill -- and
    # without this clause the surface would derive the EXIT's date, move
    # `trades.entry_date`, the entry fill and the archive row onto it, and
    # append an audit row that looks entirely valid. `--to` is no protection:
    # the server derives the wrong date and asks the operator to confirm it.
    candidate_count = payload.get("candidate_count")
    # STRICT int (Codex R2 Major 3): Python evaluates `True == 1`, so a bare
    # `!= 1` admits a JSON boolean `true`, and it admits `1.0` besides. The
    # classifier already rejects bools and non-integers on its own count field;
    # a malformed persisted payload must not authorize three ledger writes on
    # the strength of a truthy value that never asserted a singleton.
    if (
        not isinstance(candidate_count, int)
        or isinstance(candidate_count, bool)
        or candidate_count != 1
    ):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} does not carry an integer "
            f"single-candidate execution payload (candidate_count="
            f"{candidate_count!r}); it cannot authorize a date rewrite."
        )
    from swing.trades.reconciliation_classifier import (
        _expected_execution_sides,
    )
    execution_side = payload.get("execution_side")
    if execution_side not in _expected_execution_sides("entry"):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s execution_side is "
            f"{execution_side!r}, not an ENTRY side "
            f"({sorted(_expected_execution_sides('entry'))}). A SELL-side "
            "execution is evidence about an EXIT and must never date an entry."
        )
    legs = payload.get("execution_legs")
    if not isinstance(legs, list) or not legs:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} carries no execution_legs; it "
            "is a price disagreement, not DATE evidence, and cannot authorize "
            "a date rewrite."
        )
    times = [
        leg.get("time") if isinstance(leg, dict) else None for leg in legs
    ]
    derived = latest_execution_leg_date(times)
    if derived is None:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s execution_legs carry a "
            "missing or unparseable time; refusing to derive a date from a "
            "partial view of the order's own fills."
        )
    # CHRONOLOGY (Codex R14). The derived execution date must not PRECEDE the
    # date the order was ENTERED. That date is what the auto-fill envelope
    # records (`entry_date`, taken from `enter_time`), and nothing else
    # enforces the ordering: `SchwabExecutionLeg.time` is validated non-empty
    # only, with no chronology check against `SchwabOrderResponse.enter_time`,
    # and the reconciliation session distance is DIRECTIONLESS -- so a
    # backwards payload passes the order-id, quantity, price, side, session and
    # `--to` checks alike. Correcting from one would move all three coupled
    # dates to a date before the order existed, record an audit reason
    # asserting an execution that preceded its own order, and on a watchlist
    # trade produce `removed_date < added_date`.
    #
    # Compared against the ORIGINAL envelope date, which corrections never
    # rewrite -- so a re-correction is measured from the same anchor as the
    # first, not from a date this surface itself moved.
    if execution_precedes_order(derived, order_entered_date):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s latest execution leg is "
            f"{derived}, which PRECEDES the date the order was entered "
            f"({order_entered_date}). An execution cannot happen before its "
            "own order; this payload is internally contradictory and cannot "
            "authorize a correction."
        )
    if derived == str(fill_datetime)[:10]:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s latest execution leg is "
            f"{derived}, which already equals the fill's date; there is no "
            "date divergence to correct."
        )
    return derived


def _authorize(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    to_date: str,
    discrepancy_id: int,
    reason: str,
    allow_active: bool,
) -> _Authorized:
    """Steps 1-5: validate, gate, and BIND THE EXACT FILL. Read-only."""
    if not isinstance(reason, str) or not reason.strip():
        raise EntryDateCorrectionError("--reason must be a non-empty string.")
    target_requested = _validate_target_date(to_date)

    trade = _load_trade_or_refuse(conn, trade_id)

    # THE NO-OP GUARD STAYS FIRST; THE STATE GATE MOVED BELOW THE EVIDENCE
    # (Codex R4 Minor 2). The two behave differently under a bad discrepancy:
    # "already has entry_date X" is TRUE and TERMINAL whatever the cited
    # finding turns out to be, and it claims nothing about eligibility. The
    # `--allow-active` refusal is an INSTRUCTION -- it asks the operator to
    # acknowledge consequences, which implies the rest of the request is
    # otherwise sound. Raising it before the discrepancy has been proved to
    # authorize anything sends him to fetch an acknowledgement for a
    # correction that was never going to run. So the state gate now fires
    # AFTER the finding is established.
    if str(trade.entry_date) == target_requested:
        raise EntryDateCorrectionError(
            f"trade {trade_id} already has entry_date {target_requested}; "
            "nothing to correct and nothing was written."
        )

    disc = get_discrepancy(conn, discrepancy_id)
    if disc is None:
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} not found."
        )
    if disc.trade_id != trade_id:
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} belongs to trade {disc.trade_id!r}, "
            f"not {trade_id}; it cannot authorize this correction."
        )
    if disc.resolution not in AUTHORIZING_RESOLUTIONS:
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} is already dispositioned "
            f"(resolution={disc.resolution!r}). A terminal historical finding "
            "must not authorize a fresh live mutation."
        )
    if disc.discrepancy_type != _AUTHORIZING_DISCREPANCY_TYPE:
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} is a "
            f"{disc.discrepancy_type!r} row; only "
            f"{_AUTHORIZING_DISCREPANCY_TYPE!r} rows carry broker-vs-journal "
            "entry evidence today."
        )
    # A fills-vs-trades PRICE diagnostic (the A-5 / A-4 class) is internal to
    # the journal on both sides and says nothing about a date. Reuse the
    # existing shared predicate rather than writing a second one.
    from swing.trades.schwab_reconciliation import (
        _is_internal_consistency_diagnostic,
    )
    if _is_internal_consistency_diagnostic(disc):
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} is a fills-vs-trades internal "
            "consistency diagnostic; both sides are journal values and it "
            "carries no broker date evidence."
        )
    if disc.fill_id is None:
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} binds no fill_id; this surface "
            "corrects the discrepancy's OWN fill and never re-derives 'the "
            "trade's entry fill', which is ambiguous the moment a trade has "
            "more than one."
        )
    fill_row = _entry_fill_row(conn, int(disc.fill_id))
    if fill_row is None:
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id} binds fill {disc.fill_id}, which "
            "does not exist."
        )
    if int(fill_row[1]) != trade_id:
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id} belongs to trade {fill_row[1]}, not "
            f"{trade_id}."
        )
    if str(fill_row[3]) != "entry":
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id} has action {fill_row[3]!r}, not 'entry'; "
            "this surface corrects an ENTRY date."
        )
    # THE BOUND FILL MUST BE THE TRADE'S AUTHORITATIVE ENTRY FILL, AND ITS
    # DATE MUST BE THE ONE `trades.entry_date` CLAIMS (Codex R2 Major 1).
    # `action='entry'` is not the same as "the fill that dated this trade": a
    # scale-in adds a SECOND entry fill, and an `entry_price_mismatch` raised
    # on that later add-on would otherwise move `trades.entry_date`, the
    # `watchlist_archive` row and every entry-date-derived metric onto the
    # ADD-ON's execution date. `get_authoritative_entry_fill` is the project's
    # existing definition of "first by (fill_datetime ASC, fill_id ASC)"; it is
    # reused rather than re-derived. A fill-only correction path for a
    # non-authoritative add-on is real and OUT OF SCOPE -- refused, not
    # silently widened.
    from swing.data.repos.fills import get_authoritative_entry_fill
    authoritative = get_authoritative_entry_fill(conn, trade_id)
    if authoritative is None or authoritative.fill_id != int(disc.fill_id):
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id} is not trade {trade_id}'s AUTHORITATIVE "
            f"entry fill (that is fill "
            f"{None if authoritative is None else authoritative.fill_id}). "
            "Correcting a later scale-in fill would redate the whole trade; "
            "a fill-only correction path is out of scope for this surface."
        )
    pre_fill_datetime = _canonical_fill_datetime_or_refuse(
        fill_row[2], fill_id=int(disc.fill_id),
    )
    if pre_fill_datetime[:10] != str(trade.entry_date):
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id}'s date ({pre_fill_datetime[:10]}) already "
            f"disagrees with trades.entry_date ({trade.entry_date}). This "
            "surface restores a coupling; it cannot be used where the two "
            "have already diverged for some other reason."
        )
    # THE EVIDENCE MUST STILL DESCRIBE THIS FILL (Codex R3 Major 2). The
    # emitter selected its candidate by same ticker AND execution-grain
    # QUANTITY; a later correction can change `fills.quantity` while an older
    # discrepancy sits unresolved, and the stale row would then authorize three
    # ledger writes from an order that no longer matches the fill it cites.
    if str(disc.ticker or "") != str(trade.ticker):
        raise EntryDateCorrectionError(
            f"discrepancy {discrepancy_id}'s ticker ({disc.ticker!r}) no "
            f"longer matches trade {trade_id}'s ({trade.ticker!r})."
        )
    _assert_evidence_matches_fill_quantity(
        disc, fill_quantity=float(fill_row[5]),
    )
    _assert_the_price_already_agrees(disc, fill_price=float(fill_row[9]))
    source_envelope = _assert_evidence_is_this_fills_order(
        disc, fill_origin=fill_row[6], source_envelope=fill_row[7],
    )
    prior_head = _prior_multi_row_head(conn, int(disc.fill_id))
    _assert_the_date_came_from_the_auto_fill(
        disc, envelope=source_envelope, fill_date=pre_fill_datetime[:10],
        prior_applied_date=(
            None if prior_head is None else str(prior_head[1])[:10]
        ),
    )

    target_date = _derive_target_date_from_discrepancy(
        disc,
        fill_datetime=pre_fill_datetime,
        order_entered_date=(
            str(source_envelope.get("entry_date"))
            if source_envelope.get("entry_date") else None
        ),
    )
    if target_requested != target_date:
        raise EntryDateCorrectionError(
            f"--to {target_requested} does not match the date derived from "
            f"discrepancy {discrepancy_id}'s own execution evidence "
            f"({target_date}). The target date is SERVER-DERIVED; --to is a "
            "confirmation, never the source. Nothing was written."
        )

    # AND THE BOUND FILL MUST STILL BE AUTHORITATIVE AFTERWARDS (Codex R3
    # Major 1). The gate above proves it is authoritative TODAY; moving its
    # datetime FORWARD can hand that role to an intervening entry fill. With a
    # sibling entry fill on 07-25 and a move 07-23 -> 07-31, the correction
    # would commit an internally inconsistent ledger: `trades.entry_date` says
    # 07-31 while `_recompute_aggregates` takes the 07-25 fill's price as
    # `current_avg_cost`, and the audit row asserts the correction was
    # coherent. A gate evaluated only on the PRE state cannot see this.
    new_fill_datetime = _corrected_fill_datetime(pre_fill_datetime, target_date)
    _assert_still_authoritative_after_move(
        conn,
        trade_id=trade_id,
        fill_id=int(disc.fill_id),
        new_fill_datetime=new_fill_datetime,
    )
    _assert_no_sibling_fill_precedes(
        conn,
        trade_id=trade_id,
        fill_id=int(disc.fill_id),
        new_fill_datetime=new_fill_datetime,
    )

    # Bind the watchlist_archive row BEFORE any write. The table carries no
    # unique constraint on (ticker, reason, removed_date), so "the archive row
    # for this trade" is an assumption until the query proves it.
    archive_id = _resolve_archive_row(
        conn,
        ticker=str(trade.ticker),
        removed_date=str(trade.entry_date),
        trade_id=trade_id,
    )

    # THE STATE GATE FIRES LAST, after EVERY other read-only check (Codex R5
    # minor; R4's partial move was not enough). It is the only refusal in this
    # function that is an INSTRUCTION rather than a verdict -- it tells the
    # operator to come back with `--allow-active`. Raising it while an
    # intervening entry fill or an unresolvable archive row would still reject
    # the request sends him to fetch an acknowledgement for a correction that
    # was never eligible, which is the misleading ordering the move was
    # supposed to eliminate.
    allow_active_used = _gate_on_state(trade, allow_active=allow_active)

    return _Authorized(
        trade=trade,
        fill_row=fill_row,
        discrepancy=disc,
        archive_id=archive_id,
        target_date=target_date,
        allow_active_used=allow_active_used,
        prior_correction_id=None if prior_head is None else prior_head[0],
    )


def _evidence_payload(disc: Any) -> dict[str, Any]:
    """The discrepancy's `actual_value_json` as a dict, or a refusal.

    ONE parse, ONE message, used by every evidence clause -- otherwise the
    clause that happens to run first decides which refusal the operator sees,
    and a multi-candidate ARRAY payload gets explained as a missing order id.
    A multi-candidate (A1 ambiguity) emit IS a JSON array, and "which candidate
    is the truth" is exactly the question the operator has not answered.
    """
    raw = getattr(disc, "actual_value_json", None)
    payload: Any = None
    if raw:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            payload = None
    if not isinstance(payload, dict):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} carries no parseable "
            "actual_value_json OBJECT payload (a multi-candidate ambiguity is "
            "emitted as a JSON array); it cannot authorize a date rewrite."
        )
    return payload


SCHWAB_DERIVED_FILL_ORIGINS: frozenset[str] = frozenset({
    "schwab_auto", "schwab_auto_then_operator_corrected",
})


def _assert_evidence_is_this_fills_order(
    disc: Any, *, fill_origin: Any, source_envelope: Any,
) -> dict[str, Any]:
    """The cited Schwab order must be the one that CREATED this fill.

    Codex R5 Major 1, and it is the sharpest remaining hole. Every clause so
    far -- ticker, quantity, side, singleton count -- describes a SHAPE, and
    the reconciliation emitter binds its sole candidate on exactly that shape
    when the candidate failed price OR side OR session. So an UNRELATED
    same-ticker same-size BUY order could supply the date, moving the trade,
    the fill and the archive row, while the follow-up reason asserts D31 as
    the cause. `--to` is no protection: it confirms the wrong order's
    server-derived date.

    The fill already carries the answer and it was being ignored:
    `entry_auto_fill` writes the originating `schwab_order_id` into
    `schwab_source_value_json`, and `record_entry` persists it. Requiring that
    id to equal the discrepancy payload's is the arc's own doctrine -- per-row
    provenance captured at WRITE time (#30) -- applied to itself.

    An `operator_typed` / `tos_import` / `imported_legacy` fill has no such
    provenance AND cannot be a D31 victim (D31 is a defect in the Schwab
    auto-fill path), so the follow-up reason's causal claim would be false for
    it. Refused rather than dated from an order it never came from.
    """
    if str(fill_origin) not in SCHWAB_DERIVED_FILL_ORIGINS:
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id} has fill_origin={fill_origin!r}, which is "
            "not Schwab-derived. This surface corrects the D31 auto-fill "
            "defect and its audit reason says so; a manually-recorded fill "
            "carries no Schwab order provenance to bind the evidence to."
        )
    try:
        envelope = json.loads(source_envelope or "")
    except (TypeError, ValueError) as exc:
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id} claims Schwab provenance but its "
            "schwab_source_value_json is missing or unparseable; the cited "
            "order cannot be bound to it."
        ) from exc
    fill_order_id = (
        envelope.get("schwab_order_id") if isinstance(envelope, dict) else None
    )
    disc_order_id = _evidence_payload(disc).get("schwab_order_id")
    if not fill_order_id or not disc_order_id:
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id} (order {fill_order_id!r}) and discrepancy "
            f"{disc.discrepancy_id} (order {disc_order_id!r}) do not both name "
            "a Schwab order id; the evidence cannot be bound to this fill."
        )
    if str(fill_order_id) != str(disc_order_id):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} cites Schwab order "
            f"{disc_order_id!r}, but fill {disc.fill_id} was created from "
            f"order {fill_order_id!r}. A same-ticker same-size order is NOT "
            "evidence about a fill it did not produce."
        )
    return envelope


def _prior_multi_row_head(
    conn: sqlite3.Connection, fill_id: int,
) -> tuple[int, str] | None:
    """``(correction_id, applied fills.fill_datetime)`` for the UNSUPERSEDED
    multi-row head bound to this fill, or ``None``.

    Item-5 (Codex R10 Major 2). Without this the surface was SINGLE-SHOT per
    fill and every refusal message in it was FALSE: they instruct the operator
    to "re-run `swing journal correct-entry-date` against a current finding",
    but the re-run could not work -- the first correction leaves the auto-fill
    envelope's `entry_date` at its ORIGINAL value while the fill now holds the
    corrected one, so the provenance check read that as an operator edit and
    refused. A money-bearing ledger value corrected WRONGLY would have been
    permanent short of hand-editing SQLite.
    """
    from swing.trades.reconciliation_auto_correct import (
        _MULTI_ROW_CORRECTION_CHOICES,
        MULTI_ROW_BOUND_FILL_KEY,
    )

    rows = conn.execute(
        "SELECT correction_id, correction_choice, applied_value_json FROM "
        "reconciliation_corrections WHERE superseded_by_correction_id IS NULL",
    ).fetchall()
    for correction_id, choice, applied in rows:
        if choice not in _MULTI_ROW_CORRECTION_CHOICES:
            continue
        try:
            payload = json.loads(applied or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get(MULTI_ROW_BOUND_FILL_KEY) != fill_id:
            continue
        return int(correction_id), str(payload.get("fills.fill_datetime", ""))
    return None


def _assert_the_date_came_from_the_auto_fill(
    disc: Any, *, envelope: dict[str, Any], fill_date: str,
    prior_applied_date: str | None = None,
) -> None:
    """The recorded date must be the AUTO-FILL's, unedited (Codex R6 Major 2).

    `schwab_auto_then_operator_corrected` means the operator edited one of
    entry_date / entry_price / shares at the form. If he edited the DATE, the
    recorded value is HIS, not the auto-fill's -- and the follow-up reason this
    surface prints asserts flatly that `entry_auto_fill.py` read `enter_time`.
    Correcting such a fill would write a FALSE CAUSAL STATEMENT into the audit
    ledger, which is the single thing this arc exists to stop.

    Two clauses, both read off the fill's own envelope rather than inferred:

      - the envelope's `entry_date` must equal the fill's CURRENT date. For a
        pure `schwab_auto` fill that holds by construction; for a corrected one
        it holds only if the operator edited price or shares and NOT the date.
      - the envelope must carry NO `entry_date_source` key AT ALL. That key
        exists only from T1 onward, so its ABSENCE is what identifies a
        pre-T1 fill -- the only kind D31 can have produced.
    """
    if "entry_date_source" in envelope:
        source = envelope.get("entry_date_source")
        # ABSENCE is the qualifier, not a particular value (Codex R7 Major 2).
        # An earlier draft refused only `execution_leg` and admitted
        # `enter_time` -- but the POST-T1 auto-fill deliberately STAMPS
        # `enter_time` when a leg timestamp is malformed, so a later clean
        # reconciliation fetch on the same order would have been corrected
        # under a reason blaming the OLD D31 bug for a fallback the fixed code
        # took on purpose. The mutation might even be right; the recorded CAUSE
        # would be false, and this arc exists to stop exactly that.
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id}'s envelope carries "
            f"entry_date_source={source!r}, so it was written by the POST-D31 "
            "auto-fill: either it already took the execution grain, or it fell "
            "back deliberately. Only a pre-T1 envelope -- which has NO such "
            "key -- can be a D31 victim, and this surface's audit reason names "
            "D31 as the cause. Route it to CHARC rather than recording a false "
            "cause."
        )
    envelope_date = envelope.get("entry_date")
    if prior_applied_date is not None and str(prior_applied_date) == str(
        fill_date,
    ):
        # The fill's current date is a PRIOR CORRECTION's applied value, not an
        # operator edit -- the provenance chain is intact one link further
        # along. The new correction supersedes that head (below), so the
        # append-only chain records the supersession rather than accumulating
        # two live heads.
        return
    if str(envelope_date) != str(fill_date):
        raise EntryDateCorrectionError(
            f"fill {disc.fill_id}'s recorded date ({fill_date}) differs from "
            f"the Schwab auto-fill's own ({envelope_date!r}), so the operator "
            "edited it at the form. The recorded date is HIS, not the "
            "auto-fill's, and this surface's reason would blame D31 for a "
            "human edit. Refusing rather than writing a false cause."
        )


def _assert_evidence_matches_fill_quantity(
    disc: Any, *, fill_quantity: float,
) -> None:
    """The cited execution legs must still sum to the fill's CURRENT quantity.

    Same tolerance and same grain as the matcher that produced the evidence
    (`_resolve_match_quantity` sums leg quantities; the candidate filter
    compares within `_PRICE_TOLERANCE_DEFAULT`). Reusing the emitter's own
    semantics rather than inventing a second comparison.
    """
    from swing.trades.schwab_reconciliation import _PRICE_TOLERANCE_DEFAULT

    legs = _evidence_payload(disc).get("execution_legs")
    if not isinstance(legs, list) or not legs:
        return  # the leg-shape refusal fires in the date derivation
    total = 0.0
    for leg in legs:
        qty = leg.get("quantity") if isinstance(leg, dict) else None
        if not isinstance(qty, (int, float)) or isinstance(qty, bool):
            raise EntryDateCorrectionError(
                f"discrepancy {disc.discrepancy_id} carries a non-numeric "
                "execution-leg quantity; it cannot authorize a date rewrite."
            )
        # EVERY leg must be FINITE and STRICTLY POSITIVE (Codex R7 Major 2).
        # `SchwabExecutionLeg` enforces exactly that at construction, so a leg
        # violating it could never have come from the production model -- but
        # `insert_discrepancy` stores JSON, not that model, so the value is
        # schema-legal here. The sum check alone is not enough: a real 10-share
        # leg on the recorded date PLUS a zero-quantity pseudo-leg on a LATER
        # date sums to 10 and passes, and `latest_execution_leg_date` then
        # picks the pseudo-leg's date to rewrite three ledger rows.
        if not math.isfinite(float(qty)) or float(qty) <= 0:
            raise EntryDateCorrectionError(
                f"discrepancy {disc.discrepancy_id} carries an execution leg "
                f"with quantity {qty!r}. Every leg must be finite and strictly "
                "positive -- SchwabExecutionLeg enforces that at construction, "
                "so this payload could not have been emitted by the production "
                "model and must not date a trade."
            )
        total += float(qty)
    if not math.isfinite(total):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s execution-leg quantities do "
            "not sum to a finite value."
        )
    if abs(total - fill_quantity) > _PRICE_TOLERANCE_DEFAULT:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s execution legs total "
            f"{total} shares but fill {disc.fill_id} now holds "
            f"{fill_quantity}. The evidence no longer describes the row it "
            "cites -- a stale finding must not authorize a live mutation."
        )


def _assert_the_price_already_agrees(
    disc: Any, *, fill_price: float,
) -> None:
    """Refuse a discrepancy that is ALSO a price mismatch (Codex R8 Major 1).

    Shape-D is emitted when the sole candidate fails price OR side OR session,
    so a row can carry BOTH a wrong date and a genuine execution-price
    divergence. This surface corrects only the DATE, then stamps the fill
    `reconciled_discrepancy_resolved` and prints a `journal_corrected`
    follow-up that CLOSES the finding -- so a real, material price error would
    be silently discharged by a correction that never touched it.

    The emitter's own execution price is used (`payload['price']`, written from
    `_compute_execution_price`) rather than a second VWAP implementation, and
    the matcher's own tolerance rather than a new one. Trade 19's live payload
    reads $18.80 against a $18.80 fill -- `$+0.0000` -- which is precisely why
    it is a pure DATE finding and a legitimate case for this surface.
    """
    from swing.trades.schwab_reconciliation import _PRICE_TOLERANCE_DEFAULT

    payload = _evidence_payload(disc)
    execution_price = payload.get("price")
    legs = payload.get("execution_legs")
    if not isinstance(legs, list) or not legs:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} carries no execution legs to "
            "authenticate its price against."
        )
    if (
        not isinstance(execution_price, (int, float))
        or isinstance(execution_price, bool)
        or not math.isfinite(float(execution_price))
    ):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} carries no finite execution "
            f"price ({execution_price!r}); it cannot be shown to be a "
            "date-only finding."
        )
    # THE LEGS ARE THE EVIDENCE OF RECORD, so they are authenticated too
    # (Codex R10 Major 1). The summary `price` is a DERIVED field the emitter
    # wrote; a payload whose summary reads 18.80 while its 10-share leg reads
    # 19.25 satisfied the summary-vs-fill check alone and would have moved all
    # three ledger values, stamped the fill reconciled, and closed a finding
    # whose own cited legs prove a material price error. Same VWAP math as
    # `_compute_execution_price` (single leg -> its price; multi-leg ->
    # sum(p*q)/sum(q)), and the same tolerance.
    total_qty = 0.0
    weighted = 0.0
    for leg in legs:
        price = leg.get("price") if isinstance(leg, dict) else None
        qty = leg.get("quantity") if isinstance(leg, dict) else None
        if (
            not isinstance(price, (int, float)) or isinstance(price, bool)
            or not math.isfinite(float(price)) or float(price) <= 0
        ):
            raise EntryDateCorrectionError(
                f"discrepancy {disc.discrepancy_id} carries an execution leg "
                f"with price {price!r}. Every leg price must be finite and "
                "strictly positive."
            )
        total_qty += float(qty)
        weighted += float(price) * float(qty)
    leg_vwap = weighted / total_qty if total_qty > 0 else None
    if leg_vwap is None or not math.isfinite(leg_vwap):
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s execution legs do not yield "
            "a finite VWAP."
        )
    if abs(leg_vwap - float(execution_price)) > _PRICE_TOLERANCE_DEFAULT:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id}'s execution legs VWAP to "
            f"{leg_vwap} but its summary price reads {float(execution_price)}. "
            "The payload disagrees with itself; it cannot authorize a "
            "correction."
        )
    if abs(leg_vwap - fill_price) > _PRICE_TOLERANCE_DEFAULT:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} is ALSO a price mismatch: its "
            f"execution legs VWAP to {leg_vwap} and fill {disc.fill_id} "
            f"records {fill_price}. This surface corrects the DATE only."
        )
    if abs(float(execution_price) - fill_price) > _PRICE_TOLERANCE_DEFAULT:
        raise EntryDateCorrectionError(
            f"discrepancy {disc.discrepancy_id} is ALSO a price mismatch: the "
            f"execution is {float(execution_price)} and fill {disc.fill_id} "
            f"records {fill_price}. This surface corrects the DATE only, and "
            "closing the finding afterwards would silently discharge a real "
            "price error. Refusing a mixed date-and-price discrepancy."
        )


def _assert_no_sibling_fill_precedes(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    fill_id: int,
    new_fill_datetime: str,
) -> None:
    """Refuse a move that would place the ENTRY after an EXIT (Codex R8 M3).

    The authority check looks only at other `action='entry'` fills, so a closed
    trade with a stop on 07-25 would accept an entry move 07-23 -> 07-31: the
    result has its stop BEFORE its entry, `_recompute_aggregates` moves
    `last_fill_at` onto the later entry even though the trade is closed, and
    the audit row records that impossible chronology as successfully applied.
    """
    rows = conn.execute(
        "SELECT fill_id, fill_datetime, action FROM fills "
        "WHERE trade_id = ? AND action <> 'entry' AND fill_id <> ?",
        (trade_id, fill_id),
    ).fetchall()
    for other_id, other_dt, action in rows:
        if str(other_dt)[:10] < new_fill_datetime[:10]:
            raise EntryDateCorrectionError(
                f"moving fill {fill_id} to {new_fill_datetime[:10]} would "
                f"place the ENTRY after {action} fill {other_id} "
                f"({str(other_dt)[:10]}). A trade cannot exit before it "
                "enters. Nothing was written."
            )


def _assert_still_authoritative_after_move(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    fill_id: int,
    new_fill_datetime: str,
) -> None:
    """Refuse when the move would hand authority to an intervening entry fill.

    `get_authoritative_entry_fill` orders by ``(fill_datetime ASC, fill_id
    ASC)``, so the question is whether any OTHER entry fill would sort strictly
    before the corrected one under that same ordering. Evaluated on the
    PROPOSED value, because a gate evaluated only on the pre-state is blind to
    exactly the case that matters.
    """
    rows = conn.execute(
        "SELECT fill_id, fill_datetime FROM fills "
        "WHERE trade_id = ? AND action = 'entry' AND fill_id <> ?",
        (trade_id, fill_id),
    ).fetchall()
    for other_id, other_dt in rows:
        if (str(other_dt), int(other_id)) < (new_fill_datetime, fill_id):
            raise EntryDateCorrectionError(
                f"moving fill {fill_id} to {new_fill_datetime} would make "
                f"entry fill {other_id} ({other_dt}) the AUTHORITATIVE entry "
                f"fill, so trades.entry_date would no longer name it and "
                "current_avg_cost would take the intervening fill's price. "
                "Nothing was written."
            )


def _resolve_archive_row(
    conn: sqlite3.Connection, *, ticker: str, removed_date: str, trade_id: int,
) -> int:
    """Bind the `reason='entered'` archive row for THIS trade, or refuse.

    ``watchlist_archive`` carries NO trade or fill FK -- it is keyed only by
    ``(ticker, removed_date, reason)`` -- so exactly-one-match establishes
    CARDINALITY, not OWNERSHIP (Codex R2 Major 2). The gap is concrete:
    ``entry.py`` writes an archive row only when the ticker is CURRENTLY
    watchlisted, so a same-day SECOND entry on the same ticker (the first
    having already removed it from the watchlist) creates NO row of its own --
    and a naive lookup would then bind, and rewrite, the FIRST trade's row.

    The ownership proof available WITHOUT schema is that no OTHER non-voided
    trade shares this ``(ticker, entry_date)``: the lookup is keyed on this
    trade's own entry date, so any row it could wrongly bind must belong to a
    trade sharing that exact pair. When one does, ownership is unprovable and
    the correction is REFUSED with the reason named. Giving archive rows
    durable trade identity is the real fix and it is SCHEMA -- out of scope for
    this arc, recorded rather than silently approximated.
    """
    siblings = conn.execute(
        "SELECT id FROM trades WHERE ticker = ? AND entry_date = ? "
        "AND id <> ?",
        (ticker, removed_date, trade_id),
    ).fetchall()
    if siblings:
        raise EntryDateCorrectionError(
            f"trade(s) {[int(r[0]) for r in siblings]} share ticker={ticker!r} "
            f"and entry_date={removed_date!r} with trade {trade_id}. "
            "watchlist_archive has no trade identity, so which trade the "
            "archive row belongs to is UNPROVABLE here and correcting it "
            "could rewrite another trade's row. Nothing was written."
        )
    rows = conn.execute(
        "SELECT id FROM watchlist_archive "
        "WHERE ticker = ? AND reason = 'entered' AND removed_date = ?",
        (ticker, removed_date),
    ).fetchall()
    if len(rows) != 1:
        raise EntryDateCorrectionError(
            f"expected exactly ONE watchlist_archive row for ticker={ticker!r} "
            f"reason='entered' removed_date={removed_date!r}; found "
            f"{len(rows)}. A best-effort UPDATE here would rewrite the wrong "
            "row (or every row). Nothing was written."
        )
    return int(rows[0][0])


def _read_aggregates(conn: sqlite3.Connection, trade_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT current_size, current_avg_cost, last_fill_at FROM trades "
        "WHERE id = ?",
        (trade_id,),
    ).fetchone()
    return {
        "current_size": row[0],
        "current_avg_cost": row[1],
        "last_fill_at": row[2],
    }


def _corrected_fill_datetime(pre_fill_datetime: str, target_date: str) -> str:
    """Move the DATE, preserve the existing ``HH:MM:SS`` component.

    ``_normalize_trade_event_date_to_iso`` produces ``T16:00:00`` as a
    CONVENTION, not an observation, and every existing row carries it.
    Substituting the real execution clock time would make this the only row in
    the table with a real clock, which downstream ``[:10]`` prefix comparisons
    would tolerate but a future reader would misread as a measurement.
    """
    raw = str(pre_fill_datetime)
    suffix = raw[10:] if len(raw) > 10 else ""
    return f"{target_date}{suffix}"


def _compose_reason(
    operator_reason: str,
    *,
    allow_active_used: bool,
    pre_trade_locked_at: Any,
    pre_entry_date: str,
) -> str:
    """The stored reason, with the two things the operator cannot know.

    The ``pre_trade_locked_at`` staleness is NAMED (RD, 2026-08-09): after this
    correction that column is a stale derivative of the PRE-correction
    ``entry_date``. It is deliberately NOT moved, because it is written as
    ``entry_date + 'T16:00:00'`` and equals exactly that on every live trade --
    a synthetic restatement of the column under correction, never independent
    evidence. A labelled inconsistency beats an invented timestamp, and the
    reason may not cite it as corroboration.
    """
    parts: list[str] = []
    if allow_active_used:
        parts.append(_ALLOW_ACTIVE_ACKNOWLEDGEMENT.strip())
    parts.append(operator_reason.strip())
    if pre_trade_locked_at is not None:
        parts.append(
            f"trades.pre_trade_locked_at was DELIBERATELY LEFT at "
            f"{pre_trade_locked_at!s} and is now a STALE DERIVATIVE of the "
            f"pre-correction entry_date {pre_entry_date}: it is written as "
            "entry_date + 'T16:00:00' and carries no independent evidence "
            "about when the plan was locked, so moving it would manufacture a "
            "lock time nothing supports. The inconsistency is labelled, not "
            "invented away."
        )
    return " ".join(p for p in parts if p)


def _follow_up_command(
    *, discrepancy_id: int, correction_id: int, trade_id: int,
    pre_entry_date: str, target_date: str, disc: Any,
) -> str:
    """The ready-to-paste command that closes the finding honestly.

    Without this the reason text's ``<correction_id>`` would land in the ledger
    as a literal placeholder, and the sentence claiming to be checkable would
    cite nothing. ``--force`` is expected and disclosed: the D22 gate
    classifies a ``pending_ambiguity_resolution`` row with live fill/trade ids
    as ``has_menu_path``, and every menu option for
    ``multi_match_within_window`` is either FALSE (``mark_unmatched``: "journal
    entry has no corresponding broker record" -- the broker order exists and is
    cited in this discrepancy's own payload), audit-only, or unconstructible.
    The CLI records the bypass in the stored reason.
    """
    order_id = "unknown"
    with contextlib.suppress(TypeError, ValueError):
        payload = json.loads(getattr(disc, "actual_value_json", "") or "{}")
        if isinstance(payload, dict) and payload.get("schwab_order_id"):
            order_id = str(payload["schwab_order_id"])
    reason = (
        f"Journal corrected, not overridden. Schwab order {order_id} executed "
        f"{target_date}; the journal recorded the order-ENTERED date "
        f"{pre_entry_date} because swing/trades/entry_auto_fill.py read "
        "enter_time instead of executions[].time (D31). trades.entry_date, "
        f"fill {disc.fill_id}'s fill_datetime and the watchlist_archive entry "
        f"row were corrected to {target_date} for trade {trade_id} under "
        f"correction {correction_id}. trades.pre_trade_locked_at was left at "
        "its pre-correction value and is a labelled stale derivative (RD "
        "2026-08-09). The session-distance guard that raised this finding was "
        "correct; the data it measured was wrong."
    )
    return (
        f'swing journal discrepancy resolve {discrepancy_id} '
        f'--resolution journal_corrected --force --reason "{reason}"'
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def preview_entry_date_correction(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    to_date: str,
    discrepancy_id: int,
    reason: str,
    allow_active: bool = False,
) -> EntryDateCorrectionPreview:
    """``--dry-run``: every validation, every guard, every pre-value read, and
    NO write transaction. Raises the same refusals the write path raises."""
    auth = _authorize(
        conn,
        trade_id=trade_id,
        to_date=to_date,
        discrepancy_id=discrepancy_id,
        reason=reason,
        allow_active=allow_active,
    )
    trade = auth.trade
    pre_fill_datetime = str(auth.fill_row[2])
    return EntryDateCorrectionPreview(
        trade_id=trade_id,
        ticker=str(trade.ticker),
        state=str(trade.state),
        discrepancy_id=discrepancy_id,
        fill_id=int(auth.fill_row[0]),
        watchlist_archive_id=auth.archive_id,
        target_date=auth.target_date,
        pre_values={
            "trades.entry_date": str(trade.entry_date),
            "fills.fill_datetime": pre_fill_datetime,
            "watchlist_archive.removed_date": str(trade.entry_date),
        },
        post_values={
            "trades.entry_date": auth.target_date,
            "fills.fill_datetime": _corrected_fill_datetime(
                pre_fill_datetime, auth.target_date,
            ),
            "watchlist_archive.removed_date": auth.target_date,
        },
        aggregates_before=_read_aggregates(conn, trade_id),
        allow_active_used=auth.allow_active_used,
        active_trade_consequences=(
            ACTIVE_TRADE_CONSEQUENCES if auth.allow_active_used else ()
        ),
        pre_trade_locked_at_left_stale=(
            None if getattr(trade, "pre_trade_locked_at", None) is None
            else str(trade.pre_trade_locked_at)
        ),
    )


def correct_entry_date(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    to_date: str,
    discrepancy_id: int,
    reason: str,
    allow_active: bool = False,
    applied_at: str | None = None,
) -> EntryDateCorrectionResult:
    """Outer: owns ``BEGIN IMMEDIATE`` / COMMIT / ROLLBACK, rejects a
    caller-held transaction (never auto-detects -- an auto-detect guard
    re-introduces the race the explicit lock closed)."""
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "correct_entry_date must be called with no open transaction; "
            "compose via _correct_entry_date_inner inside an existing tx"
        )
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _correct_entry_date_inner(
            conn,
            trade_id=trade_id,
            to_date=to_date,
            discrepancy_id=discrepancy_id,
            reason=reason,
            allow_active=allow_active,
            applied_at=applied_at,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def _correct_entry_date_inner(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    to_date: str,
    discrepancy_id: int,
    reason: str,
    allow_active: bool = False,
    applied_at: str | None = None,
) -> EntryDateCorrectionResult:
    """Never commits. Every callee is repo-level, so no inner ``with conn:``
    can close the caller's transaction out from under it."""
    from swing.trades.reconciliation_auto_correct import (
        MULTI_ROW_BOUND_FILL_KEY,
        _emit_trade_events_correction,
        _maybe_get_active_risk_policy_id,
        _utc_now_iso_ms,
    )

    auth = _authorize(
        conn,
        trade_id=trade_id,
        to_date=to_date,
        discrepancy_id=discrepancy_id,
        reason=reason,
        allow_active=allow_active,
    )
    trade = auth.trade
    disc = auth.discrepancy
    fill_id = int(auth.fill_row[0])
    pre_entry_date = str(trade.entry_date)
    pre_fill_datetime = str(auth.fill_row[2])
    new_fill_datetime = _corrected_fill_datetime(
        pre_fill_datetime, auth.target_date,
    )

    # Step 6 -- pre-values, INCLUDING all three aggregates step 8 recomputes.
    # current_size is datetime-independent but is rewritten by the same
    # statement, so it belongs in the pre/post pair for a faithful audit.
    pre_values: dict[str, Any] = {
        # The DURABLE binding a later mutation reads to recognise this fill.
        # `reconciliation_corrections` records affected_table='trades' +
        # affected_row_id=<trade_id>, which does not name the fill -- and the
        # coupling physically lives on the fill's datetime.
        MULTI_ROW_BOUND_FILL_KEY: fill_id,
        # The archive row is updated BY PRIMARY KEY, and the correction's
        # formal `affected_row_id` names only the TRADE -- so without this the
        # append-only trail could not reconstruct one of its own three
        # mutations, and a sibling archive row with the same ticker and target
        # date would leave the change unattributable (Codex R9 Major 2).
        BOUND_ARCHIVE_KEY: auth.archive_id,
        "trades.entry_date": pre_entry_date,
        "fills.fill_datetime": pre_fill_datetime,
        "watchlist_archive.removed_date": pre_entry_date,
        "fills.reconciliation_status": str(auth.fill_row[4]),
        "trades.pre_trade_locked_at": (
            None if getattr(trade, "pre_trade_locked_at", None) is None
            else str(trade.pre_trade_locked_at)
        ),
        **{f"trades.{k}": v for k, v in _read_aggregates(conn, trade_id).items()},
    }

    # Step 7 -- the coupled UPDATEs, each a literal statement in a narrow repo
    # writer. pre_trade_locked_at is NOT in this set (see the module docstring).
    update_entry_date(conn, trade_id=trade_id, entry_date=auth.target_date)
    update_fill_datetime(
        conn, fill_id=fill_id, fill_datetime=new_fill_datetime,
    )
    try:
        update_archive_removed_date(
            conn,
            archive_id=auth.archive_id,
            removed_date=auth.target_date,
        )
    except WatchlistArchiveMatchError as exc:
        raise EntryDateCorrectionError(str(exc)) from exc

    # Step 8 -- recompute BEFORE the audit INSERT. Moving an entry fill's
    # fill_datetime can move trades.last_fill_at (any trade whose corrected
    # entry fill is its latest fill -- every open, un-exited position) AND
    # current_avg_cost (a multi-entry-fill trade where the move re-orders which
    # entry fill sorts first). An applied_value_json written before the
    # recompute structurally cannot tell the truth in those cases.
    _recompute_aggregates(conn, trade_id)

    applied_values: dict[str, Any] = {
        MULTI_ROW_BOUND_FILL_KEY: fill_id,
        BOUND_ARCHIVE_KEY: auth.archive_id,
        "trades.entry_date": auth.target_date,
        "fills.fill_datetime": new_fill_datetime,
        "watchlist_archive.removed_date": auth.target_date,
        "fills.reconciliation_status": _FILL_RECONCILED_STATUS,
        "trades.pre_trade_locked_at": pre_values["trades.pre_trade_locked_at"],
        **{f"trades.{k}": v for k, v in _read_aggregates(conn, trade_id).items()},
    }

    stored_reason = _compose_reason(
        reason,
        allow_active_used=auth.allow_active_used,
        pre_trade_locked_at=pre_values["trades.pre_trade_locked_at"],
        pre_entry_date=pre_entry_date,
    )

    # Step 9 -- the append-only audit row. The action/choice PAIR is what makes
    # it lifecycle-valid; assert the choice rather than trust the constant.
    if not CORRECTION_CHOICE:
        raise EntryDateCorrectionError(
            "correction_choice must be non-empty for "
            f"correction_action={CORRECTION_ACTION!r}"
        )
    correction_id = insert_correction(
        conn,
        ReconciliationCorrection(
            correction_id=None,
            discrepancy_id=discrepancy_id,
            correction_action=CORRECTION_ACTION,
            correction_choice=CORRECTION_CHOICE,
            affected_table="trades",
            affected_row_id=trade_id,
            field_name="entry_date",
            pre_correction_value_json=json.dumps(pre_values, sort_keys=True),
            source_canonical_value_json=json.dumps(
                {"execution_leg_date": auth.target_date}, sort_keys=True,
            ),
            applied_value_json=json.dumps(applied_values, sort_keys=True),
            # NULL, not the applied dict (Codex R3 Major 3). `models.py`
            # defines this column as OPERATOR-SUPPLIED TRUTH for tier-3
            # `operator_overridden` rows, and every existing tier-2 operator
            # resolution stores NULL (`reconciliation_auto_correct.py:1841`).
            # Populating it with `applied_values` would attribute
            # `current_size`, `current_avg_cost`, `last_fill_at` and the fill's
            # reconciliation status to the OPERATOR, who confirmed only a
            # SERVER-DERIVED date -- a false attestation in the one ledger this
            # arc exists to keep honest. The date he confirmed is preserved in
            # `source_canonical_value_json`, in `correction_choice`, and in the
            # reason. (Deviation from the plan's step 9, which specified the
            # applied dict here; the schema contract governs.)
            operator_truth_value_json=None,
            applied_at=applied_at or _utc_now_iso_ms(),
            applied_by="operator",
            correction_set_id=None,
            superseded_by_correction_id=None,
            risk_policy_id_at_correction=_maybe_get_active_risk_policy_id(conn),
            schwab_api_call_id=None,
            reconciliation_run_id=int(disc.run_id),
            correction_reason=stored_reason,
            notes=None,
        ),
    )

    # Step 9-chain -- APPEND-ONLY SUPERSESSION. `reconciliation_corrections`
    # is append-only: a re-correction INSERTs a new row and points the prior
    # row's `superseded_by_correction_id` at it, exactly as the tier-3 chain
    # does. Two live heads on one fill would be the "multiple correction-chain
    # heads" state the CLI itself labels corruption -- and once the prior head
    # is superseded the fill-scoped barrier stops blocking it, so the surface's
    # own instruction to re-run finally becomes true.
    if auth.prior_correction_id is not None:
        conn.execute(
            "UPDATE reconciliation_corrections SET "
            "superseded_by_correction_id = ? WHERE correction_id = ?",
            (correction_id, auth.prior_correction_id),
        )

    # Step 9a -- the fill was reconciled; every existing correction path
    # performs this transition and a fill left 'unreconciled' after being
    # corrected would never heal (resolve_discrepancy touches only the
    # discrepancy row).
    conn.execute(
        "UPDATE fills SET reconciliation_status = ? WHERE fill_id = ?",
        (_FILL_RECONCILED_STATUS, fill_id),
    )

    # Step 10 -- the EXISTING forensic payload shape, not an invented one, so a
    # replay reads the same tuple here as on every other correction.
    # event_type='reconciliation_auto_correct' is the only member of the live
    # trade_events CHECK enum that fits; its name is wrong for an operator
    # action and widening that CHECK is schema this arc has no authorization
    # for. Naming debt, recorded.
    _emit_trade_events_correction(
        conn,
        trade_id=trade_id,
        correction_id=correction_id,
        affected_table="trades",
        affected_row_id=trade_id,
        field_name="entry_date",
        pre_value=pre_values,
        applied_value=applied_values,
    )

    return EntryDateCorrectionResult(
        correction_id=correction_id,
        trade_id=trade_id,
        fill_id=fill_id,
        watchlist_archive_id=auth.archive_id,
        discrepancy_id=discrepancy_id,
        pre_entry_date=pre_entry_date,
        target_date=auth.target_date,
        correction_reason=stored_reason,
        follow_up_command=_follow_up_command(
            discrepancy_id=discrepancy_id,
            correction_id=correction_id,
            trade_id=trade_id,
            pre_entry_date=pre_entry_date,
            target_date=auth.target_date,
            disc=disc,
        ),
        pre_values=pre_values,
        applied_values=applied_values,
    )
