"""Hypothesis recommendation engine: matcher + prioritizer + tripwire.

Per `docs/hypothesis-recommendation-backend-brief.md` §4.2-§4.4. Three
pure(-ish) compute units:

1. `match_candidate_to_hypotheses` — given a `Candidate` and the active
   subset of the `hypothesis_registry`, return zero-or-more
   `HypothesisMatch` rows describing which hypotheses this candidate
   would advance.
2. `prioritize_recommendations` — given a flat list of matches across all
   candidates plus current registry/progress, return a display-ordered
   list of `CandidateRecommendation`s (most-investigation-valuable first).
3. `compute_tripwire_status` — given a hypothesis id and a DB connection,
   walk that hypothesis's tagged closed trades and return the consecutive-
   max-loss + absolute-loss tripwire signals.

Everything is dataclasses + pure functions; nothing here mutates DB state.
DB writes (status updates, trade entry) live in their respective repos.

**Doctrine-defensible miss set is FROZEN (brief §0 + Finviz study D1).**
The set is exposed as a module constant and ALSO accepted as a parameter
so tests can verify the matcher behaves correctly for any candidate set
operators future studies might commission. The CALL SITE in production
must use `DOCTRINE_DEFENSIBLE_MISS_SET` directly — overriding it would
require routing through the source-of-truth correction protocol.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from swing.data.models import Candidate, HypothesisRegistryEntry, Trade


# C.10 migration helper (was: list_all_exits shim from repos/trades.py).
# Local _ExitShape adapter mirroring the per-module pattern in web view
# models + review_log + pipeline runner. Dies in the future cleanup phase
# when equity.py refactors to consume Fill directly.
@dataclass(frozen=True)
class _ExitShape:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(
    conn: sqlite3.Connection,
) -> list[_ExitShape]:
    """C.10: ExitLike collection sourced from fills (action != 'entry').
    Per-fill realized_pnl + r_multiple derive on the fly via
    ``swing.trades.derived_metrics`` — single source of math truth.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import (
        list_closed_trades,
        list_open_trades,
    )
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    trades_by_id: dict[int, Trade] = {}
    for t in list_open_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t
    for t in list_closed_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t

    out: list[_ExitShape] = []
    for f in list_all_fills(conn):
        if f.action == "entry":
            continue
        trade = trades_by_id.get(f.trade_id)
        if trade is None:
            continue
        rps = initial_risk_per_share(
            entry_price=trade.entry_price,
            initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        if rps == 0 or f.quantity == 0:
            rmult: float | None = None
        else:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        exit_date = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        out.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    return out


# Frozen at Finviz-pool study D1 (research/studies/finviz-pool-binding-
# constraints.md §"Doctrine-defensible misses"). NOT modifiable post-data
# without an explicit operator-recorded amendment.
DOCTRINE_DEFENSIBLE_MISS_SET: frozenset[str] = frozenset({
    "TT8_rs_rank",
    "risk_feasibility",
    "proximity_20ma",
})

# Hypothesis-name constants. Centralized so the matcher rules and the
# tripwire string-matcher cannot drift; if a NEW migration adds a fifth
# hypothesis, add the name + matcher rule here.
H_APLUS_BASELINE = "A+ baseline"
H_NEAR_APLUS_EXTENSION = "Near-A+ defensible: extension test"
H_SUB_APLUS_VCP = "Sub-A+ VCP-not-formed"
H_CAPITAL_BLOCKED = "Capital-blocked: smaller-position test"


@dataclass(frozen=True)
class HypothesisMatch:
    """Output of `match_candidate_to_hypotheses`. One row per (candidate,
    matched-hypothesis) pair. The same candidate may appear in multiple
    matches if it fits multiple ACTIVE hypotheses."""
    hypothesis_id: int
    hypothesis_name: str
    suggested_label_descriptive: str
    # Numeric prioritization hint within a hypothesis. Lower = better
    # (closer-to-pivot, etc.). Currently derived from candidate metrics
    # the matcher already has.
    priority_hint: float
    # Carry the originating candidate forward so the prioritizer can
    # dedupe / reorder without re-running the matcher.
    candidate_ticker: str = ""


@dataclass(frozen=True)
class HypothesisProgressSummary:
    """Slim view of one hypothesis's current sample-progress + tripwire
    status, passed into `prioritize_recommendations` so the function stays
    pure (no DB access). Compute via `compute_hypothesis_progress_breakdown`
    or the lighter `compute_hypothesis_progress` repo helper."""
    hypothesis_id: int
    hypothesis_name: str
    current_sample: int
    target_sample: int
    any_tripwire_fired: bool


@dataclass(frozen=True)
class TripwireStatus:
    """Output of `compute_tripwire_status`. All fields derived from
    closed trades whose `hypothesis_label` matches the hypothesis's
    canonical name (case-insensitive prefix; see
    `_label_matches_hypothesis`).

    `current_sample` counts closed trades only — open trades have no
    realized R-multiple and so cannot contribute to either tripwire.
    `cumulative_loss` is the SUM of realized P&L across matched trades
    (winners reduce, losers add to). The absolute-loss tripwire fires
    only when the sum is negative AND its magnitude crosses the
    threshold (positive cumulative P&L cannot fire a loss tripwire).
    """
    hypothesis_id: int
    current_sample: int
    consecutive_max_loss_streak: int
    cumulative_loss: float
    consecutive_tripwire_fired: bool
    absolute_tripwire_fired: bool
    any_tripwire_fired: bool


@dataclass(frozen=True)
class CandidateRecommendation:
    """One row in the operator-facing prioritized recommendation list.
    Carries enough context that a downstream UI/CLI can pre-fill a
    `swing trade entry --hypothesis "<label>"` command without re-
    invoking the matcher."""
    candidate_ticker: str
    hypothesis_id: int
    hypothesis_name: str
    suggested_label_descriptive: str
    priority_hint: float
    distance_to_target: int
    tripwire_fired: bool


def _non_pass_criterion_names(candidate: Candidate) -> set[str]:
    """Return the set of criterion names whose result is NOT 'pass'.

    Brief §5 watch item: na counts as non-pass (matches `bucket_for`
    which treats na as fail for VCP gating). The matcher inherits that
    semantics so a `na` result on `tightness` does not let an otherwise-
    near-A+ candidate slip through the "extension test" rule.
    """
    return {c.criterion_name for c in candidate.criteria if c.result != "pass"}


def _aplus_baseline_match(candidate: Candidate) -> bool:
    return candidate.bucket == "aplus"


def _near_aplus_extension_match(candidate: Candidate) -> bool:
    """Watch bucket AND non-pass set is exactly {proximity_20ma}."""
    if candidate.bucket != "watch":
        return False
    return _non_pass_criterion_names(candidate) == {"proximity_20ma"}


def _sub_aplus_vcp_not_formed_match(
    candidate: Candidate, doctrine_defensible_set: frozenset[str],
) -> bool:
    """Watch bucket AND (tightness OR vcp_volume_contraction in non-pass)
    AND every non-pass criterion is in (defensible ∪ {tightness, vcp_volume_contraction}).
    """
    if candidate.bucket != "watch":
        return False
    non_pass = _non_pass_criterion_names(candidate)
    triggers = {"tightness", "vcp_volume_contraction"}
    if non_pass & triggers == set():
        return False
    allowed = doctrine_defensible_set | triggers
    return non_pass.issubset(allowed)


def _capital_blocked_match(candidate: Candidate) -> bool:
    """Capital-blocked = "would be A+ except risk_feasibility is the only
    blocker." Since `risk_feasibility` is a hard pre-filter in production
    (`bucket_for` returns 'skip' the moment risk fails), the production-
    realized form of this hypothesis is `bucket == 'skip'` rather than
    `'watch'`. Adversarial review R1 Major 1: the brief's literal rule
    `bucket == 'watch' AND non_pass == {'risk_feasibility'}` is dead-on-
    arrival on production data; we accept matches in either bucket as
    long as the only failing criterion is risk_feasibility.

    Allowing both buckets preserves brief intent ("candidates A+ except
    risk_feasibility") without coupling the matcher to a specific
    production gating order. Replay-harness variants that disable the
    hard filter (and so see these candidates in 'watch') still match.
    """
    if candidate.bucket not in ("watch", "skip"):
        return False
    return _non_pass_criterion_names(candidate) == {"risk_feasibility"}


def _descriptive_label(
    candidate: Candidate, hypothesis_name: str,
) -> str:
    """Build the suggested hypothesis-tag string. Format pinned because
    `compute_tripwire_status` matches by case-insensitive PREFIX on
    `hypothesis_name`; the descriptive suffix may evolve without breaking
    matching, but the leading hypothesis name MUST stay first.

    Bucket annotation rule (R2 Minor 2): for the Capital-blocked
    hypothesis, production gating buckets candidates as `skip` even
    though the operator's intent is to take the trade with smaller
    position. Rendering `(skip)` would read as "rejected" in the
    operator-facing label, which contradicts the recommendation. So we
    annotate it as `(skip; capital-blocked)` to make the deliberate
    nature of the recommendation clear in the saved label.
    """
    non_pass = sorted(_non_pass_criterion_names(candidate))
    if non_pass:
        suffix = f"; failed: {', '.join(non_pass)}"
    else:
        suffix = ""
    if hypothesis_name == H_CAPITAL_BLOCKED and candidate.bucket == "skip":
        bucket_disp = "skip; capital-blocked"
    else:
        bucket_disp = candidate.bucket
    return f"{hypothesis_name} ({bucket_disp}){suffix}"


def _priority_hint_for(candidate: Candidate) -> float:
    """Numeric hint, lower = better (matches sort).

    Use closeness-to-pivot when both close and pivot are present (smaller
    is closer-to-trigger and thus more time-sensitive). Falls back to a
    constant so the prioritizer's tie-break can take over.
    """
    if candidate.close is not None and candidate.pivot:
        return abs(1.0 - candidate.close / candidate.pivot)
    return 1.0


def match_candidate_to_hypotheses(
    candidate: Candidate,
    *,
    doctrine_defensible_set: frozenset[str] = DOCTRINE_DEFENSIBLE_MISS_SET,
    registry: Iterable[HypothesisRegistryEntry],
) -> list[HypothesisMatch]:
    """Return zero-or-more `HypothesisMatch` rows for this candidate.

    Multi-match is allowed: a candidate that fits two ACTIVE hypotheses
    surfaces both. The downstream prioritizer decides which (if any) to
    surface to the operator.
    """
    active_by_name: dict[str, HypothesisRegistryEntry] = {
        h.name: h for h in registry if h.status == "active"
    }
    matches: list[HypothesisMatch] = []

    rules: list[tuple[str, callable]] = [
        (H_APLUS_BASELINE, lambda c: _aplus_baseline_match(c)),
        (H_NEAR_APLUS_EXTENSION, lambda c: _near_aplus_extension_match(c)),
        (H_SUB_APLUS_VCP,
         lambda c: _sub_aplus_vcp_not_formed_match(c, doctrine_defensible_set)),
        (H_CAPITAL_BLOCKED, lambda c: _capital_blocked_match(c)),
    ]

    for name, rule in rules:
        h = active_by_name.get(name)
        if h is None:
            continue
        if not rule(candidate):
            continue
        matches.append(HypothesisMatch(
            hypothesis_id=h.id,
            hypothesis_name=h.name,
            suggested_label_descriptive=_descriptive_label(candidate, h.name),
            priority_hint=_priority_hint_for(candidate),
            candidate_ticker=candidate.ticker,
        ))
    return matches


def prioritize_recommendations(
    matches: Iterable[HypothesisMatch],
    *,
    registry: Iterable[HypothesisRegistryEntry],
    progress: Iterable[HypothesisProgressSummary],
) -> list[CandidateRecommendation]:
    """Rank matches by hypothesis-investigation value, ONE row per ticker.

    Sort key (lower → higher priority):
      1. tripwire_fired (False before True; tripwire-fired hypotheses
         drop to bottom — operator should evaluate before more samples).
      2. -distance_to_target (greater distance → higher priority; we
         negate so smaller key = better).
      3. priority_hint (lower = closer-to-pivot or other within-hypothesis
         signal).
      4. candidate_ticker (alpha, deterministic tie-breaker).

    Per-ticker dedup (brief §8 + adversarial review R1 Major 3): a
    candidate matching multiple hypotheses surfaces ONCE under its
    most-investigation-valuable hypothesis (the same sort key applied
    within the per-ticker group). Operator gets one recommendation per
    name on the dashboard, not duplicates.

    Matches against non-active hypotheses (paused, closed-*) are dropped
    even if the matcher returned them — defense-in-depth so a stale
    in-memory registry can't surface a closed hypothesis to the operator.
    """
    registry_list = list(registry)
    active_by_id = {h.id: h for h in registry_list if h.status == "active"}
    progress_by_id = {p.hypothesis_id: p for p in progress}

    recs: list[CandidateRecommendation] = []
    for m in matches:
        h = active_by_id.get(m.hypothesis_id)
        if h is None:
            continue
        prog = progress_by_id.get(m.hypothesis_id)
        # If progress wasn't supplied for this hypothesis, treat as 0 of
        # target (worst-case "needs samples" — a missing progress entry
        # should never silently demote priority).
        current = prog.current_sample if prog else 0
        tripwire = prog.any_tripwire_fired if prog else False
        distance = max(0, h.target_sample_size - current)
        recs.append(CandidateRecommendation(
            candidate_ticker=m.candidate_ticker,
            hypothesis_id=m.hypothesis_id,
            hypothesis_name=m.hypothesis_name,
            suggested_label_descriptive=m.suggested_label_descriptive,
            priority_hint=m.priority_hint,
            distance_to_target=distance,
            tripwire_fired=tripwire,
        ))

    sort_key = lambda r: (
        r.tripwire_fired,
        -r.distance_to_target,
        r.priority_hint,
        r.candidate_ticker,
    )
    recs.sort(key=sort_key)

    # Per-ticker dedup: keep the first (highest-priority) entry per
    # ticker. Tickers with no ticker (matcher built without
    # candidate_ticker, e.g. older test paths) are kept as-is — the
    # empty-string sentinel doesn't collide with real symbols.
    seen: set[str] = set()
    deduped: list[CandidateRecommendation] = []
    for r in recs:
        if r.candidate_ticker == "":
            deduped.append(r)
            continue
        if r.candidate_ticker in seen:
            continue
        seen.add(r.candidate_ticker)
        deduped.append(r)
    return deduped


def _label_matches_hypothesis(label: str | None, hypothesis_name: str) -> bool:
    """Trade's `hypothesis_label` matches a hypothesis if the label
    STARTS WITH the hypothesis NAME (case-insensitive).

    Adversarial review R1 Major 2: prior implementation used substring
    match, which would silently double-count a label like
    "A+ baseline / Sub-A+ VCP-not-formed combo" toward both hypotheses
    and contaminate tripwire/progress arithmetic. Prefix is strict
    enough to prevent that while still accepting VIR's free-text
    backfill (which begins with "sub-A+ VCP-not-formed ..." matching
    the "Sub-A+ VCP-not-formed" hypothesis after case-folding).

    Operator-facing implication: when free-typing a hypothesis label,
    START with the canonical hypothesis name; descriptive context goes
    AFTER. The recommendation engine's `_descriptive_label` builder
    already follows this convention. NULL labels never match.
    """
    if not label:
        return False
    return label.lower().startswith(hypothesis_name.lower())


def compute_tripwire_status(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: int,
    starting_equity: float,
) -> TripwireStatus:
    """Compute per-hypothesis tripwire signals from closed trades.

    Sample inclusion: a closed trade with non-NULL `hypothesis_label`
    contributes when `_label_matches_hypothesis(label, hypothesis.name)`
    holds.

    Consecutive-max-loss streak: walk matched closed trades by
    (entry_date DESC, id DESC) and count trailing trades whose
    aggregate share-weighted r_multiple is <= -1.0. Stops at the first
    non-loss trade (R > -1).

    Absolute-loss tripwire: cumulative realized P&L across matched
    trades; fires when cumulative_loss <= -starting_equity * pct/100.

    Raises ValueError if `hypothesis_id` is unknown.
    """
    # Local import keeps the module DB-agnostic at import time so the
    # matcher / prioritizer tests don't pull in repo modules.
    from swing.data.repos.hypothesis import get_hypothesis
    from swing.data.repos.trades import list_closed_trades

    h = get_hypothesis(conn, hypothesis_id)
    if h is None:
        raise ValueError(f"hypothesis {hypothesis_id} not found")

    closed = list_closed_trades(conn)
    matched = [
        t for t in closed
        if _label_matches_hypothesis(t.hypothesis_label, h.name)
    ]
    # C.10: migrated off ``list_all_exits`` shim. The local helper sources
    # ExitLike rows from non-entry fills, deriving realized_pnl/r_multiple
    # via swing.trades.derived_metrics.
    exits_by_trade: dict[int, list] = {}
    for e in _list_all_exitshape_via_fills(conn):
        exits_by_trade.setdefault(e.trade_id, []).append(e)

    def _r_for(trade) -> float:
        es = exits_by_trade.get(trade.id, [])
        return sum(e.r_multiple * (e.shares / trade.initial_shares) for e in es)

    def _pnl_for(trade) -> float:
        return sum(e.realized_pnl for e in exits_by_trade.get(trade.id, []))

    cumulative = sum(_pnl_for(t) for t in matched)

    # Walk by entry_date DESC, id DESC — the most recent trade first.
    matched_sorted = sorted(
        matched, key=lambda t: (t.entry_date, t.id or 0), reverse=True,
    )
    streak = 0
    for t in matched_sorted:
        if _r_for(t) <= -1.0:
            streak += 1
        else:
            break

    consec_fired = streak >= h.consecutive_loss_tripwire
    threshold = -starting_equity * (h.absolute_loss_tripwire_pct / 100.0)
    abs_fired = cumulative <= threshold

    return TripwireStatus(
        hypothesis_id=hypothesis_id,
        current_sample=len(matched),
        consecutive_max_loss_streak=streak,
        cumulative_loss=cumulative,
        consecutive_tripwire_fired=consec_fired,
        absolute_tripwire_fired=abs_fired,
        any_tripwire_fired=consec_fired or abs_fired,
    )
