"""Phase 13 T4.SB cross-bundle pin row 13 -- hypothesis-label delimiter-aware
match invariant across 4 metric surfaces.

Per spec §E recommendation: PLANTED at T-T4.SB.2; promoted GREEN post-fix
(this file lands AFTER Sub-tasks 2A-2D close the wiring across all 4
surfaces). Parametrize set: 4 surfaces (per dispatch brief §1.4 OQ-7.2
LOCK + spec §B.7.2 R2 M#4 closure):

  1. ``list_trades_for_cohort`` -- SQL helper consumer
  2. ``count_per_cohort`` -- GROUP BY-replacement consumer
  3. Dashboard hyp-progress card VM -- transitive via
     ``list_closed_trades_for_cohort``
  4. CLI ``compute_hypothesis_progress_breakdown`` -- via
     ``_label_matches_hypothesis`` Python helper

ALL 4 surfaces MUST return 1 for the planted suffix-bearing trade against
the canonical cohort name ``"Sub-A+ VCP-not-formed"``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.journal.stats import compute_hypothesis_progress_breakdown
from swing.metrics.cohort import count_per_cohort, list_trades_for_cohort
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)


def _plant_suffix_bearing_trade(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES ('ZZZ', '2026-05-12', 10.0, 100, 9.0, "
        "9.0, 'closed', 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, ?)",
        ("Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",),
    )
    conn.commit()


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase13_t4_sb_pin13.db"
    conn = ensure_schema(db_path)
    _plant_suffix_bearing_trade(conn)
    conn.close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))


def _surface_list_trades_for_cohort(cfg) -> int:
    with sqlite3.connect(cfg.paths.db_path) as conn:
        rows = list_trades_for_cohort(
            conn, hypothesis_label="Sub-A+ VCP-not-formed",
            state_filter=("closed", "reviewed"),
        )
    return len(rows)


def _surface_count_per_cohort(cfg) -> int:
    with sqlite3.connect(cfg.paths.db_path) as conn:
        counts = count_per_cohort(conn)
    return counts["Sub-A+ VCP-not-formed"]


def _surface_hyp_progress_card(cfg) -> int:
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    cohort = next(
        c for c in vm.cohorts if c.cohort_name == "Sub-A+ VCP-not-formed"
    )
    return cohort.n_closed


def _surface_cli_breakdown(cfg) -> int:
    """CLI ``compute_hypothesis_progress_breakdown`` consumes
    ``_label_matches_hypothesis`` (the Python helper). ``starting_equity``
    is positional-required and immaterial to the suffix-attribution path
    (it only feeds absolute-loss tripwire calculation; the sample count
    derives from match-set length)."""
    with sqlite3.connect(cfg.paths.db_path) as conn:
        breakdown = compute_hypothesis_progress_breakdown(
            conn, starting_equity=7500.0,
        )
    for entry in breakdown:
        if entry.name == "Sub-A+ VCP-not-formed":
            return entry.current_sample
    return 0


@pytest.mark.parametrize(
    "surface_fn,surface_name",
    [
        (_surface_list_trades_for_cohort, "list_trades_for_cohort"),
        (_surface_count_per_cohort, "count_per_cohort"),
        (_surface_hyp_progress_card, "hyp_progress_card_vm"),
        (_surface_cli_breakdown, "cli_compute_hypothesis_progress_breakdown"),
    ],
)
def test_delimiter_aware_match_invariant_holds_at_surface(
    cfg, surface_fn, surface_name,
) -> None:
    """Per spec §E: ALL 4 surfaces MUST return 1 for the suffix-bearing
    trade against the canonical cohort name ``"Sub-A+ VCP-not-formed"``.
    Pre-fix any surface using exact-equality returned 0 (silent
    suffix-attribution defect)."""
    assert surface_fn(cfg) == 1, (
        f"Surface {surface_name!r} returned non-1 -- delimiter-aware "
        "match invariant violated. See spec §B.7.1 LOCK."
    )
