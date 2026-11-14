"""D102 T2.1 -- per-night labels from the single prefill call site.

Tests 2a (and the 2h keeper is `tests/integration/
test_include_baseline_inventory_guard.py`, unchanged and green). Seeded from
trade 29's LIVE shape (`build_sg_case`): SG rows on evals 192/193/194, all
`watch`, the latest complete run eval 194.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.db import ensure_schema
from swing.recommendations.hypothesis_prefill import (
    WATCH_FIRE_WINDOW_ROWS,
    DecisionNight,
    list_decision_nights,
    lookup_active_recommendation_label,
)
from tests.trades._cohort_provenance_fixtures import (
    SG_BASELINE_LABEL,
    SG_FIRE_LABEL,
    build_sg_case,
)

EQUITY = 7500.0


def _sg(tmp_path: Path, **case) -> sqlite3.Connection:
    conn = ensure_schema(tmp_path / "swing.db", backup_dir=tmp_path / "bak")
    build_sg_case(conn, **case)
    conn.commit()
    return conn


def test_2a_three_nights_newest_first_with_dates_and_labels(tmp_path) -> None:
    conn = _sg(tmp_path)
    nights = list_decision_nights(conn, ticker="SG", starting_equity=EQUITY)
    assert [n.candidate_id for n in nights] == [15980, 15901, 15811]
    assert [n.action_session_date for n in nights] == [
        "2026-11-06", "2026-11-05", "2026-11-04"]
    assert [n.evaluation_run_id for n in nights] == [194, 193, 192]
    assert [n.bucket for n in nights] == ["watch"] * 3
    assert nights[0].label == SG_BASELINE_LABEL
    assert nights[1].label == SG_FIRE_LABEL
    # 15811 carries the batch-night shape (proximity_20ma AND tightness
    # failed), so the matcher's suggestion is the broad-watch baseline.
    assert nights[2].label == SG_BASELINE_LABEL
    assert all(isinstance(n, DecisionNight) for n in nights)
    conn.close()


def test_2a_the_newest_night_is_the_latest_night_lookup(tmp_path) -> None:
    """The default (newest) night carries exactly what the latest-night
    lookup returns today -- an operator who does not choose gets today's
    value."""
    conn = _sg(tmp_path)
    nights = list_decision_nights(conn, ticker="SG", starting_equity=EQUITY)
    assert nights[0].label == lookup_active_recommendation_label(
        conn, ticker="SG", starting_equity=EQUITY)
    conn.close()


def test_2a_an_incomplete_run_offers_no_night(tmp_path) -> None:
    conn = _sg(tmp_path, pipeline_complete={193: False})
    nights = list_decision_nights(conn, ticker="SG", starting_equity=EQUITY)
    assert [n.candidate_id for n in nights] == [15980, 15811]
    conn.close()


def test_2a_the_offer_is_the_latest_nights_bucket_only(tmp_path) -> None:
    """F6 = A: an aplus row inside the window is not offered under a watch
    latest night (its origin would be pipeline_aplus)."""
    conn = _sg(tmp_path, buckets={15901: "aplus"})
    nights = list_decision_nights(conn, ticker="SG", starting_equity=EQUITY)
    assert [n.candidate_id for n in nights] == [15980, 15811]
    conn.close()


def test_2k_no_row_in_the_latest_run_offers_nothing(tmp_path) -> None:
    """F6 edge: the latest complete run holds no row for the ticker, so the
    origin is manual_off_pipeline and the lister returns []."""
    conn = _sg(tmp_path)
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES (195, "
        "'2026-11-06T17:30:00', '2026-11-06', '2026-11-09', 1, 0, 0, 0, 0, "
        "0)")
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES (209, '2026-11-06T17:30:00', "
        "'2026-11-06T17:35:00', 'scheduled', '2026-11-06', '2026-11-09', "
        "'complete', 'lease-209', 195)")
    conn.commit()
    assert list_decision_nights(
        conn, ticker="SG", starting_equity=EQUITY) == []
    conn.close()


def test_2a_the_window_is_the_ruled_n(tmp_path) -> None:
    assert WATCH_FIRE_WINDOW_ROWS == 5
    conn = _sg(tmp_path)
    nights = list_decision_nights(
        conn, ticker="SG", starting_equity=EQUITY, n=2)
    assert [n.candidate_id for n in nights] == [15980, 15901]
    conn.close()
