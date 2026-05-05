"""CLI: `swing trade entry` pre-fills --hypothesis from active recommendation.

Frontend brief §4.3: when the operator names a ticker that has an active
hypothesis match in the latest pipeline run, the CLI auto-fills the
--hypothesis flag with the matcher's suggested label and prints what was
chosen. Explicit --hypothesis still wins as an override; tickers with no
match proceed without pre-fill (current behavior preserved).
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from tests.cli.test_cli_eval import _minimal_config
from tests.conftest import cli_entry_pre_trade_args


def _setup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def _seed_aplus_pipeline(cfg_path: Path, ticker: str) -> None:
    """Seed a complete pipeline run with one A+ candidate for `ticker`."""
    import tomllib
    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def _read_hypothesis_label(cfg_path: Path, ticker: str) -> str | None:
    import tomllib
    from swing.data.repos.trades import find_any_open_trade
    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        t = find_any_open_trade(conn, ticker=ticker)
        return t.hypothesis_label if t is not None else None
    finally:
        conn.close()


def test_entry_pre_fills_hypothesis_from_active_recommendation(tmp_path: Path):
    """Ticker has an active A+ recommendation → --hypothesis auto-fills with
    the suggested label, which starts with the canonical hypothesis name."""
    runner, cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="AAPL")

    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    # Operator-visible signal that pre-fill happened.
    assert "Pre-filled --hypothesis" in result.output
    label = _read_hypothesis_label(cfg, "AAPL")
    assert label is not None
    # Brief §0 + Session 1 R1 fix: pre-fill default value MUST start with
    # the canonical hypothesis name so future tripwire/progress
    # aggregation (case-insensitive prefix) attributes the trade correctly.
    assert label.lower().startswith("a+ baseline"), (
        f"pre-fill must preserve canonical prefix; got {label!r}"
    )


def test_entry_explicit_hypothesis_wins_over_pre_fill(tmp_path: Path):
    """When operator passes --hypothesis explicitly, it overrides the
    pre-fill — even when a recommendation exists for the ticker."""
    runner, cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="AAPL")

    explicit = "Operator-overridden hypothesis label"
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        "--hypothesis", explicit,
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    # Pre-fill message must NOT appear when explicit override is in play.
    assert "Pre-filled --hypothesis" not in result.output
    assert _read_hypothesis_label(cfg, "AAPL") == explicit


def test_entry_no_recommendation_no_prefill(tmp_path: Path):
    """Ticker has no active recommendation → no pre-fill, no message,
    label stored as NULL (preserves Session 1 / pre-existing behavior)."""
    runner, cfg = _setup(tmp_path)
    # No candidate seeded — pipeline_runs has zero rows, so the prefill
    # lookup returns no candidates.
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "ZZZ", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    assert "Pre-filled --hypothesis" not in result.output
    assert _read_hypothesis_label(cfg, "ZZZ") is None


def test_entry_pre_fill_idempotent_across_re_runs(tmp_path: Path):
    """Brief §5 watch item: pre-fill must be deterministic. Two entry
    invocations on the same ticker yield the same suggested label."""
    runner, cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="MSFT")

    r1 = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "MSFT", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ])
    assert r1.exit_code == 0, r1.output
    line1 = next(
        ln for ln in r1.output.splitlines() if "Pre-filled --hypothesis" in ln
    )
    label1 = _read_hypothesis_label(cfg, "MSFT")

    # Exit the trade so the second entry doesn't trip the duplicate-open
    # guard, then re-enter.
    runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5", "--reason", "target",
    ])

    r2 = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "MSFT", "--entry-date", "2026-04-23",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ])
    assert r2.exit_code == 0, r2.output
    line2 = next(
        ln for ln in r2.output.splitlines() if "Pre-filled --hypothesis" in ln
    )
    label2 = _read_hypothesis_label(cfg, "MSFT")
    assert line1 == line2
    assert label1 == label2


def test_entry_pre_fill_falls_back_to_standalone_eval_when_no_pipeline_FK(
    tmp_path: Path,
):
    """Cross-surface consistency (adversarial review R1 Major 1): when the
    latest pipeline run has NULL `evaluation_run_id` (legacy / drift), the
    dashboard falls back to the most recent `evaluation_runs` row by
    `run_ts`. The CLI MUST follow the same fallback so an operator who
    sees a recommendation on the dashboard can pre-fill from it.
    """
    runner, cfg = _setup(tmp_path)
    # Seed a complete pipeline_run with NULL evaluation_run_id (legacy) +
    # a standalone eval that DOES have an A+ candidate.
    import tomllib
    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'AAPL', 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id,),
            )
            # Pipeline row with NULL FK — exercises the fallback path.
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', NULL)""",
            )
    finally:
        conn.close()

    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    # Pre-fill must trigger via the fallback path.
    assert "Pre-filled --hypothesis" in result.output


def test_entry_pre_fill_when_no_pipeline_run_yet(tmp_path: Path):
    """Fresh-install path: no pipeline_runs row at all → no candidate to
    look up → no pre-fill, no crash."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *cli_entry_pre_trade_args(),
    ])
    assert result.exit_code == 0, result.output
    assert "Pre-filled --hypothesis" not in result.output
