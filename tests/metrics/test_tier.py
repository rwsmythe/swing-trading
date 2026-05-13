"""Phase 10 Sub-bundle C T-C.1 — tier-comparison + deviation-outcome tests.

Covers spec §3.3 + §3.7 computation behavior + the binding LOCKs:

- spec §3.3 R1 M3 LOCK: ``cohort_ci_overlap_descriptor`` is TEXT, NOT a
  boolean significance flag (verbatim format pinned).
- spec §3.7 R1 M4 LOCK: ``cohort_decision_criterion_evaluation_text``
  renders seed text from migration 0008 verbatim — NO automated
  evaluation in V1.
- dispatch brief §0.9 LOCK: ``cohort_relative_to_aplus_pct`` is PERCENT
  raw ratio (``cohort/aplus * 100``); ``cohort_expectancy_relative_to_aplus_pct``
  is PERCENT delta (``(cohort - aplus) / aplus * 100``).
- spec §4.3 + §4.7 surface LOCK: cohort cells suppress at n<5;
  descriptor suppresses until BOTH A+ AND Sub-A+ have n>=5.
- dispatch brief §0.5 #4 BINDING: TAXONOMY-LOCKED to 4 registered cohorts
  (orphan-labeled trades EXCLUDED).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.tier import (
    APLUS_COHORT,
    COHORT_MINIMUM_N,
    DOCTRINE_DEVIATION_CLASS,
    SUB_APLUS_COHORT,
    TAXONOMY_COHORTS,
    CohortStatistics,
    DeviationOutcomeResult,
    DeviationOutcomeRow,
    TierComparisonResult,
    compute_deviation_outcome,
    compute_tier_comparison,
)
from swing.metrics.honesty import BootstrapCI, SuppressedMetric, WilsonCI


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_tier.db")


def _seed_closed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str,
    realized_pnl_dollars: float,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    state: str = "closed",
    risk_policy_id_at_lock: int | None = 1,
    last_fill_at: str = "2026-04-08T15:30:00",
) -> None:
    """Seed a closed trade. Exit price computed so net P&L matches the target.

    Risk_per_share = entry - stop = $1; risk_budget = $1 * 100 = $100.
    realized_R = realized_pnl_dollars / $100.
    """
    exit_price = entry_price + (realized_pnl_dollars / initial_shares)
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, risk_policy_id_at_lock, last_fill_at) VALUES "
        "(?, ?, '2026-04-01', ?, ?, ?, ?, ?, 'S', 'I', "
        "'manual_off_pipeline', '2026-04-01T09:30:00', ?, ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            initial_stop, state, initial_shares, hypothesis_label,
            risk_policy_id_at_lock, last_fill_at,
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES "
        "(?, '2026-04-01T09:30:00', 'entry', ?, ?, 'unreconciled')",
        (trade_id, initial_shares, entry_price),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES (?, ?, 'exit', ?, ?, 'unreconciled')",
        (trade_id, last_fill_at, initial_shares, exit_price),
    )


def _seed_cohort_n(
    conn: sqlite3.Connection,
    *,
    cohort: str,
    n: int,
    realized_R_each: float,  # noqa: N803 — spec parameter name
    starting_trade_id: int,
    starting_ticker_offset: int = 0,
) -> None:
    """Seed n closed trades for the cohort, each with realized_R_each.

    realized_R_each is converted to realized_pnl_dollars via the standard
    fixture risk_budget=$100 (entry=$10, stop=$9, 100 shares).
    """
    pnl = realized_R_each * 100.0  # risk_budget=$100
    with conn:
        for i in range(n):
            _seed_closed_trade(
                conn,
                trade_id=starting_trade_id + i,
                ticker=f"T{starting_trade_id + i:03d}",
                hypothesis_label=cohort,
                realized_pnl_dollars=pnl,
                last_fill_at=f"2026-04-{(i % 28) + 1:02d}T15:30:00",
            )


# ---------------------------------------------------------------------------
# Structure + base cases (n=0)
# ---------------------------------------------------------------------------

def test_compute_tier_comparison_empty_data_all_suppressed(
    conn: sqlite3.Connection,
) -> None:
    """At zero closed trades all 4 cohort cells suppress + descriptor
    suppresses + every relative_to_aplus is None."""
    result = compute_tier_comparison(conn)
    assert isinstance(result, TierComparisonResult)
    assert len(result.cohorts) == 4
    seen = tuple(c.cohort_name for c in result.cohorts)
    assert seen == TAXONOMY_COHORTS
    for c in result.cohorts:
        assert c.n_closed == 0
        assert isinstance(c.win_rate, SuppressedMetric)
        assert isinstance(c.expectancy, SuppressedMetric)
    assert result.overlap_descriptor_suppressed is True
    for cohort in TAXONOMY_COHORTS:
        assert result.cohort_relative_to_aplus_pct[cohort] is None


def test_compute_deviation_outcome_empty_data_all_rows_suppressed_but_visible(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §4.7: cohort row stays VISIBLE at n<5 with the
    decision_criterion text + doctrine_deviation_class; the relative-
    expectancy cell is suppressed (None), and ``row_suppressed`` flags
    the cell-level suppression for templates."""
    result = compute_deviation_outcome(conn)
    assert isinstance(result, DeviationOutcomeResult)
    assert len(result.rows) == 4
    for row in result.rows:
        assert isinstance(row, DeviationOutcomeRow)
        assert row.row_suppressed is True
        assert row.expectancy_relative_to_aplus_pct is None
        # decision_criterion_evaluation_text is the seed text verbatim,
        # always populated regardless of n.
        assert row.decision_criterion_evaluation_text == row.decision_criteria
        assert row.decision_criteria  # non-empty


def test_doctrine_deviation_class_mapping_per_spec_3_7(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.7 row 1: the 4 enum values mapped to the 4 cohorts."""
    result = compute_deviation_outcome(conn)
    by_name = {r.cohort_name: r for r in result.rows}
    assert by_name["A+ baseline"].doctrine_deviation_class == "baseline"
    assert by_name["Near-A+ defensible: extension test"].doctrine_deviation_class == (
        "missing_proximity_20ma"
    )
    assert by_name["Sub-A+ VCP-not-formed"].doctrine_deviation_class == (
        "missing_tightness_or_vcp_volume_contraction"
    )
    assert by_name["Capital-blocked: smaller-position test"].doctrine_deviation_class == (
        "smaller_than_standard_position"
    )


# ---------------------------------------------------------------------------
# Descriptor format + suppression (spec §3.3 R1 M3 LOCK; dispatch brief §0.10)
# ---------------------------------------------------------------------------

def test_compute_tier_comparison_descriptor_suppressed_when_aplus_below_5(
    conn: sqlite3.Connection,
) -> None:
    """A+ n=4 + Sub-A+ n=5 → descriptor suppressed (BOTH must be >=5)."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=4, realized_R_each=1.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=-0.5, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    assert result.overlap_descriptor_suppressed is True
    assert "Insufficient cohort samples" in result.cohort_ci_overlap_descriptor


def test_compute_tier_comparison_descriptor_suppressed_when_sub_aplus_below_5(
    conn: sqlite3.Connection,
) -> None:
    """A+ n=5 + Sub-A+ n=4 → descriptor suppressed."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=1.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=4,
                   realized_R_each=-0.5, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    assert result.overlap_descriptor_suppressed is True


def test_compute_tier_comparison_descriptor_text_format_lock(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.3 R1 M3 + dispatch brief §0.10 LOCK:

    Format: "A+ CI [a, b] vs Sub-A+ CI [c, d] — overlap: yes|no"
    Bounds at 2-decimal precision; overlap word is "yes" or "no";
    em-dash separator.

    Seed A+ n=10 wins / 0 losses (all positive R); Sub-A+ n=5 with 1 win
    + 4 losses. Wilson CIs are well-separated → overlap should be no OR
    yes depending on bounds; this test asserts FORMAT not the value of
    the overlap word.
    """
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=10, realized_R_each=2.0,
                   starting_trade_id=1)
    # Sub-A+: 4 losses + 1 win
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=4,
                   realized_R_each=-1.0, starting_trade_id=100)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=1,
                   realized_R_each=0.5, starting_trade_id=200)
    result = compute_tier_comparison(conn)
    assert result.overlap_descriptor_suppressed is False
    desc = result.cohort_ci_overlap_descriptor
    # Verbatim format anchors (dispatch brief §0.10 LOCK):
    assert desc.startswith("A+ CI [")
    assert "] vs Sub-A+ CI [" in desc
    assert "— overlap: " in desc  # em-dash
    overlap_word = desc.rsplit(":", 1)[1].strip()
    assert overlap_word in {"yes", "no"}, (
        f"overlap word must be 'yes' or 'no' (per §3.3 R1 M3 LOCK); "
        f"got {overlap_word!r}"
    )


def test_compute_tier_comparison_descriptor_overlap_yes_when_intervals_intersect(
    conn: sqlite3.Connection,
) -> None:
    """When both cohorts are 100% wins, both Wilson CIs include 1.0 →
    overlap is yes."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=2.0, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    assert result.overlap_descriptor_suppressed is False
    assert "overlap: yes" in result.cohort_ci_overlap_descriptor


def test_compute_tier_comparison_descriptor_text_does_not_contain_boolean_keys(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.3 R1 M3 LOCK: no `classification_quality_flag` /
    `significant` / p-value text leaks into the descriptor."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=-1.0, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    desc = result.cohort_ci_overlap_descriptor.lower()
    assert "classification_quality_flag" not in desc
    assert "significant" not in desc
    assert "p-value" not in desc
    assert "p =" not in desc


# ---------------------------------------------------------------------------
# Cohort-cell renderings at n>=5 (spec §4.3 surface lock)
# ---------------------------------------------------------------------------

def test_compute_tier_comparison_at_n5_cohort_renders_wilson_and_bootstrap(
    conn: sqlite3.Connection,
) -> None:
    """A+ n=5 (all wins) → Wilson + Bootstrap CIs returned (not Suppressed)."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    assert isinstance(aplus.win_rate, WilsonCI)
    assert isinstance(aplus.expectancy, BootstrapCI)
    assert aplus.n_wins == 5
    assert aplus.n_losses == 0


def test_compute_tier_comparison_at_n_below_5_cohort_cells_suppressed(
    conn: sqlite3.Connection,
) -> None:
    """A+ n=4 → both win_rate + expectancy cells are SuppressedMetric.

    Discriminating against the per-class policy floor (3): default policy
    has class_a_n=3, so the honesty layer alone would render WilsonCI at
    n=4. The surface-locked floor of 5 (per spec §4.3) suppresses.
    """
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=4, realized_R_each=2.0,
                   starting_trade_id=1)
    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    assert isinstance(aplus.win_rate, SuppressedMetric)
    assert isinstance(aplus.expectancy, SuppressedMetric)
    # Placeholder names the surface-level required floor (5), not the
    # honesty policy floor (3).
    assert "≥5" in aplus.win_rate.placeholder_text


# ---------------------------------------------------------------------------
# cohort_relative_to_aplus_pct (dispatch brief §0.9 — RAW RATIO percent)
# ---------------------------------------------------------------------------

def test_cohort_relative_to_aplus_when_aplus_has_zero_trades_returns_suppressed(  # noqa: E501
    conn: sqlite3.Connection,
) -> None:
    """Spec §3.3 division-by-zero defense — A+ with n=0 ⇒ every non-A+
    cohort's cohort_relative_to_aplus_pct is None (NOT NaN/inf)."""
    # Seed Sub-A+ n=5 but A+ stays at n=0.
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5, realized_R_each=0.5,
                   starting_trade_id=1)
    result = compute_tier_comparison(conn)
    for cohort in TAXONOMY_COHORTS:
        assert result.cohort_relative_to_aplus_pct[cohort] is None


def test_cohort_relative_to_aplus_pct_renders_raw_ratio_as_percent(
    conn: sqlite3.Connection,
) -> None:
    """Per dispatch brief §0.9 LOCK + spec §3.3:

    A+ expectancy=2.0R, Sub-A+ expectancy=0.5R → cohort_relative_to_aplus_pct
    for Sub-A+ should be 25.0 (=0.5/2.0*100), NOT -75.0 (delta) and NOT 0.25
    (proportion).
    """
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=0.5, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    sub_aplus_pct = result.cohort_relative_to_aplus_pct[SUB_APLUS_COHORT]
    # Bootstrap CI point is the SAMPLE MEAN; with 5 identical 0.5R samples
    # the mean is exactly 0.5, same for 2.0 baseline. Ratio is 0.25 ⇒ 25%.
    assert sub_aplus_pct == pytest.approx(25.0, abs=0.01)
    # Discriminate against:
    # - -75.0 (delta interpretation)
    # - 0.25 (proportion not percent)
    # - 75.0 (inverted ratio)
    assert sub_aplus_pct != pytest.approx(-75.0, abs=0.01)
    assert sub_aplus_pct != pytest.approx(0.25, abs=0.01)
    assert sub_aplus_pct != pytest.approx(75.0, abs=0.01)


def test_cohort_relative_to_aplus_is_none_for_aplus_itself(
    conn: sqlite3.Connection,
) -> None:
    """A+ baseline self-reference is None (rendered as "—" template-side)."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    result = compute_tier_comparison(conn)
    assert result.cohort_relative_to_aplus_pct[APLUS_COHORT] is None


def test_cohort_relative_to_aplus_when_aplus_expectancy_is_zero_returns_none(
    conn: sqlite3.Connection,
) -> None:
    """A+ at zero expectancy (mean=0) → division-by-zero defense: None."""
    # Seed A+ n=5 with mixed +0.5 / -0.5 trades summing to 0 mean.
    with conn:
        for i in range(3):
            _seed_closed_trade(
                conn, trade_id=10 + i, ticker=f"AP{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=50.0,  # +0.5R
                last_fill_at=f"2026-04-{i + 1:02d}T15:30:00",
            )
        for i in range(2):
            _seed_closed_trade(
                conn, trade_id=20 + i, ticker=f"AN{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=-75.0,  # -0.75R
                last_fill_at=f"2026-04-{10 + i:02d}T15:30:00",
            )
    # samples_R: [+0.5, +0.5, +0.5, -0.75, -0.75] → mean = 0.0
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=-1.0, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    assert isinstance(aplus.expectancy, BootstrapCI)
    assert aplus.expectancy.point == pytest.approx(0.0, abs=0.01)
    assert result.cohort_relative_to_aplus_pct[SUB_APLUS_COHORT] is None


# ---------------------------------------------------------------------------
# expectancy_relative_to_aplus_pct (dispatch brief §0.9 — DELTA percent)
# ---------------------------------------------------------------------------

def test_deviation_outcome_expectancy_relative_to_aplus_pct_delta_sign(
    conn: sqlite3.Connection,
) -> None:
    """Per dispatch brief §0.9 LOCK + spec §3.7:

    A+ expectancy=2.0R, Sub-A+ expectancy=0.5R → delta percent for Sub-A+
    is -75.0 (=(0.5 - 2.0) / 2.0 * 100), sign-preserving (negative ⇒
    cohort below baseline).
    """
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=0.5, starting_trade_id=100)
    result = compute_deviation_outcome(conn)
    by_name = {r.cohort_name: r for r in result.rows}
    sub_aplus = by_name[SUB_APLUS_COHORT]
    assert sub_aplus.expectancy_relative_to_aplus_pct == pytest.approx(
        -75.0, abs=0.01,
    )
    # Discriminate against:
    # - +25.0 (raw-ratio interpretation)
    # - -0.75 (proportion not percent)
    # - +75.0 (sign error)
    assert sub_aplus.expectancy_relative_to_aplus_pct != pytest.approx(
        25.0, abs=0.01,
    )
    assert sub_aplus.expectancy_relative_to_aplus_pct != pytest.approx(
        -0.75, abs=0.01,
    )
    assert sub_aplus.expectancy_relative_to_aplus_pct != pytest.approx(
        75.0, abs=0.01,
    )


def test_deviation_outcome_expectancy_relative_to_aplus_pct_above_baseline_positive(
    conn: sqlite3.Connection,
) -> None:
    """Sub-A+ expectancy above A+ baseline → positive delta."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=1.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=1.5, starting_trade_id=100)
    result = compute_deviation_outcome(conn)
    by_name = {r.cohort_name: r for r in result.rows}
    sub_aplus = by_name[SUB_APLUS_COHORT]
    # (1.5 - 1.0) / 1.0 * 100 = 50.0
    assert sub_aplus.expectancy_relative_to_aplus_pct == pytest.approx(
        50.0, abs=0.01,
    )


def test_deviation_outcome_expectancy_relative_to_aplus_pct_aplus_row_is_none(
    conn: sqlite3.Connection,
) -> None:
    """A+ baseline row's relative-pct is None (self-reference)."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    result = compute_deviation_outcome(conn)
    aplus = next(r for r in result.rows if r.cohort_name == APLUS_COHORT)
    assert aplus.expectancy_relative_to_aplus_pct is None


def test_deviation_outcome_when_cohort_n_below_5_relative_pct_is_none(
    conn: sqlite3.Connection,
) -> None:
    """Spec §4.7 surface LOCK: cohort row with n<5 has suppressed
    expectancy → relative-pct is None (row stays visible)."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=3,
                   realized_R_each=0.5, starting_trade_id=100)
    result = compute_deviation_outcome(conn)
    by_name = {r.cohort_name: r for r in result.rows}
    sub_aplus = by_name[SUB_APLUS_COHORT]
    assert sub_aplus.row_suppressed is True
    assert sub_aplus.expectancy_relative_to_aplus_pct is None
    # Row is still visible (decision_criterion + deviation_class populated).
    assert sub_aplus.decision_criterion_evaluation_text  # non-empty
    assert sub_aplus.doctrine_deviation_class == (
        "missing_tightness_or_vcp_volume_contraction"
    )


# ---------------------------------------------------------------------------
# Decision-criterion evaluation text (spec §3.7 R1 M4 LOCK — manual only)
# ---------------------------------------------------------------------------

def test_deviation_outcome_decision_criterion_text_renders_seed_text_verbatim(
    conn: sqlite3.Connection,
) -> None:
    """Spec §3.7 R1 M4 LOCK + dispatch brief §0.11 LOCK: each row's
    ``decision_criterion_evaluation_text`` is the migration 0008 seed
    text verbatim — NO automated evaluation, NO append, NO truncate."""
    result = compute_deviation_outcome(conn)
    by_name = {r.cohort_name: r for r in result.rows}
    assert by_name["A+ baseline"].decision_criterion_evaluation_text == (
        "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%"
    )
    assert by_name["Near-A+ defensible: extension test"].decision_criterion_evaluation_text == (
        "Mean R-multiple within 25% of A+ baseline mean"
    )
    assert by_name["Sub-A+ VCP-not-formed"].decision_criterion_evaluation_text == (
        "Confirm negative mean R-multiple"
    )
    assert by_name["Capital-blocked: smaller-position test"].decision_criterion_evaluation_text == (
        "Mean R-multiple positive; defensibility of smaller-position approach"
    )


def test_deviation_outcome_decision_criterion_text_unchanged_after_aggregating_trades(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.7 R1 M4 LOCK: even AFTER aggregating real cohort trades
    with mean+win_rate computed, the rendered text is STILL the seed text
    verbatim — NO automated "criterion: ... — current: ..." synthesis."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=0.42,
                   starting_trade_id=1)
    result = compute_deviation_outcome(conn)
    aplus = next(r for r in result.rows if r.cohort_name == APLUS_COHORT)
    # The seed text MUST be the entire content (no appended "current: ..."
    # block which would indicate automated evaluation drift).
    assert aplus.decision_criterion_evaluation_text == (
        "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%"
    )
    # Discriminating check: no leaked statistic strings appended.
    for forbidden in ("current:", "mean R =", "win rate Wilson", "Pass:", "Fail:"):
        assert forbidden not in aplus.decision_criterion_evaluation_text, (
            f"automated evaluation drift: {forbidden!r} in rendered text"
        )


# ---------------------------------------------------------------------------
# Taxonomy-lock (dispatch brief §0.5 #4 BINDING)
# ---------------------------------------------------------------------------

def test_tier_comparison_does_not_render_orphan_cohort_columns(
    conn: sqlite3.Connection,
) -> None:
    """Per dispatch brief §0.5 #4 BINDING: orphan-labeled closed trades
    are NOT rendered as additional columns. The TierComparisonResult
    cohorts tuple has exactly 4 entries in TAXONOMY_COHORTS order."""
    # Seed 2 orphan-labeled closed trades.
    with conn:
        _seed_closed_trade(
            conn, trade_id=900, ticker="ORP1",
            hypothesis_label="orphan-cohort-A",
            realized_pnl_dollars=100.0,
        )
        _seed_closed_trade(
            conn, trade_id=901, ticker="ORP2",
            hypothesis_label="some-other-orphan",
            realized_pnl_dollars=-100.0,
        )
    result = compute_tier_comparison(conn)
    seen = tuple(c.cohort_name for c in result.cohorts)
    assert seen == TAXONOMY_COHORTS
    assert "orphan-cohort-A" not in seen
    assert "some-other-orphan" not in seen


def test_deviation_outcome_does_not_render_orphan_cohort_rows(
    conn: sqlite3.Connection,
) -> None:
    """Per dispatch brief §0.5 #4 BINDING: orphan-labeled closed trades
    are NOT rendered as additional rows on deviation-outcome."""
    with conn:
        _seed_closed_trade(
            conn, trade_id=900, ticker="ORP1",
            hypothesis_label="orphan-cohort",
            realized_pnl_dollars=100.0,
        )
    result = compute_deviation_outcome(conn)
    seen = tuple(r.cohort_name for r in result.rows)
    assert seen == TAXONOMY_COHORTS
    assert "orphan-cohort" not in seen


# ---------------------------------------------------------------------------
# Cohort cell suppression cascading at the cohort-vs-policy boundary
# ---------------------------------------------------------------------------

def test_cohort_cell_suppression_floor_is_5_not_class_a_floor_of_3(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §4.3 surface LOCK: the cohort cells suppress at n<5 even
    though the per-class policy floor (Class A) defaults to 3. Direct
    discriminating test: n=4 cohort has SuppressedMetric (NOT WilsonCI)."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=4, realized_R_each=2.0,
                   starting_trade_id=1)
    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    assert isinstance(aplus.win_rate, SuppressedMetric)


def test_compute_tier_comparison_at_5_trades_per_cohort_renders_descriptor(
    conn: sqlite3.Connection,
) -> None:
    """Per dispatch brief §0.10 LOCK: descriptor unlocks when BOTH A+
    AND Sub-A+ have n>=5."""
    _seed_cohort_n(conn, cohort=APLUS_COHORT, n=5, realized_R_each=2.0,
                   starting_trade_id=1)
    _seed_cohort_n(conn, cohort=SUB_APLUS_COHORT, n=5,
                   realized_R_each=-1.0, starting_trade_id=100)
    result = compute_tier_comparison(conn)
    assert result.overlap_descriptor_suppressed is False
    assert "Insufficient cohort samples" not in (
        result.cohort_ci_overlap_descriptor
    )


# ---------------------------------------------------------------------------
# Module constants + dataclass invariant tests
# ---------------------------------------------------------------------------

def test_cohort_minimum_n_is_5() -> None:
    """Surface-lock value per spec §4.3 + §4.7."""
    assert COHORT_MINIMUM_N == 5


def test_taxonomy_cohorts_lock() -> None:
    """The 4 registered cohort names in spec §4.3 + §4.7 order."""
    assert TAXONOMY_COHORTS == (
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
    )
    assert APLUS_COHORT == "A+ baseline"
    assert SUB_APLUS_COHORT == "Sub-A+ VCP-not-formed"


def test_doctrine_deviation_class_mapping_keys_match_taxonomy() -> None:
    """Spec §3.7 enum mapping covers exactly the 4 registered cohorts."""
    assert set(DOCTRINE_DEVIATION_CLASS.keys()) == set(TAXONOMY_COHORTS)
    assert set(DOCTRINE_DEVIATION_CLASS.values()) == {
        "baseline",
        "missing_proximity_20ma",
        "missing_tightness_or_vcp_volume_contraction",
        "smaller_than_standard_position",
    }


def test_cohort_statistics_post_init_rejects_n_wins_exceeds_n_closed() -> None:
    """Invariant: n_wins + n_losses <= n_closed."""
    from swing.metrics.honesty import HonestyBadges, WilsonCI
    badges = HonestyBadges(False, False)
    with pytest.raises(ValueError, match="n_wins \\+ n_losses must be"):
        CohortStatistics(
            cohort_name="X",
            n_closed=5,
            n_wins=4,
            n_losses=2,  # 4+2=6 > 5
            samples_R=(),
            legacy_trades_count=0,
            win_rate=WilsonCI(0.5, 0.4, 0.6),
            expectancy=SuppressedMetric(
                metric_name="x", n=0, n_required=5, placeholder_text="x",
            ),
            badges=badges,
            decision_criteria="x",
            target_sample_size=10,
        )


def test_tier_comparison_result_rejects_wrong_cohort_order() -> None:
    """TierComparisonResult enforces TAXONOMY_COHORTS order."""
    from swing.metrics.honesty import HonestyBadges, WilsonCI
    badges = HonestyBadges(False, False)
    wrong_order = (
        CohortStatistics(
            cohort_name="Sub-A+ VCP-not-formed",  # WRONG: should be A+ first
            n_closed=0, n_wins=0, n_losses=0, samples_R=(),
            legacy_trades_count=0,
            win_rate=SuppressedMetric(
                metric_name="x", n=0, n_required=5, placeholder_text="x",
            ),
            expectancy=SuppressedMetric(
                metric_name="x", n=0, n_required=5, placeholder_text="x",
            ),
            badges=badges, decision_criteria="x", target_sample_size=5,
        ),
    ) * 4
    with pytest.raises(ValueError, match="TAXONOMY_COHORTS order"):
        TierComparisonResult(
            cohorts=wrong_order,
            cohort_relative_to_aplus_pct={c: None for c in TAXONOMY_COHORTS},
            cohort_ci_overlap_descriptor="x",
            overlap_descriptor_suppressed=True,
        )


def test_compute_tier_comparison_includes_legacy_trade_counts(
    conn: sqlite3.Connection,
) -> None:
    """A trade with NULL risk_policy_id_at_lock is counted as legacy."""
    with conn:
        _seed_closed_trade(
            conn, trade_id=1, ticker="LEG",
            hypothesis_label=APLUS_COHORT,
            realized_pnl_dollars=100.0,
            risk_policy_id_at_lock=None,  # legacy stamp
        )
    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    assert aplus.legacy_trades_count == 1
    assert aplus.n_closed == 1
