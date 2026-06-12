"""Shared fixtures for the Arc 4b/4c cash-reconciliation tests (Tasks 6/7/8).

``cash_recon_run`` gives a v29 DB + a started reconciliation_runs row for unit-
testing ``_ingest_cash_transactions`` directly. ``cash_recon_full`` drives the
whole ``run_schwab_reconciliation`` end-to-end on a v29 DB with synthetic
journal cash + Schwab transactions + a flat (or non-flat) broker payload, built
from the REAL emitter shapes (SchwabTransactionResponse + the positions dict).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.repos import reconciliation as recon_repo
from swing.integrations.schwab.models import SchwabTransactionResponse


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


def _seed_open_trade(conn, ticker: str, *, qty: float = 10.0, entry: float = 100.0) -> int:
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, "2026-04-27", entry, int(qty), entry - 5.0, entry - 5.0,
         "managing", "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-04-27T14:23:00", "entry", qty, entry, "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    return trade_id


@pytest.fixture
def cash_recon_run(tmp_path):
    """A v29 DB + a started schwab_api reconciliation run. Returns (conn, run_id)."""
    conn = ensure_schema(tmp_path / "cash_recon.db")
    conn.execute("BEGIN")
    run_id = recon_repo.insert_run(
        conn, source="schwab_api", state="running", started_ts=now_ms(),
        period_start="2026-05-01", period_end="2026-05-31",
    )
    conn.commit()
    return conn, run_id


def _accepts_starting_equity() -> bool:
    """True once run_schwab_reconciliation grows the Task-8 starting_equity kwarg."""
    import inspect

    from swing.trades.schwab_reconciliation import run_schwab_reconciliation
    return "starting_equity" in inspect.signature(run_schwab_reconciliation).parameters


def _mk_tx(spec, idx: int) -> SchwabTransactionResponse:
    # spec = (type, iso_date, net_amount[, transaction_id[, description]])
    ttype, date, amount = spec[0], spec[1], spec[2]
    tid = str(spec[3]) if len(spec) > 3 and spec[3] is not None else f"95000{idx}"
    desc = spec[4] if len(spec) > 4 else None
    return SchwabTransactionResponse(
        transaction_id=tid, transaction_date=date, type=ttype,
        net_amount=float(amount), description=desc,
    )


@pytest.fixture
def cash_recon_full(tmp_path):
    """Drive run_schwab_reconciliation end-to-end. Returns (conn, run).

    Params:
      starting_equity, journal_cash=[(date,kind,amount,ref)],
      schwab_txs=[(type,date,amount[,tid[,desc]])], nlv, open_trades (int),
      broker_positions=[(ticker,qty)], prior_completed_period_end,
      period_start, period_end.
    """
    from swing.trades.schwab_reconciliation import run_schwab_reconciliation

    def _run(
        *,
        starting_equity: float = 1000.0,
        journal_cash: list[tuple] | None = None,
        schwab_txs: list[tuple] | None = None,
        nlv: float = 1000.0,
        open_trades: int = 0,
        broker_positions: list[tuple] | None = None,
        prior_completed_period_end: str | None = None,
        period_start: str = "2026-05-01",
        period_end: str = "2026-05-31",
        environment: str = "production",
    ):
        conn = ensure_schema(tmp_path / "cash_recon_full.db")
        # Seed journal cash rows.
        for (cdate, kind, amount, ref) in (journal_cash or []):
            conn.execute(
                "INSERT INTO cash_movements (date, kind, amount, ref, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (cdate, kind, float(amount), ref, "seed"),
            )
        # Seed open trades.
        for i in range(open_trades):
            _seed_open_trade(conn, f"TKR{i}")
        # Seed a prior COMPLETED schwab_api run (coverage-gap read).
        if prior_completed_period_end is not None:
            conn.execute("BEGIN")
            recon_repo.insert_run(
                conn, source="schwab_api", state="completed",
                started_ts="1", finished_ts="2",
                period_start="2026-04-01", period_end=prior_completed_period_end,
            )
            conn.commit()
        conn.commit()

        txs = [_mk_tx(s, i) for i, s in enumerate(schwab_txs or [])]
        positions = [
            {"instrument": {"symbol": t}, "longQuantity": q, "shortQuantity": 0}
            for (t, q) in (broker_positions or [])
        ]
        account = _SchwabAccount(net_liquidating_value=nlv, positions=positions)

        # NOTE: starting_equity is accepted as a fixture param from Task 6 but
        # only threaded into run_schwab_reconciliation in Task 8 (the equity-
        # coherence check); _extra lets Task 8 add the pass-through without
        # touching call sites.
        _extra = {}
        if _accepts_starting_equity():
            _extra["starting_equity"] = starting_equity
        run = run_schwab_reconciliation(
            conn,
            account_hash="<acct>",
            period_start=period_start,
            period_end=period_end,
            schwab_orders=[],
            schwab_transactions=txs,
            schwab_account=account,
            environment=environment,
            **_extra,
        )
        return conn, run

    return _run
