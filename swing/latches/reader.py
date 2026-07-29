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
from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    ARCHIVE_STATUS_UNAVAILABLE,
    latch_horizon_sessions,
)
from swing.latches.models import DailyBar, EntryRecord, FireRow, LatchDerivation
from swing.latches.service import derive_latches

log = logging.getLogger(__name__)

# ALL A+ fires are loaded (11 rows ever). A truncated read would break the
# re-confirmation chain and could fabricate a second latch for one mandate; the
# DISPLAY lookback is applied in the view model instead.
_FIRE_SQL = """
    SELECT c.id, c.evaluation_run_id, c.ticker, c.pivot, c.initial_stop,
           e.action_session_date, e.run_ts, p.id
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

    return derive_latches(
        fires=fires,
        bars_by_ticker=bars_by_ticker,
        entries_by_ticker=entries_by_ticker,
        horizon_session=horizon_session,
        derivation_session=derivation_session,
        horizon_sessions=horizon_sessions,
        bar_status_by_ticker=status_by_ticker,
    )
