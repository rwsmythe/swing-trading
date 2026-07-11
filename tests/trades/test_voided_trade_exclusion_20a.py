"""20-A Task B-2 — voided-trade exclusion completeness (module-export layer).

The central ``voided_trade_ids`` predicate is the single source of truth for
"which trades are void". This layer seeds a voided trade + fills and asserts:
  - every NAMED stat/cohort/equity reader EXCLUDES the void; and
  - the AUDIT-EXEMPT base repos (list_open_trades / list_closed_trades /
    list_all_fills) KEEP it visible (D19 audit-visibility).

The void is a ``trade_events`` note annotation carrying ``"voided": true``
(the operator/RD-run live mechanism; here planted via raw INSERT).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.voided_trades import voided_trade_ids


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_trade(
    conn, *, ticker: str, entry_price: float, hypothesis_label: str | None,
    entry_intent: str | None, exit_price: float,
) -> int:
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "hypothesis_label, entry_intent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, "2026-05-22", entry_price, 1, entry_price - 1.0,
         entry_price - 1.0, "reviewed", "manual_off_pipeline",
         "2026-05-22T16:00:00", hypothesis_label, entry_intent),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-22T14:00:00", "entry", 1, entry_price,
         "unreconciled"),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-22T15:00:00", "exit", 1, exit_price,
         "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    return trade_id


def _void(conn, trade_id: int) -> None:
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
        "rationale) VALUES (?, ?, 'note', ?, ?)",
        (trade_id, "2026-07-11T00:00:00",
         json.dumps({"voided": True, "reason": "SATL phantom (fixture)"}),
         "20-A B-2 void"),
    )
    conn.commit()


@pytest.fixture
def seeded(conn):
    """A voided (SATL-like) trade + a real (kept) trade in the same cohort."""
    voided_id = _seed_trade(
        conn, ticker="SATL", entry_price=10.31, hypothesis_label="H-alpha",
        entry_intent="hypothesis_test_by_design", exit_price=10.32,
    )
    kept_id = _seed_trade(
        conn, ticker="REAL", entry_price=20.00, hypothesis_label="H-alpha",
        entry_intent="hypothesis_test_by_design", exit_price=22.00,
    )
    _void(conn, voided_id)
    return conn, voided_id, kept_id


def test_predicate_returns_the_voided_id(seeded) -> None:
    conn, voided_id, kept_id = seeded
    voided = voided_trade_ids(conn)
    assert voided == frozenset({voided_id})


def test_predicate_tolerates_malformed_payload_json(seeded) -> None:
    """Codex R3 MAJOR — a malformed payload_json trade_events row must NOT
    raise (json_valid guard); the predicate still returns the real void."""
    conn, voided_id, kept_id = seeded
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
        "rationale) VALUES (?, ?, 'note', ?, ?)",
        (kept_id, "2026-07-11T00:00:00", "{not valid json", "legacy note"),
    )
    conn.commit()
    voided = voided_trade_ids(conn)  # must not raise
    assert voided == frozenset({voided_id})


def test_named_stat_readers_exclude_the_void(seeded) -> None:
    """Every enumerated cohort/stat/equity reader excludes the voided trade."""
    conn, voided_id, kept_id = seeded

    # cohort.py — list_trades_for_cohort + count_per_cohort
    from swing.metrics.cohort import (
        count_per_cohort,
        list_trades_for_cohort,
    )
    cohort_trades = list_trades_for_cohort(conn, hypothesis_label=None)
    ids = {t.id for t in cohort_trades}
    assert voided_id not in ids
    assert kept_id in ids

    # equity.py — list_all_exitshape_via_fills
    from swing.trades.equity import list_all_exitshape_via_fills
    exit_trade_ids = {e.trade_id for e in list_all_exitshape_via_fills(conn)}
    assert voided_id not in exit_trade_ids
    assert kept_id in exit_trade_ids

    # journal/stats.py — the local exitshape + hypothesis progress
    from swing.journal.stats import (
        _list_all_exitshape_via_fills as stats_exitshape,
    )
    stats_ids = {e.trade_id for e in stats_exitshape(conn)}
    assert voided_id not in stats_ids

    # web VM exitshapes
    from swing.web.view_models.journal import (
        _list_all_exitshape_via_fills as journal_vm_exitshape,
    )
    from swing.web.view_models.trades import (
        _list_all_exitshape_via_fills as trades_vm_exitshape,
    )
    assert voided_id not in {e.trade_id for e in journal_vm_exitshape(conn)}
    assert voided_id not in {e.trade_id for e in trades_vm_exitshape(conn)}

    # cli.py exitshape
    from swing.cli import _list_all_exitshape_via_fills as cli_exitshape
    assert voided_id not in {e.trade_id for e in cli_exitshape(conn)}

    # count_per_cohort excludes the void (the 16->15 restatement mechanism)
    counts = count_per_cohort(conn)
    # H-alpha registered? If not, it appears as an orphan label with 1 (kept).
    total_h_alpha = counts.get("H-alpha", 0)
    assert total_h_alpha == 1  # only the KEPT trade counts


def test_voided_open_trade_absent_from_capital_metrics(conn) -> None:
    """Codex R6 MAJOR — a voided OPEN trade is excluded from the raw-SQL
    capital concurrent-open-position count (via voided_exclusion_sql)."""
    def _open(ticker, price):
        c = conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, current_size, state, "
            "trade_origin, pre_trade_locked_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, "2026-05-22", price, 10, price - 1, price - 1, 10,
             "managing", "manual_off_pipeline", "2026-05-22T16:00:00"),
        ).lastrowid
        return int(c)

    real = _open("REAL", 20.00)
    satl = _open("SATL", 10.31)
    _void(conn, satl)
    from swing.metrics.capital import _count_concurrent_open_positions
    assert _count_concurrent_open_positions(conn) == 1  # only REAL


def test_voided_trade_absent_from_process_grade_trend(conn) -> None:
    """Codex R5 MAJOR — a voided reviewed trade is excluded from the
    process-grade trend markers."""
    def _reviewed(ticker, price):
        c = conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at, reviewed_at, process_grade) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, "2026-05-22", price, 1, price - 1, price - 1, "reviewed",
             "manual_off_pipeline", "2026-05-22T16:00:00",
             "2026-05-30T10:00:00", "A"),
        ).lastrowid
        return int(c)

    real = _reviewed("REAL", 20.00)
    satl = _reviewed("SATL", 10.31)
    _void(conn, satl)
    from swing.metrics.process_grade_trend import (
        _list_closed_reviewed_trades_ordered,
    )
    ids = {t.id for t in _list_closed_reviewed_trades_ordered(conn)}
    assert satl not in ids
    assert real in ids


def test_voided_trade_absent_from_needs_review_queue(conn) -> None:
    """Codex R4 MAJOR — a voided (phantom) trade never needs review; it is
    excluded from list_unreviewed_closed_trades."""
    # A CLOSED (unreviewed) voided trade + a real unreviewed closed trade.
    def _closed(ticker, price):
        c = conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, "2026-05-22", price, 1, price - 1, price - 1, "closed",
             "manual_off_pipeline", "2026-05-22T16:00:00"),
        ).lastrowid
        for action, p in (("entry", price), ("exit", price + 0.01)):
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
                (c, "2026-05-22T14:00:00", action, 1, p, "unreconciled"),
            )
        from swing.data.repos.fills import _recompute_aggregates
        _recompute_aggregates(conn, c)
        return int(c)

    real = _closed("REAL", 20.00)
    satl = _closed("SATL", 10.31)
    _void(conn, satl)
    from swing.data.repos.review_log import list_unreviewed_closed_trades
    queue_ids = {t.id for t in list_unreviewed_closed_trades(conn, window_days=None, today_iso=None)}
    assert satl not in queue_ids
    assert real in queue_ids


def test_audit_exempt_base_repos_keep_the_void_visible(seeded) -> None:
    """D19 — the base repos + fills stay voided-visible for audit."""
    conn, voided_id, kept_id = seeded
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import list_closed_trades
    closed_ids = {t.id for t in list_closed_trades(conn)}
    assert voided_id in closed_ids  # still visible on the audit surface
    fill_trade_ids = {f.trade_id for f in list_all_fills(conn)}
    assert voided_id in fill_trade_ids  # fills remain (never deleted)
