"""Phase 9 end-to-end integration test (Sub-bundles B + C).

Sub-bundle B (T-B.8): Reconcile a CSV with 1 close_price_mismatch +
1 stop_mismatch + 1 position_qty_mismatch + 1 cash_movement_mismatch;
verify 4 discrepancies persisted with correct material_to_review per
MATERIAL_BY_TYPE; ``list_unresolved_material_for_active_trades``
returns the active-trade attention rows (close_price + stop +
position_qty are MATERIAL=1; cash_movement is MATERIAL=0 + has no
trade_id — does NOT appear); operator resolves one via CLI → row's
resolution + resolved_at updated; parent run's unresolved counter
decremented.

Sub-bundle C (T-C.5): exercise account_equity_snapshots service +
hypothesis status audit service + back-recorded flag for >7-day gap +
identity transition returns noop_identity sentinel + source-ladder
precedence on get_latest_snapshot_on_or_before.

Sub-bundles D/E append their own sections when they land (per plan §E
T-B.8 file note).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.data.models import CashMovement, Fill, Trade
from swing.data.repos import reconciliation as recon_repo
from swing.data.repos.cash import insert_cash
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.trades.reconciliation import MATERIAL_BY_TYPE, run_tos_reconciliation
from tests.cli.test_cli_eval import _minimal_config


# A CSV exercising all four Bundle B discrepancy types:
# - ABC: open trade (managing). Broker reports 7 shares vs journal 10
#        (position_qty_mismatch); no working stop (stop_mismatch).
# - DEF: open trade (partial_exited). Journal exit fill at $11.00 for 5
#        shares. TOS CLOSE fill at $11.20 → close_price_mismatch.
# - Cash DEP REF-001: journal $400, TOS $500 → cash_movement_mismatch.
_E2E_TOS_CSV = """\
Cash Balance
DATE,TIME,TYPE,REF #,DESCRIPTION,MISC FEES,COMMISSIONS & FEES,AMOUNT,BALANCE
2026-05-12,10:00:00,DEP,="REF-001",ACH deposit,,,500.00,5500.00

Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 15:30:00,STOCK,SELL,-5,CLOSING,DEF,,,,11.2000,11.2000,MKT

Equities
Symbol,Description,Qty,Trade Price,Mark,Mark Value
ABC,ABC Inc,7,10.00,10.50,73.50

Account Order History
Notes,Time Placed,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Order Type,TIF,Mark,Status
,2026-05-12 09:30:00,STOCK,SELL,-5,TO CLOSE,DEF,,,STOCK,8.0000,STP,GTC,11.20,WORKING
"""


def _seed_partial_exited_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    shares: int,
    initial_stop: float,
    exit_date: str,
    exit_price: float,
    exit_shares: int,
) -> tuple[int, int]:
    """Seed a trade with both an entry fill AND a partial exit fill.

    Returns (trade_id, exit_fill_id). State is set to 'partial_exited'
    because exit_shares < initial_shares.
    """
    entry_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date,
        entry_price=entry_price, initial_shares=shares,
        initial_stop=initial_stop, current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, trade_origin="manual_off_pipeline",
        pre_trade_locked_at=entry_ts,
    )
    with conn:
        tid = insert_trade_with_event(
            conn, trade, event_ts=entry_ts, rationale="seed entry",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=entry_ts,
                action="entry", quantity=float(shares), price=entry_price,
            ),
            event_ts=entry_ts,
        )
        exit_ts = f"{exit_date}T15:30:00"
        exit_fid = insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=exit_ts,
                action="exit", quantity=float(exit_shares),
                price=exit_price, reason="target",
            ),
            event_ts=exit_ts,
        )
        # Transition to partial_exited; current_size = remaining shares.
        conn.execute(
            "UPDATE trades SET state='partial_exited', current_size=? "
            "WHERE id=?",
            (float(shares - exit_shares), tid),
        )
    return tid, exit_fid


def _seed_managing_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    shares: int,
    initial_stop: float,
) -> int:
    """Seed a 'managing'-state trade with one entry fill."""
    entry_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date,
        entry_price=entry_price, initial_shares=shares,
        initial_stop=initial_stop, current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, trade_origin="manual_off_pipeline",
        pre_trade_locked_at=entry_ts,
    )
    with conn:
        tid = insert_trade_with_event(
            conn, trade, event_ts=entry_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=entry_ts,
                action="entry", quantity=float(shares), price=entry_price,
            ),
            event_ts=entry_ts,
        )
        conn.execute(
            "UPDATE trades SET state='managing' WHERE id=?", (tid,),
        )
    return tid


def _seed_journal_cash(
    conn: sqlite3.Connection, *, ref: str, kind: str, amount: float,
) -> None:
    with conn:
        insert_cash(
            conn,
            CashMovement(
                id=None, date="2026-05-12", kind=kind,
                amount=amount, ref=ref, note="journal entry",
            ),
        )


@pytest.fixture
def cli_workspace(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    return runner, cfg, home / "swing-data" / "swing.db", tmp_path


def test_phase9_end_to_end_four_discrepancy_types(cli_workspace) -> None:
    """E2E: reconcile a CSV with the four Bundle B discrepancy types;
    assert each persists with the correct MATERIAL_BY_TYPE classification.
    """
    runner, cfg, db_path, tmp_path = cli_workspace
    conn = connect(db_path)
    try:
        # Trade 1 (ABC) — managing; broker reports 7 vs journal 10 + no stop.
        tid_abc = _seed_managing_trade(
            conn, ticker="ABC", entry_date="2026-05-10",
            entry_price=10.00, shares=10, initial_stop=9.00,
        )
        # Trade 2 (DEF) — partial_exited; journal exit at $11.00 for 5 shares.
        tid_def, exit_fid = _seed_partial_exited_trade(
            conn, ticker="DEF", entry_date="2026-05-08",
            entry_price=20.00, shares=10, initial_stop=18.00,
            exit_date="2026-05-12", exit_price=11.00, exit_shares=5,
        )
        # Cash movement seed: journal $400 vs TOS $500 → mismatch.
        _seed_journal_cash(conn, ref="REF-001", kind="deposit", amount=400.00)
    finally:
        conn.close()

    csv = tmp_path / "tos.csv"
    csv.write_text(_E2E_TOS_CSV, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "reconcile-tos",
        "--csv-path", str(csv), "--period-end", "2026-05-12",
    ])
    assert r.exit_code == 0, r.output

    # Verify the four discrepancy types persisted.
    conn = connect(db_path)
    try:
        runs = recon_repo.list_recent_runs(conn, limit=5)
        assert len(runs) == 1
        run = runs[0]
        assert run.state == "completed"
        ds = recon_repo.list_discrepancies_for_run(conn, run.run_id)
        types = sorted({d.discrepancy_type for d in ds})
        # Bundle B emits FIVE types possibly (entry_price + close_price +
        # stop + position_qty + cash_movement); orphan stop for DEF (the
        # CSV's DEF stop is at $8 vs journal $18 → mismatch; not 'no
        # broker stop'). ABC has no DEF qty match → position_qty.
        assert "close_price_mismatch" in types
        assert "stop_mismatch" in types
        assert "position_qty_mismatch" in types
        assert "cash_movement_mismatch" in types

        # Each discrepancy's material_to_review matches MATERIAL_BY_TYPE.
        for d in ds:
            expected_material = MATERIAL_BY_TYPE[d.discrepancy_type]
            assert d.material_to_review == expected_material, (
                f"{d.discrepancy_type}: expected material="
                f"{expected_material} got {d.material_to_review}"
            )

        # Active-trade attention surface (CANONICAL #1): distinct trades
        # covered = 2 (ABC + DEF). The query returns one row per
        # discrepancy.
        active_attn = recon_repo.list_unresolved_material_for_active_trades(conn)
        active_tids = {d.trade_id for d in active_attn}
        assert active_tids == {tid_abc, tid_def}, (
            f"active-trade attention should cover ABC + DEF; got {active_tids}"
        )
        # cash_movement_mismatch is material=0 + trade_id=None → does NOT
        # appear in either canonical query.
        cm = [d for d in active_attn
              if d.discrepancy_type == "cash_movement_mismatch"]
        assert cm == []
        # Closed-trade canonical query is empty (no closed/reviewed trades).
        closed_attn = recon_repo.list_unresolved_material_for_closed_trades(conn)
        assert closed_attn == []
    finally:
        conn.close()


def test_phase9_end_to_end_resolve_via_cli_updates_row(cli_workspace) -> None:
    """Operator resolves one discrepancy via the CLI; row's resolution +
    resolved_at + resolved_by populated; parent run unresolved counter
    decremented.
    """
    runner, cfg, db_path, tmp_path = cli_workspace
    conn = connect(db_path)
    try:
        _seed_managing_trade(
            conn, ticker="ABC", entry_date="2026-05-10",
            entry_price=10.00, shares=10, initial_stop=9.00,
        )
    finally:
        conn.close()

    csv = tmp_path / "tos.csv"
    csv.write_text(_E2E_TOS_CSV, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "reconcile-tos",
        "--csv-path", str(csv),
    ])
    assert r.exit_code == 0, r.output

    # Pick any discrepancy on the active trade.
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT discrepancy_id, run_id FROM reconciliation_discrepancies "
            "WHERE trade_id IS NOT NULL ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()
        assert row is not None
        did, run_id = row
        before = recon_repo.get_run(conn, run_id)
        unresolved_before = before.unresolved_discrepancies_count
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve",
        str(did),
        "--resolution", "journal_corrected",
        "--reason", "operator corrected journal after CLI reconcile review",
    ])
    assert r.exit_code == 0, r.output
    assert "resolved" in r.output

    conn = connect(db_path)
    try:
        d = recon_repo.get_discrepancy(conn, did)
        assert d.resolution == "journal_corrected"
        assert d.resolved_at is not None
        assert d.resolved_by == "operator"
        assert d.resolution_reason == (
            "operator corrected journal after CLI reconcile review"
        )
        after = recon_repo.get_run(conn, run_id)
        assert after.unresolved_discrepancies_count == unresolved_before - 1
    finally:
        conn.close()


# ============================================================================
# Sub-bundle C E2E (T-C.5) — account_equity_snapshots + hypothesis audit
# ============================================================================


def test_phase9_bundle_c_e2e_account_snapshot_and_hypothesis_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E happy path for Sub-bundle C (plan §F T-C.5 acceptance criteria).

    Exercises:
      - swing account snapshot via CLI records a row.
      - Back-recorded flag for a >7-day-past snapshot_date.
      - source-ladder precedence on get_latest_snapshot_on_or_before
        (schwab_api > tos_csv > manual at the same date).
      - swing hypothesis update via CLI rewires through new service:
        first call writes hypothesis_status_history row + closes prior
        seed interval + updates registry denorm; identity transition
        returns INFO + does NOT insert a duplicate row.
    """
    from swing.data.datetime_helpers import now_ms
    from swing.data.repos.account_equity_snapshots import (
        get_latest_snapshot_on_or_before,
        insert_snapshot,
    )
    from swing.data.repos.hypothesis_status_history import (
        list_history_for_hypothesis,
    )

    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"

    # ----- §1: account snapshot CLI happy path --------------------------
    r1 = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1300",
        "--date", "2026-05-12",
        "--notes", "Bundle C E2E S2",
    ])
    assert r1.exit_code == 0, r1.output
    assert "back-recorded" not in r1.output

    # Verify persisted row.
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT snapshot_date, equity_dollars, source, notes "
            "FROM account_equity_snapshots WHERE snapshot_date = ?",
            ("2026-05-12",),
        ).fetchone()
        assert row == ("2026-05-12", 1300.0, "manual", "Bundle C E2E S2")
    finally:
        conn.close()

    # ----- §2: back-recorded advisory for >7-day-past date --------------
    r2 = runner.invoke(main, [
        "--config", str(cfg_path),
        "account", "snapshot",
        "--equity", "1400",
        "--date", "2026-01-01",
        "--notes", "back-record probe",
    ])
    assert r2.exit_code == 0, r2.output
    assert "back-recorded" in r2.output

    # ----- §3: source-ladder precedence (insert tos_csv + schwab_api) ---
    conn = connect(db_path)
    try:
        insert_snapshot(
            conn,
            snapshot_date="2026-05-12",
            equity_dollars=1301.0,
            source="tos_csv",
            source_artifact_path="/tmp/probe.csv",
            recorded_at=now_ms(),
            recorded_by="operator",
            notes=None,
        )
        insert_snapshot(
            conn,
            snapshot_date="2026-05-12",
            equity_dollars=1302.5,
            source="schwab_api",
            source_artifact_path=None,
            recorded_at=now_ms(),
            recorded_by="operator",
            notes=None,
        )
        conn.commit()
        result = get_latest_snapshot_on_or_before(
            conn, asof_date="2026-05-12", with_provenance=True,
        )
        assert result is not None
        winner, suppressed = result
        assert winner.source == "schwab_api"
        assert winner.equity_dollars == 1302.5
        suppressed_sources = sorted(s.source for s in suppressed)
        assert suppressed_sources == ["manual", "tos_csv"]
    finally:
        conn.close()

    # ----- §4: hypothesis update via CLI writes audit row + denorm -----
    # The seeded hypothesis is 'active'; transition to 'paused' must
    # close the prior open-interval row + INSERT a new one + UPDATE the
    # registry status_changed_at + status_change_reason.
    list_r = runner.invoke(main, ["--config", str(cfg_path), "hypothesis", "list"])
    line = next(
        ln for ln in list_r.output.splitlines() if "A+ baseline" in ln
    )
    hid_str = next(tok for tok in line.split() if tok.isdigit())
    hid = int(hid_str)

    r3 = runner.invoke(main, [
        "--config", str(cfg_path),
        "hypothesis", "update", hid_str,
        "--status", "paused",
        "--reason", "Bundle C E2E S4",
    ])
    assert r3.exit_code == 0, r3.output
    assert "hypothesis #" in r3.output
    assert "paused" in r3.output

    conn = connect(db_path)
    try:
        rows = list_history_for_hypothesis(conn, hid)
        assert len(rows) == 2, (
            f"expected seed + new history row; got {len(rows)}"
        )
        seed_row, new_row = rows
        assert seed_row.status == "active"
        assert seed_row.effective_to is not None  # now closed
        assert seed_row.change_reason is None
        assert new_row.status == "paused"
        assert new_row.effective_to is None  # open interval
        assert new_row.change_reason == "Bundle C E2E S4"
        # Registry denorm in sync.
        reg = conn.execute(
            "SELECT status, status_change_reason FROM hypothesis_registry "
            "WHERE id = ?", (hid,),
        ).fetchone()
        assert reg == ("paused", "Bundle C E2E S4")
    finally:
        conn.close()

    # ----- §5: identity transition returns INFO ------------------------
    r4 = runner.invoke(main, [
        "--config", str(cfg_path),
        "hypothesis", "update", hid_str,
        "--status", "paused",
        "--reason", "redundant",
    ])
    assert r4.exit_code == 0, r4.output
    assert "already paused" in r4.output
    assert "info:" in r4.output

    # No new history row was inserted (still 2: seed-closed + new-open).
    conn = connect(db_path)
    try:
        rows = list_history_for_hypothesis(conn, hid)
        assert len(rows) == 2
    finally:
        conn.close()
