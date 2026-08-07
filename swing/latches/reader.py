"""The IMPURE adapter feeding the pure latch derivation.

Read-only by construction: SELECTs plus an on-disk parquet read. ZERO network
I/O (`resolve_ohlcv_window` is a two-provider parquet read -- the same reader
the pipeline observe step uses), ZERO writes (the archive read opts OUT of the
resolver's legacy migration via `migrate=False`; see `load_bars`), ZERO
transaction management.

Every boundary degrades rather than raises (condition A6): a missing archive,
a malformed TEXT date, an absent `pipeline_runs` twin. In particular NULL-TWIN
TOLERANCE IS THE NORMAL CASE, not an exception (plan A.8) -- the latch corpus
begins 2026-04-20 and the detection corpus begins 2026-06-05, so five of the
eleven A+ fires ever have no `pipeline_runs` link and never will.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import date, datetime

from swing.evaluation.dates import (
    action_session_for_run,
    is_trading_session,
    session_offset,
)
from swing.evaluation.scoring import (
    EXPECTED_TT_CRITERIA,
    EXPECTED_VCP_CRITERIA,
    StructuralInputs,
    structural_gate_passes,
)
from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    ARCHIVE_STATUS_UNAVAILABLE,
    DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR,
    DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT,
    DEFAULT_CRITERIA_LAPSE_SESSIONS,
    latch_horizon_sessions,
)
from swing.latches.models import (
    VERDICT_FAILED,
    VERDICT_PASSED,
    VERDICT_UNVERIFIABLE,
    DailyBar,
    EntryRecord,
    FireRow,
    LatchDerivation,
    SessionStructuralVerdict,
)
from swing.latches.service import derive_latches

log = logging.getLogger(__name__)

# ALL A+ fires are loaded (11 rows ever). A truncated read would break the
# re-confirmation chain and could fabricate a second latch for one mandate; the
# DISPLAY lookback is applied in the view model instead.
_FIRE_SQL = """
    SELECT c.id, c.evaluation_run_id, c.ticker, c.pivot, c.initial_stop,
           e.action_session_date, e.run_ts, p.id, c.adr_pct
    FROM candidates c
    JOIN evaluation_runs e ON e.id = c.evaluation_run_id
    LEFT JOIN pipeline_runs p ON p.evaluation_run_id = e.id
    WHERE c.bucket = 'aplus'
    ORDER BY c.ticker, e.action_session_date, e.run_ts, c.id
"""


def load_fire_rows(conn: sqlite3.Connection) -> tuple[FireRow, ...]:
    """Every `bucket='aplus'` candidates row, with BOTH id spaces attached.

    The `LEFT JOIN pipeline_runs` is verified 1:1 (`GROUP BY evaluation_run_id
    HAVING COUNT(*) > 1` returns zero rows) and legitimately NULL for the
    pre-June-2026 fires.

    A malformed row is NOT dropped here: `derive_latches` owns the degradation
    so the operator SEES that a fire existed and why it produced no latch.
    """
    out: list[FireRow] = []
    for row in conn.execute(_FIRE_SQL).fetchall():
        try:
            out.append(FireRow(
                candidate_id=int(row[0]),
                evaluation_run_id=int(row[1]),
                ticker=str(row[2]),
                # RAW, NOT coerced. SQLite is dynamically typed: a REAL column
                # happily holds the TEXT 'bad', and an eager float() here would
                # raise and DROP the whole fire -- contradicting this function's
                # contract and A6. `_validate_fire` rejects it as
                # `pivot_missing` / `stop_missing`, so the operator SEES that a
                # fire existed and why it produced no latch.
                pivot=row[3],
                initial_stop=row[4],
                action_session_date="" if row[5] is None else str(row[5]),
                run_ts="" if row[6] is None else str(row[6]),
                pipeline_run_id=None if row[7] is None else int(row[7]),
                # RAW for the same reason as `pivot`/`initial_stop` above: an
                # eager float() would raise on a TEXT-in-REAL value and drop
                # the whole fire.
                adr_pct=row[8],
            ))
        except (TypeError, ValueError) as exc:
            # Only a STRUCTURALLY impossible row lands here (a non-int id, a
            # blank ticker). It cannot be represented at all, so it is logged
            # rather than rendered.
            log.warning("latch reader: skipping unrepresentable aplus row %r: %s",
                        row[0], exc)
    return tuple(out)


def load_entry_records(conn: sqlite3.Connection, tickers) -> dict[str, list[EntryRecord]]:
    """Entries for `tickers`, keyed by ticker.

    Short-circuits the empty set: an empty `IN ()` is invalid SQL (the
    dynamic-placeholder gotcha).
    """
    values = sorted({str(t) for t in (tickers or ())})
    if not values:
        return {}
    placeholders = ",".join("?" * len(values))
    # VOIDED trades are EXCLUDED via the single-source predicate
    # (`swing/trades/voided_trades.py`, the 20-A B-2 canonical subquery, already
    # consumed by every cohort/stat/equity reader). A voided trade is a PHANTOM
    # that never executed at the broker -- the D25 SATL trade-11 case -- and it
    # is never deleted, only annotated. Letting one through here would mark a
    # latch `filled`, silencing the very no-resting-order alarm this arc exists
    # to raise, for a fire the operator never actually acted on. This is a
    # read-only IMPORT of a shared predicate, not a `swing/trades` edit.
    from swing.trades.voided_trades import voided_exclusion_sql
    rows = conn.execute(
        "SELECT id, ticker, entry_date, candidate_id, entry_price, initial_shares "
        f"FROM trades WHERE ticker IN ({placeholders})"
        f"{voided_exclusion_sql('id')} ORDER BY entry_date, id",
        values,
    ).fetchall()
    out: dict[str, list[EntryRecord]] = {}
    for row in rows:
        try:
            # The TEXT-column -> Python-date boundary, converted at the
            # callsite. A malformed row is SKIPPED: it must never be allowed to
            # clear a latch, and it must never crash the panel.
            entry_date = date.fromisoformat(str(row[2]))
            if not is_trading_session(entry_date):
                # LOGGED, NOT DROPPED (a deliberate asymmetry with bars). A
                # trade is ground truth about a REAL position; refusing to see
                # it because its date is a non-session would leave the mandate
                # armed for a position the operator actually holds and tell him
                # to place an order he does not need. The anomaly is surfaced
                # without discarding the fact.
                log.warning(
                    "latch reader: trade %r has a non-session entry_date %s",
                    row[0], entry_date.isoformat())
            rec = EntryRecord(
                trade_id=int(row[0]),
                ticker=str(row[1]),
                entry_date=entry_date,
                candidate_id=None if row[3] is None else int(row[3]),
                # NON-FATAL. `entry_price REAL NOT NULL` / `initial_shares
                # INTEGER NOT NULL` are AFFINITY declarations, not type CHECKs,
                # so SQLite will hold the TEXT 'bad' in either. Coercing them
                # as row-fatal would DROP an authoritative `candidate_id`-linked
                # fill and leave the mandate `armed` -- telling the operator to
                # place an order for a position he already holds. Degrading to
                # None instead composes correctly: the EXACT rung still
                # recognises the fill, and the WINDOWED rung refuses an
                # unverifiable price by design.
                entry_price=_optional_float(row[4], row[0], "entry_price"),
                shares=_optional_float(row[5], row[0], "initial_shares"),
            )
        except (TypeError, ValueError) as exc:
            log.warning("latch reader: skipping trade %r with a malformed row: %s",
                        row[0], exc)
            continue
        out.setdefault(rec.ticker, []).append(rec)
    return out


def load_decision_intents(conn: sqlite3.Connection, candidate_ids) -> dict:
    """The operator's `place`/`decline` ledger, keyed by CANDIDATE ID.

    THE WHOLE DECISION FAMILY, NOT JUST THE DECLINES. `governing_decision`
    resolves `place` and `decline` together because they are the two mutually
    exclusive answers to ONE question; loading declines alone would re-create the
    exact defect the design exists to prevent -- `decline(D5)` then `place(D6)`
    would terminate the mandate, because the correcting place was filtered out
    before the resolver could ever see it.

    KEYED BY CANDIDATE ID, NOT BY TICKER. A ticker carries many historical
    latches, and a ticker-keyed map hands an old mandate's decline to a newer
    latch. The pure fold applies the per-latch candidate-family rule.

    A6 AT THE SEAM, AND THE DEGRADATION IS ALL-OR-NOTHING ON PURPOSE. Any
    failure -- a missing 0033 table on an older DB, or a single row whose
    `_row_to_model` hydration raises -- yields `{}` for the WHOLE read.

    PARTIAL EVIDENCE IS WORSE THAN NONE HERE, and a per-candidate skip is not the
    conservative choice it looks like. `governing_decision` resolves ONE family
    spanning several candidate ids by RECENCY, so dropping part of it is
    NON-MONOTONIC: with a `decline(D5)` on the opening fire and the correcting
    `place(D6)` on a re-confirmation, skipping just the re-confirmation leaves the
    decline standing alone and CLEARS a latch that must stay live -- silencing the
    armed-latch alarm on evidence the reader could not read.

    The reader cannot tell which candidates share a family (the fold computes
    that), so it cannot degrade per-family -- which is precisely why it degrades
    globally instead.

    WHAT THE DEGRADED STATE ACTUALLY IS, stated exactly (Codex R3). It is the
    PRE-ITEM-3A DERIVATION -- the shipped behaviour of the whole of Phase 21, in
    which no decline terminated anything. It is NOT merely "the same latches,
    still alive", and an earlier draft of this docstring claimed exactly that,
    which overstated it: decisions participate in the fold's TOPOLOGY, so a
    decline that would have closed a predecessor before a later SAME-PIVOT fire
    goes unseen, and that fire folds in as a re-confirmation instead of opening
    its own latch -- ONE merged latch carrying the PREDECESSOR's anchor, horizon
    and frozen stop, where the un-degraded fold produces two.

    AND NEITHER DEGRADATION DIRECTION IS UNIVERSALLY SAFE (Codex R4). Skipping
    ONE candidate can CLEAR a latch that must stay live (the correcting `place`
    goes missing). Dropping ALL of them can LOSE a live successor: a decline that
    would have closed a predecessor before a later same-pivot fire goes unseen,
    that fire folds in as a re-confirmation, and the merged latch expires on the
    PREDECESSOR's horizon -- so no live mandate exists where one should, and the
    armed-latch alarm goes quiet. Any claim that one direction is simply "the
    conservative one" is false, and two earlier drafts of this docstring made it.

    ALL-OR-NOTHING IS CHOSEN ON A DIFFERENT GROUND, and it is the honest one:
    with no decision evidence the decline is not merely unproven but UNKNOWABLE,
    so there is no correct answer to compute -- and this reproduces EXACTLY the
    derivation that shipped for the whole of the previous phase, which is the one
    behaviour already understood and already witnessed. A per-candidate skip has
    no such grounding: it invents a THIRD topology matching neither the true one
    nor any that ever shipped.

    THE TRIGGER IS ITSELF THE THING TO FIX. This path needs a missing
    `latch_order_intents` table or a row that fails the dataclass validator it
    was written through -- a corrupt or pre-0033 ledger. The WARNING names the
    candidate so the corruption is repairable rather than silently absorbed.
    """
    ids = sorted({int(c) for c in (candidate_ids or ())})
    if not ids:
        return {}
    try:
        from swing.data.repos.latch_order_intents import list_intents_for_latch
    except Exception as exc:  # noqa: BLE001 -- A6
        log.warning("latch reader: decision-intent repo unavailable: %s", exc)
        return {}
    out: dict[int, tuple] = {}
    for candidate_id in ids:
        try:
            rows = list_intents_for_latch(conn, candidate_id=candidate_id)
        except Exception as exc:  # noqa: BLE001 -- A6
            log.warning(
                "latch reader: decision-intent read degraded at candidate %s, "
                "so NO decision evidence is reported for this derivation "
                "(partial evidence could clear a latch that must stay live): %s",
                candidate_id, exc)
            return {}
        family = tuple(r for r in rows if r.intent_kind in ("place", "decline"))
        if family:
            out[candidate_id] = family
    return out


def structural_inputs_from_rows(
    rows, *, bucket: str | None = None,
) -> tuple[StructuralInputs | None, str | None]:
    """Reduce one candidate's `candidate_criteria` rows for the A+ gate.

    `bucket` is that candidate's `candidates.bucket` and it decides ONLY what an
    EMPTY roster is CALLED (Codex R2). `excluded`/`error` are the evaluator's
    synthesised sentinels and carry `criteria=()` by construction; every other
    bucket was actually scored, so an empty roster there is an INCOMPLETE one.
    Both are UNVERIFIABLE and neither moves a mandate -- but the cause is
    OPERATOR-VISIBLE on the card, so mislabelling it puts a false sentence on
    the panel. `None` keeps the conservative sentinel label for the pure-helper
    callers; PRODUCTION ALWAYS PASSES IT, pinned by a loader test, because a
    default that diverges from production is its own gotcha.

    Returns `(inputs, cause)` -- exactly one of which is populated. The plan
    specified `StructuralInputs | None`; the CAUSE is returned alongside it
    because the card's detail line has to explain an UNVERIFIABLE session by
    cause, and deriving that anywhere else would be a SECOND roster check.

    `rows` are `(criterion_name, layer, result)` triples.

    THE ROSTER IS VALIDATED EXPLICITLY BECAUSE THE SCHEMA DOES NOT. The PK is
    `(candidate_id, criterion_name)` and each ROW's `layer`/`result` is
    CHECK-constrained, but NO constraint requires the roster to be COMPLETE --
    a candidate carrying three vcp rows is representable. That matters in both
    directions:

      * a missing vcp FAILURE yields `vcp_fail_count == 0` and a false PASS;
      * missing TT PASSES drop the count below `min_passes` and yield a false
        FAILURE -- and a false failure, paired with the price conjunct, can
        clear a LIVE mandate.

    So an incomplete or unexpected roster returns UNVERIFIABLE, which never
    clears anything. Grounded rather than defensive: all 11,951 evaluated rows
    on the live DB carry one identical 18-criterion roster, so this fires only
    on genuinely malformed data.

    THE RISK LAYER IS DROPPED HERE (L4) -- `risk_feasibility` is a fact about
    the operator's capital, not about the setup's structure.
    """
    tt_names: dict[str, str] = {}
    vcp_names: dict[str, str] = {}
    saw_any = False
    for row in rows or ():
        saw_any = True
        name, layer, result = str(row[0]), str(row[1]), str(row[2])
        if result not in ("pass", "fail", "na"):
            return None, "malformed_result"
        if layer == "trend_template":
            tt_names[name] = result
        elif layer == "vcp":
            vcp_names[name] = result
        # `risk` is deliberately ignored, not counted.
    if not saw_any:
        # An `excluded` (held-position) or `error` sentinel: the evaluator
        # synthesises those with `criteria=()`, so zero rows means the ticker
        # was never structurally evaluated. NOT a failure -- counting it as one
        # would let the framework withdraw a mandate BECAUSE the operator acted
        # on it.
        #
        # A SCORED bucket with no rows is a different fact and gets a different
        # name: the roster is INCOMPLETE, not absent by design.
        if bucket is not None and bucket not in ("excluded", "error"):
            return None, "incomplete_roster"
        return None, "sentinel_row"
    if (set(tt_names) != EXPECTED_TT_CRITERIA
            or set(vcp_names) != EXPECTED_VCP_CRITERIA):
        return None, "incomplete_roster"
    return StructuralInputs(
        # `na` IS A NON-PASS ON BOTH LAYERS, and the TT half is the one a
        # reader forgets: the shipped gate counts `tt_passes` as `result ==
        # "pass"`, so `na` reduces it, while `vcp_fail_count` counts `fail` AND
        # `na`. An adapter treating TT `na` as neutral can falsely PASS.
        tt_pass_count=sum(1 for r in tt_names.values() if r == "pass"),
        tt_failed_names=tuple(
            sorted(n for n, r in tt_names.items() if r != "pass")),
        vcp_fail_count=sum(
            1 for r in vcp_names.values() if r in ("fail", "na")),
    ), None


def load_session_structural_verdicts(
    conn: sqlite3.Connection, cfg, *, tickers, start: date, end: date,
) -> dict[str, tuple[SessionStructuralVerdict, ...]]:
    """Per TICKER, one verdict per EVALUATED action session in `[start, end]`.

    PER-TICKER, NOT PER-LATCH, on purpose: two latches on one ticker with
    different anchors slice the SAME sequence by their own windows, so this
    reader never needs to know about anchors and cannot disagree with itself
    between two latches.

    THE DOMAIN IS EVALUATED SESSIONS, NOT CALENDAR SESSIONS, and the live
    cadence proves the distinction is real (there is no evaluation run for
    2026-08-05 at all). A trading session with NO run is OUTSIDE the domain
    entirely -- the framework was not running, which is a fact about the
    pipeline, not about the setup. A session WITH a run but no verifiable
    verdict for this ticker IS in the domain and IS unverifiable.

    THE TWO PREDICATES ARE DELIBERATELY ASYMMETRIC, and the asymmetry is the
    whole point. A session can carry several runs -- an ad-hoc `swing eval`
    after the nightly, or a run in which the ticker went off-screen. Both
    obvious tie-breaks are unsafe in one direction:

      * "the latest ROW wins" -- a later SENTINEL erases an earlier real PASS,
        so the streak fails to reset and the latch moves toward a clear on the
        strength of a run that never looked at it;
      * "the latest VERIFIABLE row wins" -- a FAILED verdict survives a later
        run that could NOT check the ticker, which is asserting from evidence
        the most recent word contradicts.

    So the rule is split by which direction each answer moves the latch:

      PASSED  -- generous. ANY verifiable pass in the session RESETS the
                 streak, because resetting keeps a mandate ALIVE and a live
                 mandate is the conservative outcome.
      FAILED  -- strict. The LATEST RUN for that session must itself carry a
                 verifiable FAILING row, because incrementing moves the latch
                 toward withdrawal, and withdrawal is what can destroy a trade.
      anything else -- UNVERIFIABLE.

    AND THE STRICT HALF KEYS ON THE LATEST *RUN*, NOT THE LATEST *ROW*. When a
    09:00 run records a verifiable failure and an 18:00 run does not carry the
    ticker AT ALL, the latest ROW belonging to the ticker is still the 09:00
    failure -- so a row-keyed rule calls the session FAILED though the most
    recent run never checked it. That is the ordinary off-screen case, not an
    edge case.

    RUNS ARE ORDERED BY `(run_ts, evaluation_run_id)`, never by
    `(run_ts, candidate_id)`: the strict half asks which RUN was latest even
    when that run has NO row for this ticker, and such a run has no candidate
    id with which to break a `run_ts` tie.

    PASSED AND FAILED OVERLAP -- a session with an earlier verified PASS and a
    later verified FAIL satisfies both -- so the precedence is STATED rather
    than left to the order the rules happen to be written in. PASSED WINS
    (OQ-15: ambiguity must never advance a withdrawal), and the conflict is
    recorded on the verdict rather than silently absorbed.
    """
    values = sorted({str(t) for t in (tickers or ())})
    if not values:
        # The empty `IN ()` gotcha, and the shipped `load_entry_records` /
        # `load_last_closes` convention.
        return {}
    runs = conn.execute(
        "SELECT id, action_session_date, run_ts FROM evaluation_runs "
        "WHERE action_session_date >= ? AND action_session_date <= ? "
        "ORDER BY action_session_date, run_ts, id",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    if not runs:
        return {}
    # session -> the run ids that produced it, in (run_ts, id) order.
    by_session: dict[date, list[int]] = {}
    # Sessions whose run ORDER cannot be established (Codex R6). `run_ts` is
    # unconstrained TEXT and the SQL orders it LEXICALLY, so a malformed stamp
    # sorts after every valid ISO one and would be taken as "the latest run" --
    # letting a stale failing run satisfy the STRICT half from an ordering the
    # data does not support. Recorded, then used to disable the FAILED half only;
    # the generous PASS is untouched, because that direction preserves mandates.
    unorderable: set[date] = set()
    for run_id, action, run_ts in runs:
        try:
            session = date.fromisoformat(str(action))
        except (TypeError, ValueError):
            log.warning(
                "latch reader: evaluation run %r has a malformed "
                "action_session_date %r; it is not an evaluated session",
                run_id, action)
            continue
        # A NON-TRADING EVALUATED SESSION IS A CATEGORY ERROR, NOT A DATUM
        # (Codex R6), and this guard already exists TWICE in this file -- for
        # entry dates and for bars, whose comment says it exactly: "letting one
        # invalidate a mandate would clear it on a day the market never traded".
        # The verdict path was the sibling that never got it. Without it a
        # Saturday-dated run can be failure number N while `_enumerate_sessions`
        # -- which walks TRADING sessions only -- demands no Saturday bar, so the
        # rule withdraws a mandate on a day the market was closed.
        if not is_trading_session(session):
            log.warning(
                "latch reader: evaluation run %r is dated %s, not a trading "
                "session; it is not an evaluated session",
                run_id, session.isoformat())
            continue
        try:
            datetime.fromisoformat(str(run_ts))
        except (TypeError, ValueError):
            unorderable.add(session)
        by_session.setdefault(session, []).append(int(run_id))

    run_ids = [rid for ids in by_session.values() for rid in ids]
    if not run_ids:
        return {}
    # CHUNKED ON *BOTH* DIMENSIONS, like the criteria query below (Codex R1,
    # completed at R2). `run_ids` is UNBOUNDED HISTORICAL DATA -- one entry per
    # evaluation run since the earliest retained A+ fire or archive bar, which
    # the fire loader deliberately never truncates -- so a bare `IN` grows
    # without limit and eventually raises `too many SQL variables`, crashing the
    # READ-ONLY panel for EVERY latch at once rather than degrading one row.
    #
    # R2's correction is the load-bearing half: a chunk bounded on ONE dimension
    # is not bounded. Each run-chunk carried `len(chunk) + len(values)`
    # parameters, and `values` comes from the SAME unbounded fire corpus, so a
    # fixed 500 could still overflow. The budget is therefore taken from the
    # CONNECTION's own limit rather than from a guessed constant -- 999 on old
    # builds, 32766 here -- so the pair always fits by construction.
    try:
        var_limit = int(conn.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER))
    except Exception:            # noqa: BLE001 -- older/odd builds: assume 999
        var_limit = 999
    budget = max(2, var_limit - 1)
    tick_size = max(1, min(len(values), budget // 2))
    run_size = max(1, min(500, budget - tick_size))
    candidate_by_run_ticker: dict[tuple[int, str], int] = {}
    bucket_by_candidate: dict[int, str | None] = {}
    for t_start in range(0, len(values), tick_size):
        tick_chunk = values[t_start:t_start + tick_size]
        tick_ph = ",".join("?" * len(tick_chunk))
        for chunk_start in range(0, len(run_ids), run_size):
            chunk = run_ids[chunk_start:chunk_start + run_size]
            rid_ph = ",".join("?" * len(chunk))
            for row in conn.execute(
                f"SELECT id, evaluation_run_id, ticker, bucket FROM candidates "
                f"WHERE evaluation_run_id IN ({rid_ph}) "
                f"AND ticker IN ({tick_ph})",
                [*chunk, *tick_chunk],
            ).fetchall():
                candidate_by_run_ticker[(int(row[1]), str(row[2]))] = int(row[0])
                # `bucket` decides ONLY what an EMPTY roster is CALLED, and it
                # is loaded HERE because the reducer cannot see it (Codex R2).
                bucket_by_candidate[int(row[0])] = (
                    None if row[3] is None else str(row[3]))
    criteria_by_candidate: dict[int, list[tuple]] = {}
    cids = sorted(candidate_by_run_ticker.values())
    # SIZED FROM THE SAME BUDGET as the query above (Codex R3). This loop kept a
    # hard-coded 500 while its sibling learned to read the connection's limit --
    # an inconsistency the earlier fix INTRODUCED, and one that fails the whole
    # verdict load (and with it the read-only panel) on any connection whose
    # limit is below 500.
    criteria_size = max(1, min(500, budget))
    for chunk_start in range(0, len(cids), criteria_size):
        chunk = cids[chunk_start:chunk_start + criteria_size]
        ph = ",".join("?" * len(chunk))
        for cid, name, layer, result in conn.execute(
            f"SELECT candidate_id, criterion_name, layer, result "
            f"FROM candidate_criteria WHERE candidate_id IN ({ph})", chunk,
        ).fetchall():
            criteria_by_candidate.setdefault(int(cid), []).append(
                (name, layer, result))

    out: dict[str, tuple[SessionStructuralVerdict, ...]] = {}
    for ticker in values:
        verdicts: list[SessionStructuralVerdict] = []
        for session in sorted(by_session):
            run_ids_for_session = by_session[session]
            saw_pass = False
            saw_verified_fail = False
            latest_cause = "absent"
            latest_is_verified_fail = False
            for position, run_id in enumerate(run_ids_for_session):
                is_latest = position == len(run_ids_for_session) - 1
                cid = candidate_by_run_ticker.get((run_id, ticker))
                if cid is None:
                    if is_latest:
                        latest_cause = "absent"
                    continue
                inputs, cause = structural_inputs_from_rows(
                    criteria_by_candidate.get(cid, ()),
                    bucket=bucket_by_candidate.get(cid))
                if inputs is None:
                    if is_latest:
                        latest_cause = cause or "sentinel_row"
                    continue
                if structural_gate_passes(inputs, cfg):
                    saw_pass = True
                    if is_latest:
                        latest_is_verified_fail = False
                else:
                    saw_verified_fail = True
                    # The STRICT half needs to know which run was LATEST. When a
                    # malformed `run_ts` makes that unestablishable the answer is
                    # UNVERIFIABLE, never FAILED (Codex R6).
                    if is_latest and session not in unorderable:
                        latest_is_verified_fail = True
                    elif is_latest:
                        # NAME THE REAL CAUSE (Codex R7). Leaving the default
                        # `absent` here makes the card say OFF SCREEN about a
                        # ticker that WAS on screen and WAS evaluated -- only the
                        # run ordering was unusable.
                        latest_cause = "unorderable_run_ts"
            # THE CONFLICT IS A DATA-QUALITY SIGNAL (OQ-15): two runs for one
            # session disagreeing on the STRUCTURAL verdict is a fact about the
            # pipeline. It is recorded here and resolved generously below --
            # never resolved silently.
            conflicted = saw_pass and saw_verified_fail
            if saw_pass:
                verdicts.append(SessionStructuralVerdict(
                    action_session=session,
                    classification=VERDICT_PASSED,
                    conflicted=conflicted))
            elif latest_is_verified_fail:
                verdicts.append(SessionStructuralVerdict(
                    action_session=session,
                    classification=VERDICT_FAILED,
                    conflicted=conflicted))
            else:
                verdicts.append(SessionStructuralVerdict(
                    action_session=session,
                    classification=VERDICT_UNVERIFIABLE,
                    cause=latest_cause,
                    conflicted=conflicted))
        out[ticker] = tuple(verdicts)
    return out


def load_bars(cfg, ticker: str, *, start: date, end: date) -> list[DailyBar]:
    """Daily bars for `[start, end]` from the ON-DISK archive. NO network I/O.

    A thin delegate over `load_bars_with_status`, kept so its shipped signature
    and contract are untouched. See that function for the whole docstring.
    """
    bars, _status = load_bars_with_status(cfg, ticker, start=start, end=end)
    return bars


def load_bars_with_status(
    cfg, ticker: str, *, start: date, end: date,
) -> tuple[list[DailyBar], str]:
    """`load_bars`, plus WHETHER THE READ COMPLETED (Arc 21-G).

    Returns `(bars, status)` where `status` is one of `ARCHIVE_STATUSES`:

      `unavailable` -- the archive read RAISED. The absence of a witness is OUR
                       IGNORANCE, so nothing downstream may reason from it.
      `ok`          -- the read completed. An empty list is then a FACT about
                       the data (a legacy-only Shape-A ticker, or a genuinely
                       empty archive), not a failure.

    The distinction is load-bearing and cannot be inferred from the list: the
    shipped `load_bars` swallows every archive exception and returns `[]`, so
    "the archive says there is no such bar" and "the archive could not be read"
    collapse into one absence. Authorizing an alarm in the second case would be
    asserting from a stale price at exactly the moment the settling evidence
    was unreadable.

    Any failure degrades to `[]` + a warning; the derivation then reports
    `bars_available=False` so the panel says "invalidation NOT evaluated - no
    bars" rather than a silent "not invalidated".

    `migrate=False` IS THE A4 NO-WRITE PROPERTY, NOT AN OPTIMISATION.
    `resolve_ohlcv_window`'s default path runs `_backward_compat_rename`, which
    WRITES: V1 deliberately leaves the legacy `{TICKER}.parquet` in place (the
    `read_or_fetch_archive` consumers read only that path), so the both-exist
    MERGE branch is the STEADY state and rewrites `{TICKER}.yfinance.parquet`
    on every read whose merge output differs from the stored Shape A -- 6 of a
    60-ticker both-shapes sample on the live cache, plus a file CREATION for
    every legacy-only ticker (SLDB is one). A `GET /latches` must write
    NOTHING, so the panel opts out. The migration duty stays with the nightly
    pipeline's observe step, which still calls the default `migrate=True`.

    The accepted consequence: the panel reads Shape-A rows ONLY, so a ticker
    whose archive is legacy-only yields no bars and the derivation reports
    `bars_available=False` ("invalidation NOT evaluated - no bars") rather than
    a silent "not invalidated". Refactoring the legacy consumers onto the Shape
    A resolver is the banked V2 that removes the split entirely.
    """
    try:
        from swing.data.ohlcv_archive import resolve_ohlcv_window
        df, _provenance = resolve_ohlcv_window(
            ticker, start=start.isoformat(), end=end.isoformat(),
            cache_dir=cfg.paths.prices_cache_dir, migrate=False,
        )
    except Exception as exc:  # noqa: BLE001 -- A6: an unreadable archive is not a 500
        log.warning("latch reader: archive read failed for %s: %s", ticker, exc)
        return [], ARCHIVE_STATUS_UNAVAILABLE
    if df is None or df.empty:
        return [], ARCHIVE_STATUS_OK
    bars: list[DailyBar] = []
    for rec in df.to_dict("records"):
        try:
            close = float(rec["close"])
            if not math.isfinite(close):
                # A ragged archive row (the F6-addendum trailing-NaN shape)
                # must never be read as an invalidation.
                continue
            session = date.fromisoformat(str(rec["asof_date"]))
            if not is_trading_session(session):
                # The whole derivation is session-based (the horizon counts
                # sessions, the walk judges completed session closes), so a bar
                # dated on a non-session is a category error, not a datum --
                # letting one invalidate a mandate would clear it on a day the
                # market never traded. Skipping loses NO real bar.
                log.warning(
                    "latch reader: skipping non-session %s bar %s",
                    ticker, session.isoformat())
                continue
            bars.append(DailyBar(
                session=session,
                open=float(rec["open"]), high=float(rec["high"]),
                low=float(rec["low"]), close=close,
            ))
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("latch reader: skipping malformed %s bar %r: %s",
                        ticker, rec.get("asof_date"), exc)
    bars.sort(key=lambda b: b.session)
    return bars, ARCHIVE_STATUS_OK


def _optional_float(value, trade_id, field: str) -> float | None:
    """Coerce a non-load-bearing numeric, degrading a bad value to None."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        log.warning("latch reader: trade %r has a malformed %s: %r",
                    trade_id, field, value)
        return None
    if not math.isfinite(out):
        log.warning("latch reader: trade %r has a non-finite %s: %r",
                    trade_id, field, value)
        return None
    return out


def _session_at_or_before(raw: str, bound: date) -> bool:
    """True when `raw` parses to a date at-or-before `bound`, OR is unparseable
    (an unplaceable fire is kept so it can degrade VISIBLY)."""
    try:
        return date.fromisoformat(str(raw)) <= bound
    except (TypeError, ValueError):
        return True


def load_last_closes(conn: sqlite3.Connection, tickers) -> dict[str, tuple[float, str]]:
    """The most recent `candidates.close` per ticker, with its session.

    A PURE SELECT -- this is what lets `GET /latches` show a current price
    WITHOUT writing anything (A4). `PriceCache.get_many` cannot be used on the
    GET: a cache MISS dispatches the Schwab -> yfinance ladder, and both legs
    write audit rows (`schwab_api_calls` / `yfinance_calls`), which would make
    the panel GET a writer.

    THE RETURNED SESSION IS THE RUN STAMP, NOT THE CLOSE ITS OWN DATE (gotcha
    #30). `evaluation_runs.data_asof_date` is the MAX bar date across the WHOLE
    cohort (`swing/evaluation/orchestration.py`, `max(max_dates)`) -- or a
    CLI-supplied `as_of_date`, or a clock value -- while each `candidates.close`
    comes from that ticker's OWN last bar (`swing/evaluation/evaluator.py`,
    `closes.iloc[-1]`). A ticker whose archive lagged the cohort at evaluation
    time is therefore persisted with an OLDER close under a FRESHER stamp. The
    stamp is an UPPER BOUND on the close's date and nothing more; no caller may
    treat it as proof. `swing.latches.orders.classify_close_provenance` is the
    read-side treatment -- it DATES this close against the on-disk archive.
    """
    values = sorted({str(t) for t in (tickers or ())})
    if not values:
        return {}
    placeholders = ",".join("?" * len(values))
    rows = conn.execute(
        "SELECT c.ticker, c.close, e.data_asof_date FROM candidates c "
        "JOIN evaluation_runs e ON e.id = c.evaluation_run_id "
        f"WHERE c.ticker IN ({placeholders}) AND c.close IS NOT NULL "
        "ORDER BY e.data_asof_date, e.run_ts, c.id",
        values,
    ).fetchall()
    out: dict[str, tuple[float, str]] = {}
    for ticker, close, asof in rows:
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        out[str(ticker)] = (value, "" if asof is None else str(asof))
    return out


def latest_recorded_close_stamp(conn: sqlite3.Connection) -> str | None:
    """The NEWEST `evaluation_runs.data_asof_date` carrying a USABLE close.

    THE SELF-LIMITING HALF OF THE ALARM GATE (plan B.2.1 condition 2), and the
    property matters as much as the test. Corroborating a stale close at its
    OWN stamp proves WHEN it is from; it does not say whether the staleness is
    the CLOCK's fault or the TICKER's. This read answers that:

      * `stamp == L` -- the system has nothing newer than this ticker has, so
        whatever staleness remains is SYSTEM-WIDE. A system-wide gap ENDS at
        the next nightly run, so an alarm authorised under it is SELF-LIMITING
        and cannot become the drumbeat.
      * `stamp <  L` -- the system moved on without this ticker. That lag may
        be permanent, so an alarm from it would repeat forever.

    Mirrors the usability predicate `load_last_closes` and
    `count_session_recorded_closes` already share (non-NULL, numeric, finite):
    a run whose rows carry only NULL / non-finite closes has recorded nothing
    the form check can use, so it must not raise `L` and silence a legitimate
    alarm.

    A PURE SELECT (A4). Scanned newest-first and short-circuited on the first
    usable row, so it does not materialise the whole `candidates` table.
    """
    cursor = conn.execute(
        "SELECT e.data_asof_date, c.close FROM candidates c "
        "JOIN evaluation_runs e ON e.id = c.evaluation_run_id "
        "WHERE c.close IS NOT NULL AND e.data_asof_date IS NOT NULL "
        "ORDER BY e.data_asof_date DESC")
    try:
        for asof, close in cursor:
            try:
                value = float(close)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                stamp = str(asof)
                return stamp or None
    finally:
        cursor.close()
    return None


def count_session_recorded_closes(conn: sqlite3.Connection, session: date) -> int:
    """How many DISTINCT tickers carry a USABLE close recorded for `session`.

    A PURE SELECT (A4), and the only thing that tells apart the two reasons a
    latch can have no derivation-session close:

      * ZERO -- nothing has been recorded for that session at all, so NOBODY has
        a close for it. Self-resolving: the nightly run will record it. This is
        the state of every trading day between the action-session rollover at
        the market close and the nightly pipeline run.
      * NON-ZERO -- that session's closes exist, so a latch that still has none
        is not merely waiting on the nightly.

    Two deliberate choices, both from the Codex y1 MAJORs:

    1. It mirrors `load_last_closes`'s usability predicate EXACTLY (non-NULL,
       numeric, finite). The two reads must agree on what "usable" means or the
       panel's branch and its check disagree -- a session whose only rows carry
       NULL closes has recorded NOTHING the form check can use, and calling that
       "recorded" would flip every waiting latch to a warning.
    2. It asks only WHETHER a close exists, never WHERE the row came from. An
       `evaluation_runs` row is NOT the finviz screen: the evaluator appends
       held open positions (`bucket='excluded'`) and pinned tickers to the same
       run. A predicate phrased as screen membership would therefore make false
       statements about the operator's data. What the form check actually needs
       is a close, whatever produced it.

    The COUNT rather than a bool is what the label renders, so an unusual value
    (an ad-hoc `swing eval` for the same `data_asof_date` producing a handful of
    rows, rather than the nightly producing hundreds) is visible to the operator
    instead of silently deciding the branch behind his back.

    LIMIT OF THE PREDICATE, and the reason every caller says "closes DATED
    <session>" rather than "closes FOR <session>" (codex-auto-review MAJOR):
    `evaluation_runs.data_asof_date` is the MAX bar date across the WHOLE cohort
    (`swing/evaluation/orchestration.py`, `max(max_dates)`), while each
    `candidates.close` comes from that ticker's OWN last bar
    (`swing/evaluation/evaluator.py`, `closes.iloc[-1]`). A ticker whose archive
    is a bar behind therefore carries an older close under a fresher run stamp.
    This read is a STAMP query, not proof of a session's bar, and no caller may
    claim more than that. (The same stamp-vs-proof gap affects the regime price
    itself, which predates this function -- flagged to the orchestrator, NOT
    fixed here: it is a measurement-chain change, not a label change.)
    """
    rows = conn.execute(
        "SELECT DISTINCT c.ticker, c.close FROM candidates c "
        "JOIN evaluation_runs e ON e.id = c.evaluation_run_id "
        "WHERE e.data_asof_date = ? AND c.close IS NOT NULL",
        (session.isoformat(),),
    ).fetchall()
    tickers: set[str] = set()
    for ticker, close in rows:
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            tickers.add(str(ticker))
    return len(tickers)


def build_latch_derivation(
    conn: sqlite3.Connection,
    cfg,
    *,
    now: datetime | None = None,
    horizon_session_override: date | None = None,
) -> LatchDerivation:
    """Assemble every input and run the pure derivation.

    ONE clock read determines the WHOLE context (plan G.3): the forward anchor
    is `action_session_for_run(now)` and the backward anchor is derived from it
    as `session_offset(horizon_session, -1)` -- provably equal to
    `last_completed_session(now)` for every clock shape. `now` is consulted for
    NOTHING ELSE: no bar bound, no state input (Codex R3-1).

    `horizon_session_override` is what the view-telemetry beacon POST passes so
    it rebuilds the EXACT render-time context from the session anchor alone; a
    GET never passes it.
    """
    horizon_session = horizon_session_override or action_session_for_run(
        now or datetime.now())
    derivation_session = session_offset(horizon_session, -1)
    horizon_sessions = latch_horizon_sessions(cfg)

    # AS-OF SCOPING. Only fires whose action session is at-or-before the
    # horizon anchor existed in the world the anchor describes. Without this a
    # beacon POST carrying yesterday's anchor would rebuild the derivation
    # using TODAY's newer fire -- which can SUPERSEDE the very latch the
    # operator was looking at, so the view he actually performed is never
    # recorded. A fire whose session TEXT is unparseable is KEPT: it cannot be
    # placed in time, and `derive_latches` must still surface it as a visibly
    # degraded row (A6) rather than silently dropping it.
    fires = tuple(
        f for f in load_fire_rows(conn)
        if _session_at_or_before(f.action_session_date, horizon_session)
    )
    tickers = sorted({f.ticker for f in fires})
    entries_by_ticker = load_entry_records(conn, tickers)
    # Scoped to the AS-OF FIRE SET, so a beacon POST carrying yesterday's anchor
    # cannot pick up a decision recorded against a fire that did not exist in the
    # world that anchor describes.
    decisions_by_candidate = load_decision_intents(
        conn, [f.candidate_id for f in fires])

    bars_by_ticker: dict[str, list[DailyBar]] = {}
    status_by_ticker: dict[str, str] = {}
    for ticker in tickers:
        anchors = [
            f.action_session_date for f in fires
            if f.ticker == ticker and isinstance(f.action_session_date, str)
        ]
        start: date | None = None
        for raw in anchors:
            try:
                parsed = date.fromisoformat(raw)
            except ValueError:
                continue
            if start is None or parsed < start:
                start = parsed
        if start is None:
            bars_by_ticker[ticker] = []
            status_by_ticker[ticker] = ARCHIVE_STATUS_OK
            continue
        # THE LOAD WINDOW IS WIDENED TO REACH THE DERIVATION SESSION, and the
        # shipped `start > derivation_session -> []` short-circuit is GONE
        # (Arc 21-G, Codex R4 MAJOR 1). A latch fires on the nightly for action
        # session T+1, so its anchor is T+1 while that same evening the
        # derivation session is T -- the newest latch in the system, the one
        # the operator is about to act on, loaded NO bars at all and could
        # therefore never have its close DATED.
        #
        # This widens the LOAD only. `_eligible_bars` is untouched, so the
        # invalidation walk, `bars_available` and `bars_through` are
        # bit-for-bit identical: a fresh latch still reports "invalidation NOT
        # evaluated - no bars", which is correct (no session has elapsed since
        # the fire). Widening the ELIGIBLE set instead would let a pre-anchor
        # bar invalidate a mandate that did not yet exist -- RD constraint 6.
        start = min(start, derivation_session)
        bars_by_ticker[ticker], status_by_ticker[ticker] = load_bars_with_status(
            cfg, ticker, start=start, end=derivation_session)

    # THE STRUCTURAL VERDICT SEQUENCE (item 3b). Loaded over the whole latch
    # span so each latch can slice it by its OWN window; per TICKER, so two
    # latches on one ticker cannot be handed disagreeing sequences.
    verdict_start = min(
        [derivation_session, *(
            b[0].session for b in bars_by_ticker.values() if b)]
    ) if bars_by_ticker else derivation_session
    for raw in (f.action_session_date for f in fires):
        try:
            verdict_start = min(verdict_start, date.fromisoformat(str(raw)))
        except (TypeError, ValueError):
            continue
    verdicts_by_ticker = load_session_structural_verdicts(
        conn, cfg, tickers=tickers,
        start=verdict_start, end=horizon_session)

    latches_cfg = getattr(cfg, "latches", None)
    return derive_latches(
        fires=fires,
        bars_by_ticker=bars_by_ticker,
        entries_by_ticker=entries_by_ticker,
        horizon_session=horizon_session,
        derivation_session=derivation_session,
        horizon_sessions=horizon_sessions,
        bar_status_by_ticker=status_by_ticker,
        decision_intents_by_candidate_id=decisions_by_candidate,
        structural_verdicts_by_ticker=verdicts_by_ticker,
        # PRODUCTION PASSES ALL FOUR FROM CONFIG (L5). The pure derivation's
        # own defaults exist only for its signature; a production path that
        # forgot to pass them would silently derive from a module constant
        # instead of the bound calibration -- and, worse, could NEVER arm,
        # because the flag's default is False and no unit test over the pure
        # layer would notice.
        criteria_lapse_armed=getattr(
            latches_cfg, "criteria_lapse_armed", False),
        criteria_lapse_sessions=getattr(
            latches_cfg, "criteria_lapse_sessions",
            DEFAULT_CRITERIA_LAPSE_SESSIONS),
        criteria_lapse_min_widening_adr=getattr(
            latches_cfg, "criteria_lapse_min_widening_adr",
            DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR),
        criteria_lapse_min_widening_pct=getattr(
            latches_cfg, "criteria_lapse_min_widening_pct",
            DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT),
    )
