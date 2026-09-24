"""Per-hypothesis-cohort filter + aggregation helper (plan §D Task A.4).

Provides the Phase 10 read-side cohort-grain interface consumed by
Sub-bundles B + C metric computations. The helpers are pure SELECTs —
classification (win/loss/scratch) happens at the per-trade level in
``swing/metrics/process.py`` (Sub-bundle B).

Label canonicalization is via the existing
:func:`swing.trades.entry.canonicalize_hypothesis_label` helper to match
the persistence-boundary form: trades store the canonical label, and
queries by ``hypothesis_label`` use the same canonical form.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection

from swing.data.models import Trade
from swing.data.repos.trades import (
    _CLOSED_STATES_SQL,
    _row_to_trade,
    _trade_select_cols,
)
from swing.metrics.label_match import label_matches_hypothesis_sql
from swing.trades.entry import canonicalize_hypothesis_label

# Per spec §A.16 + plan §I.14: cohort listing for the dashboard.
_HYPOTHESIS_REGISTRY_NAMES_SQL = (
    "SELECT name FROM hypothesis_registry ORDER BY id"
)

def list_trades_for_cohort(
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str | None,
    state_filter: tuple[str, ...] | None = None,
    entry_intent: str | None = None,
    exclude_entry_intents: Collection[str] = (),
) -> list[Trade]:
    """Return trades matching the cohort filter.

    Arguments:
        hypothesis_label: cohort name to filter on; ``None`` returns ALL
          trades (no cohort filter — the "all trades" view).
        state_filter: optional tuple of states to filter on (e.g.,
          ``('closed', 'reviewed')``). When ``None``, no state filter
          applied.
        entry_intent: optional intent-facet predicate (Task 6 / spec §7.1).
          Sentinel convention: ``None`` = no predicate (today's behavior);
          ``'__unclassified__'`` = ``entry_intent IS NULL``; any other
          value = ``entry_intent = ?`` equality.
        exclude_entry_intents: Arc 22-B (N2 (a), E13) -- one
          ``entry_intent IS NOT ?`` clause per value (NULL-safe: a NULL
          intent still counts). Default EMPTY, so the observational callers
          (``metrics/process.py``; ``count_per_cohort`` does not call this)
          stay unfiltered; the governed readers pass
          ``cohort_intent.cohort_excluded_entry_intents(name)``.

    Per plan §A.11.1: include ALL trades labeled with the cohort regardless
    of cohort status (active / paused / closed). Paused intervals do NOT
    cause exclusion (operator-intent-at-entry semantics).

    Phase 13 T-T4.SB.2 (Item 7 Option 7C LOCK): match contract widened from
    exact equality to 3-rule delimiter-aware (exact / space-delimited /
    semicolon-delimited) so per-trade-suffix labels like
    ``"Sub-A+ VCP-not-formed (watch); failed: proximity_20ma"`` are
    correctly attributed to the canonical cohort. See
    :func:`swing.metrics.label_match.label_matches_hypothesis_sql`.
    """
    canonical = (
        canonicalize_hypothesis_label(hypothesis_label)
        if hypothesis_label is not None
        else None
    )
    where_clauses: list[str] = []
    params: list[object] = []
    if canonical is not None:
        fragment, fragment_params = label_matches_hypothesis_sql(canonical)
        where_clauses.append(fragment)
        params.extend(fragment_params)
    if state_filter:
        placeholders = ",".join("?" for _ in state_filter)
        where_clauses.append(f"state IN ({placeholders})")
        params.extend(state_filter)
    if entry_intent is not None:
        if entry_intent == "__unclassified__":
            where_clauses.append("entry_intent IS NULL")
        else:
            where_clauses.append("entry_intent = ?")
            params.append(entry_intent)
    for excluded in exclude_entry_intents:
        where_clauses.append("entry_intent IS NOT ?")
        params.append(excluded)

    cols = _trade_select_cols(conn)
    sql = f"SELECT {cols} FROM trades"  # noqa: S608
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY entry_date, ticker, id"

    rows = conn.execute(sql, params).fetchall()
    trades = [_row_to_trade(r) for r in rows]
    # 20-A B-2 — exclude voided (phantom/test) trades from cohort stats (the
    # tuition 16->15 restatement). Audit/trade-detail surfaces use the base
    # repos + get_trade, which stay voided-visible (D19).
    from swing.trades.voided_trades import voided_trade_ids
    voided = voided_trade_ids(conn)
    if voided:
        trades = [t for t in trades if t.id not in voided]
    return trades


def list_closed_trades_for_cohort(
    conn: sqlite3.Connection, *, hypothesis_label: str | None,
    entry_intent: str | None = None,
    exclude_entry_intents: Collection[str] = (),
) -> list[Trade]:
    """Return trades in 'closed' or 'reviewed' state for the cohort.

    Convenience wrapper over :func:`list_trades_for_cohort` with the
    closed-state tuple pre-filled. ``entry_intent`` threads the Task 6
    intent-facet predicate (see :func:`list_trades_for_cohort`).
    """
    return list_trades_for_cohort(
        conn,
        hypothesis_label=hypothesis_label,
        state_filter=("closed", "reviewed"),
        entry_intent=entry_intent,
        exclude_entry_intents=exclude_entry_intents,
    )


def list_intent_excluded_for_cohort(
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str,
    state_filter: tuple[str, ...] | None,
) -> tuple[tuple[int, str], ...]:
    """The cohort's label-matched trades clause (4) removes, NAMED
    ``(trade_id, reason)`` in id order (Arc 22-B, N3 (a) + RD's plan read).

    The same label match as :func:`list_trades_for_cohort`, voided trades
    excluded, ``entry_intent IN CONTRACT_EXCLUDED_ENTRY_INTENTS``. ONE
    ``LEFT JOIN entry_intent_attestations``: ``reason`` carries the
    ``UNATTESTED`` token when no evidence row exists for the trade -- the
    production detector for a value the schema could not see written (a
    fabricated or pre-trigger raw write). Declared residual: an unattested
    row with a NULL label matches no cohort and is unnamed here; it was in
    no cohort, so no count moved. ``state_filter`` of ``None`` applies no
    state predicate (a caller counting from its own loaded trade lists
    intersects the result with them).
    """
    from swing.metrics.cohort_intent import (
        CONTRACT_EXCLUDED_ENTRY_INTENTS,
        intent_exclusion_reason,
    )
    from swing.trades.voided_trades import voided_trade_ids

    if state_filter is not None and not state_filter:
        return ()  # an empty IN () is invalid SQL
    fragment, params = label_matches_hypothesis_sql(
        canonicalize_hypothesis_label(hypothesis_label))
    states = (f"AND t.state IN ({','.join('?' for _ in state_filter)}) "
              if state_filter else "")
    intents = ",".join("?" for _ in CONTRACT_EXCLUDED_ENTRY_INTENTS)
    rows = conn.execute(
        "SELECT t.id, t.entry_intent, a.attestation_id IS NOT NULL "
        "FROM trades t "
        "LEFT JOIN entry_intent_attestations a ON a.trade_id = t.id "
        f"WHERE {fragment} {states}"
        f"AND t.entry_intent IN ({intents}) "
        "ORDER BY t.id",  # noqa: S608
        [*params, *(state_filter or ()), *CONTRACT_EXCLUDED_ENTRY_INTENTS],
    ).fetchall()
    voided = voided_trade_ids(conn)
    # RD's constraint (ii) (R1-3), met by construction: the name AND the
    # UNATTESTED token come from this ONE statement, so they cannot disagree
    # with each other. The asymmetry, stated: attestations are append-only
    # (0040 trg_eia_no_delete / trg_eia_no_replace / trg_eia_no_update), so
    # "absent" can only ever become "present" -- a token read a moment early
    # is a FALSE ALARM on a row attested since, never a false all-clear.
    return tuple(
        (int(tid), intent_exclusion_reason(intent, attested=bool(attested)))
        for tid, intent, attested in rows if tid not in voided)


COHORT_READ_RACED_MESSAGE = "cohort read raced an intent write; re-run"


class CohortReadRacedError(ValueError):
    """One governed cohort render would COUNT a trade and NAME it "not
    counted" -- a write landed between the reader's counted read and its
    naming read (Arc 22-B R1-3). Every surface renders it as its refusal
    (the CLI as a ``ClickException``); never the contradictory row, never a
    partial row. A re-run reads clean."""

    def __init__(self, trade_ids: tuple[int, ...]) -> None:
        super().__init__(COHORT_READ_RACED_MESSAGE)
        self.trade_ids = trade_ids


def assert_intent_exclusion_disjoint(
    counted_ids: Collection[int | None],
    named: Collection[tuple[int, str]],
) -> None:
    """RD's constraint (i) at the render (R1-3; CHARC RULING
    R1-3-SHAPE-EXEC): raise :class:`CohortReadRacedError` when a trade this
    render COUNTS is also among the ``(trade_id, reason)`` pairs it NAMES
    "not counted" (the :func:`list_intent_excluded_for_cohort` result).
    Every governed decision reader calls this AFTER its naming read and
    BEFORE it populates ``intent_excluded``.

    WHY THE ASSERT ALONE IS SUFFICIENT (not merely cheaper). The counted
    predicate and the naming predicate differ ONLY in the intent test (the
    same label match, states and voided exclusion), so the intersection is
    reachable ONLY by an intent value moving between the two reads. That
    move is MONOTONE, counted -> excluded, never back:
    ``unintended_execution`` is terminal on UPDATE
    (0040 ``trg_trades_entry_intent_attested_terminal``), unwritable without
    its attestation row (``trg_trades_entry_intent_unattested_update`` /
    ``trg_trades_entry_intent_unattested_insert``), and the attestation
    table is append-only (``trg_eia_no_delete``, ``trg_eia_no_replace``;
    ``trg_eia_no_update`` passes only the fill-id null-out). So every
    interleaving is one of three: the write lands BEFORE the counted read
    -> excluded AND named, consistent; AFTER the naming read -> counted and
    NOT named, consistent (it was not excluded when read); BETWEEN the reads
    -> counted AND named, exactly the intersection this detects. There is
    no fourth state.

    PRECONDITION, NAMED: any future writer that moves a trade from excluded
    back to counted -- a reversal surface, which N4 says does not exist
    today -- invalidates this argument; the arc that builds one re-opens
    FORK R1-3-SHAPE-EXEC and re-rules it.

    No transaction brackets the two reads, deliberately: every governed
    reader runs the tier-2 replay between them, and the replay refuses
    under a caller-held transaction (``frozen_value_evidence.py``'s
    ``REASON_CALLER_HOLDS_TRANSACTION`` guard), so a bracket would turn every
    admitted tier-2 trade into a false exclusion. The cost, stated: a live
    race yields a typed re-run refusal instead of a silently consistent read.
    """
    counted = {int(t) for t in counted_ids if t is not None}
    raced = tuple(sorted(counted & {int(tid) for tid, _reason in named}))
    if raced:
        raise CohortReadRacedError(raced)


def count_per_cohort(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{cohort_name: closed_trade_count}`` for ALL ``hypothesis_registry``
    rows, aggregating per the 3-rule delimiter-aware match contract plus
    an orphan-preservation second query.

    Per plan §A.16 empty-cohort discipline: cohorts with zero closed trades
    are INCLUDED with value 0 (NOT omitted). This is what the dashboard
    needs to render every cohort tab even at our current n<5 state.

    Phase 13 T-T4.SB.2 (Item 7) widens the per-cohort count from exact
    equality GROUP BY to delimiter-aware match per registered hypothesis
    via :func:`swing.metrics.label_match.label_matches_hypothesis_sql`.
    A SECOND query (orphan-fallback) selects closed trades with non-NULL
    ``hypothesis_label`` that match NONE of the registered hypotheses --
    those labels surface as their own entries in the returned dict so
    operator can see an "(unregistered cohort)" placeholder. Closes
    Expansion #10 sub-discipline (e) ORPHAN-PRESERVATION-WHEN-REFACTORING
    LOCK.

    D29 -- DELIBERATELY carries NO intent-facet predicate, unlike the four
    hypothesis-PROGRESS readers. This helper feeds the trade-process card's
    cohort TABS: an OBSERVATIONAL navigation count over every labeled trade,
    including orphan labels, which match no registered hypothesis and are
    therefore governed by neither cohort authority
    (``cohort_intent.INTENT_AUTHORITY_NONE``). Filtering it would hide
    trades from the very tab that lists them, and the process card already
    exposes intent as an
    operator-selected facet (``swing/metrics/process.py``, spec §7.1). The
    governance predicate lives in ``swing/metrics/cohort_intent.py`` and is
    applied by the progress readers only.
    """
    cohort_counts: dict[str, int] = {}
    registered_names: list[str] = []
    for (name,) in conn.execute(_HYPOTHESIS_REGISTRY_NAMES_SQL):
        registered_names.append(name)
        cohort_counts[name] = 0

    # 20-A B-2 — exclude voided (phantom/test) trades from cohort counts. The
    # ids are DB-sourced ints, so inlining an ``id NOT IN (...)`` fragment is
    # injection-safe (no list-binding of a single placeholder).
    from swing.trades.voided_trades import voided_trade_ids
    voided = voided_trade_ids(conn)
    voided_excl = (
        f" AND id NOT IN ({','.join(str(int(v)) for v in sorted(voided))})"
        if voided else ""
    )

    # Per-cohort count via the shared SQL helper.
    for name in registered_names:
        fragment, params = label_matches_hypothesis_sql(name)
        sql = (
            "SELECT COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            "  AND hypothesis_label IS NOT NULL "
            f"  AND {fragment}{voided_excl}"
        )  # noqa: S608
        (count,) = conn.execute(sql, params).fetchone()
        cohort_counts[name] = int(count)

    # Orphan-label preservation: a SECOND query selects closed trades with
    # ``hypothesis_label`` NOT NULL that match NONE of the registered
    # hypotheses (Codex R4 M#1 LOCK; Expansion #10 sub-discipline (e)).
    if registered_names:
        not_clauses: list[str] = []
        not_params: list[object] = []
        for name in registered_names:
            fragment, params = label_matches_hypothesis_sql(name)
            not_clauses.append(f"NOT {fragment}")
            not_params.extend(params)
        orphan_sql = (
            "SELECT hypothesis_label, COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            "  AND hypothesis_label IS NOT NULL "
            f"  AND {' AND '.join(not_clauses)}{voided_excl} "
            "GROUP BY hypothesis_label"
        )  # noqa: S608
        for label, count in conn.execute(orphan_sql, not_params):
            cohort_counts[label] = int(count)
    else:
        # Empty-registry defensive branch (production seeds registry rows
        # via migration 0008; this covers test DBs / future startup
        # transient states). EVERY non-NULL label is an orphan; surface
        # raw labels per orphan contract.
        orphan_sql_empty = (
            "SELECT hypothesis_label, COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            f"  AND hypothesis_label IS NOT NULL{voided_excl} "
            "GROUP BY hypothesis_label"
        )  # noqa: S608
        for label, count in conn.execute(orphan_sql_empty):
            cohort_counts[label] = int(count)
    return cohort_counts


# ---------------------------------------------------------------------------
# T-C.5 elective — per-cohort discrepancy filter
# ---------------------------------------------------------------------------

def filter_trades_without_unresolved_material_discrepancies(
    conn: sqlite3.Connection, trades: list[Trade],
) -> list[Trade]:
    """Return the subset of trades that have ZERO unresolved material
    reconciliation discrepancies.

    Per electives amendment §2 Task C.5 acceptance (with the helper's
    intent — the amendment text uses "resolution IS NULL" loosely; the
    Phase 9 schema actually stores ``resolution`` as NOT NULL with the
    sentinel value ``'unresolved'`` as the default):

    - INCLUDE trades with no discrepancy rows.
    - INCLUDE trades whose discrepancies are ALL resolved
      (``resolution != 'unresolved'`` — i.e. one of
      ``'journal_corrected'`` / ``'source_treated_canonical'`` /
      ``'manual_override'`` / ``'acknowledged_immaterial'``).
    - INCLUDE trades whose discrepancies are non-material
      (``material_to_review = 0``).
    - EXCLUDE trades with at least one discrepancy row where
      ``material_to_review = 1 AND resolution = 'unresolved'``.

    Mirrors :func:`swing.data.repos.reconciliation.list_unresolved_material_for_active_trades`
    semantics so the global banner count + this per-cohort filter agree
    on which discrepancies count as "unresolved + material".

    Single-query: SELECT DISTINCT trade_id FROM reconciliation_discrepancies
    WHERE material_to_review=1 AND resolution='unresolved' AND trade_id
    IS NOT NULL; exclude those ``trade_id``s from the input list.

    Orphan-emit discrepancies (``trade_id IS NULL`` — sector_tamper /
    equity_delta / cash_movement_mismatch without a trade attribution per
    Phase 9 Sub-bundle B) do NOT affect this filter (they cannot exclude
    a specific trade). Codex R1 Minor #1 follow-up: they are ALSO excluded
    from the global ``unresolved_material_discrepancies_count`` banner
    today — :func:`swing.metrics.discrepancies.count_unresolved_material`
    JOINs on ``trades.id`` per the V1 SCOPE LIMITATION documented in
    ``swing/metrics/discrepancies.py`` (banked V2 candidate: include
    orphan discrepancies via a separate sub-query). The filter helper's
    behavior here remains correct in isolation (filtering trades), and
    no banner/filter divergence exists at V1 because both consume the
    "trade-attributed only" subset.
    """
    if not trades:
        return list(trades)
    rows = conn.execute(
        "SELECT DISTINCT trade_id FROM reconciliation_discrepancies "
        "WHERE material_to_review = 1 "
        "  AND resolution = 'unresolved' "
        "  AND trade_id IS NOT NULL",
    ).fetchall()
    excluded_ids = {int(r[0]) for r in rows}
    return [t for t in trades if t.id not in excluded_ids]
