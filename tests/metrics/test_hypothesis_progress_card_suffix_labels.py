"""T-T4.SB.2 Sub-task 2D -- dashboard hyp-progress card integration test.

Discriminating regression: post-Item-7-fix (T-T4.SB.2 Sub-tasks 2A + 2B +
2C), the dashboard hyp-progress card MUST surface non-zero ``n_closed`` for
a cohort whose closed trades carry suffix-bearing labels (e.g.,
``"Sub-A+ VCP-not-formed (watch); failed: proximity_20ma"``). Pre-fix the
card returned 0 because ``list_closed_trades_for_cohort`` -- which wraps
``list_trades_for_cohort`` -- used exact-equality SQL.

The fix lands transitively: ``build_hypothesis_progress_card_vm`` ->
``_build_cohort_vm`` -> ``_list_cohort_trades_sorted`` ->
``list_closed_trades_for_cohort`` -> ``list_trades_for_cohort`` (the SQL
helper). Sub-tasks 2B + 2C close the wiring at the SQL layer.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase13_t4_sb2_dashboard.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))


def _plant_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    hypothesis_label: str,
    state: str = "closed",
    entry_date: str = "2026-05-12",
) -> None:
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, ?, 10.0, 100, 9.0, 9.0, ?, "
        "'S', 'I', 'manual_off_pipeline', ?, 100, ?)",
        (ticker, entry_date, state,
         entry_date + "T09:00:00.000", hypothesis_label),
    )


def test_hypothesis_progress_card_non_zero_on_suffix_labels(cfg) -> None:
    """Closes Phase 13 T-T4.SB.2 Item 7 spec §B.7.1 LOCK. Pre-fix the card's
    suffix-bearing cohort returned n_closed=0 (exact-equality mismatch).
    Post-fix the 3-rule delimiter-aware match surfaces the suffix rows."""
    conn = sqlite3.connect(cfg.paths.db_path)
    for ticker, state in (
        ("AAA", "closed"), ("BBB", "closed"),
        ("CCC", "reviewed"), ("DDD", "reviewed"),
    ):
        _plant_trade(
            conn, ticker=ticker,
            hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",
            state=state,
        )
    conn.commit()
    conn.close()

    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    cohort = next(
        c for c in vm.cohorts if c.cohort_name == "Sub-A+ VCP-not-formed"
    )
    assert cohort.n_closed == 4  # Was 0 pre-fix (exact-equality mismatch).
