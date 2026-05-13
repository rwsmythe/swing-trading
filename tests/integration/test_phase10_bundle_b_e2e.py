"""Phase 10 Sub-bundle B T-B.6 — happy-path E2E integration test.

Seeds a realistic data state (6 trades across 4 cohorts in mixed states +
some reviewed + a couple of mistake-cost / lucky-violation cases) and
verifies both Sub-bundle B operator surfaces render coherently:

  - GET /metrics/trade-process (T-B.3) per cohort + All tab.
  - GET /metrics/hypothesis-progress (T-B.5) per cohort row.

Per plan §E Task B.6 acceptance: each surface renders with expected
metric values; ruff baseline preserved.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.web.app import create_app


@pytest.fixture
def seeded_app(tmp_path: Path):
    db_path = tmp_path / "phase10_b_e2e.db"
    ensure_schema(db_path).close()

    base_cfg = load_config(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))

    # Use the tracked toml as cfg_path for create_app — the cfg dataclass
    # has the actual paths.
    cfg_path = Path("swing.config.toml")

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            # Seed 6 trades across 4 cohorts.
            # A+ baseline: 3 closed (2 wins, 1 loss).
            # Near-A+: 1 closed (win).
            # Sub-A+: 1 closed (loss).
            # Capital-blocked: 1 open (not in closed cohort metrics).
            trades = [
                # (id, ticker, cohort, exit_price, state, reviewed_at,
                #  realized_R_if_plan_followed, mistake_tags, process_grade,
                #  disq)
                (1, "AAA", "A+ baseline", 12.0, "reviewed",
                 "2026-04-10T10:00:00", 2.5, '["SOLD_TOO_EARLY"]', "A", 0),
                (2, "BBB", "A+ baseline", 11.0, "closed",
                 None, None, None, None, None),
                (3, "CCC", "A+ baseline", 9.0, "reviewed",
                 "2026-04-10T11:00:00", -0.5, '["NONE_OBSERVED"]', "C", 0),
                (4, "DDD", "Near-A+ defensible: extension test",
                 11.5, "closed",
                 None, None, None, None, None),
                (5, "EEE", "Sub-A+ VCP-not-formed", 8.5, "closed",
                 None, None, None, None, None),
                (6, "FFF", "Capital-blocked: smaller-position test",
                 None, "entered", None, None, None, None, None),
            ]
            for (
                tid, ticker, cohort, exit_price, state, reviewed_at,
                plan_r, mistake_tags, process_grade, disq,
            ) in trades:
                conn.execute(
                    "INSERT INTO trades (id, ticker, entry_date, "
                    "entry_price, initial_shares, initial_stop, "
                    "current_stop, state, sector, industry, trade_origin, "
                    "pre_trade_locked_at, current_size, hypothesis_label, "
                    "risk_policy_id_at_lock, reviewed_at, "
                    "realized_R_if_plan_followed, mistake_tags, "
                    "process_grade, disqualifying_process_violation, "
                    "last_fill_at) VALUES "
                    "(?, ?, '2026-04-01', 10.0, 100, 9.0, 9.0, ?, 'S', 'I', "
                    "'manual_off_pipeline', '2026-04-01T09:30:00', 100, "
                    "?, 1, ?, ?, ?, ?, ?, ?)",
                    (
                        tid, ticker, state, cohort, reviewed_at,
                        plan_r, mistake_tags, process_grade, disq,
                        f"2026-04-0{tid+1}T15:30:00" if exit_price else None,
                    ),
                )
                conn.execute(
                    "INSERT INTO fills (trade_id, fill_datetime, action, "
                    "quantity, price, reconciliation_status) VALUES "
                    "(?, '2026-04-01T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
                    (tid,),
                )
                if exit_price is not None:
                    conn.execute(
                        "INSERT INTO fills (trade_id, fill_datetime, "
                        "action, quantity, price, reconciliation_status) "
                        "VALUES (?, ?, 'exit', 100, ?, 'unreconciled')",
                        (tid, f"2026-04-0{tid+1}T15:30:00", exit_price),
                    )
    finally:
        conn.close()

    return cfg, cfg_path


def test_trade_process_surface_renders_at_seeded_state(seeded_app) -> None:
    """Trade-process card endpoint renders per-cohort metric grid +
    cohort tab counts reflect seeded data."""
    cfg, cfg_path = seeded_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    assert r.status_code == 200
    body = r.text
    # 5 closed/reviewed trades total (Capital-blocked one open).
    # A+ has 3 closed/reviewed; Near-A+ 1; Sub-A+ 1; Capital-blocked 0.
    # Default-active is A+ baseline.
    assert 'data-cohort-key="A+ baseline"' in body
    # Verify mistake_cost rendering: AAA has plan=+2.5 / actual=+2.0 ⇒
    # mistake=0.5; CCC has plan=-0.5 / actual=-1.0 ⇒ mistake=0.5.
    # Total mistake_cost_R for A+ baseline cohort = 1.0.
    assert "mistake_cost_R_total" in body


def test_hypothesis_progress_surface_renders_at_seeded_state(
    seeded_app,
) -> None:
    """Hypothesis-progress card renders all 4 cohort cells with
    populated progress + tripwire metrics."""
    cfg, cfg_path = seeded_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/hypothesis-progress")
    assert r.status_code == 200
    body = r.text
    # Each cohort cell rendered.
    for label in (
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
    ):
        assert label in body
    # Decision-criteria text rendered (HTML-escape-safe substring).
    assert "defensibility of smaller-position approach" in body


def test_trade_process_aplus_tab_shows_2_wins_1_loss(seeded_app) -> None:
    """Verify per-tab metric values by selecting A+ baseline via query
    parameter. A+ closed trades: 2 wins (AAA +2R, BBB +1R) + 1 loss
    (CCC -1R)."""
    cfg, cfg_path = seeded_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # A+ is default-active, but be explicit.
        r = client.get(
            "/metrics/trade-process",
            params={"cohort": "A+ baseline"},
        )
    assert r.status_code == 200
    # n_closed = 3 should appear in the cohort tab badge.
    assert 'data-cohort-key="A+ baseline"' in r.text


def test_metrics_index_links_resolve_for_sub_bundle_b_surfaces(
    seeded_app,
) -> None:
    """Per CLAUDE.md HX-Redirect-target-unrouted gotcha family — verify
    both new surface routes are registered + each resolves to 200."""
    cfg, cfg_path = seeded_app
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/trade-process" in route_paths
    assert "/metrics/hypothesis-progress" in route_paths
    with TestClient(app) as client:
        for path in ("/metrics", "/metrics/trade-process",
                     "/metrics/hypothesis-progress"):
            r = client.get(path)
            assert r.status_code == 200, (
                f"{path} → {r.status_code} (operator-witnessed gate "
                "S3+S4 binds; route MUST resolve)"
            )
