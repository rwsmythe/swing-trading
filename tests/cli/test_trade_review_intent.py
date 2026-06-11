"""Task 4 (tuition-vs-error): `swing trade review --entry-intent` correction.

The review CLI gains an OPTIONAL ``--entry-intent`` correction flag. When
passed, the persisted ``entry_intent`` is set via the dedicated
``update_entry_intent`` writer (in its OWN transaction, NOT widening
``complete_trade_review``). Omitting the flag leaves the previously-persisted
value untouched.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    import tomllib

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    return runner, cfg, db_path


def _seed_closed_trade(db_path: Path, *, entry_intent: str | None = None) -> int:
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None,
                    ticker="VIR",
                    entry_date="2026-04-20",
                    entry_price=10.0,
                    initial_shares=10,
                    initial_stop=9.0,
                    current_stop=9.0,
                    state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                    trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-04-20T09:30:00",
                    entry_intent=entry_intent,
                ),
                event_ts="2026-04-20T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None,
                    trade_id=trade_id,
                    fill_datetime="2026-04-20T09:30:00",
                    action="entry",
                    quantity=10.0,
                    price=10.0,
                ),
                event_ts="2026-04-20T09:30:00",
                rationale="seed-entry",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None,
                    trade_id=trade_id,
                    fill_datetime="2026-04-25T09:30:00",
                    action="exit",
                    quantity=10.0,
                    price=11.5,
                ),
                event_ts="2026-04-25T09:30:00",
                rationale="seed-exit",
            )
            conn.execute(
                "UPDATE trades SET state = 'closed' WHERE id = ?", (trade_id,),
            )
    finally:
        conn.close()
    return trade_id


def test_cli_command_exposes_entry_intent_option() -> None:
    # Discriminator (static): fails PRE-Task-4 (no such param), passes POST.
    from swing.cli import trade_review_cmd
    assert "entry_intent" in {p.name for p in trade_review_cmd.params}


def test_cli_review_intent_corrects(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path, entry_intent=None)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--entry-intent", "standard"])
    assert res.exit_code == 0, res.output
    assert connect(db_path).execute(
        "SELECT entry_intent FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] == "standard"


def test_cli_review_omitted_intent_leaves_persisted(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    # Previously-persisted value: 'hypothesis_test_by_design'.
    trade_id = _seed_closed_trade(
        db_path, entry_intent="hypothesis_test_by_design",
    )
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean"])
    assert res.exit_code == 0, res.output
    # Omitted flag -> no call -> persisted value unchanged.
    assert connect(db_path).execute(
        "SELECT entry_intent FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] == "hypothesis_test_by_design"
