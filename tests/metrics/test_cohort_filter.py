"""Phase 10 Sub-bundle C T-C.5 — per-cohort discrepancy filter tests.

Per electives amendment §2 Task C.5 acceptance:

- Helper ``filter_trades_without_unresolved_material_discrepancies`` keeps
  trades with no discrepancies / resolved discrepancies / non-material
  discrepancies; excludes trades with at least one unresolved material
  discrepancy row.
- ``compute_tier_comparison`` + ``compute_deviation_outcome`` accept
  ``exclude_unresolved_discrepancies`` keyword; filter-active state may
  re-suppress cohorts whose post-filter ``n`` falls below the
  ``COHORT_MINIMUM_N=5`` floor (discriminating regression test).
- Route handlers accept ``?exclude_discrepancies=1`` (truthy) +
  ``?exclude_discrepancies=0`` / missing (falsy).
- Templates render the toggle link + an "excluded N" context line when
  filter is active.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.cohort import (
    filter_trades_without_unresolved_material_discrepancies,
    list_closed_trades_for_cohort,
)
from swing.metrics.honesty import SuppressedMetric, WilsonCI
from swing.metrics.tier import (
    APLUS_COHORT,
    compute_deviation_outcome,
    compute_tier_comparison,
)
from swing.web.app import create_app
from swing.web.view_models.metrics.deviation_outcome import (
    build_deviation_outcome_vm,
)
from swing.web.view_models.metrics.tier_comparison import (
    build_tier_comparison_vm,
)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

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


@pytest.fixture
def conn(cfg_and_path) -> sqlite3.Connection:
    cfg, _ = cfg_and_path
    return sqlite3.connect(cfg.paths.db_path)


def _seed_closed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    hypothesis_label: str,
    realized_pnl_dollars: float,
    last_fill_at: str = "2026-04-08T15:30:00",
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


def _seed_reconciliation_run(conn: sqlite3.Connection, run_id: int = 1) -> int:
    """Seed a minimal reconciliation_runs row that can be referenced by the
    discrepancy FK."""
    conn.execute(
        "INSERT INTO reconciliation_runs "
        "(run_id, source, source_artifact_path, source_artifact_sha256, "
        "period_start, period_end, started_ts, finished_ts, state) "
        "VALUES (?, 'tos_csv', '/tmp/test.csv', 'a' || ?, "
        "'2026-05-05', '2026-05-12', "
        "'2026-05-12T10:00:00.000', '2026-05-12T10:01:00.000', "
        "'completed')",
        (run_id, run_id),
    )
    return run_id


def _seed_discrepancy(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    trade_id: int | None,
    discrepancy_type: str = "stop_mismatch",
    field_name: str = "current_stop",
    material: int = 1,
    resolved: bool = False,
    run_id: int = 1,
) -> None:
    """Seed a reconciliation_discrepancies row.

    ``material`` ∈ {0, 1} corresponds to ``material_to_review`` column;
    ``resolved`` toggles ``resolution`` between the sentinel
    ``'unresolved'`` default and a terminal value
    (``'acknowledged_immaterial'``).
    """
    conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(discrepancy_id, run_id, trade_id, "
        "discrepancy_type, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, "
        "resolution_reason, created_at) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-05-12T10:01:00.000')",
        (
            discrepancy_id, run_id, trade_id, discrepancy_type, field_name,
            '"x"', '"y"', material,
            "acknowledged_immaterial" if resolved else "unresolved",
            "test seed" if resolved else None,
        ),
    )


# ---------------------------------------------------------------------------
# Helper: filter_trades_without_unresolved_material_discrepancies
# ---------------------------------------------------------------------------

def test_filter_returns_full_list_when_no_discrepancies(conn) -> None:
    """(a) helper returns full list when no discrepancies exist."""
    with conn:
        for i in range(3):
            _seed_closed_trade(
                conn, trade_id=i + 1, ticker=f"T{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=100.0,
            )
    trades = list_closed_trades_for_cohort(
        conn, hypothesis_label=APLUS_COHORT,
    )
    result = filter_trades_without_unresolved_material_discrepancies(
        conn, trades,
    )
    assert len(result) == 3
    assert {t.id for t in result} == {1, 2, 3}


def test_filter_excludes_trades_with_unresolved_material_discrepancies(
    conn,
) -> None:
    """(b) helper excludes trades with unresolved material discrepancies."""
    with conn:
        for i in range(3):
            _seed_closed_trade(
                conn, trade_id=i + 1, ticker=f"T{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=100.0,
            )
        _seed_reconciliation_run(conn)
        # Trade 2 has 1 unresolved + material discrepancy → EXCLUDE.
        _seed_discrepancy(
            conn, discrepancy_id=10, trade_id=2,
            material=1, resolved=False,
        )
    trades = list_closed_trades_for_cohort(
        conn, hypothesis_label=APLUS_COHORT,
    )
    result = filter_trades_without_unresolved_material_discrepancies(
        conn, trades,
    )
    assert {t.id for t in result} == {1, 3}


def test_filter_includes_trades_whose_discrepancies_are_resolved(conn) -> None:
    """(c) helper INCLUDES trades with resolved discrepancies (any
    ``resolution`` value other than ``'unresolved'`` — e.g.,
    ``'acknowledged_immaterial'``)."""
    with conn:
        _seed_closed_trade(
            conn, trade_id=1, ticker="A", hypothesis_label=APLUS_COHORT,
            realized_pnl_dollars=100.0,
        )
        _seed_reconciliation_run(conn)
        _seed_discrepancy(
            conn, discrepancy_id=10, trade_id=1,
            material=1, resolved=True,  # resolution NOT NULL
        )
    trades = list_closed_trades_for_cohort(
        conn, hypothesis_label=APLUS_COHORT,
    )
    result = filter_trades_without_unresolved_material_discrepancies(
        conn, trades,
    )
    assert {t.id for t in result} == {1}


def test_filter_includes_trades_with_non_material_discrepancies(conn) -> None:
    """(d) helper INCLUDES trades with non-material discrepancies
    (material_to_review=0)."""
    with conn:
        _seed_closed_trade(
            conn, trade_id=1, ticker="A", hypothesis_label=APLUS_COHORT,
            realized_pnl_dollars=100.0,
        )
        _seed_reconciliation_run(conn)
        _seed_discrepancy(
            conn, discrepancy_id=10, trade_id=1,
            material=0, resolved=False,  # non-material
        )
    trades = list_closed_trades_for_cohort(
        conn, hypothesis_label=APLUS_COHORT,
    )
    result = filter_trades_without_unresolved_material_discrepancies(
        conn, trades,
    )
    assert {t.id for t in result} == {1}


def test_filter_ignores_orphan_discrepancies_without_trade_id(conn) -> None:
    """Orphan-emit discrepancies (trade_id IS NULL) do NOT exclude any
    specific trade — they remain counted by the global banner only."""
    with conn:
        _seed_closed_trade(
            conn, trade_id=1, ticker="A", hypothesis_label=APLUS_COHORT,
            realized_pnl_dollars=100.0,
        )
        _seed_reconciliation_run(conn)
        _seed_discrepancy(
            conn, discrepancy_id=10, trade_id=None,
            discrepancy_type="equity_delta", field_name="equity_dollars",
            material=1, resolved=False,
        )
    trades = list_closed_trades_for_cohort(
        conn, hypothesis_label=APLUS_COHORT,
    )
    result = filter_trades_without_unresolved_material_discrepancies(
        conn, trades,
    )
    assert {t.id for t in result} == {1}


def test_filter_passes_through_empty_input(conn) -> None:
    """Empty input ⇒ empty output (no DB query side-effects)."""
    assert filter_trades_without_unresolved_material_discrepancies(
        conn, [],
    ) == []


# ---------------------------------------------------------------------------
# compute_tier_comparison + compute_deviation_outcome filter-active
# ---------------------------------------------------------------------------

def _seed_5_aplus_trades_with_one_unresolved(conn: sqlite3.Connection) -> None:
    """Seed A+ n=5 wins; mark trade_id=3 with an unresolved material
    discrepancy. Filter-active → cohort drops to n=4 → re-suppresses."""
    with conn:
        for i in range(5):
            _seed_closed_trade(
                conn, trade_id=i + 1, ticker=f"AW{i}",
                hypothesis_label=APLUS_COHORT,
                realized_pnl_dollars=200.0,
                last_fill_at=f"2026-04-{i + 1:02d}T15:30:00",
            )
        _seed_reconciliation_run(conn)
        _seed_discrepancy(
            conn, discrepancy_id=10, trade_id=3,
            material=1, resolved=False,
        )


def test_filter_re_suppresses_when_n_drops_below_5(cfg_and_path) -> None:
    """Discriminating per electives amendment §2 watch item: seed cohort
    with 5 closed trades + 1 unresolved material discrepancy → filter
    brings cohort to n=4 → cohort cells re-suppress (surface-locked
    floor of 5)."""
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        # Without filter: A+ has n=5 → renders Wilson CI.
        no_filter = compute_tier_comparison(conn)
        aplus_no_filter = next(
            c for c in no_filter.cohorts if c.cohort_name == APLUS_COHORT
        )
        assert aplus_no_filter.n_closed == 5
        assert isinstance(aplus_no_filter.win_rate, WilsonCI)

        # With filter: A+ drops to n=4 → cells suppress.
        with_filter = compute_tier_comparison(
            conn, exclude_unresolved_discrepancies=True,
        )
        aplus_with_filter = next(
            c for c in with_filter.cohorts if c.cohort_name == APLUS_COHORT
        )
        assert aplus_with_filter.n_closed == 4
        assert isinstance(aplus_with_filter.win_rate, SuppressedMetric)
        assert isinstance(aplus_with_filter.expectancy, SuppressedMetric)

        # Filter-active flags surfaced for template rendering.
        assert with_filter.exclude_unresolved_discrepancies_active is True
        assert with_filter.excluded_trades_count == 1
    finally:
        conn.close()


def test_filter_active_passes_through_to_deviation_outcome(
    cfg_and_path,
) -> None:
    """compute_deviation_outcome delegates the filter parameter."""
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        result = compute_deviation_outcome(
            conn, exclude_unresolved_discrepancies=True,
        )
    finally:
        conn.close()
    assert result.exclude_unresolved_discrepancies_active is True
    assert result.excluded_trades_count == 1
    aplus_row = next(r for r in result.rows if r.cohort_name == APLUS_COHORT)
    # After filter A+ has n=4 → row_suppressed=True per surface lock.
    assert aplus_row.n_closed == 4
    assert aplus_row.row_suppressed is True


def test_filter_inactive_keeps_default_behavior(cfg_and_path) -> None:
    """Without ``exclude_unresolved_discrepancies``, behavior matches the
    pre-T-C.5 baseline."""
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        result = compute_tier_comparison(conn)
    finally:
        conn.close()
    assert result.exclude_unresolved_discrepancies_active is False
    assert result.excluded_trades_count == 0


# ---------------------------------------------------------------------------
# Route handlers: ?exclude_discrepancies=1 query parameter
# ---------------------------------------------------------------------------

def test_route_tier_comparison_accepts_exclude_discrepancies_query(
    cfg_and_path,
) -> None:
    cfg, cfg_path = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # No filter: 200.
        r_no = client.get("/metrics/tier-comparison")
        # Filter active.
        r_yes = client.get("/metrics/tier-comparison?exclude_discrepancies=1")
    assert r_no.status_code == 200
    assert r_yes.status_code == 200
    # The filter-active body advertises the excluded count.
    assert "(excluded 1 trades with unresolved discrepancies)" in r_yes.text
    # The filter-inactive body does NOT advertise the excluded count.
    assert "(excluded " not in r_no.text
    # Toggle anchors verified by string presence.
    assert "Hide trades with unresolved discrepancies" in r_no.text
    assert "Show all trades" in r_yes.text


def test_route_deviation_outcome_accepts_exclude_discrepancies_query(
    cfg_and_path,
) -> None:
    cfg, cfg_path = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_no = client.get("/metrics/deviation-outcome")
        r_yes = client.get(
            "/metrics/deviation-outcome?exclude_discrepancies=1",
        )
    assert r_no.status_code == 200
    assert r_yes.status_code == 200
    assert "(excluded 1 trades with unresolved discrepancies)" in r_yes.text
    assert "Hide trades with unresolved discrepancies" in r_no.text
    assert "Show all trades" in r_yes.text


def test_route_filter_zero_falsy_keeps_filter_inactive(cfg_and_path) -> None:
    """``?exclude_discrepancies=0`` is falsy ⇒ filter NOT active."""
    cfg, cfg_path = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison?exclude_discrepancies=0")
    assert r.status_code == 200
    # No excluded-count context line; the "Hide..." link still visible.
    assert "(excluded " not in r.text
    assert "Hide trades with unresolved discrepancies" in r.text


# ---------------------------------------------------------------------------
# VM-layer factory parameter wiring
# ---------------------------------------------------------------------------

def test_vm_factory_threads_exclude_unresolved_discrepancies(cfg_and_path) -> None:
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    vm = build_tier_comparison_vm(
        cfg=cfg,
        exclude_unresolved_discrepancies=True,
    )
    assert vm.result is not None
    assert vm.result.exclude_unresolved_discrepancies_active is True
    assert vm.result.excluded_trades_count == 1


def test_deviation_vm_factory_threads_exclude_unresolved_discrepancies(
    cfg_and_path,
) -> None:
    cfg, _ = cfg_and_path
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_5_aplus_trades_with_one_unresolved(conn)
    conn.close()

    vm = build_deviation_outcome_vm(
        cfg=cfg,
        exclude_unresolved_discrepancies=True,
    )
    assert vm.result is not None
    assert vm.result.exclude_unresolved_discrepancies_active is True
    assert vm.result.excluded_trades_count == 1
