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
the emitted value is the naive ``[:10]`` prefix of the winning leg's RAW
timestamp string — the UTC calendar date, with NO conversion to
America/New_York. The reconciliation side reads the same fact the same way
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
from datetime import UTC, datetime
from typing import Any

__all__ = ["latest_execution_leg_date"]


def latest_execution_leg_date(raw_times: Iterable[Any]) -> str | None:
    """The ``YYYY-MM-DD`` of the LATEST execution leg, or ``None``.

    ``None`` means "no usable execution-grain date", and it is returned for
    exactly two reasons, both of which the callers surface rather than absorb:

      - the leg collection is empty;
      - ANY leg's ``time`` is unparseable.

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
        ranked.append((parsed, canonical))
    if not ranked:
        return None
    _, winning_date = max(ranked, key=lambda pair: pair[0])
    return winning_date
