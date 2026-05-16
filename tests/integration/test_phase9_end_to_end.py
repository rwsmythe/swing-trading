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
        # Phase 12 C.C T-C.6: the auto-correct pivot has now run + most
        # discrepancies have moved to ``pending_ambiguity_resolution``.
        # Reset to ``unresolved`` so this Phase 9 e2e test exercises the
        # canonical-query surface as designed (the pivot has its own
        # E2E test at tests/trades/test_run_tos_reconciliation_pivot.py).
        conn.execute(
            "UPDATE reconciliation_discrepancies SET "
            "resolution='unresolved', ambiguity_kind=NULL, "
            "resolution_reason=NULL, resolved_at=NULL, resolved_by=NULL"
        )
        conn.commit()
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
        # Phase 12 C.C T-C.6: reset post-pivot resolution back to
        # ``unresolved`` so the test exercises the legacy resolve-CLI
        # path against a pre-pivot row shape (avoids the schema
        # cross-CHECK that forbids journal_corrected from
        # pending_ambiguity_resolution while ambiguity_kind IS NOT NULL).
        conn.execute(
            "UPDATE reconciliation_discrepancies SET "
            "resolution='unresolved', ambiguity_kind=NULL, "
            "resolution_reason=NULL, resolved_at=NULL, resolved_by=NULL"
        )
        conn.commit()
        row = conn.execute(
            "SELECT discrepancy_id, run_id FROM reconciliation_discrepancies "
            "WHERE trade_id IS NOT NULL ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()
        assert row is not None
        did, run_id = row
        before = recon_repo.get_run(conn, run_id)
        # Refresh unresolved_before from the rewrite — the original
        # run-level count was set at pre-pivot time + may be stale.
        unresolved_before = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE run_id=? AND resolution='unresolved'", (run_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE reconciliation_runs SET unresolved_discrepancies_count=? "
            "WHERE run_id=?", (unresolved_before, run_id),
        )
        conn.commit()
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


# ============================================================================
# Sub-bundle D E2E (T-D.3) — sector/industry tamper hardening
# ============================================================================


def test_phase9_bundle_d_e2e_sector_tamper_audit_surfaces_in_cli_list(
    cli_workspace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E for Sub-bundle D per plan §G T-D.3 acceptance criteria.

    1. Seed a cached candidate row for ticker TAMP with sector=Healthcare
       + industry=Biotechnology anchored to today's action_session_for_run(now()).
    2. Operator submits a tamper-attempt entry POST via TestClient with
       sector=Technology (mismatched).
    3. Verify HTTP 400 rejection + a single ``sector_tamper`` discrepancy
       row persists with the spec §3.3.1 JSON shape.
    4. Invoke ``swing journal discrepancy list`` via CLI and verify the
       ``sector_tamper`` row surfaces in the output — confirming the
       full operator-facing audit-trail loop (route emit → CLI surface).

    Note: this test exercises both the web POST + the CLI list surface
    in a single workspace. The cli_workspace fixture provides an
    already-migrated DB at v17; we open the same DB via TestClient +
    via CliRunner sequentially.
    """
    from datetime import datetime as _dt

    from fastapi.testclient import TestClient

    from swing.config import load as load_config
    from swing.evaluation.dates import action_session_for_run
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from tests.web.conftest import full_phase7_entry_payload

    runner, cfg_path, db_path, tmp_path = cli_workspace
    cfg = load_config(cfg_path)
    session_iso = action_session_for_run(_dt.now()).isoformat()

    # ----- §1: Seed the cached candidate row + watchlist row. ----------
    conn = connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO watchlist (ticker, added_date, "
                "last_qualified_date, status, qualification_count, "
                "not_qualified_streak, last_data_asof_date, "
                "entry_target, last_close) VALUES "
                "('TAMP', '2026-04-01', ?, 'watch', 1, 0, ?, "
                "11.0, 10.0)",
                (session_iso, session_iso),
            )
            cur = conn.execute(
                "INSERT INTO evaluation_runs (run_ts, data_asof_date, "
                "action_session_date, finviz_csv_path, "
                "tickers_evaluated, aplus_count, watch_count, "
                "skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0)",
                (f"{session_iso}T08:00:00", session_iso, session_iso),
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO pipeline_runs (started_ts, finished_ts, "
                "trigger, data_asof_date, action_session_date, state, "
                "lease_token, evaluation_run_id) "
                "VALUES (?, ?, 'manual', ?, ?, 'complete', "
                "'tok-d3', ?)",
                (
                    f"{session_iso}T08:00:00",
                    f"{session_iso}T09:00:00",
                    session_iso,
                    session_iso,
                    eval_id,
                ),
            )
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, "
                "bucket, close, pivot, initial_stop, adr_pct, "
                "tight_streak, pullback_pct, prior_trend_pct, "
                "rs_rank, rs_return_12w_vs_spy, rs_method, "
                "pattern_tag, notes, sector, industry) "
                "VALUES (?, 'TAMP', 'watch', 10.0, 10.0, 9.5, 2.0, "
                "5, NULL, NULL, NULL, NULL, 'fallback_spy', NULL, "
                "NULL, 'Healthcare', 'Biotechnology')",
                (eval_id,),
            )
    finally:
        conn.close()

    # ----- §2: Tamper-attempt POST via TestClient. ---------------------
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=10.5, asof=_dt.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    app = create_app(cfg, cfg_path)
    payload = full_phase7_entry_payload(
        ticker="TAMP",
        entry_date="2026-04-26",
        entry_price="10.0",
        shares="1",
        initial_stop="9.0",
        rationale="aplus-setup",
        notes="",
    )
    payload["sector"] = "Technology"  # tampered
    payload["industry"] = "Biotechnology"
    # Phase 9 Bundle D Codex R2 Major #1: the form-render-anchor field
    # carries the cached candidate's evaluation_run_id. POST validates
    # against that exact row so a fresh pipeline run between GET + POST
    # can't false-reject / false-accept.
    payload["sector_industry_evaluation_run_id"] = str(eval_id)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/trades/entry", data=payload,
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 400, (
        f"Expected 400 (sector tamper rejection), got "
        f"{resp.status_code}. Body[:500]: {resp.text[:500]!r}"
    )
    # No trade row inserted (entry POST rejected).
    conn = connect(db_path)
    try:
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker='TAMP'"
        ).fetchone()[0]
        # Audit row + discrepancy persisted.
        runs = conn.execute(
            "SELECT run_id, source, state FROM reconciliation_runs "
            "ORDER BY run_id DESC"
        ).fetchall()
        sector_tamper_disc = conn.execute(
            "SELECT discrepancy_id, ticker, field_name, "
            "material_to_review, resolution "
            "FROM reconciliation_discrepancies "
            "WHERE discrepancy_type='sector_tamper'"
        ).fetchall()
    finally:
        conn.close()
    assert trade_count == 0
    assert len(runs) >= 1
    audit_run = next((r for r in runs if r[1] == "system_audit"), None)
    assert audit_run is not None, runs
    assert audit_run[2] == "completed"
    assert len(sector_tamper_disc) == 1, sector_tamper_disc
    disc_id, disc_ticker, field_name, material, resolution = (
        sector_tamper_disc[0]
    )
    assert disc_ticker == "TAMP"
    assert field_name == "sector"
    assert material == 0  # V1 advisory
    assert resolution == "unresolved"

    # ----- §3: swing journal discrepancy list surfaces the row. ---------
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "journal", "discrepancy", "list",
    ])
    assert r.exit_code == 0, r.output
    # Type column + ticker + field_name surface in the CLI table.
    assert "sector_tamper" in r.output
    assert "TAMP" in r.output
    assert "sector" in r.output

    # --unresolved + --material filters: this row is advisory (mat=0)
    # so --material excludes it; --unresolved includes it.
    r_unres = runner.invoke(main, [
        "--config", str(cfg_path),
        "journal", "discrepancy", "list", "--unresolved",
    ])
    assert r_unres.exit_code == 0, r_unres.output
    assert "sector_tamper" in r_unres.output

    r_mat = runner.invoke(main, [
        "--config", str(cfg_path),
        "journal", "discrepancy", "list", "--material",
    ])
    assert r_mat.exit_code == 0, r_mat.output
    # sector_tamper is material=0 V1 — should NOT appear under --material.
    assert "sector_tamper" not in r_mat.output, (
        f"sector_tamper should be filtered out by --material (V1 "
        f"advisory, material=0). Output: {r_mat.output!r}"
    )
