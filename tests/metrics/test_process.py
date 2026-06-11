"""Phase 10 Sub-bundle B T-B.1 — trade-process metric computation tests."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.honesty import BootstrapCI, SuppressedMetric, WilsonCI
from swing.metrics.process import (
    TradeProcessMetricsResult,
    compute_trade_process_metrics,
)


# ---------------------------------------------------------------------------
# Fixtures + DB seeders
# ---------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Schema-v17 DB; seed risk_policy already populated by ensure_schema."""
    return ensure_schema(tmp_path / "phase10_process.db")


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str | None = "A+ baseline",
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    state: str = "closed",
    risk_policy_id_at_lock: int | None = None,
    pre_trade_locked_at: str = "2026-04-01T09:30:00",
    last_fill_at: str | None = "2026-04-08T09:30:00",
    realized_R_if_plan_followed: float | None = None,  # noqa: N803
    reviewed_at: str | None = None,
    mistake_tags: str | None = None,
    process_grade: str | None = None,
    disqualifying_process_violation: int | None = None,
    entry_intent: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, risk_policy_id_at_lock, last_fill_at, "
        "realized_R_if_plan_followed, reviewed_at, mistake_tags, "
        "process_grade, disqualifying_process_violation, entry_intent) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, 'S', 'I', 'manual_off_pipeline', ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            trade_id, ticker, "2026-04-01",
            entry_price, initial_shares, initial_stop, initial_stop, state,
            pre_trade_locked_at, initial_shares, hypothesis_label,
            risk_policy_id_at_lock, last_fill_at,
            realized_R_if_plan_followed, reviewed_at, mistake_tags,
            process_grade, disqualifying_process_violation, entry_intent,
        ),
    )
    conn.commit()


def _seed_fill(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    fill_datetime: str,
    action: str,
    quantity: float,
    price: float,
    fees: float | None = None,
) -> None:
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, fees, reconciliation_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, fill_datetime, action, quantity, price, fees, "unreconciled"),
    )
    conn.commit()


def _seed_full_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    entry_price: float,
    initial_stop: float,
    initial_shares: int,
    exit_price: float,
    fees: float | None = None,
    hypothesis_label: str | None = "A+ baseline",
    reviewed_at: str | None = None,
    realized_R_if_plan_followed: float | None = None,  # noqa: N803
    risk_policy_id_at_lock: int | None = None,
    pre_trade_locked_at: str = "2026-04-01T09:30:00",
    last_fill_at: str = "2026-04-08T15:30:00",
    state: str = "closed",
    mistake_tags: str | None = None,
    process_grade: str | None = None,
    disqualifying_process_violation: int | None = None,
    entry_intent: str | None = None,
) -> None:
    """Helper: seed trade + entry fill + exit fill so the cohort
    aggregator computes realized_R correctly."""
    _seed_trade(
        conn,
        trade_id=trade_id, ticker=ticker,
        entry_price=entry_price, initial_stop=initial_stop,
        initial_shares=initial_shares,
        hypothesis_label=hypothesis_label,
        state=state, reviewed_at=reviewed_at,
        risk_policy_id_at_lock=risk_policy_id_at_lock,
        pre_trade_locked_at=pre_trade_locked_at,
        last_fill_at=last_fill_at,
        realized_R_if_plan_followed=realized_R_if_plan_followed,
        mistake_tags=mistake_tags,
        process_grade=process_grade,
        disqualifying_process_violation=disqualifying_process_violation,
        entry_intent=entry_intent,
    )
    _seed_fill(
        conn, trade_id=trade_id, fill_datetime=pre_trade_locked_at,
        action="entry", quantity=initial_shares, price=entry_price,
    )
    _seed_fill(
        conn, trade_id=trade_id, fill_datetime=last_fill_at,
        action="exit", quantity=initial_shares, price=exit_price,
        fees=fees,
    )


# ---------------------------------------------------------------------------
# Empty-cohort discriminating tests (§A.16 + §I.14 binding)
# ---------------------------------------------------------------------------

def test_compute_metrics_empty_cohort_returns_all_suppressed(
    conn: sqlite3.Connection,
) -> None:
    """Empty cohort: every Class A/B/C metric returns SuppressedMetric."""
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert isinstance(result, TradeProcessMetricsResult)
    assert result.n_closed == 0
    assert result.n_wins == 0
    assert result.n_losses == 0
    assert result.n_scratches == 0
    assert result.n_reviewed == 0
    assert isinstance(result.realized_R.value, SuppressedMetric)
    assert isinstance(result.expectancy_R.value, SuppressedMetric)
    assert isinstance(result.win_rate.value, SuppressedMetric)
    assert isinstance(result.loss_rate.value, SuppressedMetric)
    assert isinstance(result.scratch_rate.value, SuppressedMetric)
    assert isinstance(result.profit_factor.value, SuppressedMetric)
    assert isinstance(result.payoff_ratio.value, SuppressedMetric)
    # Cohort SUM totals always render as 0.0 (point); no suppression for sums.
    assert result.mistake_cost_R_total.value == 0.0
    assert result.lucky_violation_R_total.value == 0.0


def test_empty_cohort_when_label_none_aggregates_all(
    conn: sqlite3.Connection,
) -> None:
    """`hypothesis_label=None` returns the "all closed" aggregate (per spec §4.1)."""
    result = compute_trade_process_metrics(conn, hypothesis_label=None)
    assert result.cohort_label is None
    assert result.n_closed == 0


# ---------------------------------------------------------------------------
# Per-trade win/loss/scratch classification (AT-TRADE-TIME policy)
# ---------------------------------------------------------------------------

def test_n3_class_a_renders_wilson_ci_class_b_suppresses(
    conn: sqlite3.Connection,
) -> None:
    """Per migration 0017 seed: class_a_n=3, class_b_n=5, class_c_n=5.

    At n=3 closed trades:
      - Class A (win_rate / loss_rate / scratch_rate) renders WilsonCI.
      - Class B (realized_R / expectancy_R / ...) SUPPRESSES (n<5).
      - Class C (profit_factor / payoff_ratio) SUPPRESSES (n<5 + diversity).

    Plan §E acceptance text spoke of "Class B point-estimate-with-warning
    at n=3" matching spec §5.2 — but the shipped Phase 9 Sub-bundle A
    migration seed has ``low_sample_size_threshold_class_b_n=5`` (matches
    spec §5.3 "≥5 for bootstrap CI"). This test pins behavior against
    PRODUCTION seed values; downstream tests at n=5 exercise the Class B
    bootstrap-CI branch.
    """
    # Three winners: each +2R (entry=10, stop=9, exit=12 ⇒ +2R).
    for i in range(1, 4):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"T{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0,
        )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.n_closed == 3
    assert result.n_wins == 3
    # Class A at n=3 renders WilsonCI (production seed class_a_n=3).
    assert isinstance(result.win_rate.value, WilsonCI)
    assert result.win_rate.badges.confidence_floor_warning is True
    # Class B at n=3 SUPPRESSED (production seed class_b_n=5).
    assert isinstance(result.realized_R.value, SuppressedMetric)
    # Class C at n=3 + n_losses=0 → suppressed (low n; diversity is
    # secondary).
    assert isinstance(result.profit_factor.value, SuppressedMetric)
    assert isinstance(result.payoff_ratio.value, SuppressedMetric)


def test_n5_class_b_renders_bootstrap_ci_below_confidence_floor(
    conn: sqlite3.Connection,
) -> None:
    """At n=5 closed trades (≥ class_b_n=5):
      - Class B renders BootstrapCI.
      - confidence_floor_warning=True (n < global_confidence_floor_n=20).
      - low_confidence_warning=False (n>=5 not in 3..4 band).
    """
    # 3 winners (+2R) + 2 losers (-1R) — provides diversity for Class C also.
    for i in range(1, 4):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"W{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0,
        )
    for i in range(4, 6):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"L{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=9.0,
        )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.n_closed == 5
    assert isinstance(result.realized_R.value, BootstrapCI)
    assert result.realized_R.badges.confidence_floor_warning is True
    assert result.realized_R.badges.low_confidence_warning is False
    # Class A still renders + carries confidence_floor_warning.
    assert isinstance(result.win_rate.value, WilsonCI)
    assert result.win_rate.badges.confidence_floor_warning is True


def test_scratch_classification_uses_at_trade_time_scratch_epsilon(
    conn: sqlite3.Connection,
) -> None:
    """Per plan §A.5: a trade stamped under policy_id with
    scratch_epsilon=0.05 is classified differently from a trade stamped
    under scratch_epsilon=0.50, even for the SAME realized_R value.

    Trade A: realized_R≈+0.10, stamped under epsilon=0.05 → 'win'.
    Trade B: realized_R≈+0.10, stamped under epsilon=0.50 → 'scratch'.
    """
    # Seed two distinct policies. The default seed policy_id=1 has
    # scratch_epsilon=0.10 (ratified-default per Phase 9 Sub-bundle A).
    # Insert policy_id=2 with scratch_epsilon=0.50.
    conn.execute(
        "UPDATE risk_policy SET is_active=0 WHERE policy_id=1",
    )
    # Re-read the row to know its full shape; we'll just INSERT a second
    # with the same constants but different scratch_epsilon.
    p1 = conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id=1",
    ).fetchone()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id=1",
    ).description]
    base = dict(zip(cols, p1))
    base["policy_id"] = 2
    base["scratch_epsilon_R"] = 0.50
    base["is_active"] = 1
    base["effective_from"] = "2026-04-15T00:00:00.000"
    placeholders = ",".join(["?"] * len(cols))
    conn.execute(
        f"INSERT INTO risk_policy ({','.join(cols)}) "  # noqa: S608
        f"VALUES ({placeholders})",
        [base[c] for c in cols],
    )
    conn.commit()

    # Both trades end with realized_R ≈ +0.10 (exit at 10.10 vs entry at 10).
    _seed_full_trade(
        conn, trade_id=1, ticker="EPSA",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.10, risk_policy_id_at_lock=1,
    )
    _seed_full_trade(
        conn, trade_id=2, ticker="EPSB",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.10, risk_policy_id_at_lock=2,
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    # Trade A: |0.10| >= 0.05 ⇒ 'win'; Trade B: |0.10| < 0.50 ⇒ 'scratch'.
    assert result.n_wins == 1
    assert result.n_scratches == 1
    assert result.n_losses == 0


def test_legacy_trade_with_null_stamp_uses_live_policy_with_annotation(
    conn: sqlite3.Connection,
) -> None:
    """Per §A.5: trades with NULL risk_policy_id_at_lock fall back to LIVE
    policy. Result surfaces ``legacy_trades_count`` so the dashboard layer
    can render ``[legacy: pre-Phase-9 trade]`` annotation."""
    _seed_full_trade(
        conn, trade_id=1, ticker="LEGY",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0, risk_policy_id_at_lock=None,
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.legacy_trades_count == 1
    assert result.n_closed == 1


def test_at_trade_time_policy_classification_preserves_under_supersession(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §1.3 + §A.5: classifications stamped at trade time are
    INVARIANT under LIVE-policy supersession.

    Three trades stamped under policy_id=1 (epsilon=0.10) close as:
    realized_R = +0.05 / -0.05 / +0.30. Classifications: scratch/scratch/win.
    Now we supersede to policy_id=2 (epsilon=0.50) — those classifications
    MUST NOT change.
    """
    # Seed three trades all stamped under default policy_id=1 (epsilon=0.10).
    # Trade A: exit=10.05, realized_R≈+0.05 ⇒ scratch (|0.05|<0.10).
    # Trade B: exit=9.95, realized_R≈-0.05 ⇒ scratch.
    # Trade C: exit=10.30, realized_R≈+0.30 ⇒ win.
    _seed_full_trade(
        conn, trade_id=1, ticker="AAA",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.05, risk_policy_id_at_lock=1,
    )
    _seed_full_trade(
        conn, trade_id=2, ticker="BBB",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=9.95, risk_policy_id_at_lock=1,
    )
    _seed_full_trade(
        conn, trade_id=3, ticker="CCC",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.30, risk_policy_id_at_lock=1,
    )
    result_before = compute_trade_process_metrics(
        conn, hypothesis_label="A+ baseline",
    )
    assert result_before.n_scratches == 2
    assert result_before.n_wins == 1

    # Supersede to a new active policy with epsilon=0.50.
    conn.execute("UPDATE risk_policy SET is_active=0 WHERE policy_id=1")
    p1 = conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id=1",
    ).fetchone()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id=1",
    ).description]
    base = dict(zip(cols, p1))
    base["policy_id"] = 2
    base["scratch_epsilon_R"] = 0.50
    base["is_active"] = 1
    base["effective_from"] = "2026-04-15T00:00:00.000"
    placeholders = ",".join(["?"] * len(cols))
    conn.execute(
        f"INSERT INTO risk_policy ({','.join(cols)}) "  # noqa: S608
        f"VALUES ({placeholders})",
        [base[c] for c in cols],
    )
    conn.commit()

    # Trades remain stamped under policy_id=1 (epsilon=0.10) — classifications
    # MUST be UNCHANGED despite the live policy now using epsilon=0.50.
    # Under epsilon=0.50, |0.05| < 0.50 ⇒ scratch (same as before);
    # |0.30| < 0.50 ⇒ would be 'scratch' under live but is 'win' under
    # at-trade-time (epsilon=0.10). This is the discriminating case.
    result_after = compute_trade_process_metrics(
        conn, hypothesis_label="A+ baseline",
    )
    assert result_after.n_wins == 1, (
        "Trade C must remain 'win' under at-trade-time epsilon=0.10 "
        "even though live epsilon=0.50 would classify it as scratch"
    )
    assert result_after.n_scratches == 2
    assert result_after.n_losses == 0


# ---------------------------------------------------------------------------
# Cohort isolation + paused-interval inclusion
# ---------------------------------------------------------------------------

def test_cohort_metrics_isolate_by_label(conn: sqlite3.Connection) -> None:
    """Trades in other cohorts must NOT contribute to this cohort's
    metrics — basic filter integrity."""
    _seed_full_trade(
        conn, trade_id=1, ticker="A1",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0, hypothesis_label="A+ baseline",
    )
    _seed_full_trade(
        conn, trade_id=2, ticker="S1",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=8.5, hypothesis_label="Sub-A+ VCP-not-formed",
    )
    a_plus = compute_trade_process_metrics(
        conn, hypothesis_label="A+ baseline",
    )
    sub_a = compute_trade_process_metrics(
        conn, hypothesis_label="Sub-A+ VCP-not-formed",
    )
    assert a_plus.n_closed == 1
    assert a_plus.n_wins == 1
    assert sub_a.n_closed == 1
    assert sub_a.n_losses == 1
    all_trades = compute_trade_process_metrics(conn, hypothesis_label=None)
    assert all_trades.n_closed == 2


def test_cohort_metrics_include_trades_during_paused_interval(
    conn: sqlite3.Connection,
) -> None:
    """Per plan §A.11.1: trades labeled with a cohort count toward cohort
    metrics regardless of cohort.status at trade-time. (Paused intervals
    do NOT cause exclusion.)

    The cohort governance state lives on hypothesis_registry; the metric
    helper does NOT consult it — so a paused cohort's trades still appear
    in metric aggregates.
    """
    # Pause the A+ baseline cohort.
    conn.execute(
        "UPDATE hypothesis_registry SET status='paused', "
        "status_changed_at='2026-04-01T00:00:00', "
        "status_change_reason='test pause' WHERE name='A+ baseline'",
    )
    conn.commit()
    _seed_full_trade(
        conn, trade_id=1, ticker="PAUSE",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0, hypothesis_label="A+ baseline",
    )
    result = compute_trade_process_metrics(
        conn, hypothesis_label="A+ baseline",
    )
    assert result.n_closed == 1, (
        "Trades labeled with a paused cohort must still appear "
        "in cohort metrics per §A.11.1 inclusion policy"
    )
    assert result.n_wins == 1


# ---------------------------------------------------------------------------
# Class C ratio diversity + suppression
# ---------------------------------------------------------------------------

def test_profit_factor_zero_losses_returns_suppressed(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §5.3: profit_factor with no losers ⇒ Insufficient diversity."""
    # 5 winners + 0 losers → meets class_c_n threshold but fails diversity.
    for i in range(1, 6):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"W{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0,
        )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    # 5 wins + 0 losses → diversity suppression (placeholder == "Insufficient
    # outcome diversity" per honesty.py).
    assert isinstance(result.profit_factor.value, SuppressedMetric)
    assert "diversity" in result.profit_factor.value.placeholder_text.lower()


def test_payoff_ratio_zero_losses_returns_suppressed(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §5.3: payoff_ratio requires ≥1 win + ≥1 loss."""
    for i in range(1, 6):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"W{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0,
        )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert isinstance(result.payoff_ratio.value, SuppressedMetric)


def test_profit_factor_with_diversity_renders_point(
    conn: sqlite3.Connection,
) -> None:
    """5 trades + ≥1 win + ≥1 loss + n≥class_c_n → ratio rendered."""
    # 3 winners (+2R each) + 2 losers (-1R each).
    for i in range(1, 4):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"W{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0,
        )
    for i in range(4, 6):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"L{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=9.0,
        )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert not isinstance(result.profit_factor.value, SuppressedMetric)
    # profit_factor = sum(+R)/abs(sum(-R)) = (3*2)/(2*1) = 3.0
    assert result.profit_factor.value == pytest.approx(3.0, abs=0.01)
    # payoff_ratio = avg_win / abs(avg_loss) = 2.0 / 1.0 = 2.0
    assert not isinstance(result.payoff_ratio.value, SuppressedMetric)
    assert result.payoff_ratio.value == pytest.approx(2.0, abs=0.01)


# ---------------------------------------------------------------------------
# Mistake-cost / lucky-violation cohort sums
# ---------------------------------------------------------------------------

def test_mistake_cost_R_cohort_sum_via_phase6_helper(
    conn: sqlite3.Connection,
) -> None:
    """Cohort SUM aggregates per-trade values computed via Phase 6 helpers.

    Trade A: realized_R=+0.50 (entry 10, exit 10.50, ⇒ +0.50R),
    realized_R_if_plan_followed=+2.00 ⇒ mistake_cost_R = 1.50.

    Trade B: realized_R=+3.00 (entry 10, exit 13),
    realized_R_if_plan_followed=+1.50 ⇒ lucky_violation_R = 1.50.

    Cohort sums: mistake_cost_R_total=1.50, lucky_violation_R_total=1.50.
    """
    _seed_full_trade(
        conn, trade_id=1, ticker="SE",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.50,
        realized_R_if_plan_followed=2.00,
    )
    _seed_full_trade(
        conn, trade_id=2, ticker="LL",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=13.00,
        realized_R_if_plan_followed=1.50,
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.mistake_cost_R_total.value == pytest.approx(1.50, abs=0.01)
    assert result.lucky_violation_R_total.value == pytest.approx(1.50, abs=0.01)


def test_mistake_cost_R_recomputes_per_trade_ignoring_review_log_aggregate(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major #1 — design choice banked at return report §5.

    The plan §E Task B.1 acceptance text discusses "preferring review_log
    aggregate when present"; empirical verification (see
    swing/metrics/process.py docstring at the cohort sum loop) shows
    review_log is CADENCE-grain (one row per review window, NOT per
    trade) + carries no trade-grain FK. The cohort-sum aggregator
    therefore ALWAYS re-computes per-trade via Phase 6 helpers from
    ``trades.realized_R_if_plan_followed`` + ``actual_realized_R_effective``.

    Discriminating test: seed a closed trade with realized_R_if_plan=2.0
    + actual=+0.5 (so per-trade compute → 1.5R mistake cost) +
    EXPLICITLY insert a review_log row with total_mistake_cost_R=99.0
    covering the same period. Assert the cohort metric reflects the
    PER-TRADE compute (1.5R), NOT the review_log aggregate (99.0R).
    """
    _seed_full_trade(
        conn, trade_id=1, ticker="DISC",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=10.50,  # +0.5R actual
        realized_R_if_plan_followed=2.0,  # plan +2.0R → mistake = 1.5R
        reviewed_at="2026-04-15T10:00:00",
    )
    # Plant a review_log row with conflicting totals — if the
    # cohort aggregator preferred this source, the cohort sum would be
    # 99.0R (not 1.5R). The discriminating assertion below rejects that
    # path.
    conn.execute(
        "INSERT INTO review_log (review_type, period_start, period_end, "
        "scheduled_date, completed_date, skipped, duration_minutes, "
        "n_trades_reviewed, total_mistake_cost_R, total_lucky_violation_R, "
        "primary_lesson, next_period_focus, created_at) VALUES "
        "('weekly', '2026-04-13', '2026-04-19', '2026-04-19', "
        "'2026-04-19T10:00:00', 0, 30, 1, 99.0, 0.0, "
        "'discriminating', NULL, '2026-04-19T10:00:00')",
    )
    conn.commit()

    result = compute_trade_process_metrics(
        conn, hypothesis_label="A+ baseline",
    )
    # mistake_cost_R_total = per-trade sum = 1.5R, NOT review_log aggregate
    # 99.0R.
    assert result.mistake_cost_R_total.value == pytest.approx(1.5, abs=0.01)


def test_mistake_cost_R_zero_when_plan_unspecified(
    conn: sqlite3.Connection,
) -> None:
    """Trade closed but `realized_R_if_plan_followed=None` → contributes 0
    to both cohort sums (Phase 6 helper returns 0 for None plan)."""
    _seed_full_trade(
        conn, trade_id=1, ticker="NOP",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        realized_R_if_plan_followed=None,
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.mistake_cost_R_total.value == 0.0
    assert result.lucky_violation_R_total.value == 0.0


# ---------------------------------------------------------------------------
# process_grade distribution (5 Class A rates)
# ---------------------------------------------------------------------------

def test_process_grade_distribution_rate_per_grade(
    conn: sqlite3.Connection,
) -> None:
    """Distribution of process_grade across 5 reviewed trades — each
    grade rendered as a Class A rate over n_reviewed denominator."""
    grades = ["A", "A", "B", "C", "F"]
    for i, g in enumerate(grades, start=1):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"G{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=10.0 + 0.10 * i,
            reviewed_at="2026-04-15T09:30:00",
            process_grade=g,
        )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.n_reviewed == 5
    dist = result.process_grade_distribution
    assert set(dist.keys()) == {"A", "B", "C", "D", "F"}
    # 2/5 = 0.40 for A.
    assert isinstance(dist["A"].value, WilsonCI)
    assert dist["A"].events_k == 2
    assert dist["A"].sample_n == 5
    # 0/5 = 0.00 for D — still rendered (not suppressed); WilsonCI with point=0.
    assert dist["D"].events_k == 0


# ---------------------------------------------------------------------------
# mistake_tag_frequency (per-tag Class A rates)
# ---------------------------------------------------------------------------

def test_mistake_tag_frequency_per_tag_rate(conn: sqlite3.Connection) -> None:
    """Per-tag count / n_reviewed; sorted alphabetical."""
    _seed_full_trade(
        conn, trade_id=1, ticker="T1",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        mistake_tags=json.dumps(["SOLD_TOO_EARLY", "EMOTIONAL"]),
    )
    _seed_full_trade(
        conn, trade_id=2, ticker="T2",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        mistake_tags=json.dumps(["SOLD_TOO_EARLY"]),
    )
    _seed_full_trade(
        conn, trade_id=3, ticker="T3",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        mistake_tags=json.dumps([]),
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    freq = result.mistake_tag_frequency
    assert "SOLD_TOO_EARLY" in freq
    assert "EMOTIONAL" in freq
    # Sub-tag counts: 2/3 + 1/3.
    assert freq["SOLD_TOO_EARLY"].events_k == 2
    assert freq["SOLD_TOO_EARLY"].sample_n == 3
    assert freq["EMOTIONAL"].events_k == 1
    assert freq["EMOTIONAL"].sample_n == 3


# ---------------------------------------------------------------------------
# disqualifying_process_violation_rate
# ---------------------------------------------------------------------------

def test_disqualifying_rate_over_reviewed_trades(
    conn: sqlite3.Connection,
) -> None:
    """Rate computed over REVIEWED trades only (unreviewed excluded)."""
    _seed_full_trade(
        conn, trade_id=1, ticker="D1",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        disqualifying_process_violation=1,
    )
    _seed_full_trade(
        conn, trade_id=2, ticker="D2",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        disqualifying_process_violation=0,
    )
    # An unreviewed trade — excluded from disqualifying_rate denominator.
    _seed_full_trade(
        conn, trade_id=3, ticker="D3",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        reviewed_at=None,
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.n_reviewed == 2
    assert result.disqualifying_process_violation_rate.events_k == 1
    assert result.disqualifying_process_violation_rate.sample_n == 2


# ---------------------------------------------------------------------------
# capture_ratio winners-only invariant
# ---------------------------------------------------------------------------

def test_capture_ratio_uses_winners_only(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.1: capture_ratio aggregates only over winners with
    positive MFE_R. Losers contribute to giveback_R_winner_to_loser
    (different metric)."""
    # 3 winners with MFE snapshots; 1 loser with positive MFE.
    for i in range(1, 4):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"W{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0,  # +2R win
        )
        conn.execute(
            "INSERT INTO daily_management_records "
            "(trade_id, record_type, review_date, data_asof_session, "
            "created_at, mfe_mae_precision_level, is_superseded, "
            "open_MFE_R_to_date, open_MAE_R_to_date) VALUES "
            "(?, 'daily_snapshot', '2026-04-05', '2026-04-05', "
            "'2026-04-05T09:30:00', 'daily_approximate', 0, 3.0, 0.5)",
            (i,),
        )
    _seed_full_trade(
        conn, trade_id=4, ticker="LSR",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=9.0,  # -1R loss
    )
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, "
        "created_at, mfe_mae_precision_level, is_superseded, "
        "open_MFE_R_to_date, open_MAE_R_to_date) VALUES "
        "(4, 'daily_snapshot', '2026-04-05', '2026-04-05', "
        "'2026-04-05T09:30:00', 'daily_approximate', 0, 1.5, 1.5)",
    )
    conn.commit()

    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    # capture_ratio samples should include ONLY the 3 winners (capture =
    # realized_R / MFE_R = 2.0 / 3.0 ≈ 0.667 each).
    # giveback_R_winner: MFE - realized = 3 - 2 = 1.0 (3 samples).
    # giveback_R_winner_to_loser: MFE - realized = 1.5 - (-1) = 2.5 (1 sample).
    assert result.capture_ratio.sample_n == 3
    assert result.giveback_R_winner.sample_n == 3
    assert result.giveback_R_winner_to_loser.sample_n == 1


# ---------------------------------------------------------------------------
# holding_period_days trading-day computation
# ---------------------------------------------------------------------------

def test_holding_period_skips_weekends(conn: sqlite3.Connection) -> None:
    """Trading-day count: Mon Apr 6 → Fri Apr 10 = 5 trading days inclusive."""
    _seed_full_trade(
        conn, trade_id=1, ticker="HOLD",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
        pre_trade_locked_at="2026-04-06T09:30:00",  # Mon
        last_fill_at="2026-04-10T15:30:00",  # Fri
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.holding_period_days.sample_n == 1
    # Class B at n=1 < class_b_n=3 ⇒ suppressed. n=1 sample but
    # cell.value is a SuppressedMetric; we can still assert sample_n.
    assert isinstance(result.holding_period_days.value, SuppressedMetric)


# ---------------------------------------------------------------------------
# Invalid-stop edge case (entry == stop)
# ---------------------------------------------------------------------------

def test_invalid_planned_risk_budget_excludes_trade_from_realized_R(
    conn: sqlite3.Connection,
) -> None:
    """Per plan §A.0: entry==stop (risk_per_share=0) ⇒ realized_R undefined;
    trade is excluded from realized_R sample but still counted in n_closed."""
    _seed_full_trade(
        conn, trade_id=1, ticker="ZERO",
        entry_price=10.0, initial_stop=10.0, initial_shares=100,
        exit_price=11.0,
    )
    # A valid winner trade alongside.
    _seed_full_trade(
        conn, trade_id=2, ticker="GOOD",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=11.0,
    )
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    assert result.n_closed == 2
    # realized_R cell has 1 sample (only the valid trade).
    assert result.realized_R.sample_n == 1


def test_failure_mode_excluded_from_mistake_tag_frequency_metric(
    conn: sqlite3.Connection,
) -> None:
    # A reviewed trade carrying BOTH a mistake tag AND a failure_mode must NOT
    # leak the failure_mode token into mistake_tag_frequency.
    from swing.data.models import FAILURE_MODES
    _seed_full_trade(
        conn, trade_id=1, ticker="ORTH",
        entry_price=10.0, initial_stop=9.0, initial_shares=100, exit_price=11.0,
        reviewed_at="2026-04-15T09:30:00",
        mistake_tags=json.dumps(["SOLD_TOO_EARLY"]),
    )
    # The metric runs against v24 here (the test DB is migrated to HEAD), so the
    # failure_mode column exists; stamp it directly on the seeded reviewed row.
    conn.execute(
        "UPDATE trades SET failure_mode = 'execution_error' WHERE id = 1")
    result = compute_trade_process_metrics(conn, hypothesis_label="A+ baseline")
    freq = result.mistake_tag_frequency
    # PRE-FIX (hypothetical leak): "execution_error" would appear as a key.
    # POST-FIX: the metric only sees mistake_tags -> the failure_mode token is absent.
    assert "execution_error" in FAILURE_MODES  # sanity: it IS a failure-mode token
    assert "execution_error" not in freq
    assert set(freq.keys()).isdisjoint(FAILURE_MODES)
    assert "SOLD_TOO_EARLY" in freq  # the real mistake tag still counts


# ---------------------------------------------------------------------------
# Task 6 — entry_intent faceting (regression arithmetic)
# ---------------------------------------------------------------------------

def test_compute_trade_process_metrics_intent_filter(
    conn: sqlite3.Connection,
) -> None:
    """Fixture: 2 standard + 3 by_design closed-reviewed + 1 NULL
    closed-NOT-reviewed. Regression arithmetic distinguishes the filtered
    slice from the unfiltered aggregate."""
    # 2 standard, reviewed.
    for i in (1, 2):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"STD{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0, hypothesis_label=None,
            reviewed_at="2026-04-10T09:00:00", entry_intent="standard",
        )
    # 3 by_design, reviewed.
    for i in (3, 4, 5):
        _seed_full_trade(
            conn, trade_id=i, ticker=f"BD{i}",
            entry_price=10.0, initial_stop=9.0, initial_shares=100,
            exit_price=12.0, hypothesis_label=None,
            reviewed_at="2026-04-10T09:00:00",
            entry_intent="hypothesis_test_by_design",
        )
    # 1 NULL intent, closed but NOT reviewed.
    _seed_full_trade(
        conn, trade_id=6, ticker="NULL6",
        entry_price=10.0, initial_stop=9.0, initial_shares=100,
        exit_price=12.0, hypothesis_label=None,
        reviewed_at=None, entry_intent=None,
    )

    all_m = compute_trade_process_metrics(conn, hypothesis_label=None)
    std_m = compute_trade_process_metrics(
        conn, hypothesis_label=None, entry_intent="standard")
    bd_m = compute_trade_process_metrics(
        conn, hypothesis_label=None,
        entry_intent="hypothesis_test_by_design")
    unc_m = compute_trade_process_metrics(
        conn, hypothesis_label=None, entry_intent="__unclassified__")

    assert all_m.n_reviewed == 5
    assert std_m.n_reviewed == 2
    assert bd_m.n_reviewed == 3
    assert unc_m.n_reviewed == 0
    # n_closed mirrors the slice: all 6, std 2, bd 3, unc 1.
    assert all_m.n_closed == 6
    assert std_m.n_closed == 2
    assert bd_m.n_closed == 3
    assert unc_m.n_closed == 1
    # no-filter equals omitting the param entirely.
    assert all_m.n_reviewed == compute_trade_process_metrics(
        conn, hypothesis_label=None).n_reviewed
