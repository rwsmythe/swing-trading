"""The IMPURE adapter feeding the pure latch derivation.

Read-only by construction: SELECTs plus an on-disk parquet read. ZERO network
I/O (`resolve_ohlcv_window` is a two-provider parquet read -- the same reader
the pipeline observe step uses), ZERO writes, ZERO transaction management.

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

from swing.evaluation.dates import action_session_for_run, session_offset
from swing.latches.constants import latch_horizon_sessions
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
                pivot=None if row[3] is None else float(row[3]),
                initial_stop=None if row[4] is None else float(row[4]),
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
    rows = conn.execute(
        "SELECT id, ticker, entry_date, candidate_id, entry_price, initial_shares "
        f"FROM trades WHERE ticker IN ({placeholders}) ORDER BY entry_date, id",
        values,
    ).fetchall()
    out: dict[str, list[EntryRecord]] = {}
    for row in rows:
        try:
            # The TEXT-column -> Python-date boundary, converted at the
            # callsite. A malformed row is SKIPPED: it must never be allowed to
            # clear a latch, and it must never crash the panel.
            entry_date = date.fromisoformat(str(row[2]))
            rec = EntryRecord(
                trade_id=int(row[0]),
                ticker=str(row[1]),
                entry_date=entry_date,
                candidate_id=None if row[3] is None else int(row[3]),
                entry_price=None if row[4] is None else float(row[4]),
                shares=None if row[5] is None else float(row[5]),
            )
        except (TypeError, ValueError) as exc:
            log.warning("latch reader: skipping trade %r with a malformed row: %s",
                        row[0], exc)
            continue
        out.setdefault(rec.ticker, []).append(rec)
    return out


def load_bars(cfg, ticker: str, *, start: date, end: date) -> list[DailyBar]:
    """Daily bars for `[start, end]` from the ON-DISK archive. NO network I/O.

    Any failure degrades to `[]` + a warning; the derivation then reports
    `bars_available=False` so the panel says "invalidation NOT evaluated - no
    bars" rather than a silent "not invalidated".

    (Reviewer note: `resolve_ohlcv_window` performs a one-shot legacy
    `{TICKER}.parquet` -> Shape-A rename on first read. That is pre-existing
    production read-path behaviour shared with the pipeline observe step -- a
    cache-file migration, not domain state, and explicitly NOT the A4 view
    record.)
    """
    try:
        from swing.data.ohlcv_archive import resolve_ohlcv_window
        df, _provenance = resolve_ohlcv_window(
            ticker, start=start.isoformat(), end=end.isoformat(),
            cache_dir=cfg.paths.prices_cache_dir,
        )
    except Exception as exc:  # noqa: BLE001 -- A6: an unreadable archive is not a 500
        log.warning("latch reader: archive read failed for %s: %s", ticker, exc)
        return []
    if df is None or df.empty:
        return []
    bars: list[DailyBar] = []
    for rec in df.to_dict("records"):
        try:
            close = float(rec["close"])
            if not math.isfinite(close):
                # A ragged archive row (the F6-addendum trailing-NaN shape)
                # must never be read as an invalidation.
                continue
            bars.append(DailyBar(
                session=date.fromisoformat(str(rec["asof_date"])),
                open=float(rec["open"]), high=float(rec["high"]),
                low=float(rec["low"]), close=close,
            ))
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("latch reader: skipping malformed %s bar %r: %s",
                        ticker, rec.get("asof_date"), exc)
    bars.sort(key=lambda b: b.session)
    return bars


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

    fires = load_fire_rows(conn)
    tickers = sorted({f.ticker for f in fires})
    entries_by_ticker = load_entry_records(conn, tickers)

    bars_by_ticker: dict[str, list[DailyBar]] = {}
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
        if start is None or start > derivation_session:
            bars_by_ticker[ticker] = []
            continue
        bars_by_ticker[ticker] = load_bars(
            cfg, ticker, start=start, end=derivation_session)

    return derive_latches(
        fires=fires,
        bars_by_ticker=bars_by_ticker,
        entries_by_ticker=entries_by_ticker,
        horizon_session=horizon_session,
        derivation_session=derivation_session,
        horizon_sessions=horizon_sessions,
    )
