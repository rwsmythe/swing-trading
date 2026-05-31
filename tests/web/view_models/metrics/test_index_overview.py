"""T-5.2 — metrics overview VM enhancement (P14.N5)."""
from __future__ import annotations

import sqlite3
from dataclasses import fields
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.evaluation.dates import last_completed_session
from swing.web.view_models.metrics.index import (
    MetricsIndexSurface,
    _ascii,
    _SURFACES,
)


# --------------------------------------------------------------------------
# Seeded-DB fixtures (reuse the production insert shapes; gotcha: no synthetic
# drift). capital + funnel build one trend point per completed pipeline_runs
# row keyed by substr(started_ts,1,10) within the last 30 NYSE sessions, so
# the run COUNT is the discriminator. process-grade draws from reviewed trades.
# --------------------------------------------------------------------------
def _make_cfg(tmp_path: Path, name: str):
    db_path = tmp_path / name
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))


def _recent_sessions(n: int) -> list[str]:
    import exchange_calendars
    import pandas as pd

    cal = exchange_calendars.get_calendar("XNYS")
    asof = last_completed_session(datetime.now())
    sessions = cal.sessions_window(pd.Timestamp(asof), -(n - 1))
    dates = sorted({ts.date().isoformat() for ts in sessions})
    return dates[-n:]


def _seed_runs(conn: sqlite3.Connection, session_dates: list[str]) -> None:
    for i, d in enumerate(session_dates):
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) VALUES "
            "(?, 'manual', ?, ?, 'complete', ?)",
            (f"{d}T09:30:00", d, d, f"t-{i}"),
        )
    conn.commit()


def _seed_reviewed_trades(conn: sqlite3.Connection, n: int) -> None:
    for i in range(n):
        day = (i % 27) + 1
        trade_id = 1000 + i
        ts = f"2026-04-{day:02d}T16:00:00"
        fill_ts = f"2026-04-{day:02d}T15:30:00"
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size, "
            "process_grade, entry_grade, management_grade, exit_grade, "
            "disqualifying_process_violation, realized_R_if_plan_followed, "
            "reviewed_at, last_fill_at) VALUES "
            "(?, ?, '2026-03-15', 10.0, 100, 9.0, 9.0, 'reviewed', 'S', 'I', "
            "'manual_off_pipeline', '2026-03-15T09:30:00', 0, 'B', 'B', 'B', "
            "'B', 0, 1.0, ?, ?)",
            (trade_id, f"T{i:03d}", ts, fill_ts),
        )
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES "
            "(?, '2026-03-15T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
            (trade_id,),
        )
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES "
            "(?, ?, 'exit', 100, 11.0, 'unreconciled')",
            (trade_id, fill_ts),
        )
    conn.commit()


@pytest.fixture
def high_data_cfg_conn(tmp_path):
    cfg = _make_cfg(tmp_path, "high.db")
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_runs(conn, _recent_sessions(12))  # >=10 -> capital + funnel draw
    _seed_reviewed_trades(conn, 12)          # window 10 -> process-grade draws
    yield cfg, conn
    conn.close()


@pytest.fixture
def low_data_cfg_conn(tmp_path):
    cfg = _make_cfg(tmp_path, "low.db")
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_runs(conn, _recent_sessions(3))  # <5 -> capital + funnel suppress
    yield cfg, conn
    conn.close()


@pytest.fixture
def borderline_7_runs_cfg_conn(tmp_path):
    cfg = _make_cfg(tmp_path, "bord.db")
    conn = sqlite3.connect(cfg.paths.db_path)
    _seed_runs(conn, _recent_sessions(7))  # capital draws (>=5), funnel suppresses (<10)
    yield cfg, conn
    conn.close()


def test_surface_has_overview_fields_with_safe_defaults():
    names = {f.name for f in fields(MetricsIndexSurface)}
    assert {
        "headline_stat_text", "headline_caption", "headline_suppressed_text",
        "sparkline_points", "sparkline_suppressed_text", "sparkline_kind",
    } <= names
    s = MetricsIndexSurface(path="/x", label="X", description="d")
    assert s.headline_stat_text is None
    assert s.sparkline_kind == "none"


def test_ascii_sanitizer_coerces_geq_glyph_without_question_mark():
    # honesty.py emits "need: >=N" with a real U+2265; the overview must ASCII it
    # via a MAPPED substitution (no silent "?" masking - Codex R2 MINOR).
    out = _ascii("[grade: n too low (current: 3, need: ≥5)]")
    assert out.isascii()
    assert ">=5" in out
    assert "?" not in out  # the glyph was mapped, not replace-masked
    assert _ascii(None) is None


def test_surfaces_registry_is_ascii():
    # The template renders surface.label + surface.description verbatim; the
    # static registry MUST be ASCII so body.isascii() holds (Codex R2 CRITICAL).
    for s in _SURFACES:
        assert s.label.isascii(), s.label
        assert s.description.isascii(), s.description


# --------------------------------------------------------------------------
# T-5.2.b — the 3 trend-surface extractors (sparklines; per-surface threshold)
# --------------------------------------------------------------------------
from swing.web.view_models.metrics.index import (  # noqa: E402
    _extract_capital_friction,
    _extract_identification_funnel,
    _extract_process_grade_trend,
)


def test_capital_sparkline_present_when_runs_at_or_above_5(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_capital_friction(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "inline_svg"
    assert card.sparkline_points is not None
    assert card.sparkline_suppressed_text is None
    assert card.headline_caption == "utilization"


def test_capital_sparkline_suppressed_below_5(low_data_cfg_conn):
    cfg, conn = low_data_cfg_conn  # 3 runs
    card = _extract_capital_friction(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "inline_svg"
    assert card.sparkline_points is None
    assert "needs >=5 runs" in card.sparkline_suppressed_text


def test_funnel_sparkline_threshold_is_10_not_5(borderline_7_runs_cfg_conn):
    cfg, conn = borderline_7_runs_cfg_conn
    funnel_card = _extract_identification_funnel(cfg, conn, "2026-05-30")
    assert funnel_card.sparkline_points is None
    assert "needs >=10 runs" in funnel_card.sparkline_suppressed_text


def test_capital_draws_on_same_7_run_db_funnel_suppresses(borderline_7_runs_cfg_conn):
    # The NON-uniform-threshold discriminator: capital's 5-run floor draws on
    # the SAME 7-run DB where funnel's 10-run floor suppresses.
    cfg, conn = borderline_7_runs_cfg_conn
    cap = _extract_capital_friction(cfg, conn, "2026-05-30")
    fun = _extract_identification_funnel(cfg, conn, "2026-05-30")
    assert cap.sparkline_points is not None
    assert fun.sparkline_points is None


def test_process_grade_sparkline_uses_line_band_gate(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_process_grade_trend(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "inline_svg"
    assert (card.sparkline_points is not None) ^ (card.sparkline_suppressed_text is not None)
    assert card.headline_caption == "rolling grade"


# --------------------------------------------------------------------------
# T-5.2.c — the 6 headline-only extractors + the 2 OQ-4 constants
# --------------------------------------------------------------------------
from swing.web.view_models.metrics.index import (  # noqa: E402
    DEVIATION_HEADLINE_COHORT,
    PATTERN_HEADLINE_CLASS,
    _extract_deviation_outcome,
    _extract_hypothesis_progress,
    _extract_maturity_stage,
    _extract_pattern_outcomes,
    _extract_tier_comparison,
    _extract_trade_process,
)


def test_hypothesis_progress_headline_counts_registered_cohorts(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_hypothesis_progress(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "none"
    assert card.headline_caption == "registered cohorts"
    assert card.headline_stat_text == "4"  # 4 TAXONOMY_COHORTS registered


def test_maturity_headline_is_open_position_count(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_maturity_stage(cfg, conn, "2026-05-30")
    assert card.headline_caption == "open positions"
    assert card.headline_stat_text is not None  # "0" is a valid honest value


def test_pattern_outcomes_uses_fixed_class_and_existing_suppression(low_data_cfg_conn):
    cfg, conn = low_data_cfg_conn
    card = _extract_pattern_outcomes(cfg, conn, "2026-05-30")
    assert card.sparkline_kind == "none"
    assert f"({PATTERN_HEADLINE_CLASS})" in card.headline_caption
    assert (card.headline_stat_text is not None) or (card.headline_suppressed_text is not None)


def test_deviation_headline_uses_fixed_cohort(high_data_cfg_conn):
    cfg, conn = high_data_cfg_conn
    card = _extract_deviation_outcome(cfg, conn, "2026-05-30")
    assert "delta vs A+" in card.headline_caption
    assert DEVIATION_HEADLINE_COHORT


def test_trade_process_and_tier_headline_use_existing_suppression(low_data_cfg_conn):
    cfg, conn = low_data_cfg_conn
    tp = _extract_trade_process(cfg, conn, "2026-05-30")
    tier = _extract_tier_comparison(cfg, conn, "2026-05-30")
    assert tp.sparkline_kind == "none"
    assert tier.sparkline_kind == "none"
    # Each surface emits EITHER a headline value OR an honest suppressed text.
    assert (tp.headline_stat_text is not None) or (tp.headline_suppressed_text is not None)
    assert (tier.headline_stat_text is not None) or (tier.headline_suppressed_text is not None)
