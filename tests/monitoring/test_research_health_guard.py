"""19-B Task 5 -- the broken-context write-suppression guard + machine-readable
signals (db_detection_count, _prior_env_had_detections) + the writer `extra:` merge.

Machine-readable end to end: the count helper is exercised against a REAL seeded
DB (real insert_detection_event rows) and the writer round-trip against the REAL
18-F reader.
"""
from __future__ import annotations

import json
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.monitoring.research_health import (
    ResearchHealthCheck,
    ResearchHealthStatus,
    _prior_env_had_detections,
    _read_prior_env,
    db_detection_count,
    should_suppress_broken_context_write,
    write_research_health_artifact,
)
from swing.monitoring.stoplights import read_validated_research_envelope


def _seed_detections(db_path: Path, n: int) -> None:
    conn = ensure_schema(db_path)
    for i in range(n):
        insert_detection_event(conn, PatternDetectionEvent(
            detection_id=None, ticker=f"T{i}", detection_date="2026-06-05",
            data_asof_date="2026-06-04", pattern_class="vcp",
            structural_anchors_json="{}", composite_score=1.0, detector_version="t",
            source="synthetic", per_pattern_metadata_json="{}",
            created_at="2026-06-05T00:00:00"))
    conn.commit()
    conn.close()


# --- signal (i): anchor divergence -----------------------------------------

def test_signal_i_manifest_wrote_but_scan_root_empty_suppresses(tmp_path):
    suppress, reason = should_suppress_broken_context_write(
        current_detection_count=5, exports_root=tmp_path / "empty",
        shadow_manifest_path=tmp_path / "m.json", prior_env=None)
    assert suppress is True
    assert reason


def test_signal_i_shadow_failure_no_manifest_does_not_suppress(tmp_path):
    # shadow_manifest_path=None (a genuine failure / first-ever run) -> the honest
    # drumbeat-RED is NOT hidden.
    suppress, reason = should_suppress_broken_context_write(
        current_detection_count=5, exports_root=tmp_path / "empty",
        shadow_manifest_path=None, prior_env=None)
    assert suppress is False
    assert reason is None


def test_signal_i_manifest_present_in_scan_root_does_not_suppress(tmp_path):
    root = tmp_path / "research"
    (root / "shadow-expectancy-20260613T000000Z").mkdir(parents=True)
    suppress, _ = should_suppress_broken_context_write(
        current_detection_count=5, exports_root=root,
        shadow_manifest_path=tmp_path / "m.json", prior_env=None)
    assert suppress is False


# --- signal (ii): wrong-HOME empty read ------------------------------------

def test_signal_ii_empty_db_prior_had_detections_suppresses(tmp_path):
    prior = {"monitor": "research_measurement", "detection_count": 5}
    suppress, reason = should_suppress_broken_context_write(
        current_detection_count=0, exports_root=tmp_path,
        shadow_manifest_path=None, prior_env=prior)
    assert suppress is True
    assert reason


def test_signal_ii_empty_db_prior_zero_detections_does_not_suppress(tmp_path):
    prior = {"monitor": "research_measurement", "detection_count": 0}
    suppress, _ = should_suppress_broken_context_write(
        current_detection_count=0, exports_root=tmp_path,
        shadow_manifest_path=None, prior_env=prior)
    assert suppress is False  # genuine-fresh


def test_signal_ii_empty_db_old_prior_no_field_does_not_suppress(tmp_path):
    prior = {"monitor": "research_measurement"}  # pre-19-B, no detection_count
    suppress, _ = should_suppress_broken_context_write(
        current_detection_count=0, exports_root=tmp_path,
        shadow_manifest_path=None, prior_env=prior)
    assert suppress is False  # conservative


def test_signal_ii_empty_db_prior_none_does_not_suppress(tmp_path):
    suppress, _ = should_suppress_broken_context_write(
        current_detection_count=0, exports_root=tmp_path,
        shadow_manifest_path=None, prior_env=None)
    assert suppress is False


def test_signal_ii_populated_db_does_not_suppress(tmp_path):
    prior = {"monitor": "research_measurement", "detection_count": 5}
    suppress, _ = should_suppress_broken_context_write(
        current_detection_count=3, exports_root=tmp_path,
        shadow_manifest_path=None, prior_env=prior)
    assert suppress is False


# --- db_detection_count -----------------------------------------------------

def test_db_detection_count_counts_rows(tmp_path):
    db = tmp_path / "swing.db"
    _seed_detections(db, 3)
    conn = ensure_schema(db)
    assert db_detection_count(conn) == 3
    conn.close()


def test_db_detection_count_empty_db_zero(tmp_path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    assert db_detection_count(conn) == 0
    conn.close()


def test_db_detection_count_missing_table_sentinel(tmp_path):
    import sqlite3
    conn = sqlite3.connect(tmp_path / "bare.db")
    assert db_detection_count(conn) == -1  # never suppresses on a pre-schema DB
    conn.close()


# --- _prior_env_had_detections ---------------------------------------------

def test_prior_env_had_detections_true():
    assert _prior_env_had_detections(
        {"monitor": "research_measurement", "detection_count": 5}) is True


def test_prior_env_had_detections_wrong_monitor_false():
    assert _prior_env_had_detections(
        {"monitor": "tool_health", "detection_count": 5}) is False


def test_prior_env_had_detections_bool_is_not_int():
    # detection_count True is a bool (subclass of int) -> must be rejected.
    assert _prior_env_had_detections(
        {"monitor": "research_measurement", "detection_count": True}) is False


def test_prior_env_had_detections_missing_field_false():
    assert _prior_env_had_detections({"monitor": "research_measurement"}) is False
    assert _prior_env_had_detections(None) is False


# --- writer extra: merge + round-trip through the REAL reader ---------------

def test_writer_extra_stamps_detection_count_and_reader_tolerates(
    tmp_path, monkeypatch,
):
    from datetime import UTC, datetime
    status = ResearchHealthStatus(
        overall="green",
        checks=[ResearchHealthCheck(key="k", status="green", summary="s",
                                    detail=None)],
        generated_ts=datetime.now(UTC).isoformat(timespec="seconds"))
    out = tmp_path / "health" / "latest.json"
    write_research_health_artifact(status, out_path=out, extra={"detection_count": 7})
    env = json.loads(out.read_text(encoding="utf-8"))
    assert env["detection_count"] == 7  # the machine-readable witness stamped
    # the extra key round-trips through the 18-F validating reader (ignored, valid).
    # Point the cfg-less accessor at this artifact so the reader resolves here.
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda cfg=None: out)
    assert read_validated_research_envelope() is not None
    assert _read_prior_env(out)["detection_count"] == 7


# --- _read_prior_env --------------------------------------------------------

def test_read_prior_env_absent_none(tmp_path):
    assert _read_prior_env(tmp_path / "nope.json") is None


def test_read_prior_env_unparseable_none(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{ not json", encoding="utf-8")
    assert _read_prior_env(p) is None


def test_read_prior_env_valid_dict(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"monitor": "research_measurement", "detection_count": 3}',
                 encoding="utf-8")
    assert _read_prior_env(p) == {"monitor": "research_measurement",
                                  "detection_count": 3}


def test_read_prior_env_deeply_nested_none(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("[" * 5000 + "]" * 5000, encoding="utf-8")
    assert _read_prior_env(p) is None
