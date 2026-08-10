"""Item-5 D31 — the SINGLE source for "which date did this order execute on".

Two consumers derive an entry date from a Schwab order's execution legs:

  - :mod:`swing.trades.entry_auto_fill` — from a ``SchwabOrderResponse``'s
    ``executions[*].time`` attributes, at form-render time;
  - :mod:`swing.trades.entry_date_correction` — from a discrepancy's persisted
    ``actual_value_json.execution_legs[*]['time']`` dicts, when the operator
    corrects a recorded date.

They MUST agree, and the correction surface's whole authorization argument is
that the date it writes is *the same date the auto-fill should have written*.
Two implementations of one derivation is the #24-#26 two-path-divergence
class, so the derivation lives here once and neither caller reimplements it.

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
13:30Z-20:00Z (EDT), entirely within one UTC day. The clean fix converts BOTH
sites in one change; it is out of scope here and is recorded rather than
half-applied.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

__all__ = ["latest_execution_leg_date"]


def latest_execution_leg_date(raw_times: Iterable[Any]) -> str | None:
    """The ``YYYY-MM-DD`` of the LATEST execution leg, or ``None``.

    ``None`` means "no usable execution-grain date", and it is returned for
    exactly four reasons, all of which the callers surface rather than absorb:

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
    ``trades.entry_date`` and ``watchlist_archive.removed_date`` and break every
    downstream ``[:10]`` prefix and lexical date comparison in the project. So a
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
