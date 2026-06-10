"""Phase 10 Sub-bundle B T-B.4 — HypothesisProgressCardVM tests.

Includes the §A.5.1 BINDING discriminating regression test for
``cumulative_R_pct_of_capital`` multi-policy semantics — per-trade-divide
then-sum (NOT sum-then-divide-by-live-policy + NOT averaged-policy).
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.web.view_models.metrics.hypothesis_progress_card import (
    TRANSITION_TIMELINE_CAP,
    CohortProgressVM,
    HypothesisProgressCardVM,
    build_hypothesis_progress_card_vm,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_hp.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


def _insert_extra_policy(
    conn: sqlite3.Connection,
    *,
    capital_floor: float,
    scratch_epsilon: float = 0.10,
    activate: bool = True,
) -> int:
    """Insert a new risk_policy row + return its policy_id. When
    ``activate`` is True, supersede the active policy."""
    if activate:
        conn.execute("UPDATE risk_policy SET is_active=0 WHERE is_active=1")
    template = conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id=1",
    ).fetchone()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM risk_policy WHERE policy_id=1",
    ).description]
    base = dict(zip(cols, template))
    # Drop policy_id so AUTOINCREMENT assigns next.
    base.pop("policy_id", None)
    base["capital_floor_constant_dollars"] = capital_floor
    base["scratch_epsilon_R"] = scratch_epsilon
    base["is_active"] = 1 if activate else 0
    base["effective_from"] = "2026-04-15T00:00:00.000"
    placeholders = ",".join(["?"] * len(base))
    cur = conn.execute(
        f"INSERT INTO risk_policy ({','.join(base.keys())}) "  # noqa: S608
        f"VALUES ({placeholders})",
        list(base.values()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_trade_with_pnl(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str,
    realized_pnl_dollars: float,
    risk_policy_id_at_lock: int | None,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    initial_shares: int = 100,
    state: str = "closed",
    last_fill_at: str = "2026-04-08T15:30:00",
) -> None:
    """Seed a closed trade where (exit - entry) * shares = realized_pnl_dollars.

    With entry=10, initial_shares=100: exit = 10 + realized_pnl / 100.
    """
    exit_price = entry_price + (realized_pnl_dollars / initial_shares)
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, risk_policy_id_at_lock, last_fill_at) VALUES "
        "(?, ?, '2026-04-01', ?, ?, ?, ?, ?, 'S', 'I', "
        "'manual_off_pipeline', ?, ?, ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            initial_stop, state, "2026-04-01T09:30:00", initial_shares,
            hypothesis_label, risk_policy_id_at_lock, last_fill_at,
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
        "price, reconciliation_status) VALUES (?, ?, "
        "'exit', ?, ?, 'unreconciled')",
        (trade_id, last_fill_at, initial_shares, exit_price),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Basic structure + base-layout integration
# ---------------------------------------------------------------------------

def test_vm_renders_4_cohorts_always(cfg) -> None:
    """Even at 0 closed trades, all 4 hypothesis_registry cohorts render."""
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    assert isinstance(vm, HypothesisProgressCardVM)
    assert isinstance(vm, BaseLayoutVM)
    assert len(vm.cohorts) == 5
    names = [c.cohort_name for c in vm.cohorts]
    assert names == [
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
        "Broad-watch baseline",
    ]


def test_vm_progress_pct_at_zero_trades_is_0(cfg) -> None:
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    for c in vm.cohorts:
        assert c.n_closed == 0
        assert c.progress_pct == 0.0


def test_vm_consecutive_loss_run_at_zero_trades_is_0(cfg) -> None:
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    for c in vm.cohorts:
        assert c.consecutive_loss_run == 0
        # distance = tripwire - run = tripwire when run=0.
        assert c.distance_to_loss_tripwire == c.consecutive_loss_tripwire


def test_vm_decision_criteria_renders_seed_text_verbatim(cfg) -> None:
    """Decision-criteria seed text from migration 0008 is rendered verbatim
    on the cohort VM (no canonicalization, no truncation)."""
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    by_name = {c.cohort_name: c for c in vm.cohorts}
    assert by_name["A+ baseline"].decision_criteria == (
        "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%"
    )
    assert by_name["Near-A+ defensible: extension test"].decision_criteria == (
        "Mean R-multiple within 25% of A+ baseline mean"
    )
    assert by_name["Sub-A+ VCP-not-formed"].decision_criteria == (
        "Confirm negative mean R-multiple"
    )
    assert by_name["Capital-blocked: smaller-position test"].decision_criteria == (
        "Mean R-multiple positive; defensibility of smaller-position approach"
    )


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    assert vm.session_date
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.ohlcv_source_degraded is False
    assert vm.unresolved_material_discrepancies_count == 0


# ---------------------------------------------------------------------------
# §A.5.1 BINDING: multi-policy cumulative_R_pct_of_capital semantics
# ---------------------------------------------------------------------------

def test_vm_cumulative_R_uses_per_trade_at_trade_time_capital_floor(  # noqa: N802
    cfg, conn: sqlite3.Connection,
) -> None:
    """Per plan §A.5.1 BINDING + dispatch brief §0.8 LOCK.

    Trade A: realized P&L = -$50 stamped under policy_id=1 (capital_floor=$7500).
    Trade B: realized P&L = -$100 stamped under policy_id=2 (capital_floor=$10000).
    Supersede to active policy_id=3 (capital_floor=$5000).

    Expected per §A.5.1 PER-TRADE-DIVIDE-THEN-SUM:
        (-50 / 7500) + (-100 / 10000) = -0.00667 + -0.01000 = -0.01667
        → -1.667% of capital.

    REJECTED naive alternative: -150 / 5000 = -3.000% (live-policy aggregation).
    REJECTED averaged alternative: -150 / 8750 = -1.714% (mean of floors).
    """
    # policy_id=1 already exists (floor=7500). Insert policy_id=2 (floor=10000)
    # without activating; then policy_id=3 (floor=5000) activating.
    pid2 = _insert_extra_policy(conn, capital_floor=10000.0, activate=False)
    pid3 = _insert_extra_policy(conn, capital_floor=5000.0, activate=True)
    assert pid3 != pid2

    with conn:
        _seed_trade_with_pnl(
            conn, trade_id=1, ticker="A1",
            hypothesis_label="A+ baseline",
            realized_pnl_dollars=-50.0,
            risk_policy_id_at_lock=1,
        )
        _seed_trade_with_pnl(
            conn, trade_id=2, ticker="B1",
            hypothesis_label="A+ baseline",
            realized_pnl_dollars=-100.0,
            risk_policy_id_at_lock=pid2,
        )
    conn.close()

    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    # Per §A.5.1: -50/7500 + -100/10000 = -1.6667%.
    assert aplus.cumulative_R_pct_of_capital == pytest.approx(-1.6667, abs=0.01)
    # Discriminate against -3.00 (live-policy) + -1.714 (averaged-policy):
    assert abs(aplus.cumulative_R_pct_of_capital - (-3.0)) > 0.5
    assert abs(aplus.cumulative_R_pct_of_capital - (-1.714)) > 0.04


def test_vm_cumulative_R_pre_phase9_legacy_trade_uses_live_floor_with_annotation(  # noqa: N802
    cfg, conn: sqlite3.Connection,
) -> None:
    """Per §A.5: legacy trade with NULL stamp falls back to LIVE policy
    floor; ``legacy_trades_count`` flags the fallback for UI annotation."""
    with conn:
        _seed_trade_with_pnl(
            conn, trade_id=1, ticker="LEG",
            hypothesis_label="A+ baseline",
            realized_pnl_dollars=-75.0,
            risk_policy_id_at_lock=None,  # legacy NULL stamp
        )
    conn.close()

    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    # Live policy floor is $7500 → -75/7500 = -1.0%.
    assert aplus.cumulative_R_pct_of_capital == pytest.approx(-1.0, abs=0.01)
    assert aplus.legacy_trades_count == 1


# ---------------------------------------------------------------------------
# Consecutive-loss tripwire
# ---------------------------------------------------------------------------

def test_vm_distance_to_loss_tripwire_decrements_per_loss(
    cfg, conn: sqlite3.Connection,
) -> None:
    """A+ baseline tripwire=5; seed 2 consecutive losses; distance=3."""
    with conn:
        for i in range(1, 3):
            _seed_trade_with_pnl(
                conn, trade_id=i, ticker=f"L{i}",
                hypothesis_label="A+ baseline",
                realized_pnl_dollars=-100.0,
                risk_policy_id_at_lock=1,
                last_fill_at=f"2026-04-0{i+1}T15:30:00",
            )
    conn.close()
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    assert aplus.consecutive_loss_run == 2
    # tripwire=5, run=2 → distance=3.
    assert aplus.distance_to_loss_tripwire == 3


def test_vm_consecutive_loss_run_resets_on_win(
    cfg, conn: sqlite3.Connection,
) -> None:
    """Run only counts CONSECUTIVE losses ending at most-recent close;
    a winning trade interrupts the streak."""
    with conn:
        # Loss → Loss → Win (most recent). Run should be 0 (most-recent trade
        # was win).
        _seed_trade_with_pnl(
            conn, trade_id=1, ticker="L1", hypothesis_label="A+ baseline",
            realized_pnl_dollars=-100.0, risk_policy_id_at_lock=1,
            last_fill_at="2026-04-02T15:30:00",
        )
        _seed_trade_with_pnl(
            conn, trade_id=2, ticker="L2", hypothesis_label="A+ baseline",
            realized_pnl_dollars=-100.0, risk_policy_id_at_lock=1,
            last_fill_at="2026-04-03T15:30:00",
        )
        _seed_trade_with_pnl(
            conn, trade_id=3, ticker="W1", hypothesis_label="A+ baseline",
            realized_pnl_dollars=+200.0, risk_policy_id_at_lock=1,
            last_fill_at="2026-04-04T15:30:00",
        )
    conn.close()
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    assert aplus.consecutive_loss_run == 0


# ---------------------------------------------------------------------------
# §A.11 transition timeline (cap=5, newest-first)
# ---------------------------------------------------------------------------

def test_vm_transition_timeline_capped_at_5_newest_first(
    cfg, conn: sqlite3.Connection,
) -> None:
    """Seed 7 history rows; assert cap at 5 + newest-first ordering."""
    # Aplus hypothesis_id=1 already seeded by migration 0017.
    statuses = ["active", "paused", "active", "paused", "active", "paused", "active"]
    times = [
        "2026-05-01T10:00:00.000",
        "2026-05-02T10:00:00.000",
        "2026-05-03T10:00:00.000",
        "2026-05-04T10:00:00.000",
        "2026-05-05T10:00:00.000",
        "2026-05-06T10:00:00.000",
        "2026-05-07T10:00:00.000",
    ]
    # First close the open seed row (one already exists for hyp_id=1).
    conn.execute(
        "UPDATE hypothesis_status_history SET effective_to=? "
        "WHERE hypothesis_id=1 AND effective_to IS NULL",
        ("2026-05-01T10:00:00.000",),
    )
    for i, (s, t) in enumerate(zip(statuses, times)):
        effective_to = times[i + 1] if i + 1 < len(times) else None
        conn.execute(
            "INSERT INTO hypothesis_status_history "
            "(hypothesis_id, status, effective_from, effective_to, "
            "change_reason, recorded_at) VALUES "
            "(1, ?, ?, ?, ?, ?)",
            (s, t, effective_to, f"test transition {i}", t),
        )
    conn.commit()
    conn.close()

    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    assert len(aplus.transition_timeline) == TRANSITION_TIMELINE_CAP
    # Newest first: effective_from descending.
    times_returned = [e.effective_from for e in aplus.transition_timeline]
    assert times_returned == sorted(times_returned, reverse=True)
    # The 5 newest are 05-07, 05-06, 05-05, 05-04, 05-03.
    assert times_returned[0] == "2026-05-07T10:00:00.000"
    assert times_returned[-1] == "2026-05-03T10:00:00.000"


# ---------------------------------------------------------------------------
# §A.11.1 paused-interval inclusion
# ---------------------------------------------------------------------------

def test_vm_paused_cohort_metrics_include_trades_stamped_during_paused_interval(
    cfg, conn: sqlite3.Connection,
) -> None:
    """Per plan §A.11.1: trades labeled during paused intervals still
    count toward cohort metrics + tripwire computation."""
    # Pause the cohort + add a trade.
    conn.execute(
        "UPDATE hypothesis_registry SET status='paused', "
        "status_changed_at='2026-04-01T00:00:00', "
        "status_change_reason='test pause' WHERE name='A+ baseline'",
    )
    with conn:
        _seed_trade_with_pnl(
            conn, trade_id=1, ticker="PAU",
            hypothesis_label="A+ baseline",
            realized_pnl_dollars=-50.0,
            risk_policy_id_at_lock=1,
        )
    conn.close()
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    assert aplus.status == "paused"
    assert aplus.n_closed == 1
    assert aplus.consecutive_loss_run == 1
    # cumulative_R_pct = -50/7500 = -0.667%.
    assert aplus.cumulative_R_pct_of_capital == pytest.approx(-0.667, abs=0.01)


# ---------------------------------------------------------------------------
# distance_to_absolute_loss_tripwire
# ---------------------------------------------------------------------------

def test_vm_distance_to_absolute_loss_tripwire_clamped_at_zero(
    cfg, conn: sqlite3.Connection,
) -> None:
    """When the drawdown EXCEEDS the absolute tripwire, distance clamps to 0."""
    # A+ baseline absolute_loss_tripwire_pct = 5.0 per migration 0008.
    # Seed a trade with very large loss: -$400 / $7500 = -5.333% → exceeds
    # tripwire.
    with conn:
        _seed_trade_with_pnl(
            conn, trade_id=1, ticker="BIG",
            hypothesis_label="A+ baseline",
            realized_pnl_dollars=-400.0,
            risk_policy_id_at_lock=1,
            initial_stop=5.0,  # widen risk so realized_R doesn't crash
            initial_shares=100,
        )
    conn.close()
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    aplus = next(c for c in vm.cohorts if c.cohort_name == "A+ baseline")
    assert aplus.cumulative_R_pct_of_capital == pytest.approx(-5.333, abs=0.01)
    # tripwire=5.0; |draw|=5.333 → distance = max(0, 5.0 - 5.333) = 0.
    assert aplus.distance_to_absolute_loss_tripwire == 0.0
