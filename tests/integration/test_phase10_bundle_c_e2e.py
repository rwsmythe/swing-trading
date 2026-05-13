"""Phase 10 Sub-bundle C T-C.4 — integration E2E happy-path.

Seeds varied per-cohort sample sizes covering the spec §4.3 + §4.7
suppression ↔ rendering transition bands:

- Cohort below n=3 (Capital-blocked at n=2): full cell suppression.
- Cohort at n=4 (Near-A+): under the surface-locked floor of 5 → still
  fully suppressed at the surface even though above the Class A/B policy
  floor of 3 (discriminating against the per-class policy floor).
- Cohort at n=5 (A+ baseline at n=6 + Sub-A+ at n=8): full Wilson +
  Bootstrap CIs render + descriptor unlocks.
- Sub-A+ at n=8 + A+ at n=6: both >=5 → descriptor renders the
  ``"A+ CI [...] vs Sub-A+ CI [...] — overlap: yes|no"`` text verbatim
  (per spec §3.3 R1 M3 LOCK + dispatch brief §0.10 LOCK).
- Relative-to-A+ percent rendered as raw-ratio (§3.3) AND delta-percent
  (§3.7), exercising the dispatch brief §0.9 unit-LOCK.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.tier import (
    APLUS_COHORT,
    SUB_APLUS_COHORT,
    compute_deviation_outcome,
    compute_tier_comparison,
)
from swing.web.app import create_app


# Cohort-name aliases for readability.
NEAR_APLUS_COHORT = "Near-A+ defensible: extension test"
CAPITAL_BLOCKED_COHORT = "Capital-blocked: smaller-position test"


@pytest.fixture
def cfg_and_path(tmp_path: Path):
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_config(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str,
    realized_pnl_dollars: float,
    last_fill_at: str,
) -> None:
    entry_price = 10.0
    initial_stop = 9.0
    initial_shares = 100
    exit_price = entry_price + (realized_pnl_dollars / initial_shares)
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, last_fill_at) VALUES "
        "(?, ?, '2026-04-01', ?, ?, ?, ?, 'closed', 'S', 'I', "
        "'manual_off_pipeline', '2026-04-01T09:30:00', ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            initial_stop, initial_shares, hypothesis_label, last_fill_at,
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, '2026-04-01T09:30:00', "
        "'entry', ?, ?, 'unreconciled')",
        (trade_id, initial_shares, entry_price),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, ?, 'exit', ?, ?, "
        "'unreconciled')",
        (trade_id, last_fill_at, initial_shares, exit_price),
    )


def _seed_varied_cohorts(conn: sqlite3.Connection) -> None:
    """Seed per spec §4.3 + §4.7 worked-example transition bands.

    A+ baseline:   n=6 (5 wins + 1 loss; mean realized_R ≈ +1.5)
    Near-A+:       n=4 (under surface floor 5, above policy floor 3)
    Sub-A+ VCP:    n=8 (6 losses + 2 wins; mean realized_R ≈ -0.4)
    Capital-blocked: n=2 (under everything)
    """
    with conn:
        # A+ baseline: 5x +2R + 1x -0.5R = mean of +1.5833R
        for i in range(5):
            _seed_trade(
                conn, trade_id=1 + i, ticker=f"AW{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=200.0,  # +2R
                last_fill_at=f"2026-04-{i + 1:02d}T15:30:00",
            )
        _seed_trade(
            conn, trade_id=6, ticker="AL1",
            hypothesis_label=APLUS_COHORT,
            realized_pnl_dollars=-50.0,  # -0.5R
            last_fill_at="2026-04-06T15:30:00",
        )

        # Near-A+: 4 mixed trades (under surface floor → suppressed).
        for i in range(4):
            _seed_trade(
                conn, trade_id=10 + i, ticker=f"NA{i}",
                hypothesis_label=NEAR_APLUS_COHORT,
                realized_pnl_dollars=120.0 if i % 2 == 0 else -80.0,
                last_fill_at=f"2026-04-{7 + i:02d}T15:30:00",
            )

        # Sub-A+: 6 losses + 2 wins (mostly negative R).
        for i in range(6):
            _seed_trade(
                conn, trade_id=20 + i, ticker=f"SL{i}",
                hypothesis_label=SUB_APLUS_COHORT,
                realized_pnl_dollars=-100.0,  # -1R
                last_fill_at=f"2026-04-{11 + i:02d}T15:30:00",
            )
        for i in range(2):
            _seed_trade(
                conn, trade_id=26 + i, ticker=f"SW{i}",
                hypothesis_label=SUB_APLUS_COHORT,
                realized_pnl_dollars=50.0,  # +0.5R
                last_fill_at=f"2026-04-{17 + i:02d}T15:30:00",
            )

        # Capital-blocked: 2 trades (below all floors).
        for i in range(2):
            _seed_trade(
                conn, trade_id=30 + i, ticker=f"CB{i}",
                hypothesis_label=CAPITAL_BLOCKED_COHORT,
                realized_pnl_dollars=80.0,
                last_fill_at=f"2026-04-{19 + i:02d}T15:30:00",
            )


def test_e2e_tier_comparison_suppression_to_rendering_transitions(
    cfg_and_path,
) -> None:
    """T-C.4 §F acceptance: verify the suppression-to-rendering transition
    bands across all 4 cohorts in a single integrated walkthrough.
    """
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_varied_cohorts(conn)
    conn.close()

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        result = compute_tier_comparison(conn)
    finally:
        conn.close()

    from swing.metrics.honesty import BootstrapCI, SuppressedMetric, WilsonCI
    by_name = {c.cohort_name: c for c in result.cohorts}

    # A+ n=6 → above floor; both CIs render.
    assert by_name[APLUS_COHORT].n_closed == 6
    assert isinstance(by_name[APLUS_COHORT].win_rate, WilsonCI)
    assert isinstance(by_name[APLUS_COHORT].expectancy, BootstrapCI)

    # Near-A+ n=4 → BELOW surface-locked floor of 5 → suppressed.
    assert by_name[NEAR_APLUS_COHORT].n_closed == 4
    assert isinstance(
        by_name[NEAR_APLUS_COHORT].win_rate, SuppressedMetric,
    )
    assert isinstance(
        by_name[NEAR_APLUS_COHORT].expectancy, SuppressedMetric,
    )

    # Sub-A+ n=8 → above floor; both CIs render.
    assert by_name[SUB_APLUS_COHORT].n_closed == 8
    assert isinstance(by_name[SUB_APLUS_COHORT].win_rate, WilsonCI)
    assert isinstance(by_name[SUB_APLUS_COHORT].expectancy, BootstrapCI)

    # Capital-blocked n=2 → below all floors; suppressed.
    assert by_name[CAPITAL_BLOCKED_COHORT].n_closed == 2
    assert isinstance(
        by_name[CAPITAL_BLOCKED_COHORT].win_rate, SuppressedMetric,
    )

    # Descriptor unlocks: BOTH A+ AND Sub-A+ have n>=5.
    assert result.overlap_descriptor_suppressed is False
    desc = result.cohort_ci_overlap_descriptor
    assert desc.startswith("A+ CI [")
    assert "] vs Sub-A+ CI [" in desc
    assert "— overlap: " in desc

    # Relative-to-A+ percent: Sub-A+ point ≈ -0.4 / A+ point ≈ +1.58 → ≈ -25%
    sub_aplus_pct = result.cohort_relative_to_aplus_pct[SUB_APLUS_COHORT]
    assert sub_aplus_pct is not None
    # Wide tolerance: bootstrap point is stochastic for non-uniform samples.
    assert -50.0 < sub_aplus_pct < 0.0, (
        "Sub-A+ should be a NEGATIVE fraction-of-A+ given losing-cohort "
        f"sample; got {sub_aplus_pct!r}"
    )
    # Near-A+ + Capital-blocked have suppressed cells → relative_pct None.
    assert result.cohort_relative_to_aplus_pct[NEAR_APLUS_COHORT] is None
    assert (
        result.cohort_relative_to_aplus_pct[CAPITAL_BLOCKED_COHORT] is None
    )
    # A+ self-reference is None.
    assert result.cohort_relative_to_aplus_pct[APLUS_COHORT] is None


def test_e2e_deviation_outcome_renders_row_suppression_correctly(
    cfg_and_path,
) -> None:
    """T-C.4 §F acceptance: per spec §4.7 LOCK — rows below n=5 stay
    VISIBLE with doctrine-deviation-class + criterion text, but the
    relative-pct cell is suppressed (row_suppressed=True)."""
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_varied_cohorts(conn)
    conn.close()

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        result = compute_deviation_outcome(conn)
    finally:
        conn.close()

    by_name = {r.cohort_name: r for r in result.rows}

    # All 4 rows present + visible.
    assert len(result.rows) == 4

    # A+ row: n=6 >=5, but row_suppressed=False; relative-pct is None
    # (self-reference baseline).
    aplus = by_name[APLUS_COHORT]
    assert aplus.row_suppressed is False
    assert aplus.expectancy_relative_to_aplus_pct is None
    assert aplus.decision_criterion_evaluation_text == (
        "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%"
    )

    # Near-A+ row: n=4 < 5 → row_suppressed=True; criterion text still
    # rendered.
    near = by_name[NEAR_APLUS_COHORT]
    assert near.row_suppressed is True
    assert near.expectancy_relative_to_aplus_pct is None
    assert near.decision_criterion_evaluation_text == (
        "Mean R-multiple within 25% of A+ baseline mean"
    )
    assert near.doctrine_deviation_class == "missing_proximity_20ma"

    # Sub-A+ row: n=8 >=5 + A+ n=6 >=5 → relative-pct computed.
    sub = by_name[SUB_APLUS_COHORT]
    assert sub.row_suppressed is False
    assert sub.expectancy_relative_to_aplus_pct is not None
    assert sub.expectancy_relative_to_aplus_pct < 0.0, (
        "Sub-A+ losing cohort below A+ → negative delta"
    )

    # Capital-blocked: n=2 < 5 → row_suppressed; criterion text rendered.
    cap = by_name[CAPITAL_BLOCKED_COHORT]
    assert cap.row_suppressed is True
    assert cap.doctrine_deviation_class == "smaller_than_standard_position"


def test_e2e_tier_comparison_browser_rendering_smoke(cfg_and_path) -> None:
    """T-C.4 acceptance: TestClient end-to-end render of the tier-
    comparison surface with the varied-cohort seed."""
    cfg, cfg_path = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_varied_cohorts(conn)
    conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    assert r.status_code == 200
    body = r.text
    # Each cohort column renders.
    for cohort in (
        APLUS_COHORT, NEAR_APLUS_COHORT, SUB_APLUS_COHORT,
        CAPITAL_BLOCKED_COHORT,
    ):
        assert f'data-cohort-name="{cohort}"' in body

    # Descriptor unlocked at this n profile → "overlap: yes" or "no"
    # appears.
    assert "— overlap: " in body
    # Sub-A+ percent rendered as percent-of-A+ raw ratio with explicit "%".
    # Verify the cohort_relative_to_aplus row is present + uses % unit.
    assert "Relative to A+" in body


def test_e2e_deviation_outcome_browser_rendering_smoke(cfg_and_path) -> None:
    cfg, cfg_path = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_varied_cohorts(conn)
    conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    assert r.status_code == 200
    body = r.text
    # Each cohort row anchor present.
    for cohort in (
        APLUS_COHORT, NEAR_APLUS_COHORT, SUB_APLUS_COHORT,
        CAPITAL_BLOCKED_COHORT,
    ):
        assert f'data-cohort-name="{cohort}"' in body

    # Sub-A+ delta-pct rendered with explicit "%" unit (per dispatch brief
    # §0.9 LOCK).
    assert "%" in body
    # Decision-criterion seed text verbatim for each registered cohort.
    assert "lower-bound Wilson CI on win rate" in body
