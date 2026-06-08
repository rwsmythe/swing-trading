"""Phase 10 Sub-bundle D T-D.1 — capital-friction (spec §3.4) tests.

Covers:
- 6 spec §3.4 metrics + PROVISIONAL/LIVE dynamic badge (plan §A.6).
- 9 BINDING discriminating tests for ``risk_feasibility_blocked_rate``
  set-membership guard per plan §A.19 (Codex R1 M#1 + R2 M#3 + R3 M#3 +
  R4 M#1+M#2+M#3 sequence).
- §A.0.1 historical-reconstruction discipline (current trade state, not
  reconstructed).
- §A.15 session-anchor LOCK (asof_date is backward-looking).
- ``concurrent_open_positions`` historical proxy per plan §A.0.1 + T-D.1
  relocated test ("open at pre_trade_locked_at only").
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.evaluation.criteria.risk_feasibility import NAME as RISK_FEAS_NAME
from swing.metrics.capital import (
    EXPECTED_CRITERIA_NAMES,
    CapitalFrictionResult,
    _count_open_at_run,
    compute_capital_friction,
)

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_capital.db")


# Spec §1 18 expected criterion_name values per plan §A.19.
_FULL_PASS_CRITERIA: tuple[tuple[str, str], ...] = tuple(
    (name, "pass") for name in [
        "adr", "ma_stack_10_20_50", "ma_short_rising", "orderliness",
        "prior_trend", "proximity_20ma", "pullback", "risk_feasibility",
        "tightness", "vcp_volume_contraction",
        "TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
        "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
        "TT7_within_52w_high_25pct", "TT8_rs_rank",
    ]
)


def _seed_evaluation_run(
    conn: sqlite3.Connection,
    *,
    run_id: int = 1,
    run_ts: str = "2026-05-12T13:00:00",
    data_asof: str = "2026-05-11",
    action_session: str = "2026-05-12",
) -> int:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES "
        "(?, ?, ?, ?, 0, 0, 0, 0, 0, 0)",
        (run_id, run_ts, data_asof, action_session),
    )
    return run_id


def _seed_pipeline_run(
    conn: sqlite3.Connection,
    *,
    run_id: int = 1,
    started_ts: str = "2026-05-12T13:00:00",
    data_asof: str = "2026-05-11",
    action_session: str = "2026-05-12",
    state: str = "complete",
    evaluation_run_id: int | None = 1,
) -> int:
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES "
        "(?, ?, ?, 'manual', ?, ?, ?, 'tok', ?)",
        (run_id, started_ts, started_ts, data_asof, action_session, state,
         evaluation_run_id),
    )
    return run_id


def _seed_candidate(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    evaluation_run_id: int,
    ticker: str,
    bucket: str = "skip",
    criteria: tuple[tuple[str, str], ...] = _FULL_PASS_CRITERIA,
) -> int:
    """Seed a candidate row + its criterion result rows.

    ``criteria`` is an iterable of ``(criterion_name, result)`` pairs.
    Default emits ALL 18 EXPECTED criteria with ``result='pass'``.
    """
    conn.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, "
        "rs_method) VALUES (?, ?, ?, ?, 'universe')",
        (candidate_id, evaluation_run_id, ticker, bucket),
    )
    for name, result in criteria:
        # Layer must match CHECK enum ('trend_template','vcp','risk').
        if name == RISK_FEAS_NAME:
            layer = "risk"
        elif name.startswith("TT"):
            layer = "trend_template"
        else:
            layer = "vcp"
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, "
            "layer, result) VALUES (?, ?, ?, ?)",
            (candidate_id, name, layer, result),
        )
    return candidate_id


def _override_one_criterion(
    base: tuple[tuple[str, str], ...], *, name: str, new_result: str,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (n, new_result if n == name else r) for (n, r) in base
    )


def _seed_open_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    current_size: float = 100.0,
    current_avg_cost: float = 10.0,
    current_stop: float | None = None,
    state: str = "managing",
    pre_trade_locked_at: str = "2026-05-01T09:30:00",
    last_fill_at: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost, last_fill_at) VALUES (?, ?, '2026-05-01', ?, ?, "
        "?, ?, ?, 'S', 'I', 'manual_off_pipeline', ?, ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            current_stop if current_stop is not None else initial_stop,
            state, pre_trade_locked_at, current_size, current_avg_cost,
            last_fill_at,
        ),
    )


def _seed_closed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    pre_trade_locked_at: str,
    last_fill_at: str,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost, last_fill_at) VALUES (?, ?, '2026-04-01', 10.0, "
        "100, 9.0, 9.0, 'closed', 'S', 'I', 'manual_off_pipeline', ?, 0, "
        "10.0, ?)",
        (trade_id, ticker, pre_trade_locked_at, last_fill_at),
    )


def _seed_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    equity_dollars: float = 2000.0,
    source: str = "manual",
) -> None:
    conn.execute(
        "INSERT INTO account_equity_snapshots (snapshot_date, equity_dollars, "
        "source, recorded_at, recorded_by) VALUES (?, ?, ?, ?, 'test')",
        (snapshot_date, equity_dollars, source, snapshot_date + "T08:00:00"),
    )


# ---------------------------------------------------------------------------
# PROVISIONAL/LIVE dynamic badge tests (plan §A.6 + dispatch brief §0.8)
# ---------------------------------------------------------------------------

def test_compute_capital_friction_no_snapshot_returns_provisional_badge(conn):
    """With empty account_equity_snapshots, badge = PROVISIONAL and
    denominator = capital_floor_constant_dollars."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert isinstance(result, CapitalFrictionResult)
    assert result.capital_denominator_badge == "PROVISIONAL"
    assert result.capital_denominator_dollars == 7500.0


def test_capital_denominator_badge_text_matches_plan_a6_line_233_format(conn):
    """Plan §A.6 line 233 BINDING (Codex R1 M#1 + R2 m#2 fix): badge_text
    matches the locked format EXACTLY (full-string equality, not just
    substring containment)."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # EXACT string match per plan §A.6 line 233 LOCK.
    assert result.capital_denominator_badge_text == (
        "PROVISIONAL: $7,500.00 floor used as live-capital fallback "
        "(no snapshot ≤ 2026-05-12)"
    )
    # Seed a snapshot — text should switch to LIVE format exact-match.
    _seed_snapshot(conn, snapshot_date="2026-05-12", equity_dollars=2000.0)
    result2 = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result2.capital_denominator_badge_text == (
        "LIVE: $2,000.00 equity from account_equity_snapshots "
        "on-or-before 2026-05-12"
    )


def test_compute_capital_friction_with_snapshot_returns_live_badge(conn):
    """With a snapshot on-or-before asof_date, badge = LIVE and
    denominator = snapshot.equity_dollars (per plan §A.6 shipped code; NOT
    max-with-floor — brief §0.8 text was author-error)."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    _seed_snapshot(conn, snapshot_date="2026-05-11", equity_dollars=2000.0)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.capital_denominator_badge == "LIVE"
    assert result.capital_denominator_dollars == 2000.0


# ---------------------------------------------------------------------------
# 9 BINDING discriminating tests for risk_feasibility_blocked_rate (§A.19)
# ---------------------------------------------------------------------------

def test_risk_feasibility_blocked_rate_uses_constant_not_string_literal():
    """Plan §A.19 + Codex R5 Major #1: implementation imports
    ``NAME`` constant, not string literal."""
    from swing.metrics import capital as cap_mod
    src = Path(cap_mod.__file__).read_text(encoding="utf-8")
    assert (
        "from swing.evaluation.criteria.risk_feasibility import NAME" in src
    ), (
        "swing/metrics/capital.py must import NAME constant from "
        "swing.evaluation.criteria.risk_feasibility (plan §A.19 lock)"
    )
    # Defensive: assert the bare string literal 'risk_feasibility' is NOT
    # used in any rate-computation context. Allow doc/comments but not in
    # SQL or set-comparison code.
    assert "'risk_feasibility'" not in src, (
        "Bare string literal 'risk_feasibility' MUST NOT appear in "
        "swing/metrics/capital.py — use NAME constant"
    )


def test_risk_feasibility_blocked_rate_excludes_candidates_failing_other_criteria(conn):
    """Candidate failing risk_feasibility AND another criterion is NOT in
    numerator; rate stays bounded."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # C1: would-have-qualified except risk → numerator=1, denom=1.
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=_override_one_criterion(
                        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                        new_result="fail"))
    # C2: fails risk AND fails MA-stack → NOT in numerator.
    crit_c2 = _override_one_criterion(
        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME, new_result="fail")
    crit_c2 = _override_one_criterion(
        crit_c2, name="ma_stack_10_20_50", new_result="fail")
    _seed_candidate(conn, candidate_id=2, evaluation_run_id=eval_id,
                    ticker="BBB", criteria=crit_c2)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # Denominator = 1 (only C1); Numerator = 1 (C1 blocked); rate = 1.0.
    assert result.risk_feasibility_blocked_rate == 1.0
    assert result.risk_feasibility_blocked_rate <= 1.0  # rate bounded


def test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_other_criteria(conn):
    """Candidate with ``result='na'`` on non-risk criterion → excluded
    from denominator (na is not pass)."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # C1: all-pass-except risk-fail → denom contributor.
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=_override_one_criterion(
                        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                        new_result="fail"))
    # C2: risk='fail' but proximity='na' → excluded.
    crit_c2 = _override_one_criterion(
        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME, new_result="fail")
    crit_c2 = _override_one_criterion(
        crit_c2, name="proximity_20ma", new_result="na")
    _seed_candidate(conn, candidate_id=2, evaluation_run_id=eval_id,
                    ticker="BBB", criteria=crit_c2)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # Denom = 1 (only C1; C2 excluded due to na on non-risk).
    assert result.risk_feasibility_blocked_rate == 1.0


def test_risk_feasibility_blocked_rate_excludes_candidates_with_na_on_risk_feasibility(conn):
    """All-other-pass + risk_feasibility='na' → excluded BOTH sides."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # C1: clean blocked → num=1, denom=1, rate=1.0.
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=_override_one_criterion(
                        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                        new_result="fail"))
    # C2: all-pass + risk='na' → excluded.
    crit_c2 = _override_one_criterion(
        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME, new_result="na")
    _seed_candidate(conn, candidate_id=2, evaluation_run_id=eval_id,
                    ticker="BBB", criteria=crit_c2)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # Denom=1 (only C1); C2 excluded since na ≠ assessed.
    assert result.risk_feasibility_blocked_rate == 1.0


def test_risk_feasibility_blocked_rate_excludes_candidates_with_partial_criteria_rows(
    conn, caplog
):
    """Candidate with only 3 of 18 criterion rows → excluded BOTH sides +
    WARNING log emitted."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # C1: full + clean blocked → num=1, denom=1.
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=_override_one_criterion(
                        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                        new_result="fail"))
    # C2: only 3 of 18 criteria rows → excluded.
    partial = ((RISK_FEAS_NAME, "fail"), ("adr", "pass"),
               ("orderliness", "pass"))
    _seed_candidate(conn, candidate_id=2, evaluation_run_id=eval_id,
                    ticker="BBB", criteria=partial)
    with caplog.at_level(logging.WARNING, logger="swing.metrics.capital"):
        result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.risk_feasibility_blocked_rate == 1.0
    # Discriminating: WARNING log mentions candidate_id=2 + missing set.
    warning_msgs = [r.message for r in caplog.records
                    if r.levelname == "WARNING"]
    assert any("candidate_id=2" in m for m in warning_msgs), (
        f"Expected WARNING naming candidate_id=2; got: {warning_msgs}"
    )
    assert any("missing" in m.lower() for m in warning_msgs), (
        f"Expected WARNING with 'missing'; got: {warning_msgs}"
    )


def test_risk_feasibility_blocked_rate_set_membership_guard_catches_missing_plus_extra(
    conn, caplog
):
    """18 rows with 1 EXPECTED missing AND 1 UNKNOWN present (count=18 but
    membership wrong) → excluded + WARNING (discriminates set-guard vs
    count-only guard)."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=_override_one_criterion(
                        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                        new_result="fail"))
    # C2: drop adr; add bogus_unknown. Count = 18 still.
    perturbed = tuple(
        (n, r) for (n, r) in _override_one_criterion(
            _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME, new_result="fail")
        if n != "adr"
    ) + (("bogus_unknown", "pass"),)
    assert len(perturbed) == 18  # count-only guard would let this through.
    _seed_candidate(conn, candidate_id=2, evaluation_run_id=eval_id,
                    ticker="BBB", criteria=perturbed)
    with caplog.at_level(logging.WARNING, logger="swing.metrics.capital"):
        result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # C2 excluded → rate = 1.0 (only C1 counted).
    assert result.risk_feasibility_blocked_rate == 1.0
    warning_msgs = [r.message for r in caplog.records
                    if r.levelname == "WARNING"]
    assert any("candidate_id=2" in m and "adr" in m for m in warning_msgs), (
        f"Expected WARNING naming candidate_id=2 + missing 'adr'; got: "
        f"{warning_msgs}"
    )


def test_risk_feasibility_blocked_rate_extra_names_logs_info_not_excluded(
    conn, caplog
):
    """All 18 expected + 1 extra unknown → INCLUDED in rate + INFO log."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # C1 has 18 + 1 extra. fail risk_feasibility → still counted.
    base = _override_one_criterion(
        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME, new_result="fail")
    perturbed = base + (("extra_unknown", "pass"),)
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=perturbed)
    with caplog.at_level(logging.INFO, logger="swing.metrics.capital"):
        result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.risk_feasibility_blocked_rate == 1.0  # included
    info_msgs = [r.message for r in caplog.records if r.levelname == "INFO"]
    assert any("candidate_id=1" in m and "extra_unknown" in m
               for m in info_msgs), (
        f"Expected INFO naming candidate_id=1 + unexpected criterion "
        f"'extra_unknown'; got: {info_msgs}"
    )


def test_risk_feasibility_blocked_rate_expected_criteria_names_set_matches_pipeline_writer():
    """Plan §A.19 Codex R4 Major #1: EXPECTED_CRITERIA_NAMES set matches
    the names actually written by the pipeline writer ``_step_evaluate``."""
    # Discriminate against undercount: verify EXACTLY 18 names + each
    # individual name expected.
    expected_18 = frozenset({
        "adr", "ma_stack_10_20_50", "ma_short_rising", "orderliness",
        "prior_trend", "proximity_20ma", "pullback", "risk_feasibility",
        "tightness", "vcp_volume_contraction",
        "TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
        "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
        "TT7_within_52w_high_25pct", "TT8_rs_rank",
    })
    assert expected_18 == EXPECTED_CRITERIA_NAMES, (
        f"Drift between EXPECTED_CRITERIA_NAMES and pipeline writer enum: "
        f"missing={expected_18 - EXPECTED_CRITERIA_NAMES}, "
        f"extras={EXPECTED_CRITERIA_NAMES - expected_18}"
    )
    assert len(EXPECTED_CRITERIA_NAMES) == 18


def test_risk_feasibility_blocked_rate_at_most_1(conn):
    """Rate is bounded to [0, 1] — never above 1 even with adversarial seed."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # 3 candidates: all clean blocked.
    for cid, ticker in [(1, "AAA"), (2, "BBB"), (3, "CCC")]:
        _seed_candidate(conn, candidate_id=cid, evaluation_run_id=eval_id,
                        ticker=ticker, criteria=_override_one_criterion(
                            _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                            new_result="fail"))
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.risk_feasibility_blocked_rate is not None
    assert 0.0 <= result.risk_feasibility_blocked_rate <= 1.0


def test_risk_feasibility_blocked_rate_at_zero_qualifying_returns_suppressed(conn):
    """Zero would-have-qualified candidates → suppressed text not NaN."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    # Candidate fails MA-stack (NOT would-have-qualified).
    crit = _override_one_criterion(
        _FULL_PASS_CRITERIA, name="ma_stack_10_20_50", new_result="fail")
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=crit)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.risk_feasibility_blocked_rate is None
    assert result.risk_feasibility_blocked_rate_suppressed_text is not None
    assert (
        "N/A — 0 would-have-qualified candidates this run"
        in result.risk_feasibility_blocked_rate_suppressed_text
    )


# ---------------------------------------------------------------------------
# §3.4 other-metrics tests
# ---------------------------------------------------------------------------

def test_concurrent_open_positions_counts_entered_managing_partial_exited(conn):
    """Counts trades in state ∈ {entered, managing, partial_exited}."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA", state="entered")
    _seed_open_trade(conn, trade_id=2, ticker="BBB", state="managing")
    _seed_open_trade(conn, trade_id=3, ticker="CCC", state="partial_exited")
    _seed_closed_trade(conn, trade_id=4, ticker="DDD",
                       pre_trade_locked_at="2026-04-01T09:30:00",
                       last_fill_at="2026-04-08T15:30:00")
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.concurrent_open_positions == 3


def test_capital_cycle_time_days_zero_closed_returns_none(conn):
    """Empty closed-cohort → cycle_time_days is None."""
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.capital_cycle_time_days is None


def test_capital_cycle_time_days_simple_mean(conn):
    """Mean over closed trades (last_fill_at - pre_trade_locked_at)."""
    _seed_closed_trade(conn, trade_id=1, ticker="AAA",
                       pre_trade_locked_at="2026-04-01T09:30:00",
                       last_fill_at="2026-04-08T15:30:00")  # 7 days
    _seed_closed_trade(conn, trade_id=2, ticker="BBB",
                       pre_trade_locked_at="2026-04-01T09:30:00",
                       last_fill_at="2026-04-15T15:30:00")  # 14 days
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.capital_cycle_time_days is not None
    # Mean of 7 days and 14 days = 10.5 days (each truncates the timestamp
    # delta to whole-day precision: 7.25d and 14.25d → mean ≈ 10.75d).
    assert 10.5 < result.capital_cycle_time_days < 11.0


def test_current_capital_utilization_pct_rendered_as_percent(conn):
    """current_capital_utilization_pct is PERCENT (e.g., 45.0 = 45%)."""
    # Floor $7500; one position with $7500 / 2 = $3750 exposure → 50%.
    _seed_open_trade(conn, trade_id=1, ticker="AAA", entry_price=37.5,
                     current_size=100.0, current_avg_cost=37.5,
                     initial_stop=33.75)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # exposure = 37.5 * 100 = $3750; capital = $7500 (PROVISIONAL).
    # utilization = 3750/7500 * 100 = 50.0%.
    assert result.capital_denominator_badge == "PROVISIONAL"
    assert result.capital_denominator_dollars == 7500.0
    assert result.current_capital_utilization_pct is not None
    assert abs(result.current_capital_utilization_pct - 50.0) < 0.01


def test_current_portfolio_heat_pct_rendered_as_percent(conn):
    """current_portfolio_heat_pct is PERCENT."""
    # avg_cost=$10, stop=$9, size=100 → heat contrib = (10-9)*100=$100.
    # Floor $7500; heat = 100/7500 * 100 ≈ 1.333%.
    _seed_open_trade(conn, trade_id=1, ticker="AAA", entry_price=10.0,
                     current_size=100.0, current_avg_cost=10.0,
                     current_stop=9.0)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.current_portfolio_heat_pct is not None
    assert abs(result.current_portfolio_heat_pct - 1.3333) < 0.01


def test_capital_feasibility_pressure_index_composite(conn):
    """capital_feasibility_pressure_index = blocked_rate * utilization_pct
    (proportion form: utilization_pct/100 * blocked_rate)."""
    eval_id = _seed_evaluation_run(conn)
    _seed_pipeline_run(conn, evaluation_run_id=eval_id)
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=eval_id,
                    ticker="AAA", criteria=_override_one_criterion(
                        _FULL_PASS_CRITERIA, name=RISK_FEAS_NAME,
                        new_result="fail"))
    # 50% utilization (per fixture above).
    _seed_open_trade(conn, trade_id=10, ticker="ZZZ", entry_price=37.5,
                     current_size=100.0, current_avg_cost=37.5,
                     initial_stop=33.75)
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    # blocked=1.0, utilization=50%; composite = 1.0 * 0.50 = 0.50.
    assert result.capital_feasibility_pressure_index is not None
    assert abs(result.capital_feasibility_pressure_index - 0.50) < 0.01


def test_capital_feasibility_pressure_index_none_when_blocked_suppressed(conn):
    """Composite is None when either input is None."""
    # No pipeline_run → no blocked_rate available.
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.risk_feasibility_blocked_rate is None
    assert result.capital_feasibility_pressure_index is None


# ---------------------------------------------------------------------------
# §A.0.1 historical-reconstruction discipline tests
# ---------------------------------------------------------------------------

def test_compute_capital_friction_historical_trend_uses_current_trade_state(
    conn,
):
    """Plan §A.0.1 Codex R2 Major #4: historical trend points compute
    against CURRENT trade state (NOT historical reconstruction).

    Seed trade T1 with current_size=200; trade was opened with
    initial_shares=100. Run R1 happened at trade-open time.
    Query for R1 → utilization computed against current_size=200.
    """
    asof = date(2026, 5, 12)
    sessions = _trading_sessions(asof, 5)
    # First session (oldest) is R1 — the trade was locked at that session.
    r1_session = sessions[0]
    eval_id = _seed_evaluation_run(
        conn, run_id=1, run_ts=r1_session + "T13:00",
        data_asof=r1_session, action_session=r1_session,
    )
    _seed_pipeline_run(
        conn, run_id=1, started_ts=r1_session + "T13:00:00",
        data_asof=r1_session, action_session=r1_session,
        evaluation_run_id=eval_id,
    )
    # Trade with current_size=200 (changed since R1).
    _seed_open_trade(conn, trade_id=1, ticker="AAA",
                     entry_price=37.5, initial_shares=100,
                     current_size=200.0, current_avg_cost=37.5,
                     initial_stop=33.75,
                     pre_trade_locked_at=r1_session + "T09:30:00",
                     last_fill_at=None)
    # Seed 4 more runs on subsequent trading sessions.
    for i, sd in enumerate(sessions[1:], start=2):
        _seed_evaluation_run(
            conn, run_id=i, run_ts=sd + "T13:00",
            data_asof=sd, action_session=sd,
        )
        _seed_pipeline_run(
            conn, run_id=i, started_ts=sd + "T13:00:00",
            data_asof=sd, action_session=sd,
            evaluation_run_id=i,
        )
    result = compute_capital_friction(conn, asof_date=asof)
    # Find run R1 in trend.
    r1_points = [
        p for p in result.trend_runs if p.pipeline_run_id == 1
    ]
    assert len(r1_points) == 1, (
        f"Expected R1 in trend; got: {result.trend_runs}"
    )
    r1 = r1_points[0]
    # exposure = 37.5 * 200 = $7500 → utilization = 7500/7500*100 = 100%.
    # If historical reconstruction were used (initial_shares=100):
    #   exposure = 37.5 * 100 = $3750 → utilization = 50%.
    # Discriminating: assert 100% (CURRENT state), NOT 50% (historical).
    assert r1.current_capital_utilization_pct is not None
    assert abs(r1.current_capital_utilization_pct - 100.0) < 0.5, (
        f"Historical trend MUST use current_size=200 (current state) → "
        f"100%, NOT initial_shares=100 → 50%; got: "
        f"{r1.current_capital_utilization_pct}"
    )


def test_concurrent_open_positions_at_historical_run_uses_open_at_pre_trade_locked_at_only(
    conn,
):
    """Plan §A.0.1 Codex R3 Major #2 (relocated from D.5): historical
    ``concurrent_open_positions`` uses ``pre_trade_locked_at <= run.started_ts
    AND (last_fill_at IS NULL OR last_fill_at >= run.started_ts)``."""
    asof = date(2026, 5, 12)
    sessions = _trading_sessions(asof, 5)
    r1_session = sessions[2]  # middle of window
    eval_id = _seed_evaluation_run(
        conn, run_id=1, run_ts=r1_session + "T13:00",
        data_asof=r1_session, action_session=r1_session,
    )
    _seed_pipeline_run(
        conn, run_id=1, started_ts=r1_session + "T13:00:00",
        data_asof=r1_session, action_session=r1_session,
        evaluation_run_id=eval_id,
    )
    # Trade T1: locked before R1, no fill_at yet (still open at R1).
    _seed_open_trade(conn, trade_id=1, ticker="OPEN1",
                     pre_trade_locked_at=sessions[0] + "T09:30:00",
                     last_fill_at=None)
    # Trade T2: locked AFTER R1 (not open at R1).
    _seed_open_trade(conn, trade_id=2, ticker="OPEN2",
                     pre_trade_locked_at=sessions[4] + "T09:30:00",
                     last_fill_at=None)
    # Trade T3: locked before R1, closed BEFORE R1.
    _seed_closed_trade(conn, trade_id=3, ticker="CLOSED",
                       pre_trade_locked_at=sessions[0] + "T09:30:00",
                       last_fill_at=sessions[1] + "T15:30:00")
    # Trade T4: locked before R1, closed AFTER R1 — still open at R1.
    _seed_closed_trade(conn, trade_id=4, ticker="LATER",
                       pre_trade_locked_at=sessions[1] + "T09:30:00",
                       last_fill_at=sessions[3] + "T15:30:00")
    # Need ≥5 runs.
    for i, sd in enumerate(sessions, start=2):
        if sd == r1_session:
            continue
        _seed_evaluation_run(
            conn, run_id=i, run_ts=sd + "T13:00",
            data_asof=sd, action_session=sd,
        )
        _seed_pipeline_run(
            conn, run_id=i, started_ts=sd + "T13:00:00",
            data_asof=sd, action_session=sd,
            evaluation_run_id=i,
        )
    result = compute_capital_friction(conn, asof_date=asof)
    r1_points = [p for p in result.trend_runs if p.pipeline_run_id == 1]
    assert len(r1_points) == 1
    r1 = r1_points[0]
    # Open at R1 = T1 (still open) + T4 (closed after R1). NOT T2 or T3.
    assert r1.concurrent_open_positions == 2, (
        f"Expected 2 trades open at R1 (T1 + T4); got: "
        f"{r1.concurrent_open_positions}"
    )


# ---------------------------------------------------------------------------
# §I.13 session-anchor round-trip integration test (BINDING)
# ---------------------------------------------------------------------------

def test_session_anchor_round_trip_provisional_to_live_after_snapshot_write(
    conn,
):
    """Plan §I.13 BINDING: write snapshot at session N + immediately invoke
    compute_capital_friction(asof_date=N) + assert LIVE badge returned.

    Discriminates against forward-looking ``action_session_for_run`` for
    asof_date (would create the session-anchor read/write mismatch family).
    """
    _seed_open_trade(conn, trade_id=1, ticker="AAA")
    asof = date(2026, 5, 12)
    # Before snapshot → PROVISIONAL.
    pre = compute_capital_friction(conn, asof_date=asof)
    assert pre.capital_denominator_badge == "PROVISIONAL"
    # Write snapshot on session N.
    _seed_snapshot(conn, snapshot_date="2026-05-12", equity_dollars=2500.0)
    # Immediately re-query.
    post = compute_capital_friction(conn, asof_date=asof)
    assert post.capital_denominator_badge == "LIVE"
    assert post.capital_denominator_dollars == 2500.0


def test_compute_capital_friction_returns_asof_date_field(conn):
    """Result carries asof_date for VM-layer rendering."""
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.asof_date == "2026-05-12"


# ---------------------------------------------------------------------------
# Trend suppression + §A.0.1 disclaimer-required tests
# ---------------------------------------------------------------------------

def _trading_sessions(end: date, n: int) -> list[str]:
    """Return n most-recent NYSE trading session ISO dates ending at `end`."""
    import exchange_calendars
    import pandas as pd
    cal = exchange_calendars.get_calendar("XNYS")
    return sorted({
        ts.date().isoformat()
        for ts in cal.sessions_window(pd.Timestamp(end), -n)
    })


def test_trend_suppressed_below_5_runs(conn):
    """Spec §4.4: multi-run trend suppressed at <5 runs."""
    sessions = _trading_sessions(date(2026, 5, 12), 3)
    for i, sd in enumerate(sessions, start=1):
        _seed_evaluation_run(
            conn, run_id=i, run_ts=sd + "T13:00",
            data_asof=sd, action_session=sd,
        )
        _seed_pipeline_run(
            conn, run_id=i, started_ts=sd + "T13:00:00",
            data_asof=sd, action_session=sd,
            evaluation_run_id=i,
        )
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.trend_suppressed is True
    assert result.trend_suppressed_text is not None


def test_trend_rendered_at_5_runs(conn):
    """Spec §4.4: trend rendered once n≥5 runs."""
    sessions = _trading_sessions(date(2026, 5, 12), 5)
    for i, sd in enumerate(sessions, start=1):
        _seed_evaluation_run(
            conn, run_id=i, run_ts=sd + "T13:00",
            data_asof=sd, action_session=sd,
        )
        _seed_pipeline_run(
            conn, run_id=i, started_ts=sd + "T13:00:00",
            data_asof=sd, action_session=sd,
            evaluation_run_id=i,
        )
    result = compute_capital_friction(conn, asof_date=date(2026, 5, 12))
    assert result.trend_suppressed is False
    assert len(result.trend_runs) == 5


def test_dataclass_post_init_rejects_nan_or_inf():
    """Lesson #1: ``__post_init__`` validators reject NaN/inf on numeric
    fields."""
    from swing.metrics.capital import CapitalFrictionResult
    base_kwargs = dict(
        asof_date="2026-05-12",
        current_capital_utilization_pct=None,
        current_portfolio_heat_pct=None,
        concurrent_open_positions=0,
        capital_cycle_time_days=None,
        latest_run_id=None,
        risk_feasibility_blocked_rate=None,
        risk_feasibility_blocked_rate_suppressed_text=None,
        capital_feasibility_pressure_index=None,
        capital_denominator_dollars=7500.0,
        capital_denominator_badge="PROVISIONAL",
        capital_denominator_badge_text="PROVISIONAL: $7,500.00 placeholder",
        trend_runs=(),
        trend_suppressed=True,
        trend_suppressed_text="placeholder",
    )
    with pytest.raises(ValueError, match="finite|NaN|inf"):
        CapitalFrictionResult(
            **{**base_kwargs, "current_capital_utilization_pct": float("nan")}
        )
    with pytest.raises(ValueError):
        CapitalFrictionResult(
            **{**base_kwargs, "concurrent_open_positions": -1}
        )
    with pytest.raises(ValueError, match="badge|PROVISIONAL|LIVE"):
        CapitalFrictionResult(
            **{**base_kwargs, "capital_denominator_badge": "FOO"}
        )


# ---------------------------------------------------------------------------
# Issue #3 — _count_open_at_run state-based predicate (spec
# docs/superpowers/specs/2026-06-07-count-open-at-run-predicate-design.md).
#
# The E1-E11 edge-case matrix (spec §4). The fix gates the terminal
# ``last_fill_at`` clause behind ``state NOT IN ('closed','reviewed')`` so a
# still-open trade entered before the run (whose only fill is its entry,
# ``last_fill_at < started_ts``) is no longer wrongly excluded.
#
# E1/E4/E5 are the discriminating regressions: asserted under BOTH the
# pre-fix (buggy) predicate and the shipped predicate per
# feedback_regression_test_arithmetic.
# ---------------------------------------------------------------------------

# Chosen historical run-start instant for the whole E-matrix.
_R = "2026-05-10T13:00:00"


def _old_predicate_count(conn: sqlite3.Connection, started_ts: str) -> int:
    """The PRE-FIX (buggy) predicate, reproduced verbatim.

    Treats ``last_fill_at`` as a close time for EVERY trade
    (``last_fill_at IS NULL OR last_fill_at = '' OR last_fill_at >= ?``),
    with NO ``state`` gate. Used by the E1/E4/E5 discriminating tests to
    prove the fixture genuinely exercises the difference between the old and
    new predicate (feedback_regression_test_arithmetic), not just the new
    behavior.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM trades "
        "WHERE pre_trade_locked_at IS NOT NULL "
        "AND pre_trade_locked_at <> '' "
        "AND pre_trade_locked_at <= ? "
        "AND (last_fill_at IS NULL OR last_fill_at = '' "
        "     OR last_fill_at >= ?)",
        (started_ts, started_ts),
    ).fetchone()
    return int(row[0])


def _seed_trade_row(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    state: str,
    pre_trade_locked_at: str | None,
    last_fill_at: str | None,
) -> None:
    """Minimal trade row carrying only the columns ``_count_open_at_run``
    reads: ``state``, ``pre_trade_locked_at``, ``last_fill_at``. Other
    columns are filled with COUNT-irrelevant placeholders."""
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost, last_fill_at) VALUES (?, ?, '2026-05-01', 10.0, "
        "100, 9.0, 9.0, ?, 'S', 'I', 'manual_off_pipeline', ?, 100, 10.0, ?)",
        (trade_id, ticker, state, pre_trade_locked_at, last_fill_at),
    )


# --- E1/E4/E5: discriminating regressions (old=0, new=1) -------------------

def test_e1_still_open_entered_before_run_skyt(conn):
    """E1 (SKYT): non-terminal trade entered before R whose only fill is the
    entry (``last_fill_at < R``, non-NULL). Old predicate WRONGLY excludes
    (→0); new predicate counts (→1)."""
    _seed_trade_row(conn, trade_id=1, ticker="SKYT", state="managing",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-05T09:30:00")
    assert _old_predicate_count(conn, _R) == 0  # pre-fix: wrongly excluded
    assert _count_open_at_run(conn, started_ts=_R) == 1  # fixed: counted


def test_e4_partial_stop_still_open(conn):
    """E4: a partial STOP fill (``action='stop'``) sits on a still-open
    ``partial_exited`` trade; its ``last_fill_at`` is the pre-run stop fill.
    The G2 partial-stop hazard — old predicate excludes (→0); new counts
    (→1) by keying on state, not the fill timestamp."""
    _seed_trade_row(conn, trade_id=1, ticker="PSTP", state="partial_exited",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-08T15:30:00")
    assert _old_predicate_count(conn, _R) == 0  # pre-fix: wrongly excluded
    assert _count_open_at_run(conn, started_ts=_R) == 1  # fixed: counted


def test_e5_trim_then_still_open(conn):
    """E5: a partial TRIM scale-out on a still-open ``partial_exited`` trade;
    ``last_fill_at`` is the pre-run trim fill. Old predicate excludes (→0);
    new counts (→1)."""
    _seed_trade_row(conn, trade_id=1, ticker="TRIM", state="partial_exited",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-08T15:30:00")
    assert _old_predicate_count(conn, _R) == 0  # pre-fix: wrongly excluded
    assert _count_open_at_run(conn, started_ts=_R) == 1  # fixed: counted


# --- E2/E3/E6/E7/E9/E10: agreement / behavior cases ------------------------

def test_e2_stop_closed_before_run(conn):
    """E2: ``closed`` trade whose closing fill is before R → not open at R
    → 0 (old and new agree)."""
    _seed_trade_row(conn, trade_id=1, ticker="E2", state="closed",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-08T15:30:00")
    assert _count_open_at_run(conn, started_ts=_R) == 0


def test_e3_closed_at_or_after_run_start(conn):
    """E3: ``closed`` trade whose closing fill is at/after R → was open at R
    → 1 (old and new agree)."""
    _seed_trade_row(conn, trade_id=1, ticker="E3", state="closed",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-11T15:30:00")
    assert _count_open_at_run(conn, started_ts=_R) == 1


def test_e6_entered_after_run(conn):
    """E6: trade locked AFTER R → excluded by the outer entry guard → 0."""
    _seed_trade_row(conn, trade_id=1, ticker="E6", state="managing",
                    pre_trade_locked_at="2026-05-15T09:30:00",
                    last_fill_at=None)
    assert _count_open_at_run(conn, started_ts=_R) == 0


def test_e7_reviewed_closed_before_run(conn):
    """E7: ``reviewed`` (terminal, treated identically to ``closed``) whose
    last fill is before R → 0."""
    _seed_trade_row(conn, trade_id=1, ticker="E7", state="reviewed",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-08T15:30:00")
    assert _count_open_at_run(conn, started_ts=_R) == 0


def test_e8_closed_null_last_fill_degrades_to_count(conn):
    """E8: anomalous ``closed`` row with NULL ``last_fill_at`` →
    degrade-to-count (preserves the NULL-permissive branch) → 1."""
    _seed_trade_row(conn, trade_id=1, ticker="E8", state="closed",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at=None)
    assert _count_open_at_run(conn, started_ts=_R) == 1


def test_e9_boundary_closed_exactly_at_run_start_inclusive(conn):
    """E9: ``closed`` with ``last_fill_at == R`` → ``>=`` inclusive boundary
    (OQ-2) counts it → 1."""
    _seed_trade_row(conn, trade_id=1, ticker="E9", state="closed",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at=_R)
    assert _count_open_at_run(conn, started_ts=_R) == 1


def test_e10_empty_pre_trade_locked_at_excluded(conn):
    """E10: rows with empty ``pre_trade_locked_at`` → excluded by the
    unchanged outer ``<> ''`` guard → 0.

    Note: the live schema declares ``pre_trade_locked_at TEXT NOT NULL``
    (migration 0014:163), so an actual NULL is unseedable; the predicate's
    ``IS NOT NULL`` clause is a defensive guard (mirrors the holding-period
    query style) and only the empty-string case is reachable here.
    """
    _seed_trade_row(conn, trade_id=1, ticker="E10E", state="managing",
                    pre_trade_locked_at="", last_fill_at=None)
    assert _count_open_at_run(conn, started_ts=_R) == 0


# --- E11: degrade-safe malformed-timestamp test ----------------------------

def test_e11_malformed_last_fill_at_degrades_safely(conn):
    """E11 (degrade-safe, spec §4 + G4 caveat): a ``closed`` row whose
    ``last_fill_at`` is a malformed/non-ISO string (a correction-path or
    legacy artifact) MUST NOT crash the COUNT query. Since the predicate is
    pure SQL string comparison (no ``datetime.fromisoformat`` parse), the
    malformed value simply sorts lexicographically.

    The query is a ``COUNT(*)`` so per-row contribution is unobservable;
    instead assert (a) the call returns an ``int`` and does not raise; and
    (b) the DETERMINISTIC delta — count N well-formed rows, re-count after
    adding exactly one malformed-``last_fill_at`` closed row, assert the
    difference equals that row's explicitly-specified lexicographic outcome.

    Chosen malformed value: ``"garbage-not-iso"``. SQLite TEXT columns use
    the default BINARY collation, so this compares byte-wise: ``'g'``
    (0x67) > ``'2'`` (0x32), hence ``"garbage-not-iso" >= started_ts`` is
    TRUE → the closed row counts → delta = +1. (A meaningless-but-bounded
    over-order; never an exception.)
    """
    # N=2 well-formed still-open rows → known baseline count.
    _seed_trade_row(conn, trade_id=1, ticker="WF1", state="managing",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="2026-05-05T09:30:00")
    _seed_trade_row(conn, trade_id=2, ticker="WF2", state="managing",
                    pre_trade_locked_at="2026-05-06T09:30:00",
                    last_fill_at="2026-05-06T09:30:00")
    baseline = _count_open_at_run(conn, started_ts=_R)
    assert baseline == 2

    # Add exactly one closed row with a malformed last_fill_at.
    _seed_trade_row(conn, trade_id=3, ticker="BADTS", state="closed",
                    pre_trade_locked_at="2026-05-05T09:30:00",
                    last_fill_at="garbage-not-iso")
    after = _count_open_at_run(conn, started_ts=_R)

    # (a) no crash, returns an int.
    assert isinstance(after, int)
    # (b) deterministic delta = +1 (lexicographic outcome above).
    assert after - baseline == 1
