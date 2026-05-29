import sqlite3
import pytest
from pathlib import Path
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent
from swing.data.repos.pattern_detection_events import (
    insert_detection_event, get_detection_event_by_id, list_detection_events,
    list_observable_detections,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=22, backup_dir=tmp_path)
    return c


def _event(**kw) -> PatternDetectionEvent:
    base = dict(
        detection_id=None, ticker="AAA", detection_date="2026-05-29",
        data_asof_date="2026-05-28", pattern_class="vcp",
        structural_anchors_json='{"window":{},"evidence":{"pivot_price":10.0}}',
        composite_score=0.72, detector_version="vcp_v1", source="pipeline",
        per_pattern_metadata_json='{"sector":"Tech","market_cap":null}',
        created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    return PatternDetectionEvent(**base)


def test_insert_and_get_round_trip(conn):
    with conn:
        det_id = insert_detection_event(conn, _event())
    assert isinstance(det_id, int)
    got = get_detection_event_by_id(conn, det_id)
    assert got is not None
    assert got.ticker == "AAA"
    assert got.pattern_class == "vcp"
    assert got.source == "pipeline"
    assert got.composite_score == pytest.approx(0.72)
    assert got.chart_render_id is None  # nullable audit linkage


def test_insert_is_caller_tx_no_autocommit(conn):
    # insert without an enclosing `with conn` does NOT persist after rollback.
    insert_detection_event(conn, _event(ticker="BBB"))
    conn.rollback()
    assert list_detection_events(conn, ticker="BBB") == []


def test_unique_source_ticker_date_class(conn):
    with conn:
        insert_detection_event(conn, _event())
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            insert_detection_event(conn, _event())  # same identity key


def test_observable_excludes_same_run_data_cutoff(conn):
    # detection data cutoff == observation_date -> NOT observable (STRICT <).
    with conn:
        insert_detection_event(conn, _event(data_asof_date="2026-05-29"))
    obs = list_observable_detections(
        conn, source="pipeline", observation_date="2026-05-29")
    assert obs == []


def test_observable_includes_prior_cutoff_with_no_observation_yet(conn):
    # No observation yet + data_asof_date < observation_date -> observable.
    with conn:
        insert_detection_event(conn, _event(data_asof_date="2026-05-28"))
    obs = list_observable_detections(
        conn, source="pipeline", observation_date="2026-05-29")
    assert len(obs) == 1
    assert obs[0].ticker == "AAA"
