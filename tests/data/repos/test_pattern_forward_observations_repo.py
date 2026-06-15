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


# Production-shaped FINITE OHLC json. build_ohlc_today_json emits all of
# {open,high,low,close,volume,provider}; the 18-B.1 insert_observation write
# barrier reads open/high/low/close, so the default fixture must carry the full
# finite OHLC set. (The prior close-only synthetic shape predates the barrier
# and would now be rejected as missing OHLC keys.)
_FINITE_OHLC_JSON = (
    '{"open":10.0,"high":11.5,"low":9.8,"close":11.0,'
    '"volume":12345,"provider":"yfinance"}'
)


def _obs(detection_id, date, **kw) -> PatternForwardObservation:
    base = dict(
        observation_id=None, detection_id=detection_id, observation_date=date,
        ohlc_today_json=_FINITE_OHLC_JSON,
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


# --- 18-B.1: insert_observation OHLC finiteness write-barrier (C-18B1) ------

# A NON-FINITE bar in the production ohlc_today_json shape (close=NaN, the real
# #99/06-10 cohort shape: O/H/L present, Close non-finite). JSON has no NaN
# literal, so it is emitted via json.dumps(..., float("nan")) -> the token
# `NaN`, which json.loads round-trips back to a Python float('nan').
import json
import math


def _nonfinite_ohlc_json(*, open_=10.0, high=11.5, low=9.8, close=float("nan")):
    return json.dumps({
        "open": open_, "high": high, "low": low, "close": close,
        "volume": 12345, "provider": "yfinance",
    })


def test_insert_observation_rejects_nonfinite_ohlc_write_barrier(conn):
    """WRITE-BARRIER (both-ways arithmetic; 18-B.1 FIX 2).

    PRE-FIX (no guard in insert_observation): a non-finite OHLC observation
    (close=NaN) INSERTs cleanly -- ohlc_today_json is plain `TEXT NOT NULL`
    with NO finiteness CHECK (migration 0022:69), so NaN reaches durable,
    append-only storage and permanently poisons the temporal-log finiteness
    monitor (the 06-10 103-row cohort exactly this way).
    POST-FIX: insert_observation raises BEFORE the INSERT (fail-loud backstop),
    so no row is written. The test asserts (a) the raise and (b) that ZERO rows
    landed -- distinguishing the guard from a post-insert check.
    """
    det = _det(conn)
    obs = _obs(det, "2026-05-29", ohlc_today_json=_nonfinite_ohlc_json())
    with pytest.raises(ValueError) as exc:
        with conn:
            insert_observation(conn, obs)
    msg = str(exc.value)
    # Names the offending field + the observation context (detection_id).
    assert "close" in msg.lower()
    assert f"detection_id={det}" in msg
    # ASCII-safe (Windows cp1252 stdout crashes on non-ASCII glyphs).
    msg.encode("ascii")
    # Nothing was written -- the barrier is BEFORE the INSERT, not after.
    assert get_observations_for_detection(conn, det) == []


def test_insert_observation_accepts_finite_ohlc_no_false_positive(conn):
    """A clean FINITE OHLC bar (the default fixture) still inserts -- the guard
    must not false-positive on good data."""
    det = _det(conn)
    with conn:
        oid = insert_observation(conn, _obs(det, "2026-05-29"))
    assert oid > 0
    chain = get_observations_for_detection(conn, det)
    assert len(chain) == 1


def test_insert_observation_accepts_finite_ohlc_with_nan_volume(conn):
    """Volume is EXEMPT (Arc-8: legit volume-less bars exist). A bar with
    FINITE OHLC but volume=NaN still inserts cleanly -- the barrier gates OHLC
    only, never volume."""
    det = _det(conn)
    vol_nan = json.dumps({
        "open": 10.0, "high": 11.5, "low": 9.8, "close": 11.0,
        "volume": float("nan"), "provider": "yfinance",
    })
    # Sanity: volume IS non-finite in this fixture (so the test truly exercises
    # the exemption, not a finite-volume happy path).
    assert math.isnan(json.loads(vol_nan)["volume"])
    with conn:
        oid = insert_observation(conn, _obs(det, "2026-05-29",
                                            ohlc_today_json=vol_nan))
    assert oid > 0


def test_read_path_preserves_accepted_nonfinite_historical_rows(conn):
    """READ-PRESERVATION (encodes the CHARC finding; MANDATORY; 18-B.1).

    Seed a non-finite historical row BYPASSING the new write barrier (raw
    conn.execute INSERT of the non-finite ohlc_today_json text -- mirrors the
    monitor plan-Task-2 raw-insert technique), then read it back through every
    repo reader and assert NO raise. This proves the 103 accepted historical
    non-finite rows (the immutable 06-10 cohort) still read clean.

    This test is the guard against a future 'consistency-fix' relocating the
    barrier onto PatternForwardObservation.__post_init__: that fires on the
    READ mapper _row_to_observation, so a __post_init__-located finiteness guard
    would RAISE here -> FAIL this test. The barrier MUST stay WRITE-path only.
    """
    det = _det(conn)
    poisoned = _nonfinite_ohlc_json()  # close=NaN, valid status/sessions
    # Raw INSERT -- bypasses insert_observation's guard entirely (direct SQL).
    with conn:
        conn.execute(
            """
            INSERT INTO pattern_forward_observations
                (detection_id, observation_date, ohlc_today_json, status,
                 status_change_event, sessions_since_detection, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (det, "2026-05-29", poisoned, "pending", None, 1,
             "2026-05-29T00:00:00Z"),
        )
    # Every reader (the mapper _row_to_observation under each) reads it WITHOUT
    # raising -- the accepted historical rows stay intact.
    chain = get_observations_for_detection(conn, det)
    assert len(chain) == 1
    assert chain[0].ohlc_today_json == poisoned

    latest = get_latest_observation_for_detection(conn, det)
    assert latest is not None
    assert latest.ohlc_today_json == poisoned

    batch = get_latest_observations_for_detections(conn, [det])
    assert det in batch
    assert batch[det].ohlc_today_json == poisoned


# Each case is a (label, ohlc_today_json) pair the barrier MUST reject -- the
# genuinely-unconstrained reachable input shapes (no schema CHECK gates them):
# malformed JSON, JSON decoding to a non-dict, missing OHLC keys, None / bool /
# string (non-numeric), +/-inf, and a huge int literal that overflows float().
_REJECTED_SHAPES = [
    ("malformed_json", "{not valid json"),
    ("json_non_dict_list", "[1, 2, 3]"),
    ("json_non_dict_number", "42"),
    ("json_non_dict_null", "null"),
    ("missing_open", '{"high":1.0,"low":1.0,"close":1.0,"provider":"yfinance"}'),
    ("open_is_null",
     '{"open":null,"high":1.0,"low":1.0,"close":1.0,"provider":"yfinance"}'),
    ("open_is_bool",
     '{"open":true,"high":1.0,"low":1.0,"close":1.0,"provider":"yfinance"}'),
    ("open_is_string",
     '{"open":"10.0","high":1.0,"low":1.0,"close":1.0,"provider":"yfinance"}'),
    ("close_is_inf",
     '{"open":1.0,"high":1.0,"low":1.0,"close":1e9999,"provider":"yfinance"}'),
    ("close_is_neg_inf",
     '{"open":1.0,"high":1.0,"low":1.0,"close":-1e9999,"provider":"yfinance"}'),
    # A huge INTEGER literal: valid JSON, parses to a Python int that passes the
    # type guard but overflows float() -- the barrier must re-raise ValueError
    # (not a raw OverflowError). Codex R1 MAJOR.
    ("open_int_overflows_float",
     '{"open":' + "9" * 400 + ',"high":1.0,"low":1.0,"close":1.0,'
     '"provider":"yfinance"}'),
]


@pytest.mark.parametrize("label, bad_json",
                         _REJECTED_SHAPES,
                         ids=[c[0] for c in _REJECTED_SHAPES])
def test_insert_observation_rejects_unconstrained_bad_shapes(conn, label, bad_json):
    """Every unconstrained reachable bad shape RAISES ValueError BEFORE the
    INSERT (fail-loud), the message is ASCII-safe, and ZERO rows land. (Codex
    R1 MINOR coverage + the R1 MAJOR overflow case.)"""
    det = _det(conn)
    with pytest.raises(ValueError) as exc:
        with conn:
            insert_observation(conn, _obs(det, "2026-05-29",
                                          ohlc_today_json=bad_json))
    str(exc.value).encode("ascii")  # ASCII-safe message
    assert get_observations_for_detection(conn, det) == []
