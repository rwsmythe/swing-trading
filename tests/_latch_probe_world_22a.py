"""22-A probe-world builders: a fire, an archive, an acceptance, an order.

WHY A SECOND FIXTURE MODULE.  ``tests/_latch_link_fixtures_22a.py`` builds the
LEDGER shapes migration 0037 mints from (task 2/3's grain).  ``mandate_alive_at``
needs a whole DERIVATION WORLD -- an evaluation run, an A+ fire, an on-disk
OHLCV archive, optional decisions and other trades -- plus an
``AcceptedLatchOrder`` to ask about.  The two are composed here rather than
merged, so neither module's callers move.

**THE HAND-BUILT ORDER IS BOUND TO THE EMITTER'S, NOT ASSUMED EQUAL TO IT.**
Most probe cases care only about the fire identity and the frozen values, so
minting a real link for each would add a ``place`` intent -- which is a DECISION
row the as-of rule then inspects -- to fixtures that are not about decisions.
``order_for_candidate`` therefore builds the dataclass directly.  That is the
synthetic-fixture-vs-production-emitter drift class, so a test in the task-6
module asserts ``order_for_candidate`` is FIELD-IDENTICAL to the order built
from a REAL trigger-minted link for the same fire, on every field except the
link/intent ids the mint assigns.

FROZEN CLOCK.  Nothing here reads the wall clock; every session is an explicit
date and every probe is anchored by ``fill_session``.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from types import SimpleNamespace

from swing.evaluation.dates import session_offset
from swing.trades.latched_origin import AcceptedLatchOrder
from tests._latch_link_fixtures_22a import insert_intent, place_row, validity_row

TICKER = "FTRE"
ANCHOR = date(2026, 7, 20)          # a Monday; the fire's action session
PIVOT = 18.34
STOP = 14.88
FILL_SESSION = date(2026, 7, 27)    # the Monday after; five sessions elapsed
BROKER_ORDER_ID = "1002937461"

# Closes for [ANCHOR, FILL_SESSION-1]: above the stop (no invalidation) and
# below the pivot (so the fold's lifetime rule is not what ends the mandate).
BASE_CLOSES: dict[date, float] = {
    date(2026, 7, 20): 17.10,
    date(2026, 7, 21): 17.25,
    date(2026, 7, 22): 17.02,
    date(2026, 7, 23): 17.44,
    date(2026, 7, 24): 17.31,
}


def probe_cfg(tmp_path, *, horizon_sessions: int = 30) -> SimpleNamespace:
    """The reader's config surface, and nothing more than it reads.

    ``horizon_sessions`` is production's 30 by default.  The horizon cases set
    it SMALL so a fill can land exactly on the expiry without generating thirty
    sessions of bars -- the horizon LENGTH is a free dimension for every case
    here except the ones that name it.
    """
    cache = tmp_path / "prices"
    cache.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        paths=SimpleNamespace(prices_cache_dir=cache, db_path=tmp_path / "t.db"),
        pipeline=SimpleNamespace(
            observe_max_pending_window_sessions=horizon_sessions),
    )


def write_closes(cfg, closes: dict[date, float], *, ticker: str = TICKER) -> None:
    """Write the Shape-A parquet the reader loads (``migrate=False``)."""
    import pandas as pd

    rows = [
        {
            "asof_date": session.isoformat(),
            "open": close, "high": close + 0.10, "low": close - 0.10,
            "close": close, "volume": 100.0,
        }
        for session, close in sorted(closes.items())
    ]
    pd.DataFrame(rows).to_parquet(
        cfg.paths.prices_cache_dir / f"{ticker}.yfinance.parquet")


def seed_run(
    conn: sqlite3.Connection, run_id: int, action_session: date,
) -> None:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
        (run_id, f"{session_offset(action_session, -1).isoformat()}T17:30:05",
         session_offset(action_session, -1).isoformat(),
         action_session.isoformat()),
    )


def seed_fire(
    conn: sqlite3.Connection,
    *,
    run_id: int = 121,
    action_session: date = ANCHOR,
    ticker: str = TICKER,
    pivot: float | None = PIVOT,
    initial_stop: float | None = STOP,
    bucket: str = "aplus",
) -> int:
    """One evaluation run and one candidate on it.  Returns the candidate id."""
    seed_run(conn, run_id, action_session)
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (?, ?, ?, 17.10, ?, ?, "
        "'universe')",
        (run_id, ticker, bucket, pivot, initial_stop),
    )
    return int(cur.lastrowid)


def order_for_candidate(
    conn: sqlite3.Connection,
    candidate_id: int,
    *,
    broker_order_id: str = BROKER_ORDER_ID,
    link_id: int = 1,
    validity_intent_id: int = 2,
    place_intent_id: int = 1,
    actual_quantity: int | None = 9,
    freeze_tier: str = "live_at_acceptance",
    actual_limit_price: float | None = None,
    frozen_pivot: float | None = None,
    frozen_invalidation: float | None = None,
) -> AcceptedLatchOrder:
    """An ``AcceptedLatchOrder`` whose frozen values are the fire's, AS STORED.

    ``frozen_pivot`` / ``frozen_invalidation`` default to the candidate row's
    own values -- which is what the minting trigger copies -- so a drift fixture
    is built by MUTATING the candidate afterwards, never by hand-writing a
    mismatched pair.
    """
    run_id, ticker, detection, pivot, stop = conn.execute(
        "SELECT c.evaluation_run_id, c.ticker, e.action_session_date, c.pivot, "
        "c.initial_stop FROM candidates c JOIN evaluation_runs e "
        "ON e.id = c.evaluation_run_id WHERE c.id = ?",
        (candidate_id,),
    ).fetchone()
    return AcceptedLatchOrder(
        link_id=link_id,
        validity_intent_id=validity_intent_id,
        place_intent_id=place_intent_id,
        candidate_id=candidate_id,
        evaluation_run_id=int(run_id),
        ticker=str(ticker),
        detection_date=str(detection),
        broker_order_id=broker_order_id,
        frozen_pivot=pivot if frozen_pivot is None else frozen_pivot,
        frozen_invalidation=(
            stop if frozen_invalidation is None else frozen_invalidation),
        actual_quantity=actual_quantity,
        freeze_tier=freeze_tier,
        actual_limit_price=actual_limit_price,
    )


def accept_and_link(
    conn: sqlite3.Connection,
    candidate_id: int,
    *,
    session: date,
    recorded_ts: str | None = None,
    broker_order_id: str = BROKER_ORDER_ID,
    key: str = "probe",
) -> AcceptedLatchOrder:
    """Place an order, record the broker's ACCEPTANCE, read the MINTED link.

    The link is never inserted by hand: the trigger mints it, and the order is
    built from the stored row, so this is real emitter output.

    ``session`` / ``recorded_ts`` are explicit because a ``place`` intent is a
    DECISION row, and the probe's as-of rule refuses a decision recorded on or
    after the fill session.  A fixture that left them at their defaults would
    refuse for a reason unrelated to the case under test.
    """
    from swing.data.repos.latch_order_mandate_links import (
        list_links_for_broker_order,
    )

    run_id, ticker, detection = conn.execute(
        "SELECT c.evaluation_run_id, c.ticker, e.action_session_date "
        "FROM candidates c JOIN evaluation_runs e ON e.id = c.evaluation_run_id "
        "WHERE c.id = ?", (candidate_id,),
    ).fetchone()
    stamp = recorded_ts or f"{session.isoformat()}T10:00:00"
    common = {
        "evaluation_run_id": int(run_id),
        "ticker": str(ticker),
        "detection_date": str(detection),
        "action_session_date": session.isoformat(),
        "recorded_ts": stamp,
    }
    place_id = insert_intent(conn, place_row(
        candidate_id, idempotency_key=f"{key}-place", **common))
    insert_intent(conn, validity_row(
        candidate_id, place_id, key=f"{key}-validity",
        actual_broker_order_id=broker_order_id, **common))
    links = list_links_for_broker_order(conn, broker_order_id)
    assert len(links) == 1, (
        "the minting trigger produced "
        f"{len(links)} links for {broker_order_id!r}; the fixture is wrong, "
        "not the trigger"
    )
    link = links[0]
    return AcceptedLatchOrder(
        link_id=int(link.link_id),
        validity_intent_id=link.validity_intent_id,
        place_intent_id=link.place_intent_id,
        candidate_id=link.candidate_id,
        evaluation_run_id=link.evaluation_run_id,
        ticker=link.ticker,
        detection_date=link.detection_date,
        broker_order_id=link.broker_order_id,
        frozen_pivot=link.frozen_pivot,
        frozen_invalidation=link.frozen_invalidation,
        actual_quantity=link.actual_quantity,
        freeze_tier=link.freeze_tier,
        actual_limit_price=18.89,
    )


def record_decision(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    run_id: int,
    ticker: str,
    detection: date,
    session: date,
    kind: str = "decline",
    recorded_ts: str | None = None,
) -> int:
    """A ``place`` / ``decline`` written through the PRODUCTION dataclass + repo.

    Hand-built rows are how a fixture stops matching the emitter; this one
    cannot, because it goes through the same validator the panel does.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos.latch_order_intents import record_intent

    intent = LatchOrderIntent(
        intent_id=None, candidate_id=candidate_id, evaluation_run_id=run_id,
        ticker=ticker, detection_date=detection.isoformat(), pipeline_run_id=None,
        idempotency_key=f"key-{candidate_id}-{session.isoformat()}-{kind}",
        action_session_date=session.isoformat(),
        recorded_ts=recorded_ts or f"{session.isoformat()}T10:00:00",
        surface="latch_panel", intent_kind=kind,
        decline_reason="off the screen" if kind == "decline" else None,
        framework_order_type="STOP_LIMIT", framework_duration="GOOD_TILL_CANCEL",
        framework_stop_price=PIVOT, framework_limit_price=18.89,
        framework_quantity=9, derivation_zone_cap_pct=3.0,
        derivation_sizing_equity=7500.0, derivation_max_risk_pct=0.005,
        derivation_position_pct_cap=0.15, derivation_sizing_basis="limit_price",
        derivation_regime_close=17.10,
        derivation_regime_close_session=detection.isoformat(),
        derivation_real_equity=1300.0, derivation_equity_floor=7500.0)
    with conn:
        return record_intent(conn, intent=intent)


def seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    entry_date: date,
    price: float,
    ticker: str = TICKER,
    candidate_id: int | None = None,
    shares: int = 2,
) -> None:
    """Another operator entry, for the consumption / fill-terminal fixtures."""
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at, candidate_id) VALUES "
        "(?, ?, ?, ?, ?, 14.88, 14.88, 'entered', 'manual_off_pipeline', "
        "'2026-07-17T17:30:05', ?)",
        (trade_id, ticker, entry_date.isoformat(), price, shares, candidate_id),
    )
