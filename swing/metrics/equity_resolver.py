"""Live-capital denominator resolver — PROVISIONAL/LIVE contract (plan §A.6).

Per spec §2 split-policy + Phase 9 Sub-bundle C ``account_equity_snapshots``,
the dynamic PROVISIONAL badge on §3.4 + §3.5 operational metrics resolves
the denominator at query time:

- **LIVE** when an ``account_equity_snapshots`` row exists with
  ``snapshot_date <= asof_date``; returns the snapshot's ``equity_dollars``.
- **PROVISIONAL** when no snapshot satisfies the predicate; falls back to
  the at-trade-time policy's ``capital_floor_constant_dollars`` (NOT the
  user-memory ``max($7,500, actual)`` semantic — that is the operator's
  mental model, not a system-computed value).

The helper is **anchor-agnostic** — ``asof_date`` is the caller's
responsibility per plan §A.15 session-anchor matrix. Sub-bundle D consumers
use ``swing.evaluation.last_completed_session(datetime.now())``; Sub-bundle E
identification-funnel uses ``pipeline_run.started_ts.date()``.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Literal

from swing.data.models import RiskPolicy
from swing.data.repos.account_equity_snapshots import (
    get_latest_snapshot_on_or_before,
)


def resolve_live_capital_denominator_dollars(
    conn: sqlite3.Connection,
    *,
    asof_date: date,
    at_trade_time_policy: RiskPolicy,
) -> tuple[float, Literal["LIVE", "PROVISIONAL"]]:
    """Resolve the live-capital denominator dollars for the given asof_date.

    Returns ``(value, "LIVE")`` when an ``account_equity_snapshots`` row is
    on-or-before ``asof_date``; ``(value, "PROVISIONAL")`` otherwise.

    PROVISIONAL fallback uses ``at_trade_time_policy.capital_floor_constant_dollars``
    (passed in by caller per plan §A.5 split — the helper itself is policy-
    agnostic; caller decides whether to pass LIVE or AT-TRADE-TIME policy).

    Per plan §A.6 + §I.4: the badge-render text composition lives at the
    view-model layer (Sub-bundles D + E); this helper returns only the
    raw value + the LIVE/PROVISIONAL discriminator.
    """
    snapshot = get_latest_snapshot_on_or_before(
        conn, asof_date=asof_date.isoformat(),
    )
    if snapshot is not None:
        # `get_latest_snapshot_on_or_before` without `with_provenance` returns
        # a single AccountEquitySnapshot (NOT a tuple). The type annotation
        # union in the repo helper covers both modes.
        return (float(snapshot.equity_dollars), "LIVE")
    return (float(at_trade_time_policy.capital_floor_constant_dollars), "PROVISIONAL")
