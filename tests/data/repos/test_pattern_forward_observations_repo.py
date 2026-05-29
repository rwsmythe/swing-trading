import sqlite3
import pytest
from pathlib import Path
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import (
    insert_observation, get_observations_for_detection,
    get_latest_observation_for_detection, get_latest_observations_for_detections,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=22, backup_dir=tmp_path)
    return c


def _det(conn, **kw) -> int:
    base = dict(
        detection_id=None, ticker="AAA", detection_date="2026-05-29",
        data_asof_date="2026-05-28", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=0.7,
        detector_version="v1", source="pipeline",
        per_pattern_metadata_json="{}", created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    with conn:
        return insert_detection_event(conn, PatternDetectionEvent(**base))


def _obs(detection_id, date, **kw) -> PatternForwardObservation:
    base = dict(
        observation_id=None, detection_id=detection_id, observation_date=date,
        ohlc_today_json='{"close":11.0,"provider":"yfinance"}',
        status="pending", sessions_since_detection=1,
        created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    return PatternForwardObservation(**base)


def test_insert_and_chain_ordered_asc(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-30", sessions_since_detection=2))
        insert_observation(conn, _obs(det, "2026-05-29", sessions_since_detection=1))
    chain = get_observations_for_detection(conn, det)
    assert [o.observation_date for o in chain] == ["2026-05-29", "2026-05-30"]


def test_unique_detection_date(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-29"))
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            insert_observation(conn, _obs(det, "2026-05-29"))


def test_latest_observation(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-29", status="pending"))
        insert_observation(conn, _obs(det, "2026-05-30", status="triggered_open",
                                      sessions_since_detection=2,
                                      status_change_event="entry_fired"))
    latest = get_latest_observation_for_detection(conn, det)
    assert latest.observation_date == "2026-05-30"
    assert latest.status == "triggered_open"


import inspect
import swing.data.repos.pattern_forward_observations as mod


def test_batch_latest_empty_input_short_circuits(conn):
    # Empty input returns {} WITHOUT executing SQL. Patch conn.execute to a
    # tripwire to prove no SQL ran.
    class Tripwire:
        def execute(self, *a, **k):
            raise AssertionError("SQL must not run on empty input")
    assert get_latest_observations_for_detections(Tripwire(), []) == {}


def test_batch_latest_multi_detection(conn):
    d1, d2 = _det(conn, ticker="AAA"), _det(conn, ticker="BBB")
    with conn:
        insert_observation(conn, _obs(d1, "2026-05-29", status="pending"))
        insert_observation(conn, _obs(d1, "2026-05-30", status="triggered_open",
                                      sessions_since_detection=2,
                                      status_change_event="entry_fired"))
        insert_observation(conn, _obs(d2, "2026-05-29", status="invalidated",
                                      status_change_event="shape_break"))
    latest = get_latest_observations_for_detections(conn, [d1, d2])
    assert latest[d1].status == "triggered_open"
    assert latest[d2].status == "invalidated"


def test_restrict_fk_blocks_deleting_detection_with_observations(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-29"))
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute(
                "DELETE FROM pattern_detection_events WHERE detection_id = ?",
                (det,),
            )


def test_observable_excludes_terminal_latest_status(conn):
    # CROSS-REPO (deferred here from T-2.2 to avoid a forward import): a
    # detection whose latest observation status is terminal drops out of
    # list_observable_detections (Codex chain #1 Critical #1 ordering fix).
    from swing.data.repos.pattern_detection_events import list_observable_detections
    det = _det(conn, data_asof_date="2026-05-28")
    with conn:
        insert_observation(conn, _obs(
            det, "2026-05-29", status="expired", sessions_since_detection=1,
            status_change_event="observation_horizon_reached"))
    obs = list_observable_detections(
        conn, source="pipeline", observation_date="2026-05-30")
    assert obs == []


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
