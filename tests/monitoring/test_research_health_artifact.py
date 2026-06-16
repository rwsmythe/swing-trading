"""Task 1 (18-D nightly half) -- the single-sourced atomic artifact writer
``write_research_health_artifact`` in swing/monitoring/research_health.py (C-NH4).

The writer is extracted from scripts/research_health.py's local
``_write_latest_json_atomic`` so the nightly pipeline step (Task 2) and the
script call the SAME function -- NO second copy of the atomic write.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.monitoring.research_health import (
    ResearchHealthCheck,
    ResearchHealthStatus,
    write_research_health_artifact,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "research_health.py"
_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "_research_health_script_artifact", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seed_green_db(db_path: Path) -> None:
    conn = ensure_schema(db_path)
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="AAA", detection_date="2026-06-05",
        data_asof_date="2026-06-04", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00"))
    insert_observation(conn, PatternForwardObservation(
        observation_id=None, detection_id=det, observation_date="2026-06-05",
        ohlc_today_json=_FINITE_OHLC, status="invalidated",
        sessions_since_detection=1, created_at="2026-06-05T00:00:00"))
    conn.commit()
    conn.close()


def _fresh_manifest(exports_root: Path) -> None:
    ts = datetime.now(UTC) - timedelta(hours=1)
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    run_dir = exports_root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 1}}},
        "unattributed": {},
    }}), encoding="utf-8")


def _green_status() -> ResearchHealthStatus:
    """A minimal conformant green status (default generated_ts = fresh aware-UTC)."""
    check = ResearchHealthCheck(
        key="temporal_log_finiteness", status="green",
        summary="0 non-finite", detail=None)
    return ResearchHealthStatus(overall="green", checks=[check])


def test_write_research_health_artifact_atomic_no_tmp_leftover(tmp_path: Path) -> None:
    status = _green_status()
    out = tmp_path / "health" / "latest.json"
    returned = write_research_health_artifact(status, out_path=out)
    assert returned == out
    assert out.exists()
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["monitor"] == "research_measurement"
    assert parsed["overall"] == "green"
    # no leftover .tmp -- the atomic write replaced + cleaned up.
    assert not list((tmp_path / "health").glob("*.tmp"))


def test_write_research_health_artifact_default_path_uses_accessor(
    tmp_path: Path, monkeypatch,
) -> None:
    # out_path=None must resolve via the ACCESSOR (not a hardcoded constant) so a
    # monkeypatch of the accessor is honored.
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    returned = write_research_health_artifact(_green_status())
    assert returned == artifact
    assert artifact.exists()
    parsed = json.loads(artifact.read_text(encoding="utf-8"))
    assert parsed["monitor"] == "research_measurement"


def test_write_research_health_artifact_creates_parent_dir(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deeper" / "health" / "latest.json"
    assert not out.parent.exists()
    write_research_health_artifact(_green_status(), out_path=out)
    assert out.parent.exists()
    assert out.exists()


def test_script_invokes_shared_writer(tmp_path: Path, monkeypatch) -> None:
    # The C-NH4 single-source PROOF: the script must call the SHARED
    # write_research_health_artifact symbol -- a private duplicate copy would NOT
    # invoke it -> the spy records zero calls -> this FAILS. (An artifact-equality
    # comparison cannot distinguish that; both copies emit the same bytes.)
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)  # exports_root = artifact.parent.parent = tmp_path

    import swing.monitoring.research_health as rh

    calls: list[tuple] = []
    real_writer = rh.write_research_health_artifact

    def _spy(status, out_path=None):
        calls.append((status, out_path))
        return real_writer(status, out_path=out_path)

    monkeypatch.setattr(rh, "write_research_health_artifact", _spy)

    mod = _load_script_module()
    rc = mod.main(["--db", str(db)])
    assert rc == 0
    assert len(calls) == 1, f"expected exactly one shared-writer call, got {len(calls)}"
    status, out_path = calls[0]
    assert status.to_dict()["monitor"] == "research_measurement"
    assert out_path == artifact
