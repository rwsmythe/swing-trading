"""Soft-warn message surfaces from web exit_post + CLI exit when final exit closes the trade.

Brief §6.2 watch item 4: same message-string from both paths (single constant).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.cli import main
from swing.trades.review import SOFT_WARN_REVIEW_DUE_MESSAGE, soft_warn_review_due_message


def test_soft_warn_message_constant_includes_review_due_text() -> None:
    assert "Review" in SOFT_WARN_REVIEW_DUE_MESSAGE
    assert "7 days" in SOFT_WARN_REVIEW_DUE_MESSAGE


def test_soft_warn_review_due_message_function_uses_cfg_window_days() -> None:
    """Minor 1: soft_warn_review_due_message(n) uses n, not hardcoded 7."""
    msg_7 = soft_warn_review_due_message(7)
    assert "7 days" in msg_7
    assert "Review" in msg_7

    msg_14 = soft_warn_review_due_message(14)
    assert "14 days" in msg_14
    assert "7 days" not in msg_14

    # The constant is the default-7 alias
    assert SOFT_WARN_REVIEW_DUE_MESSAGE == soft_warn_review_due_message(7)


@pytest.fixture
def half_exited_trade_db(tmp_path: Path) -> Path:
    """Tmp DB with one open trade (10 shares total, 5 already exited).
    The remaining 5-share exit closes the trade → soft-warn surfaces.
    """
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import (
        insert_exit_with_event, insert_trade_with_event,
    )
    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        trade_id = insert_trade_with_event(
            conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, status="open", state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        # First partial exit: 5 of 10 shares — trade stays open
        insert_exit_with_event(
            conn, Exit(
                id=None, trade_id=trade_id, exit_date="2026-04-25",
                exit_price=11.5, shares=5, reason="partial",
                realized_pnl=7.5, r_multiple=1.5, notes=None,
            ),
            event_ts="2026-04-25T09:30:00",
        )
    conn.close()
    return db_path


def test_cli_exit_emits_soft_warn_when_final_exit_closes_trade(
    half_exited_trade_db: Path, tmp_path: Path,
) -> None:
    """Final-exit-closes-trade path: CLI emits SOFT_WARN_REVIEW_DUE_MESSAGE."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    # Overwrite db_path in the config to point at the half-exited fixture.
    text = cfg_path.read_text(encoding="utf-8")
    import re
    text = re.sub(
        r'db_path\s*=\s*"[^"]*"',
        f'db_path = "{half_exited_trade_db.as_posix()}"',
        text,
    )
    cfg_path.write_text(text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [
        "--config", str(cfg_path),
        "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-05-02",
        "--exit-price", "12.0", "--shares", "5", "--reason", "manual",
    ])
    assert result.exit_code == 0, result.output
    assert SOFT_WARN_REVIEW_DUE_MESSAGE in result.output


@pytest.fixture
def test_app_half_exited(half_exited_trade_db: Path):
    """FastAPI app bound to the half-exited DB fixture."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.web.app import create_app
    # Load the project's swing.config.toml as a baseline, then point db_path
    # at the half-exited fixture:
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=half_exited_trade_db))
    app = create_app(cfg)
    return app


def test_web_exit_post_surfaces_soft_warn_when_final_exit_closes(
    test_app_half_exited,
) -> None:
    with TestClient(test_app_half_exited) as client:
        response = client.post(
            "/trades/1/exit",
            data={
                "exit_date": "2026-05-02", "exit_price": "12.0",
                "shares": "5", "reason": "manual",
            },
            headers={"HX-Request": "true"},
        )
    assert response.status_code == 200
    # The response should contain the soft-warn fragment text:
    assert "Review due within 7 days" in response.text
