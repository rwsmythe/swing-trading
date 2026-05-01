"""Unit tests for swing.recommendations.hypothesis_prefill.

Lifted helper from swing/cli.py:_lookup_active_recommendation_label
(pre-Phase-4.5) to swing/recommendations/hypothesis_prefill.py.
Public name; both CLI and web VM consume it.

Test seed pattern mirrors tests/cli/test_cli_trade_entry_hypothesis_prefill.py
so the helper-side and CLI-side tests exercise identical fixture shape.
"""
from __future__ import annotations

from pathlib import Path

import tomllib
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.recommendations.hypothesis_prefill import (
    lookup_active_recommendation_label,
)
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return cfg


def _seed_aplus_pipeline(cfg_path: Path, ticker: str) -> None:
    """Seed a complete pipeline run with one A+ candidate for `ticker`."""
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


def test_lookup_active_recommendation_label_returns_exact_matcher_label(
    tmp_path: Path,
):
    """Discriminating: with an A+ candidate seeded for AAPL, the helper
    returns EXACTLY the matcher's suggested_label_descriptive output.

    Per Codex R1 Major 3, exact-equality (not prefix-match) catches
    wrong-label bugs WITHIN the same hypothesis family — e.g. a regression
    that returned `suggested_label_short`, picked the wrong prioritized
    index, or formatted the bucket-suffix differently.

    For the seed fixture (bucket='aplus', no failing criteria), the
    matcher chain produces "A+ baseline (aplus)" deterministically — see
    "Matcher output for the seed fixture" near the top of this plan.
    The plan's load-bearing constant.

    Sanity: if the helper short-circuited (wrong table query), forgot
    the prioritizer step, returned the wrong field, or read from a
    stale evaluation_run_id, this exact-equality assertion fails.
    """
    cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="AAPL")

    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        label = lookup_active_recommendation_label(
            conn, ticker="AAPL", starting_equity=1200.0,
        )
    finally:
        conn.close()

    # Exact-equality with the matcher's deterministic output for this
    # fixture. NOT a prefix match — the matcher's full descriptive
    # label is the contract.
    assert label == "A+ baseline (aplus)", (
        f"helper must return exact matcher output; got {label!r}"
    )


def test_lookup_active_recommendation_label_returns_None_for_non_matching(
    tmp_path: Path,
):
    """Degenerate: ticker has no candidate row → helper returns None.
    Preserves the no-match → NULL persistence guarantee (downstream
    record_entry → canonicalize_hypothesis_label semantic).

    Sanity: if the helper falsely returned the label from another
    ticker (cursor-iteration bug, missing ticker filter), this
    assertion would fail.
    """
    cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="AAPL")  # AAPL exists; ZZZ does not.

    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        label = lookup_active_recommendation_label(
            conn, ticker="ZZZ", starting_equity=1200.0,
        )
    finally:
        conn.close()

    assert label is None
