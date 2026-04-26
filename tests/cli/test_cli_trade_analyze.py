"""CLI: `swing trade analyze <trade_id>` — per-trade retrospective output.

Brief: `docs/trade-analyze-cli-brief.md` §4.2. Tests cover the same branching
as the compute layer, focused here on the operator-facing rendered text.
"""
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun, Exit, Trade
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def _db_path_from_cfg(cfg_path: Path) -> Path:
    cfg_data = tomllib.loads(cfg_path.read_text())
    return Path(cfg_data["paths"]["db_path"])


def _watch_candidate(
    ticker: str, *, pivot: float, close: float, initial_stop: float = 8.0,
) -> Candidate:
    base = (
        CriterionResult("TT1_above_150_200", "trend_template", "pass",
                        "close=10.75 150MA=7.00 200MA=6.53", "close > MAs"),
        CriterionResult("proximity_20ma", "vcp", "fail", "+15.38%", "<= 5.0%"),
        CriterionResult("tightness", "vcp", "fail", "0 day streak", ">= 2 days"),
        CriterionResult("risk_feasibility", "risk", "pass",
                        "2 sh, $6.08 risk", ">= 1 share"),
    )
    return Candidate(
        ticker=ticker, bucket="watch", close=close, pivot=pivot,
        initial_stop=initial_stop, adr_pct=5.0, tight_streak=0,
        pullback_pct=0.0, prior_trend_pct=96.0, rs_rank=None,
        rs_return_12w_vs_spy=0.5, rs_method="fallback_spy",
        pattern_tag=None, notes=None, criteria=base,
    )


def _seed_vir_like_trade(cfg_path: Path) -> int:
    """Seed a VIR-like closed trade with one pre-entry watch recommendation
    + a single full-share stop-hit exit. Returns the trade id."""
    db_path = _db_path_from_cfg(cfg_path)
    conn = ensure_schema(db_path)
    try:
        run = EvaluationRun(
            id=None, run_ts="2026-04-19T18:47:34",
            data_asof_date="2026-04-17", action_session_date="2026-04-20",
            finviz_csv_path=None, tickers_evaluated=1,
            aplus_count=0, watch_count=1, skip_count=0,
            excluded_count=0, error_count=0,
        )
        with conn:
            run_id = insert_evaluation_run(conn, run)
            insert_candidates(conn, run_id, [
                _watch_candidate("VIR", pivot=10.76, close=10.75,
                                 initial_stop=8.26),
            ])
        trade = Trade(
            id=None, ticker="VIR", entry_date="2026-04-20",
            entry_price=11.30, initial_shares=2, initial_stop=8.26,
            current_stop=8.26, status="open",
            watchlist_entry_target=10.76, watchlist_initial_stop=8.26,
            notes="trade test",
            hypothesis_label="sub-A+ VCP-not-formed test",
        )
        with conn:
            tid = insert_trade_with_event(
                conn, trade, event_ts="2026-04-20T09:30:00", rationale=None,
            )
        ex = Exit(
            id=None, trade_id=tid, exit_date="2026-04-24", exit_price=10.30,
            shares=2, reason="stop-hit", realized_pnl=-2.0,
            r_multiple=-0.32894737, notes=None,
        )
        with conn:
            insert_exit_with_event(
                conn, ex, event_ts="2026-04-24T16:00:00", rationale=None,
            )
        return tid
    finally:
        conn.close()


def _seed_manual_trade(cfg_path: Path, *, hypothesis: str | None = None) -> int:
    """Seed a manually-sourced (no candidate row) open trade."""
    db_path = _db_path_from_cfg(cfg_path)
    conn = ensure_schema(db_path)
    try:
        trade = Trade(
            id=None, ticker="ZZZ", entry_date="2026-04-20",
            entry_price=50.0, initial_shares=10, initial_stop=45.0,
            current_stop=45.0, status="open",
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, hypothesis_label=hypothesis,
        )
        with conn:
            return insert_trade_with_event(
                conn, trade, event_ts="2026-04-20T09:30:00", rationale=None,
            )
    finally:
        conn.close()


# --- happy path: VIR-like trade ----------------------------------------------


def test_analyze_renders_full_sections_for_vir_like(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    tid = _seed_vir_like_trade(cfg)

    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", str(tid)])
    assert r.exit_code == 0, r.output
    out = r.output

    assert "VIR" in out
    assert f"TRADE #{tid}" in out
    assert "Status: closed" in out
    assert "$11.30" in out
    assert "Initial stop: $8.26" in out
    assert "Hypothesis: sub-A+ VCP-not-formed test" in out
    assert "RECOMMENDATIONS" in out
    assert "bucket=watch" in out
    # Failed criteria called out by name + value
    assert "proximity_20ma" in out
    assert "tightness" in out
    # Exit + outcomes
    assert "EXITS" in out
    assert "stop-hit" in out
    assert "DEVIATIONS" in out
    # 5.02% above pivot — single decimal place is enough for the operator
    assert "5.0" in out  # don't pin format too tight
    assert "OUTCOMES" in out
    assert "-$2.00" in out or "$-2.00" in out
    # Hold duration: 2026-04-20 to 2026-04-24 = 4 days
    assert "Hold duration" in out
    assert "4 days" in out


# --- manually-sourced trade graceful handling --------------------------------


def test_analyze_renders_manually_sourced_trade(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    tid = _seed_manual_trade(cfg, hypothesis="manual")

    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", str(tid)])
    assert r.exit_code == 0, r.output
    out = r.output

    # Sentinel text per brief §4.2 — operator should see a clear reason there
    # are no recs, not a silent empty section.
    assert "MANUALLY-SOURCED" in out
    # Deviations section either omitted or marked "N/A" — never crash on None
    assert "DEVIATIONS" not in out or "N/A" in out
    # Open trade with no exits → no realized P&L reported as a number
    assert "OUTCOMES" in out
    assert "Hypothesis: manual" in out


def test_analyze_renders_partial_exit_open_trade_with_ongoing_duration(tmp_path: Path):
    """Adversarial R2 M2: a partial exit on an open trade must NOT render
    'entry to last exit' duration — the position is still live. The CLI
    should label the duration as ongoing and surface the last partial
    exit date separately."""
    runner, cfg = _setup(tmp_path)
    db_path = _db_path_from_cfg(cfg)
    conn = ensure_schema(db_path)
    try:
        trade = Trade(
            id=None, ticker="AAA", entry_date="2026-04-15",
            entry_price=100.0, initial_shares=10, initial_stop=95.0,
            current_stop=95.0, status="open",
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, hypothesis_label=None,
        )
        with conn:
            tid = insert_trade_with_event(
                conn, trade, event_ts="2026-04-15T09:30:00", rationale=None,
            )
        # Partial exit: 4 of 10 shares. Trade remains open.
        ex = Exit(
            id=None, trade_id=tid, exit_date="2026-04-18",
            exit_price=110.0, shares=4, reason="target",
            realized_pnl=40.0, r_multiple=2.0, notes=None,
        )
        with conn:
            insert_exit_with_event(
                conn, ex, event_ts="2026-04-18T16:00:00", rationale=None,
            )
    finally:
        conn.close()

    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", str(tid)])
    assert r.exit_code == 0, r.output
    out = r.output
    # "ongoing" + "last partial exit 2026-04-18" markers, NOT "entry to last exit"
    assert "ongoing" in out
    assert "last partial exit 2026-04-18" in out
    assert "trade still open" in out
    assert "(entry to last exit)" not in out


def test_analyze_renders_null_hypothesis_label_as_none(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    tid = _seed_manual_trade(cfg, hypothesis=None)

    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", str(tid)])
    assert r.exit_code == 0, r.output
    assert "Hypothesis: (none)" in r.output


def test_analyze_null_notes_renders_as_none(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    tid = _seed_manual_trade(cfg, hypothesis=None)
    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", str(tid)])
    assert r.exit_code == 0
    assert "Notes: (none)" in r.output


# --- error / input handling --------------------------------------------------


def test_analyze_missing_trade_exits_nonzero(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", "999"])
    assert r.exit_code != 0
    assert "999" in r.output or "not found" in r.output.lower()


def test_analyze_cli_runs_in_query_only_mode(tmp_path: Path, monkeypatch):
    """Adversarial M2: read-only safety should be technically enforced, not
    just behaviorally trusted. The CLI must set PRAGMA query_only on the
    connection so a future write bug in the compute path raises rather than
    silently mutating the production DB."""
    runner, cfg = _setup(tmp_path)
    tid = _seed_vir_like_trade(cfg)

    # Patch analyze_trade to attempt a write and verify SQLite refuses it.
    import swing.journal.analyze as analyze_mod

    real_analyze = analyze_mod.analyze_trade
    captured: dict[str, object] = {}

    def attempt_write(conn, trade_id):
        try:
            conn.execute(
                "UPDATE trades SET notes='SHOULD NOT PERSIST' WHERE id=?",
                (trade_id,),
            )
        except sqlite3.OperationalError as e:
            captured["write_blocked"] = str(e)
        return real_analyze(conn, trade_id)

    monkeypatch.setattr("swing.cli.analyze_trade", attempt_write, raising=False)
    # The CLI imports `analyze_trade` lazily inside the command body, so the
    # patch needs to sit on the module the command imports from.
    monkeypatch.setattr(analyze_mod, "analyze_trade", attempt_write)

    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze", str(tid)])
    assert r.exit_code == 0, r.output
    assert "write_blocked" in captured, (
        "PRAGMA query_only did not block the UPDATE — read-only enforcement is missing."
    )

    # Confirm the trades.notes was NOT mutated.
    db_path = _db_path_from_cfg(cfg)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT notes FROM trades WHERE id=?", (tid,),
        ).fetchone()
        assert row[0] != "SHOULD NOT PERSIST"
    finally:
        conn.close()


def test_analyze_non_int_trade_id_rejected(tmp_path: Path):
    """SQL-injection guard via click int parsing."""
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "trade", "analyze",
                             "1; DROP TABLE trades;--"])
    assert r.exit_code != 0
    # Click rejects with a usage error before the command body runs
    assert "invalid value" in r.output.lower() or "is not a valid integer" in r.output.lower()
    # Verify trades table still exists
    db_path = _db_path_from_cfg(cfg)
    conn = sqlite3.connect(db_path)
    try:
        cnt = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
        ).fetchone()
        assert cnt is not None
    finally:
        conn.close()
