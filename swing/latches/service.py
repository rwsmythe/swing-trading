"""The PURE latch derivation (Phase 21 Arc A).

No DB access, no network, no transaction management -- the Phase-12 classifier
convention. Every input arrives pre-fetched; `swing/latches/reader.py` owns the
I/O.

The two anchors (plan G.3, RD-CONFIRMED):

* ``horizon_session``    -- the FORWARD anchor (``action_session_for_run``).
  Answers "is the mandate live for the session I am about to trade", so it is
  what the HORIZON is measured against.
* ``derivation_session`` -- the BACKWARD anchor (``last_completed_session``).
  The newest session whose CLOSE can be judged, so it bounds the INVALIDATION
  bar walk. A bar newer than this is a look-ahead (the nightly warm legitimately
  writes one at 17:30 for the NEXT session).

They are not independent: production always passes
``derivation_session = session_offset(horizon_session, -1)``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from swing.evaluation.dates import session_offset, sessions_behind
from swing.latches.constants import DEFAULT_LATCH_HORIZON_SESSIONS, LATCH_ZONE_CAP_PCT
from swing.latches.identity import LatchIdentity, parse_session_date
from swing.latches.models import (
    DailyBar,
    DegradedFire,
    EntryRecord,
    FireRow,
    Latch,
    LatchDerivation,
)

# The display precision every price comparison rounds to (the
# price-precision-parity gotcha): a sub-cent float artifact must never fork a
# latch or flip an agreement flag.
_PRICE_DP = 2

_STATE_BY_CLEAR_REASON = {
    "fill": "filled",
    "invalidation": "invalidated",
    "horizon": "horizon_expired",
    "superseded": "superseded",
}


@dataclass
class _Draft:
    """A latch under construction during the per-ticker fold (MUTABLE)."""

    fire: FireRow
    anchor: date
    pivot: float
    stop: float
    horizon_expiry: date
    reconfirmation_candidate_ids: list[int] = field(default_factory=list)
    reconfirmation_sessions: list[str] = field(default_factory=list)

    @property
    def candidate_set(self) -> set[int]:
        return {self.fire.candidate_id, *self.reconfirmation_candidate_ids}


@dataclass(frozen=True)
class _Terminal:
    reason: str
    session: date
    trade_id: int | None = None
    fill_link_basis: str | None = None


def _validate_fire(fire: FireRow) -> tuple[date | None, str | None]:
    """Return ``(anchor, None)`` for a usable fire, else ``(None, reason)``.

    Every shape here was checked against the REAL write boundary (plan A.10):
    migration 0001 puts NO ``NOT NULL`` on ``candidates.pivot`` /
    ``initial_stop`` and no bucket<->pivot CHECK, and SQLite stores
    ``float('nan')`` as NULL -- so a ``bucket='aplus'`` row with a missing or
    non-finite price is reachable, not impossible.
    """
    try:
        anchor = parse_session_date("action_session_date", fire.action_session_date)
    except ValueError:
        return None, "bad_session_date"
    if not _usable_price(fire.pivot):
        return None, "pivot_missing"
    if not _usable_price(fire.initial_stop):
        return None, "stop_missing"
    if float(fire.initial_stop) >= float(fire.pivot):
        return None, "stop_not_below_pivot"
    return anchor, None


def _usable_price(value) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) > 0.0


def _eligible_bars(
    bars: list[DailyBar], *, anchor: date, upper: date,
) -> list[DailyBar]:
    """The bar walk's eligible set: ``anchor <= session <= upper``, INCLUSIVE
    at BOTH ends (plan A.7).

    The anchor session's own bar counts (the mandate is live from that
    session's open); a bar before the anchor is history the pivot was computed
    FROM, not an invalidation of a mandate that did not yet exist.
    """
    return sorted(
        (b for b in bars if anchor <= b.session <= upper),
        key=lambda b: b.session,
    )


def _match_fill(
    draft: _Draft,
    entries: list[EntryRecord],
    *,
    consumed: set[int],
    effective_end: date,
    as_of: date,
) -> tuple[EntryRecord | None, str | None]:
    """The two-rung fill ladder, EXACT first (plan A.6).

    Rung 1 (``candidate_id``): an entry whose ``candidate_id`` is in this
    latch's candidate set AND dated inside ``[anchor, as_of]``.
    Rung 2 (``windowed``): ONLY when ``entry.candidate_id IS NULL`` -- ticker
    match inside ``[anchor, min(effective_end, as_of)]``, where
    ``effective_end`` is the ACTUAL live window (bounded by the non-fill
    terminal), not the nominal horizon.

    ``as_of`` IS LOAD-BEARING ON BOTH RUNGS. The open-latch rule's liveness
    PROBE asks "had this latch terminated by session S?", and a fill dated
    AFTER S has not happened yet as of S. Without the bound the probe sees a
    FUTURE fill, concludes the latch was already dead at S, and opens a second
    latch where the correct answer is a re-confirmation -- i.e. the probe and
    the final resolution disagree about the same latch.
    """
    cset = draft.candidate_set
    available = [e for e in entries if e.trade_id not in consumed]
    exact = [
        e for e in available
        if e.candidate_id is not None
        and e.candidate_id in cset
        and draft.anchor <= e.entry_date <= as_of
    ]
    if exact:
        return min(exact, key=lambda e: (e.entry_date, e.trade_id)), "candidate_id"
    windowed = [
        e for e in available
        if e.candidate_id is None
        and draft.anchor <= e.entry_date <= min(effective_end, as_of)
    ]
    if windowed:
        return min(windowed, key=lambda e: (e.entry_date, e.trade_id)), "windowed"
    return None, None


def _has_fill_link_anomaly(draft: _Draft, entries: list[EntryRecord]) -> bool:
    """A ``candidate_id`` match dated BEFORE the anchor is NOT a fill -- it is
    a mis-linked row, surfaced loudly rather than silently clearing a latch
    backwards."""
    cset = draft.candidate_set
    return any(
        e.candidate_id is not None
        and e.candidate_id in cset
        and e.entry_date < draft.anchor
        for e in entries
    )


def _resolve_terminal(
    draft: _Draft,
    *,
    bars: list[DailyBar],
    entries: list[EntryRecord],
    consumed: set[int],
    horizon_ref: date,
    bar_bound: date,
    horizon_sessions: int,
    dry_run: bool,
) -> _Terminal | None:
    """Resolve this latch's terminal, or ``None`` when it is still live.

    Three passes (plan A.6 c), which is what removes the circularity between
    "the fill bounds the terminal" and "the terminal bounds the fill":

    1. the NON-FILL terminal -- the invalidation bar walk, then the horizon;
    2. the fill search, bounded by that non-fill terminal;
    3. the precedence ``fill > invalidation > horizon`` (RD gate G.4: facts
       beat signals beat deadlines).

    ``dry_run`` makes this a read-only probe (the open-latch rule's liveness
    test), so a probe never consumes a trade the real resolution must see.
    """
    nonfill: _Terminal | None = None
    for bar in _eligible_bars(bars, anchor=draft.anchor, upper=bar_bound):
        # RD constraint 6: CLOSES, not intraday touches. Strict `<` -- a close
        # exactly AT the frozen stop is not below it.
        if bar.close < draft.stop:
            nonfill = _Terminal("invalidation", bar.session)
            break
    if nonfill is None and sessions_behind(horizon_ref, draft.anchor) >= horizon_sessions:
        # Inclusive-expire, matching the in-tree observe-window precedent
        # (`swing/pipeline/runner.py` `sessions_since_detection >= max_pending`).
        nonfill = _Terminal("horizon", draft.horizon_expiry)

    effective_end = (
        draft.horizon_expiry if nonfill is None
        else min(draft.horizon_expiry, nonfill.session)
    )
    entry, basis = _match_fill(
        draft, entries, consumed=consumed, effective_end=effective_end,
        as_of=horizon_ref)

    if entry is not None and not dry_run:
        # An accepted match is definitively THIS latch's trade, so it is
        # consumed either way -- rule (b), one trade fills at most one latch.
        consumed.add(entry.trade_id)
    if entry is not None and (nonfill is None or entry.entry_date <= nonfill.session):
        return _Terminal("fill", entry.entry_date, entry.trade_id, basis)
    return nonfill


def _finalize(
    draft: _Draft,
    *,
    terminal: _Terminal | None,
    bars: list[DailyBar],
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int,
    fill_link_anomaly: bool,
) -> Latch:
    eligible = _eligible_bars(
        bars, anchor=draft.anchor, upper=derivation_session)
    sessions_elapsed = sessions_behind(horizon_session, draft.anchor)
    state = "armed" if terminal is None else _STATE_BY_CLEAR_REASON[terminal.reason]
    return Latch(
        identity=LatchIdentity(
            candidate_id=draft.fire.candidate_id,
            evaluation_run_id=draft.fire.evaluation_run_id,
            ticker=draft.fire.ticker,
            detection_date=draft.fire.action_session_date,
            pipeline_run_id=draft.fire.pipeline_run_id,
        ),
        latched_pivot=draft.pivot,
        latched_initial_stop=draft.stop,
        zone_cap=round(draft.pivot * (1.0 + LATCH_ZONE_CAP_PCT / 100.0), 4),
        anchor=draft.anchor,
        horizon_expiry=draft.horizon_expiry,
        sessions_elapsed=sessions_elapsed,
        sessions_to_horizon=max(0, horizon_sessions - sessions_elapsed),
        state=state,
        clear_reason=None if terminal is None else terminal.reason,
        clear_session=None if terminal is None else terminal.session,
        clear_trade_id=None if terminal is None else terminal.trade_id,
        fill_link_basis=None if terminal is None else terminal.fill_link_basis,
        fill_link_anomaly=fill_link_anomaly,
        bars_available=bool(eligible),
        bars_through=eligible[-1].session if eligible else None,
        reconfirmation_candidate_ids=tuple(draft.reconfirmation_candidate_ids),
        reconfirmation_sessions=tuple(draft.reconfirmation_sessions),
    )


def _fold_ticker(
    ticker_fires: list[FireRow],
    *,
    bars: list[DailyBar],
    entries: list[EntryRecord],
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int,
) -> tuple[list[Latch], list[DegradedFire]]:
    """The per-ticker fold implementing the OPEN-LATCH rule (plan A.2).

    Module-level (not a closure) so the loop variables it reads are BOUND
    parameters -- a closure over the enclosing per-ticker loop would be a
    late-binding hazard, and `consumed` in particular must be exactly this
    ticker's running set.
    """
    latches: list[Latch] = []
    degraded: list[DegradedFire] = []
    consumed: set[int] = set()
    open_draft: _Draft | None = None

    def _close(draft: _Draft, *, superseded_session: date | None = None) -> None:
        if superseded_session is not None:
            terminal: _Terminal | None = _Terminal("superseded", superseded_session)
        else:
            terminal = _resolve_terminal(
                draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=horizon_session, bar_bound=derivation_session,
                horizon_sessions=horizon_sessions, dry_run=False)
        latches.append(_finalize(
            draft, terminal=terminal, bars=bars,
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions,
            fill_link_anomaly=_has_fill_link_anomaly(draft, entries)))

    for fire in sorted(ticker_fires, key=lambda f: f.sort_key):
        anchor, reason = _validate_fire(fire)
        if reason is not None:
            degraded.append(DegradedFire(
                candidate_id=fire.candidate_id,
                evaluation_run_id=fire.evaluation_run_id,
                ticker=fire.ticker,
                action_session_date=fire.action_session_date,
                reason=reason))
            continue

        if open_draft is not None:
            if open_draft.anchor == anchor:                       # clause (i)
                open_draft.reconfirmation_candidate_ids.append(fire.candidate_id)
                open_draft.reconfirmation_sessions.append(fire.action_session_date)
                continue
            live_probe = _resolve_terminal(
                open_draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=anchor, bar_bound=min(anchor, derivation_session),
                horizon_sessions=horizon_sessions, dry_run=True)
            if live_probe is None:                                # clause (ii)
                same_pivot = (
                    round(float(fire.pivot), _PRICE_DP)
                    == round(open_draft.pivot, _PRICE_DP))
                if same_pivot:                                    # branch (a)
                    open_draft.reconfirmation_candidate_ids.append(fire.candidate_id)
                    open_draft.reconfirmation_sessions.append(
                        fire.action_session_date)
                    continue
                _close(open_draft, superseded_session=anchor)     # branch (b)
            else:                                                 # clause (iii)
                _close(open_draft)
            open_draft = None

        open_draft = _Draft(
            fire=fire, anchor=anchor,
            pivot=float(fire.pivot), stop=float(fire.initial_stop),
            horizon_expiry=session_offset(anchor, horizon_sessions))

    if open_draft is not None:
        _close(open_draft)
    return latches, degraded


def derive_latches(
    *,
    fires,
    bars_by_ticker,
    entries_by_ticker,
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int = DEFAULT_LATCH_HORIZON_SESSIONS,
) -> LatchDerivation:
    """Fold every A+ fire into latches. PURE.

    THE OPEN-LATCH RULE (plan A.2, RD-RULED). Processing a ticker's fires in
    ``(action_session_date, run_ts, candidate_id)`` order, each row is
    dispositioned against that ticker's most recent latch:

    (i)  SAME-SESSION CLAUSE -- unconditional collapse. If the latch's anchor
         equals this row's action session, the row is a RE-CONFIRMATION *even
         if that latch already cleared during that session*. A trading session
         is the atomic unit: it has ONE verdict, so at most one latch per
         ``(ticker, action_session_date)`` can ever be opened.
    (ii) ARMED RE-FIRE -- two branches. If the latch is still LIVE as of this
         row's session:
           (a) SAME frozen pivot  -> RE-CONFIRMATION (no new latch, no
               re-freeze; the count and the session list grow);
           (b) DIFFERENT pivot    -> the old latch CLEARS with
               ``clear_reason='superseded'`` stamped at this row's session, and
               a NEW latch ARMS at the new frozen values.
    (iii) otherwise the row opens a new latch normally.

    The hazard constraint 1 guards is not re-freezing as such -- it is
    re-freezing SILENTLY. A supersede is loud: the old latch terminates with a
    RECORDED reason, distinguishable from `horizon` forever.
    """
    horizon_sessions = int(horizon_sessions)
    by_ticker: dict[str, list[FireRow]] = {}
    for fire in fires:
        by_ticker.setdefault(fire.ticker, []).append(fire)

    latches: list[Latch] = []
    degraded: list[DegradedFire] = []

    for ticker in sorted(by_ticker):
        ticker_latches, ticker_degraded = _fold_ticker(
            by_ticker[ticker],
            bars=list(bars_by_ticker.get(ticker) or ()),
            entries=list(entries_by_ticker.get(ticker) or ()),
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions,
        )
        latches.extend(ticker_latches)
        degraded.extend(ticker_degraded)

    latches.sort(key=lambda x: (x.identity.ticker, x.anchor, x.identity.candidate_id))
    degraded.sort(key=lambda x: (x.ticker, x.action_session_date, x.candidate_id))
    return LatchDerivation(
        latches=tuple(latches),
        degraded=tuple(degraded),
        derivation_session=derivation_session,
        horizon_session=horizon_session,
        horizon_sessions=horizon_sessions,
    )
