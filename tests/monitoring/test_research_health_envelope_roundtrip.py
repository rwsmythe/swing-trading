"""Task 8 -- the all-5-gates-by-construction proof: write latest.json -> read it
back through the LIVE 18-F read_validated_research_envelope -> assert it
validates (green/yellow/red, NOT grey). A data-shape-vs-live-reader round-trip
(memory feedback_adversarial_review_verify_data_shapes), not a logic-vs-spec
check.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.monitoring import stoplights
from swing.monitoring.research_health import compute_research_health

_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'
# FIX 1 (18-D): finiteness #1 reds ONLY on a non-finite obs STRICTLY AFTER the
# 2026-06-13 18-A baseline. The red seed dates its detection + NaN observation
# after that barrier (a genuine post-fix regression); the detection's asof is
# post-baseline too so it stays non-mature -> only finiteness drives the red.
_POST_CUTOFF_DATE = "2026-06-16"  # strictly after the 2026-06-13 baseline


def _seed_db(db_path: Path, *, color: str) -> None:
    conn = ensure_schema(db_path)
    if color == "red":
        det_date = asof = obs_date = _POST_CUTOFF_DATE
        close = "NaN"
    else:
        det_date, asof, obs_date = "2026-06-05", "2026-06-04", "2026-06-05"
        close = "1.5"
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="AAA", detection_date=det_date,
        data_asof_date=asof, pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00"))
    ohlc = ('{"open": 1.0, "high": 2.0, "low": 0.5, "close": ' + close
            + ', "volume": 100.0, "provider": "yfinance"}')
    conn.execute(
        "INSERT INTO pattern_forward_observations "
        "(detection_id, observation_date, ohlc_today_json, status, "
        "sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, obs_date, ohlc, "invalidated", 1, "2026-06-05T00:00:00"))
    conn.commit()
    conn.close()


def _fresh_manifest(exports_root: Path, *, days: int = 0, hours: int = 1,
                    invalid_ohlc: int = 1) -> None:
    ts = datetime.now(UTC) - timedelta(days=days, hours=hours)
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    run_dir = exports_root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": invalid_ohlc}}},
        "unattributed": {},
    }}), encoding="utf-8")


def _write_via_aggregator(db: Path, artifact: Path, exports_root: Path):
    from swing.data.db import connect
    conn = connect(db)
    try:
        status = compute_research_health(conn, exports_root=exports_root)
    finally:
        conn.close()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(status.to_dict(), indent=2), encoding="utf-8")
    return status


def test_envelope_roundtrips_through_18f_reader(tmp_path, monkeypatch) -> None:
    db = tmp_path / "swing.db"
    _seed_db(db, color="green")
    artifact = tmp_path / "health" / "latest.json"
    assert not artifact.exists()  # fresh dir -- no stale file
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)
    status = _write_via_aggregator(db, artifact, tmp_path)
    written = artifact.read_text(encoding="utf-8")
    validated = stoplights.read_validated_research_envelope()
    assert validated is not None  # validates, NOT grey
    overall, env = validated
    assert overall in {"green", "yellow", "red"}
    assert overall == status.overall
    # the reader validated the EXACT file just written this invocation
    assert json.dumps(env, indent=2) == written or env == json.loads(written)


@pytest.mark.parametrize("color", ["green", "yellow", "red"])
def test_envelope_roundtrips_green_yellow_red(tmp_path, monkeypatch, color) -> None:
    db = tmp_path / "swing.db"
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    if color == "red":
        _seed_db(db, color="red")
        _fresh_manifest(tmp_path)
    elif color == "yellow":
        _seed_db(db, color="green")
        _fresh_manifest(tmp_path, days=5)  # stale drumbeat -> yellow
    else:
        _seed_db(db, color="green")
        _fresh_manifest(tmp_path)
    status = _write_via_aggregator(db, artifact, tmp_path)
    assert status.overall == color
    validated = stoplights.read_validated_research_envelope()
    assert validated is not None
    assert validated[0] == color


def test_written_envelope_roundtrips_for_manifest_absent_vs_corrupt(
    tmp_path, monkeypatch,
) -> None:
    db = tmp_path / "swing.db"
    _seed_db(db, color="green")
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)

    # (i) absent: no shadow-expectancy-* dir -> excluded green, but drumbeat RED
    # (never ran) -> overall RED -> reader validates RED.
    status_absent = _write_via_aggregator(db, artifact, tmp_path)
    validated = stoplights.read_validated_research_envelope()
    assert validated is not None
    assert validated[0] == status_absent.overall == "red"

    # (ii) corrupt: a FRESH dir with a malformed manifest -> excluded yellow +
    # drumbeat at-least yellow -> overall at-least yellow -> validates (NOT grey).
    ts = datetime.now(UTC) - timedelta(hours=1)
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    run_dir = tmp_path / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text("{not valid", encoding="utf-8")
    status_corrupt = _write_via_aggregator(db, artifact, tmp_path)
    validated2 = stoplights.read_validated_research_envelope()
    assert validated2 is not None
    assert validated2[0] in {"yellow", "red"}
    assert validated2[0] == status_corrupt.overall


def test_envelope_generated_ts_is_not_future_for_reader_on_any_host(
    tmp_path, monkeypatch,
) -> None:
    db = tmp_path / "swing.db"
    _seed_db(db, color="green")
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)
    # FRESH aware-UTC stamp -> validates (neither future nor stale).
    _write_via_aggregator(db, artifact, tmp_path)
    assert stoplights.read_validated_research_envelope() is not None

    # a deliberately-OLD aware-UTC stamp (8 days) -> reader greys it STALE.
    env = json.loads(artifact.read_text(encoding="utf-8"))
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat(timespec="seconds")
    env["generated_ts"] = old
    artifact.write_text(json.dumps(env), encoding="utf-8")
    assert stoplights.read_validated_research_envelope() is None  # stale -> grey
