import inspect
import sqlite3
from pathlib import Path

import pytest

import swing.data.repos.pattern_detection_events as mod
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent
from swing.data.repos.pattern_detection_events import (
    get_detection_event_by_id,
    insert_detection_event,
    list_detection_events,
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
    with pytest.raises(sqlite3.IntegrityError), conn:
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


def test_repo_defines_no_update_or_delete_functions():
    names = [n for n, o in inspect.getmembers(mod, inspect.isfunction)
             if o.__module__ == mod.__name__]
    offenders = [n for n in names if n.startswith(("update_", "delete_"))]
    assert offenders == [], f"append-only violated: {offenders}"


def test_repo_source_has_no_mutating_sql():
    # Codex chain #2 Minor #2: the name-prefix grep is not enough -- a generic
    # helper could embed UPDATE/DELETE/REPLACE. Assert the module SOURCE has no
    # mutating SQL STATEMENT (the repo is INSERT/SELECT only). The patterns
    # match SQL-statement shapes (verb + SQL continuation), so prose/docstrings
    # mentioning "update_*"/"delete_*" do NOT false-positive.
    import re
    src = inspect.getsource(mod).upper()
    for pat in (r"\bUPDATE\s+\w+\s+SET\b", r"\bDELETE\s+FROM\b",
                r"\bREPLACE\s+INTO\b", r"\bDROP\s+(TABLE|INDEX)\b"):
        assert re.search(pat, src) is None, f"append-only violated: {pat}"
