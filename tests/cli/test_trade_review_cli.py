"""Click integration tests for swing trade review.

Phase 7 Sub-B B.6 fixture migration: legacy ``Exit(...)``+``insert_exit_with_event``
seeding rewritten to ``Fill(action='exit')``+``insert_fill_with_event`` (the
``Exit`` dataclass is a stub post Sub-A T3 and raises on construction).

Phase 7 Sub-B B.7 unskip: ``swing/cli.py`` now reads ``trade.state`` (predicate
``state != 'closed'``) and routes review-completion through
``complete_trade_review`` so the trade transitions to ``state='reviewed'``
atomically with the review-fields write.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    """Create a minimal config + migrated DB. Returns (runner, cfg_path, db_path)."""
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


def _seed_closed_trade(db_path: Path) -> int:
    """Seed a closed VIR trade with entry+exit fills. Returns the trade_id."""
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
            conn.execute("UPDATE trades SET state = 'closed' WHERE id = ?", (trade_id,))
    finally:
        conn.close()
    return trade_id


def test_review_persists_all_ten_fields(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        "--mistake-tags", "CHASED",
        "--mistake-tags", "FOMO",
        "--entry-grade", "C",
        "--management-grade", "B",
        "--exit-grade", "B",
        "--realized-r-if-plan-followed", "2.0",
        "--mistake-cost-confidence", "medium",
        "--lesson-learned", "Wait for the breakout, not the build-up.",
    ])
    assert result.exit_code == 0, result.output

    # Verify persistence via direct SQL
    from swing.data.db import connect
    conn = connect(db_path)
    row = conn.execute(
        "SELECT reviewed_at, mistake_tags, entry_grade, process_grade, "
        "realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned "
        "FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    conn.close()

    assert row[0] is not None  # reviewed_at populated
    tags = json.loads(row[1])
    assert tags == ["CHASED", "FOMO"]  # canonicalized + sorted
    assert row[2] == "C"
    # process grade: entry=C(2), management=B(3), exit=B(3), disqualifying=False
    # weighted = 0.40*2 + 0.35*3 + 0.25*3 = 0.80 + 1.05 + 0.75 = 2.60 → C bucket [2.00, 2.75)
    assert row[3] == "C"
    assert row[4] == 2.0
    assert row[5] == "medium"
    assert "breakout" in row[6]


def test_review_list_flag_shows_pending_trades(tmp_path: Path) -> None:
    """R1 Major 2: brief §3.1 contract is `swing trade review --list`.

    Single command with `--list` flag, NOT a separate `review-list` subcommand.
    """
    runner, cfg, db_path = _setup(tmp_path)
    _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review", "--list",
    ])
    assert result.exit_code == 0, result.output
    assert "VIR" in result.output


def test_review_without_trade_id_or_list_flag_errors(tmp_path: Path) -> None:
    """Missing `--trade-id` AND missing `--list` flag → UsageError."""
    runner, cfg, db_path = _setup(tmp_path)

    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "review",
    ])
    assert result.exit_code != 0
    assert "trade-id" in result.output.lower() or "list" in result.output.lower()


def test_review_unknown_mistake_tag_rejected(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        "--mistake-tags", "NOT_REAL",
        "--entry-grade", "A",
        "--management-grade", "A",
        "--exit-grade", "A",
        "--lesson-learned", "n/a",
    ])
    assert result.exit_code != 0
    assert "unknown mistake tag" in result.output.lower()


def _seed_recently_closed_trade(db_path: Path) -> int:
    """Seed a trade closed YESTERDAY (within the 7-day window). Returns trade_id."""
    from datetime import date, timedelta
    conn = ensure_schema(db_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None,
                    ticker="RECENT",
                    entry_date="2026-04-01",
                    entry_price=10.0,
                    initial_shares=10,
                    initial_stop=9.0,
                    current_stop=9.0,
                    state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                    trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-04-01T09:30:00",
                ),
                event_ts="2026-04-01T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None,
                    trade_id=trade_id,
                    fill_datetime="2026-04-01T09:30:00",
                    action="entry",
                    quantity=10.0,
                    price=10.0,
                ),
                event_ts="2026-04-01T09:30:00",
                rationale="seed-entry",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None,
                    trade_id=trade_id,
                    fill_datetime=f"{yesterday}T09:30:00",
                    action="exit",
                    quantity=10.0,
                    price=11.5,
                ),
                event_ts=f"{yesterday}T09:30:00",
                rationale="seed-exit",
            )
            conn.execute("UPDATE trades SET state = 'closed' WHERE id = ?", (trade_id,))
    finally:
        conn.close()
    return trade_id


def test_review_list_shows_recently_closed_trades(tmp_path: Path) -> None:
    """Major 1: --list shows ALL closed-unreviewed, including trades within the window."""
    runner, cfg, db_path = _setup(tmp_path)
    _seed_recently_closed_trade(db_path)  # trade closed yesterday (within 7-day window)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review", "--list",
    ])
    assert result.exit_code == 0, result.output
    # A trade closed yesterday must appear in the list even though it's within the window:
    assert "RECENT" in result.output


def test_review_empty_mistake_tags_rejected(tmp_path: Path) -> None:
    """Major 2: empty mistake_tags must be rejected — operator must use 'none_observed'."""
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        # No --mistake-tags at all
        "--entry-grade", "A",
        "--management-grade", "A",
        "--exit-grade", "A",
        "--lesson-learned", "n/a",
    ])
    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert "mistake" in output_lower or "tag" in output_lower


# ---------------------------------------------------------------------------
# B.7 — discriminating tests
# ---------------------------------------------------------------------------


def test_review_transitions_state_closed_to_reviewed(tmp_path: Path) -> None:
    """B.7: review-completion routes through ``complete_trade_review`` so the
    trade transitions ``closed → reviewed`` atomically with the review-fields
    write.

    Pre-fix (direct ``update_trade_review_fields``): trades.state stayed
    ``'closed'`` after review; only ``reviewed_at`` was populated.
    Post-fix (service-routed): trades.state == ``'reviewed'`` AND a
    ``state_transition`` row lands in trade_events.
    """
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        "--mistake-tags", "none_observed",
        "--entry-grade", "A",
        "--management-grade", "A",
        "--exit-grade", "A",
        "--lesson-learned", "Followed the plan.",
    ])
    assert result.exit_code == 0, result.output

    from swing.data.db import connect
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT state FROM trades WHERE id = ?", (trade_id,),
        ).fetchone()
        assert row[0] == "reviewed", (
            f"trade.state should be 'reviewed' after review-completion; got {row[0]!r}"
        )
        # state_transition writes a 'note' event with notes='state_transition closed->reviewed'
        ev = conn.execute(
            "SELECT notes FROM trade_events WHERE trade_id = ? "
            "AND event_type = 'note' "
            "AND notes LIKE 'state_transition closed->reviewed%'",
            (trade_id,),
        ).fetchone()
        assert ev is not None, (
            "complete_trade_review should record a state_transition audit event"
        )
    finally:
        conn.close()


def test_review_rejects_already_reviewed_trade(tmp_path: Path) -> None:
    """B.7: cli.py review precondition is ``state != 'closed'`` (NOT
    ``state not in ('closed', 'reviewed')``). An already-reviewed trade
    must be rejected.

    Pre-fix (naïve ``state not in ('closed','reviewed')``): would re-review.
    Post-fix (``state != 'closed'``): raises ClickException.
    """
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    # Flip the trade to the reviewed state directly (simulates a prior review).
    from swing.data.db import connect
    conn = connect(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE trades SET state = 'reviewed' WHERE id = ?", (trade_id,),
            )
    finally:
        conn.close()

    result = runner.invoke(main, [
        "--config", str(cfg),
        "trade", "review",
        "--trade-id", str(trade_id),
        "--mistake-tags", "none_observed",
        "--entry-grade", "A",
        "--management-grade", "A",
        "--exit-grade", "A",
        "--lesson-learned", "n/a",
    ])
    assert result.exit_code != 0
    assert "not closed" in result.output.lower()


def test_cli_valid_failure_mode_persists(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--failure-mode", "thesis_invalidated"])
    assert res.exit_code == 0, res.output
    from swing.data.db import connect
    assert connect(db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] == "thesis_invalidated"


def test_cli_command_exposes_failure_mode_option() -> None:
    # Discriminator (regression-arithmetic, Codex R3 #2): the omitted-option test
    # below would pass PRE-B6 too (the existing CLI completes review + leaves the
    # column NULL), so it cannot distinguish on its own. This static check fails
    # PRE-B6 (no such param) and passes POST-B6.
    from swing.cli import trade_review_cmd
    assert "failure_mode" in {p.name for p in trade_review_cmd.params}


def test_cli_omitted_failure_mode_persists_null(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean"])
    assert res.exit_code == 0, res.output
    from swing.data.db import connect
    assert connect(db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] is None  # regression guard (omitted -> NULL)


def test_cli_invalid_failure_mode_is_clean_clickexception(tmp_path: Path) -> None:
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--failure-mode", "not_a_token"])
    # Discriminator (Codex R3 #2): PRE-B6 Click raises "No such option:
    # --failure-mode" -> exit code 2 + that message. POST-B6 the explicit
    # membership check raises click.ClickException -> exit code 1 + the planned
    # "Invalid --failure-mode" message. Assert the EXACT post-fix shape so the
    # pre-fix UsageError does NOT satisfy it.
    assert res.exit_code == 1
    assert "Invalid --failure-mode" in res.output


def test_cli_empty_string_failure_mode_normalizes_to_null(tmp_path: Path) -> None:
    # L5 parity (Codex R1 MAJOR): an explicit `--failure-mode ""` is "no
    # attribution" -> NULL, NOT an invalid-token error. PRE-FIX: the membership
    # check rejects "" -> exit 1 "Invalid --failure-mode". POST-FIX: `... or None`
    # normalizes "" -> None -> exit 0 + NULL persisted.
    runner, cfg, db_path = _setup(tmp_path)
    trade_id = _seed_closed_trade(db_path)
    res = runner.invoke(main, [
        "--config", str(cfg), "trade", "review", "--trade-id", str(trade_id),
        "--entry-grade", "A", "--management-grade", "A", "--exit-grade", "A",
        "--mistake-tags", "none_observed", "--lesson-learned", "clean",
        "--failure-mode", ""])
    assert res.exit_code == 0, res.output
    from swing.data.db import connect
    assert connect(db_path).execute(
        "SELECT failure_mode FROM trades WHERE id=?",
        (trade_id,)).fetchone()[0] is None
