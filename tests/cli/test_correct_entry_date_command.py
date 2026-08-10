"""CLI: `swing journal correct-entry-date` (item-5 T2).

Pins the three things a service-level test cannot see:

  - the command is REGISTERED on the flat `journal` group (there is no
    `journal trade` subgroup; a command written under one could not have been
    registered at all);
  - a service refusal surfaces as a clean `ClickException`, not a traceback;
  - the success path prints the ready-to-paste follow-up command with the REAL
    correction id substituted and NO `<placeholder>` -- without which the
    operator would compose an audit sentence by hand under a live-ledger gate,
    and a literal `<correction_id>` would land in the ledger.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config

PRE_DATE = "2026-07-23"
TARGET_DATE = "2026-07-31"


def _setup(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"; project.mkdir(parents=True)
    home = tmp_path / "home"; home.mkdir(parents=True)
    cfg = _minimal_config(project, home)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    return runner, cfg, home / "swing-data" / "swing.db"


def _seed(db_path: Path, *, trade_state: str = "closed") -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at, current_size, current_avg_cost, "
            "last_fill_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("FTRE", PRE_DATE, 18.8, 10, 16.554, 16.554, trade_state,
             "pipeline_watch_manual", f"{PRE_DATE}T16:00:00", 0.0, 18.8,
             "2026-08-04T16:00:00"),
        )
        trade_id = int(cur.lastrowid)
        fcur = conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status, fill_origin, "
            "schwab_source_value_json) VALUES (?,?,?,?,?,?,?,?)",
            (trade_id, f"{PRE_DATE}T16:00:00", "entry", 10.0, 18.8,
             "unreconciled", "schwab_auto",
             # The REAL production envelope. Its `schwab_order_id` is what
             # binds the discrepancy's evidence to THIS fill -- an unrelated
             # same-ticker same-size order is not evidence about a fill it did
             # not produce.
             json.dumps({
                 "entry_date": PRE_DATE,
                 "entry_date_source": "enter_time",
                 "entry_price": 18.8,
                 "schwab_instrument_symbol": "FTRE",
                 "schwab_order_id": "1007308870656",
                 "shares": 10,
             }, sort_keys=True)),
        )
        fill_id = int(fcur.lastrowid)
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES (?,?,?,?,?,?)",
            (trade_id, "2026-08-04T16:00:00", "stop", 10.0, 18.4,
             "unreconciled"),
        )
        conn.execute(
            "INSERT INTO watchlist_archive (ticker, added_date, removed_date, "
            "reason, qualification_count) VALUES ('FTRE','2026-06-30',?, "
            "'entered', 19)", (PRE_DATE,),
        )
        rcur = conn.execute(
            "INSERT INTO reconciliation_runs (source, started_ts, state) "
            "VALUES ('schwab_api','2026-08-01T03:41:00','completed')",
        )
        run_id = int(rcur.lastrowid)
        dcur = conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, trade_id, fill_id, ticker, field_name, "
            "expected_value_json, actual_value_json, delta_text, "
            "material_to_review, resolution, ambiguity_kind, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "entry_price_mismatch", trade_id, fill_id, "FTRE",
             "price", json.dumps({"price": 18.8}),
             json.dumps({
                 "candidate_count": 1,
                 "execution_legs": [{
                     "leg_id": 1, "price": 18.8, "quantity": 10.0,
                     "time": "2026-07-31T13:30:05+0000",
                 }],
                 "execution_sessions_from_fill": 6,
                 # The BUY side is load-bearing: a SELL-side execution is
                 # evidence about an EXIT and must never date an entry.
                 "execution_side": "BUY",
                 "price": 18.8,
                 "schwab_order_id": "1007308870656",
                 "schwab_order_price": 18.89,
             }, sort_keys=True),
             "$+0.0000 (schwab execution minus journal)", 1,
             "pending_ambiguity_resolution", "multi_match_within_window",
             "2026-08-01T03:41:06.772"),
        )
        conn.commit()
        return {
            "trade_id": trade_id, "fill_id": fill_id,
            "discrepancy_id": int(dcur.lastrowid),
        }
    finally:
        conn.close()


def _args(cfg, ids, *extra):
    return [
        "--config", str(cfg), "journal", "correct-entry-date",
        str(ids["trade_id"]), "--to", TARGET_DATE,
        "--discrepancy", str(ids["discrepancy_id"]),
        "--reason", "RD ruling 20260801T145327Z part 3.", *extra,
    ]


def test_the_command_is_registered_on_the_flat_journal_group(tmp_path, monkeypatch):
    runner, cfg, _ = _setup(tmp_path, monkeypatch)
    r = runner.invoke(main, ["--config", str(cfg), "journal", "--help"])
    assert r.exit_code == 0, r.output
    assert "correct-entry-date" in r.output


def test_success_prints_the_real_id_and_the_pasteable_follow_up(
    tmp_path, monkeypatch,
):
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, _args(cfg, ids))
    assert r.exit_code == 0, r.output

    conn = sqlite3.connect(db)
    try:
        cid = conn.execute(
            "SELECT correction_id FROM reconciliation_corrections",
        ).fetchone()[0]
        assert conn.execute(
            "SELECT entry_date, pre_trade_locked_at FROM trades WHERE id = ?",
            (ids["trade_id"],),
        ).fetchone() == (TARGET_DATE, f"{PRE_DATE}T16:00:00")
    finally:
        conn.close()

    assert f"correction {cid} applied" in r.output
    assert f"under correction {cid}" in r.output
    assert "<" not in r.output
    assert "swing journal discrepancy resolve" in r.output
    assert "--resolution journal_corrected" in r.output
    # A non-ASCII glyph in a CLI string crashes Windows cp1252 stdout, and
    # capsys hides it; assert the bytes the OS encoder would see.
    r.output.encode("cp1252")


def test_a_service_refusal_surfaces_as_a_clean_click_error(
    tmp_path, monkeypatch,
):
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "correct-entry-date",
        str(ids["trade_id"]), "--to", "2026-08-03",
        "--discrepancy", str(ids["discrepancy_id"]), "--reason", "typo",
    ])
    assert r.exit_code != 0
    assert "SERVER-DERIVED" in r.output
    assert "Traceback" not in r.output


def test_dry_run_prints_before_and_after_and_writes_nothing(
    tmp_path, monkeypatch,
):
    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db)
    r = runner.invoke(main, _args(cfg, ids, "--dry-run"))
    assert r.exit_code == 0, r.output
    assert "DRY RUN" in r.output
    assert "trades.entry_date" in r.output
    assert f"{PRE_DATE} -> {TARGET_DATE}" in r.output
    # It shows what it knows and SAYS what it does not.
    assert "(recomputed on apply)" in r.output
    assert "pre_trade_locked_at stays at" in r.output
    r.output.encode("cp1252")

    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
        ).fetchone()[0] == PRE_DATE
        assert conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections",
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_an_active_trade_refusal_prints_the_whole_inventory(
    tmp_path, monkeypatch,
):
    from swing.trades.entry_date_correction import ACTIVE_TRADE_CONSEQUENCES

    runner, cfg, db = _setup(tmp_path, monkeypatch)
    ids = _seed(db, trade_state="managing")
    r = runner.invoke(main, _args(cfg, ids))
    assert r.exit_code != 0
    for item in ACTIVE_TRADE_CONSEQUENCES:
        assert item in r.output
    r.output.encode("cp1252")

    r2 = runner.invoke(main, _args(cfg, ids, "--allow-active"))
    assert r2.exit_code == 0, r2.output
    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
        ).fetchone()[0] == TARGET_DATE
    finally:
        conn.close()
