"""22-F T-D1..T-D4 -- one LOUD pin per DECLARED class (plan section 5;
CHARC F-F4 (1), R18).

Each test here is a PIN, not a discriminator: there is no fix, so it passes on
the pre- and post-arc trees by design. What it asserts is LOUDNESS -- a
declared class whose write-side constraint is bypassed still refuses the
object with its own typed message rather than degrading silently. Each pin's
falsifier (a mutation that swallows the refusal and so turns the pin RED) was
run once and is recorded in its commit message.

* T-D1 INV-MODEL (persisted subset): a ``fills`` row planted past its CHECK
  reaches the ``Fill.__post_init__`` mirror on the journal drill-down.
* T-D2 INV-TYPE (caller-constant): ``wilson_ci`` with a non-0.05 alpha.
* T-D3 PROG-TX: ``record_snapshot`` under a caller-held transaction.
* T-D4 C1-13: ``_set_trades_value`` on a trade whose ``entry_intent`` is
  already non-NULL.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event


def _seed_trade_with_entry_fill(db_path: Path) -> int:
    """The journal drill-down world (`tests/web/test_journal_drilldown_route.py`):
    one trade plus its entry fill, written through the production writers."""
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="VIR", entry_date="2026-04-20",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, state="managing",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None, trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-04-20T09:30:00",
                    thesis="breakout", why_now="volume",
                    invalidation_condition="loses 9"),
                event_ts="2026-04-20T09:30:00")
            insert_fill_with_event(
                conn,
                Fill(fill_id=None, trade_id=tid,
                     fill_datetime="2026-04-20T09:30:00", action="entry",
                     quantity=10.0, price=10.0),
                event_ts="2026-04-20T09:30:00")
    finally:
        conn.close()
    return tid


# --- T-D1 -- INV-MODEL pin ---------------------------------------------------

def test_d1_the_drilldown_does_not_read_fill_origin_so_it_cannot_carry_the_pin(
        tmp_path: Path, monkeypatch) -> None:
    """The plan's named route, VERIFIED FIRST (T-D1: "execution verifies this
    route builds Fill models; else pick the route that does"). It builds
    ``Fill`` models, but its reader ``list_fills_for_trade``
    (``repos/fills.py:317-331``) does not SELECT ``fill_origin``, so the model
    takes the default and the planted value never reaches the mirror: 200. No
    repo reader SELECTs the column. The one production path that does is the
    tier-2 split handler (``reconciliation_auto_correct.py:3160-3193``), which
    carries the pin below. This test records the observation, so a future
    reader that starts selecting the column is noticed here."""
    from swing.web import app as app_module
    from swing.web.view_models import trade_chronology

    db_path = tmp_path / "d1.db"
    tid = _seed_trade_with_entry_fill(db_path)
    raw = sqlite3.connect(db_path)
    try:
        raw.execute("PRAGMA ignore_check_constraints = ON")
        raw.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, fill_origin) VALUES (?, '2026-04-21T10:00:00', 'exit', "
            "1.0, 11.0, 'bogus')", (tid,))
        raw.commit()
    finally:
        raw.close()

    # DID-IT-FIRE: the reader the drill-down resolves at call time is counted.
    calls: list[int] = []
    real_reader = trade_chronology.list_fills_for_trade

    def counting_reader(conn, trade_id):
        calls.append(trade_id)
        return real_reader(conn, trade_id)

    monkeypatch.setattr(trade_chronology, "list_fills_for_trade",
                        counting_reader)

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg,
                     paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = app_module.create_app(cfg)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(f"/journal/trades/{tid}")
    assert calls == [tid]
    assert r.status_code == 200


def test_d1_inv_model_pin_a_check_bypassed_fill_origin_is_refused_loudly_on_split(
        tmp_path: Path, monkeypatch) -> None:
    """PIN. A ``fills.fill_origin`` outside its CHECK
    (``0020_phase13_charts_patterns_autofill_usability.sql:395``) can only exist
    if that constraint was bypassed. The one read that hands a persisted
    ``fill_origin`` to a ``Fill`` is the tier-2 ``split_into_partials`` handler:
    it reads the original row's origin (``reconciliation_auto_correct.py:3193``)
    and builds each replacement ``Fill`` with it (``:3263``). The mirror,
    ``Fill.__post_init__`` (``swing/data/models.py:447-448``), refuses the
    value there. The operator sees a typed CLI exit that carries the mirror's
    own message, and the original fill survives on a fresh read."""
    from click.testing import CliRunner

    from swing.cli import main
    from swing.data import models as models_module
    from tests.cli.test_cli_eval import _minimal_config
    from tests.cli.test_discrepancy_resolve_ambiguity_cli import (
        _plant_pending_ambiguity,
        _seed_reconciliation_run,
    )
    from tests.cli.test_discrepancy_resolve_ambiguity_cli import (
        _seed_trade_with_entry_fill as _seed_cli_trade,
    )

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"

    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_cli_trade(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
            resolution_reason="Pass-2 surfaced an ambiguity",
            expected_json=json.dumps({"price": 7.50}),
            actual_json=json.dumps({"_pass2": True}))
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute("UPDATE fills SET fill_origin = 'bogus' WHERE fill_id = ?",
                     (fill_id,))
        conn.commit()
    finally:
        conn.close()

    # DID-IT-FIRE: the mirror the split handler resolves at call time.
    fired: list[str] = []
    real_post_init = models_module.Fill.__post_init__

    def counting_post_init(self):
        fired.append(self.fill_origin)
        return real_post_init(self)

    monkeypatch.setattr(models_module.Fill, "__post_init__",
                        counting_post_init)

    partials = json.dumps([
        {"qty": 20, "price": 7.50, "fill_datetime": "2026-04-27T14:23:00"},
        {"qty": 19, "price": 7.50, "fill_datetime": "2026-04-27T14:24:00"},
    ])
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve-ambiguity",
        str(did), "--choice", "split_into_partials",
        "--custom-value", partials, "--reason", "pin T-D1"])
    assert "bogus" in fired
    assert r.exit_code != 0
    assert r.exception is None or isinstance(r.exception, SystemExit), (
        repr(r.exception))
    assert "fill_origin must be one of" in r.output

    fresh = sqlite3.connect(db_path)
    try:
        assert fresh.execute(
            "SELECT fill_id, fill_origin FROM fills WHERE trade_id = ?",
            (trade_id,)).fetchall() == [(fill_id, "bogus")]
    finally:
        fresh.close()


# --- T-D2 -- INV-TYPE pin ----------------------------------------------------

def test_d2_inv_type_pin_a_non_default_alpha_is_refused_naming_the_supported_one(
        ) -> None:
    """PIN. Every swing/ caller of ``wilson_ci`` passes no ``alpha`` (the
    default 0.05; caller lines quoted in the executing ledger, R46), so the
    ``_z_for_alpha`` refusal (``honesty.py:188``) is caller-constant; the pin
    proves it stays LOUD if a caller ever passes another value."""
    from swing.metrics.honesty import wilson_ci

    with pytest.raises(NotImplementedError, match=r"alpha=0\.05"):
        wilson_ci(k=1, n=2, alpha=0.10)


# --- T-D3 -- PROG-TX pin -----------------------------------------------------

def test_d3_prog_tx_pin_record_snapshot_refuses_a_caller_held_transaction(
        tmp_path: Path) -> None:
    """PIN. Operator roots open a fresh connection and hold no transaction
    when calling (the PROG-TX write-side constraint, root ``connect`` lines in
    the executing ledger), so a CliRunner-level variant is not constructible;
    the service-level refusal is pinned LOUD, with nothing written."""
    from swing.trades.account_equity_snapshots import (
        CallerHeldTransactionError,
        record_snapshot,
    )

    db_path = tmp_path / "d3.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN")
        assert conn.in_transaction
        with pytest.raises(CallerHeldTransactionError,
                           match="caller MUST NOT hold an open transaction"):
            record_snapshot(conn, equity_dollars=1000.0,
                            snapshot_date="2026-09-24")
        conn.rollback()
    finally:
        conn.close()
    fresh = sqlite3.connect(db_path)
    try:
        assert fresh.execute(
            "SELECT COUNT(*) FROM account_equity_snapshots").fetchone() == (0,)
    finally:
        fresh.close()


# --- T-D4 -- C1-13 pin -------------------------------------------------------

def test_d4_c1_13_pin_set_trades_value_on_an_already_assigned_trade_raises(
        tmp_path: Path) -> None:
    """PIN. ``assign`` runs ``_set_trades_value`` inside its one ``BEGIN
    IMMEDIATE`` after ``preflight`` re-ran (SERVICE-prevented, weaker than
    schema-prevented). With that bypassed -- the value planted raw -- the
    guarded UPDATE touches zero rows and refuses LOUDLY; nothing moves."""
    from swing.trades.entry_intent_assignment import _set_trades_value

    db_path = tmp_path / "d4.db"
    tid = _seed_trade_with_entry_fill(db_path)
    raw = sqlite3.connect(db_path)
    try:
        raw.execute("UPDATE trades SET entry_intent = 'standard' WHERE id = ?",
                    (tid,))
        raw.commit()
    finally:
        raw.close()

    conn = connect(db_path)
    try:
        with pytest.raises(RuntimeError, match="touched 0 rows"):
            _set_trades_value(conn, tid)
        conn.rollback()
    finally:
        conn.close()
    fresh = sqlite3.connect(db_path)
    try:
        assert fresh.execute("SELECT entry_intent FROM trades WHERE id = ?",
                             (tid,)).fetchone() == ("standard",)
    finally:
        fresh.close()
