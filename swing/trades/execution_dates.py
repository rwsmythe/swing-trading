"""D31 — the SINGLE source for "which date did this order execute on".

THREE consumers derive a date from a Schwab order's execution legs (two entry,
one exit; the count was two until the D31 exit-side follow-on):

  - :mod:`swing.trades.entry_auto_fill` — the ENTRY date, from a
    ``SchwabOrderResponse``'s ``executions[*].time`` attributes, at
    form-render time;
  - :mod:`swing.trades.entry_date_correction` — the ENTRY date, from a
    discrepancy's persisted ``actual_value_json.execution_legs[*]['time']``
    dicts, when the operator corrects a recorded date;
  - :mod:`swing.trades.exit_auto_fill` — the EXIT date, from a
    ``SchwabOrderResponse``'s ``executions[*].time`` attributes, at
    form-render time, per candidate.

The two ENTRY consumers must agree with EACH OTHER, and the correction
surface's whole authorization argument is that the date it writes is *the same
date the auto-fill should have written*. The EXIT consumer derives a different
FACT (when a SELL executed, not when a BUY did) by the same RULE, and its
agreement obligation is with the reconciliation session guard rather than with
either entry consumer — see ``exit_auto_fill._execution_date``, which states
the exit-side invariant. Two implementations of one derivation is the #24-#26
two-path-divergence class, so the derivation lives here once and no caller
reimplements it.

Timezone convention, stated because it is a decision and not an oversight:
the emitted value is the winning leg's OWN offset-local calendar date — the
``[:10]`` prefix of its RAW timestamp string — with NO conversion to
America/New_York and no offset arithmetic. Schwab emits ``+0000`` on every
execution leg, so in practice that IS the UTC calendar date; the two are
distinguished here because they are not the same claim, and a MIXED-offset
collection is REFUSED rather than resolved (see the function's own note).
The reconciliation side reads the same fact the same way
(``swing/trades/schwab_reconciliation.py`` ``_fill_execution_session_distance``:
``_date.fromisoformat(str(raw_time)[:10])``). An auto-fill that converted to
ET while the A2-date guard did not would manufacture a permanent one-session
disagreement on every after-hours execution — precisely the shape of the
finding this arc exists to close.

Known residue: the divergence begins at 00:00Z, i.e. 20:00 ET on the previous
local date (19:00 ET under EST). A US-equity execution in the 20:00-24:00 ET
after-hours block lands on the NEXT UTC date, so both paths agree on a date
one day later than the operator's calendar. Regular US equity hours are
13:30Z-20:00Z (EDT), entirely within one UTC day. The residue is unchanged by
the exit-side consumer but its BLAST RADIUS now includes exit dates as well as
entry dates. The clean fix converts BOTH sites — this module and the
reconciliation guard — in one change; it is out of scope here and is recorded
rather than half-applied.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

__all__ = ["execution_precedes_order", "latest_execution_leg_date"]


def latest_execution_leg_date(raw_times: Iterable[Any]) -> str | None:
    """The ``YYYY-MM-DD`` of the LATEST execution leg, or ``None``.

    ``None`` means "no usable execution-grain date", and it is returned for
    exactly THREE reasons, all of which the callers surface rather than absorb
    (the count read "four" against three bullets from the day this function
    was written; corrected by counting the code's own refusal branches at the
    D31 exit-side follow-on):

      - the leg collection is empty;
      - ANY leg's ``time`` is unparseable, non-``str``, or not in the EXTENDED
        ``YYYY-MM-DD...`` format;
      - the legs do not all share ONE utc offset.

    The second is deliberate. ``SchwabExecutionLeg.time`` is validated
    NON-EMPTY, not PARSEABLE, so any non-empty string reaches here. Skipping a
    bad leg and ranking the rest would date a trade from a PARTIAL view of its
    own fills, silently — a whole-collection refusal is visible.

    The LATEST is computed by parsing every leg and taking ``max()``. Never
    index the collection: ``_extract_executions_from_order_raw`` builds it with
    a plain ``append`` in API order and never sorts, so ``[0]`` / ``[-1]`` mean
    "whatever Schwab listed", which coincides with "the latest execution" only
    by luck. Parsing is used ONLY to rank; a naive leg timestamp is ranked as
    UTC for that purpose.

    THE EXTENDED FORMAT IS REQUIRED, and the returned value is CANONICAL
    ``YYYY-MM-DD`` (Codex R1 Major 2). ``datetime.fromisoformat`` on 3.11+
    accepts BASIC ISO forms -- ``20260731``, compact datetimes, ``2026-W31-5``
    week dates -- and a naive ``[:10]`` slice of those yields ``"20260731"`` or
    ``"2026-W31-5"``, neither of which is a date. That value would flow into
    ``trades.entry_date`` and ``watchlist_archive.removed_date`` from the entry
    consumers, and into ``fills.fill_datetime`` from the exit one, and break
    every downstream ``[:10]`` prefix and lexical date comparison in the
    project. So a
    leg time must be a ``str`` whose first ten characters ARE the canonical
    date, and the emitted value is ``parsed.date().isoformat()``. Anything else
    is a whole-collection refusal, exactly as an unparseable value is.
    """
    ranked: list[tuple[datetime, str]] = []
    offsets: set[timedelta] = set()
    for raw in raw_times:
        if not isinstance(raw, str):
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            return None
        canonical = parsed.date().isoformat()
        if raw[:10] != canonical:
            # A basic/compact/week-date form, or a value whose own text
            # disagrees with the date it parses to. Never silently canonicalize
            # a shape we did not expect from this emitter.
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        offset = parsed.utcoffset() or timedelta(0)
        offsets.add(offset)
        ranked.append((parsed, canonical))
    if not ranked:
        return None
    if len(offsets) > 1:
        # MIXED OFFSETS ARE REFUSED, not silently resolved (Codex R2 Major 4).
        # Ranking is by ABSOLUTE INSTANT while the emitted value is the leg's
        # own offset-local prefix, and those two only agree while every leg
        # shares one offset. With mixed offsets a later-in-absolute-time leg at
        # -10:00 can carry an EARLIER local date than an earlier leg at +14:00,
        # so "the latest leg's date" stops having one answer. Picking either
        # convention here would silently diverge from the reconciliation guard,
        # which reads the raw prefix with no offset arithmetic at all -- the
        # #24-#26 class. A whole-collection refusal is the honest answer, and
        # the callers already surface a refusal as a visible fallback. Schwab
        # emits `+0000` on every leg, so this is a guard, not a live path.
        return None
    _, winning_date = max(ranked, key=lambda pair: pair[0])
    return winning_date


def execution_precedes_order(
    execution_date: str | None, order_entered_date: str | None,
) -> bool:
    """True when a derived execution date PRECEDES the order's entered date.

    THE RULE LIVES HERE so every consumer obeys it (Codex R16) -- three of
    them as of the D31 exit-side follow-on. R14 put the check in the correction
    surface only, and the entry auto-fill -- the very path T1 changed to take
    the execution grain -- kept accepting a backwards date. Consumers of one
    derivation disagreeing about what the derivation ADMITS is the #24-#26
    divergence class arriving one layer up from the value itself, which is why
    the exit consumer inherited the rule by import rather than by resemblance.

    Nothing else enforces the ordering: `SchwabExecutionLeg.time` is validated
    non-empty only, with no cross-field chronology check against
    `SchwabOrderResponse.enter_time`, and the reconciliation session distance is
    DIRECTIONLESS. An execution cannot happen before its own order, so a payload
    asserting it is internally contradictory.

    The RULE is shared; the RESPONSE is each consumer's own, and legitimately
    differs: both auto-fills fall back VISIBLY to the entered date (stamping
    `entry_date_source` / `exit_date_source` = `'enter_time'`), because each is
    a form default the operator sees and can override, while the correction
    surface REFUSES with a message naming the contradiction, because it is
    about to rewrite three ledger rows.

    Comparison is `<`, not `<=`: a same-day execution is ordinary.
    """
    if not execution_date or not order_entered_date:
        return False
    return str(execution_date) < str(order_entered_date)
