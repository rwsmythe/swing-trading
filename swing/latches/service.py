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
from dataclasses import dataclass, field, replace
from datetime import date

from swing.evaluation.dates import session_offset, sessions_behind
from swing.latches.classification import admissible_decisions, governing_decision
from swing.latches.constants import (
    DEFAULT_LATCH_HORIZON_SESSIONS,
    zone_cap_for_pivot,
)
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

# `declined` REUSES `horizon_expired` (RD OQ-2's Option B, applied to this
# reason as residual R1). The state enum is a MECHANISM -- everything that must
# tell a decline apart from a horizon expiry keys on the REASON, which is
# first-class: the stale-order severity (`orders.py`
# `_CRITICAL_STALE_CLEAR_REASONS`) and the panel's `_state_label` branch. The
# alternative -- a new `LATCH_STATES` member -- is FOUR persisted CHECK clauses
# across migrations 0032 and 0033 and buys nothing the reason does not carry.
_STATE_BY_CLEAR_REASON = {
    "fill": "filled",
    "invalidation": "invalidated",
    "horizon": "horizon_expired",
    "superseded": "superseded",
    "declined": "horizon_expired",
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

    @property
    def zone_cap(self) -> float:
        """The frozen buy-zone limit cap. Single-sourced in
        `swing/latches/constants.py` so the fill heuristic, the finalized
        `Latch` and the dashboard's buy limit cannot drift apart."""
        return zone_cap_for_pivot(self.pivot)


# THE PRECEDENCE LADDER, PROJECTED ONTO THE LIVE VOCABULARY (RD's R6 ruling,
# 2026-08-06). His ladder reads
#
#     fill > declined > superseded > invalidation > criteria_lapsed > horizon
#
# and its AUTHORITY is that ruling, not this table. What the table holds is the
# ladder RESTRICTED to the reasons this resolver can actually produce today --
# every key here has a producer, and a rung for a reason with no writer would be
# a guard preceding its condition. The domain is pinned against
# `LATCH_CLEAR_REASONS` by test, so the vocabulary and its precedence cannot
# drift apart: adding a reason without ranking it fails immediately.
#
# RANK BREAKS SAME-SESSION TIES AND NOTHING ELSE. A terminal is an event with a
# DATE and the EARLIEST one ends the mandate; nothing later can un-happen it
# (L10). A resolver that scanned for one reason before considering another would
# rewrite a terminal that had already resolved -- and would then compare the
# fill against the wrong date, attributing a buy to a mandate the framework had
# already retired.
#
# The reasoning behind the order is RD's: operator FACTS (a fill) beat operator
# DECISIONS (a decline) beat framework EVENTS (a re-fire, which is an
# affirmative CURRENT fact) beat framework EVIDENCE of decay (an invalidation)
# beat DEADLINES (the horizon).
_CLEAR_REASON_RANK = {
    "fill": 0,
    "declined": 1,
    "superseded": 2,
    "invalidation": 3,
    "horizon": 4,
}


@dataclass(frozen=True)
class _Terminal:
    reason: str
    session: date
    trade_id: int | None = None
    fill_link_basis: str | None = None

    @property
    def order_key(self) -> tuple[date, int]:
        """Earliest date first; rank only on a tie."""
        return (self.session, _CLEAR_REASON_RANK[self.reason])


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

    The windowed rung ADDITIONALLY requires the entry price to sit inside this
    latch's own frozen executable zone (see `_price_in_executable_zone`). Date
    proximity alone is not identity: RD constraint 4 says "a pre-existing
    position or unrelated order in the same ticker must not read as this
    latch's fill", and `trades.candidate_id` is nullable (migration 0021
    backfilled every pre-v21 row to NULL), so an unrelated manual/legacy buy in
    the same ticker at an unrelated price would otherwise CLEAR the mandate --
    marking it `filled` and silencing the order alarms for a fire the operator
    never acted on.

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
        and _price_in_executable_zone(e.entry_price, draft)
    ]
    if windowed:
        return min(windowed, key=lambda e: (e.entry_date, e.trade_id)), "windowed"
    return None, None


def _price_in_executable_zone(entry_price, draft: _Draft) -> bool:
    """Could a fill at `entry_price` have come from THIS latch's mandate?

    The mandate is a BUY STOP at the frozen pivot with a limit cap at
    pivot x 1.03, so an execution it produced lands in the CLOSED interval
    [pivot, zone_cap] -- a gap through the cap is exactly what the cap exists to
    refuse. Compared at display precision (the price-precision-parity gotcha).

    An ABSENT or non-finite price is NOT verifiable, so it does NOT match: the
    windowed rung is a heuristic for legacy rows, and a heuristic must not clear
    a live mandate on evidence it cannot check. The EXACT `candidate_id` rung is
    unaffected -- an explicit link is authoritative regardless of price.
    """
    if entry_price is None or isinstance(entry_price, bool):
        return False
    if not isinstance(entry_price, (int, float)):
        return False
    value = float(entry_price)
    if not math.isfinite(value):
        return False
    return (round(draft.pivot, _PRICE_DP)
            <= round(value, _PRICE_DP)
            <= round(draft.zone_cap, _PRICE_DP))


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


def _resolve_decline(
    draft: _Draft, decisions, *, upper: date,
) -> _Terminal | None:
    """The ``declined`` terminal for this draft, or ``None`` (RD OQ-4).

    THE CROSS-KIND RESOLVER, NOT "THE LATEST DECLINE". ``governing_decision``
    resolves the ``place``/``decline`` FAMILY together because they are the two
    mutually exclusive answers to ONE question -- so ``decline(D5)`` followed by
    ``place(D6)`` yields a PLACE and this latch does not terminate. Keying on the
    latest DECLINE instead would withdraw a mandate the operator had corrected
    himself and re-placed, while the classifier went on scoring it ``accepted``:
    one latch, two contradictory answers. Sharing the resolver is the only thing
    that makes them agree.

    The family and window scoping live in ``admissible_decisions``, which BOTH
    this resolver and ``classify_latch`` call -- and the filter runs BEFORE the
    winner is chosen, never after (see that function).

    ``upper`` is the caller's as-of bound already capped at ``horizon_expiry``:
    an intent that has not happened yet as of a liveness probe must not decide
    it, and one recorded after the mandate lapsed is not a withdrawal OF it.
    """
    governing = governing_decision(admissible_decisions(
        decisions, candidate_set=draft.candidate_set,
        lower=draft.anchor, upper=upper))
    if governing is None or governing.intent_kind != "decline":
        return None
    try:
        session = date.fromisoformat(str(governing.action_session_date))
    except (TypeError, ValueError):        # pragma: no cover -- filtered above
        return None
    return _Terminal("declined", session)


def _resolve_terminal(
    draft: _Draft,
    *,
    bars: list[DailyBar],
    entries: list[EntryRecord],
    consumed: set[int],
    horizon_ref: date,
    bar_bound: date,
    fill_bound: date,
    horizon_sessions: int,
    dry_run: bool,
    decisions=(),
) -> _Terminal | None:
    """Resolve this latch's terminal, or ``None`` when it is still live.

    Three passes (plan A.6 c), which is what removes the circularity between
    "the fill bounds the terminal" and "the terminal bounds the fill":

    1. the NON-FILL candidates -- the invalidation bar walk, the operator's
       governing decline, and the horizon -- resolved EARLIEST-DATE-FIRST with
       ``_CLEAR_REASON_RANK`` breaking a same-session tie only;
    2. the fill search, bounded by that non-fill terminal;
    3. the fill's own rung, which is the same ranked comparison: rank 0 means a
       fill AT OR BEFORE the winning non-fill terminal takes it.

    So the precedence is ``fill > declined > invalidation > horizon`` (RD gate
    G.4 as extended by his OQ-4 and R6 rulings: operator facts beat operator
    decisions beat framework evidence beats deadlines). ``superseded`` is stamped
    by the FOLD rather than here -- it is authored by the arrival of the NEXT
    fire, which this function cannot see -- and it carries its rank for the one
    comparison the fold makes.

    THREE SEPARATE BOUNDS, because they answer different questions:

    * ``bar_bound``   -- the newest session whose CLOSE may be judged.
    * ``fill_bound``  -- the newest session whose FILL may be counted.
    * ``horizon_ref`` -- the session the horizon is measured against.

    They diverge for the liveness PROBE. "Was this latch live when a fire for
    session S arrived?" is asked at the moment that fire exists -- the evening
    BEFORE S -- so S's own bar and S's own fill have not happened yet and must
    NOT decide it. The HORIZON is different: a mandate whose window closes at S
    is already dead for S, so the horizon stays INCLUSIVE at S.

    ``dry_run`` makes this a read-only probe, so a probe never consumes a trade
    the real resolution must see.
    """
    candidates: list[_Terminal] = []
    # The walk stops at the HORIZON EXPIRY as well as at `bar_bound`: once the
    # mandate is dead, a later close below the stop is not an invalidation OF
    # IT. Without the cap a post-expiry break would overwrite `horizon_expired`
    # with `invalidated`, move the clear session forward, and escalate a stale
    # resting order from `warning` to `critical` -- all for a mandate that had
    # already lapsed. The expiry session ITSELF is still walked, so same-session
    # precedence (invalidation beats horizon) is preserved.
    for bar in _eligible_bars(
        bars, anchor=draft.anchor, upper=min(bar_bound, draft.horizon_expiry)
    ):
        # RD constraint 6: CLOSES, not intraday touches. Strict `<` -- a close
        # exactly AT the frozen stop is not below it -- and compared at DISPLAY
        # precision on BOTH sides, like every other price comparison in this
        # arc. A parquet float artifact (close 14.879999999 vs a 14.88 stop)
        # would otherwise CLEAR a live mandate while the panel renders both
        # numbers as 14.88, and clearing silences the no-resting-order alarm.
        # Rounding is conservative in the SAFE direction: it keeps a marginal
        # mandate armed rather than silently killing it.
        if round(bar.close, _PRICE_DP) < round(draft.stop, _PRICE_DP):
            candidates.append(_Terminal("invalidation", bar.session))
            break
    # THE OPERATOR'S OWN DECISION, capped at the expiry like every other walk.
    decline = _resolve_decline(
        draft, decisions, upper=min(fill_bound, draft.horizon_expiry))
    if decline is not None:
        candidates.append(decline)
    if sessions_behind(horizon_ref, draft.anchor) >= horizon_sessions:
        # Inclusive-expire, matching the in-tree observe-window precedent
        # (`swing/pipeline/runner.py` `sessions_since_detection >= max_pending`).
        #
        # THE HORIZON IS A RANKED CANDIDATE, NOT A FALLBACK, and the outcome is
        # identical: both other walks are capped AT the expiry, so any date they
        # produce is at-or-before it, and on the boundary session their ranks
        # win. Expressing it as a candidate is what makes `horizon`'s place in
        # the ladder a fact the table decides rather than one the control flow
        # implies.
        candidates.append(_Terminal("horizon", draft.horizon_expiry))

    nonfill = min(candidates, key=lambda t: t.order_key) if candidates else None

    effective_end = (
        draft.horizon_expiry if nonfill is None
        else min(draft.horizon_expiry, nonfill.session)
    )
    entry, basis = _match_fill(
        draft, entries, consumed=consumed, effective_end=effective_end,
        as_of=fill_bound)

    if entry is not None and not dry_run:
        # An accepted match is definitively THIS latch's trade, so it is
        # consumed either way -- rule (b), one trade fills at most one latch.
        consumed.add(entry.trade_id)
    if entry is not None:
        fill = _Terminal("fill", entry.entry_date, entry.trade_id, basis)
        # THE SAME RANKED COMPARISON as the non-fill candidates, so the fill's
        # place in the ladder is decided by the table too. Rank 0 is what makes
        # a fill dated exactly ON the winning terminal's session take it --
        # "you cannot decline a filled mandate", and the same for an
        # invalidation or an expiry landing that day.
        if nonfill is None or fill.order_key <= nonfill.order_key:
            return fill
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
        zone_cap=draft.zone_cap,
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
    decisions=(),
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

    def _close(draft: _Draft, *, forced: _Terminal | None = None) -> Latch:
        """`forced` is a terminal the FOLD authored rather than the resolver.

        `superseded` is the only such reason: it is created by the ARRIVAL of
        the next fire, which `_resolve_terminal` cannot see. The R6 branch below
        passes the winner of `declined` vs `superseded` through the same
        parameter, so the fold has exactly ONE stamping path.
        """
        if forced is not None:
            terminal: _Terminal | None = forced
        else:
            terminal = _resolve_terminal(
                draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=horizon_session, bar_bound=derivation_session,
                fill_bound=horizon_session, decisions=decisions,
                horizon_sessions=horizon_sessions, dry_run=False)
        closed = _finalize(
            draft, terminal=terminal, bars=bars,
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions,
            fill_link_anomaly=_has_fill_link_anomaly(draft, entries))
        latches.append(closed)
        return closed

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
            # The facts that may decide liveness stop STRICTLY BEFORE the
            # re-fire's own session (see `_resolve_terminal`); the horizon
            # stays inclusive AT it.
            prior = session_offset(anchor, -1)
            live_probe = _resolve_terminal(
                open_draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=anchor,
                bar_bound=min(prior, derivation_session),
                fill_bound=prior, decisions=decisions,
                horizon_sessions=horizon_sessions, dry_run=True)
            # THE FINAL RESOLUTION CAN REVERSE THE PROBE, AND THAT REVERSAL
            # OUTRANKS BOTH BRANCHES BELOW.
            #
            # The probe deliberately cannot see the re-fire session's own fill,
            # so it can report the old latch dead-by-horizon (clause iii) OR
            # still-live (clause ii) while the FINAL resolution -- which CAN see
            # it -- resolves that same latch to a FILL at-or-after this fire's
            # session. Arming a new mandate on top of that tells the operator to
            # buy a position he has JUST BOUGHT: the worst output this surface
            # can produce. Checked ONCE, ahead of both branches, so the horizon
            # path and the supersede path cannot diverge on it.
            final_probe = _resolve_terminal(
                open_draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=horizon_session, bar_bound=derivation_session,
                fill_bound=horizon_session, decisions=decisions,
                horizon_sessions=horizon_sessions, dry_run=True)
            if (final_probe is not None
                    and final_probe.reason == "fill"
                    and final_probe.session >= anchor):
                closed = _close(open_draft)
                latches[-1] = replace(
                    closed,
                    reconfirmation_candidate_ids=(
                        *closed.reconfirmation_candidate_ids, fire.candidate_id),
                    reconfirmation_sessions=(
                        *closed.reconfirmation_sessions, fire.action_session_date),
                )
                open_draft = None
                continue

            if live_probe is None:                                # clause (ii)
                same_pivot = (
                    round(float(fire.pivot), _PRICE_DP)
                    == round(open_draft.pivot, _PRICE_DP))
                if same_pivot:                                    # branch (a)
                    open_draft.reconfirmation_candidate_ids.append(fire.candidate_id)
                    open_draft.reconfirmation_sessions.append(
                        fire.action_session_date)
                    continue
                # branch (b) -- R6 (RD, 2026-08-06): `declined` OUTRANKS
                # `superseded`. If the operator had already declined this
                # mandate it was not live to be re-based, and stamping
                # `superseded` would overwrite his own recorded decision with a
                # framework inference. The fold must consult the decline HERE
                # because the liveness probe deliberately stops short of the
                # re-fire's own session, so a same-session decline is invisible
                # to it. Resolved by the SAME ranked comparison the resolver
                # uses -- one ladder, not a second hand-written rule.
                declined = _resolve_decline(
                    open_draft, decisions,
                    upper=min(anchor, open_draft.horizon_expiry))
                supersede = _Terminal("superseded", anchor)
                _close(open_draft, forced=min(
                    [t for t in (declined, supersede) if t is not None],
                    key=lambda t: t.order_key))
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
    bar_status_by_ticker=None,
    decision_intents_by_candidate_id=None,
) -> LatchDerivation:
    """Fold every A+ fire into latches. PURE.

    ``decision_intents_by_candidate_id`` (item 3a) is the operator's
    ``place``/``decline`` ledger keyed by CANDIDATE ID, the way ``bars`` and
    ``entries`` already arrive -- loaded by ``reader.py``, never read from a DB
    in here (L8).

    BOTH HALVES OF THAT NAME ARE LOAD-BEARING. ``decision``, not ``decline``:
    the resolver needs the whole family or a decline the operator CORRECTED by
    re-placing would still withdraw his mandate. ``by_candidate_id``, not
    ``by_ticker``: a ticker carries many historical latches, and a ticker-keyed
    mapping hands an old mandate's decline to a NEWER latch. Each latch selects
    the intents in its OWN candidate family -- the opening fire plus its
    re-confirmations, the identity rule the fill ladder's exact rung already
    uses.

    ``bar_status_by_ticker`` (Arc 21-G) is the per-ticker archive READ status
    in ``ARCHIVE_STATUSES``, carried through onto ``LatchDerivation`` alongside
    the per-ticker ``{session -> close}`` map derived from ``bars_by_ticker``.
    Both are pass-through display/provenance context: the FOLD, the eligible
    set and ``_finalize`` do not consult either, so the invalidation walk,
    ``bars_available`` and ``bars_through`` are bit-for-bit unchanged.

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
           (b) DIFFERENT pivot    -> the old latch CLEARS at this row's session
               and a NEW latch ARMS at the new frozen values. The reason is
               ``superseded`` UNLESS the operator had already recorded a
               governing ``decline`` for that same session or earlier, in which
               case it is ``declined`` (R6: his decision outranks the framework's
               inference about a mandate he had already ended).
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

    decisions_by_candidate = dict(decision_intents_by_candidate_id or {})
    for ticker in sorted(by_ticker):
        # Flattened per TICKER here; `admissible_decisions` then applies the
        # per-LATCH candidate-family rule inside the fold, so the family
        # predicate is stated once rather than duplicated at the assembly site.
        ticker_decisions = tuple(
            intent
            for fire in by_ticker[ticker]
            for intent in decisions_by_candidate.get(fire.candidate_id, ())
        )
        ticker_latches, ticker_degraded = _fold_ticker(
            by_ticker[ticker],
            bars=list(bars_by_ticker.get(ticker) or ()),
            entries=list(entries_by_ticker.get(ticker) or ()),
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions,
            decisions=ticker_decisions,
        )
        latches.extend(ticker_latches)
        degraded.extend(ticker_degraded)

    latches.sort(key=lambda x: (x.identity.ticker, x.anchor, x.identity.candidate_id))
    degraded.sort(key=lambda x: (x.ticker, x.action_session_date, x.candidate_id))
    # The witness map is derived HERE, from the bars the caller already passed,
    # so it cannot drift from the bars the walk saw. It is not consulted above.
    archive_closes = {
        ticker: {b.session: b.close for b in (bars or ())}
        for ticker, bars in (bars_by_ticker or {}).items()
    }
    return LatchDerivation(
        latches=tuple(latches),
        degraded=tuple(degraded),
        derivation_session=derivation_session,
        horizon_session=horizon_session,
        horizon_sessions=horizon_sessions,
        archive_closes=archive_closes,
        archive_status=dict(bar_status_by_ticker or {}),
    )
