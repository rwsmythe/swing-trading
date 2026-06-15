"""Task 8 -- scripts/research_health.py probe surface (ASCII / --json / exit
code / ATOMIC latest.json write / subprocess ASCII-bytes guard).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = REPO_ROOT / "scripts" / "research_health.py"
_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "_research_health_script", _SCRIPT_PATH)
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
    # one TERMINAL (invalidated) detection so coverage expects no tail vs the
    # real wall clock -- keeps the script test clock-independent.
    insert_observation(conn, PatternForwardObservation(
        observation_id=None, detection_id=det, observation_date="2026-06-05",
        ohlc_today_json=_FINITE_OHLC, status="invalidated",
        sessions_since_detection=1, created_at="2026-06-05T00:00:00"))
    conn.commit()
    conn.close()


# FIX 1 (18-D): finiteness #1 reds ONLY on a non-finite obs STRICTLY AFTER the
# 2026-06-13 18-A baseline cutoff. The red-DB seed dates its NaN obs after that
# barrier (a genuine post-fix regression) so the probe goes red as intended.
_POST_CUTOFF_DATE = "2026-06-16"  # strictly after the 2026-06-13 baseline


def _seed_red_db(db_path: Path) -> None:
    conn = ensure_schema(db_path)
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="ZZZ", detection_date=_POST_CUTOFF_DATE,
        data_asof_date=_POST_CUTOFF_DATE, pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00"))
    conn.execute(
        "INSERT INTO pattern_forward_observations "
        "(detection_id, observation_date, ohlc_today_json, status, "
        "sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, _POST_CUTOFF_DATE,
         '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, '
         '"volume": 100.0, "provider": "yfinance"}', "invalidated", 1,
         "2026-06-05T00:00:00"))
    conn.commit()
    conn.close()


def _fresh_manifest(exports_root: Path) -> None:
    """A fresh shadow-expectancy-* dir ~1h before now (UTC) so drumbeat is green
    + excluded under threshold (relative to the real wall clock the script uses).
    """
    ts = datetime.now(UTC) - timedelta(hours=1)
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    run_dir = exports_root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 1}}},
        "unattributed": {},
    }}), encoding="utf-8")


def test_script_all_clear_exit_zero(tmp_path, monkeypatch, capsys) -> None:
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)  # exports_root = artifact.parent.parent = tmp_path
    mod = _load_script_module()
    rc = mod.main(["--db", str(db)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "all clear" in out.lower()


def test_script_attention_exit_one(tmp_path, monkeypatch, capsys) -> None:
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)
    mod = _load_script_module()
    rc = mod.main(["--db", str(db)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ATTENTION" in out
    assert "temporal_log_finiteness" in out


def test_script_json_flag(tmp_path, monkeypatch, capsys) -> None:
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)
    mod = _load_script_module()
    rc = mod.main(["--db", str(db), "--json"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["monitor"] == "research_measurement"
    assert parsed["overall"] in {"green", "yellow", "red"}
    assert isinstance(parsed["checks"], list)
    assert len(parsed["checks"]) == 7
    assert rc == 0  # --json always exits 0 even when red


def test_script_writes_latest_json_atomic_and_validates_through_reader(
    tmp_path, monkeypatch,
) -> None:
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(tmp_path)
    mod = _load_script_module()
    from swing.monitoring import stoplights
    for flag in ([], ["--json"]):
        # remove any prior file so each path must write afresh
        if artifact.exists():
            artifact.unlink()
        mod.main(["--db", str(db), *flag])
        assert artifact.exists(), f"latest.json not written for flag {flag}"
        parsed = json.loads(artifact.read_text(encoding="utf-8"))
        assert parsed["monitor"] == "research_measurement"
        # no leftover .tmp file
        tmps = list((tmp_path / "health").glob("*.tmp"))
        assert not tmps, f"leftover tmp files for flag {flag}: {tmps}"
        # round-trip through the LIVE 18-F reader -> validates (not grey)
        validated = stoplights.read_validated_research_envelope()
        assert validated is not None, f"reader greyed the {flag} artifact"


def test_script_creates_health_dir_when_absent(tmp_path, monkeypatch) -> None:
    db = tmp_path / "swing.db"
    _seed_green_db(db)
    artifact = tmp_path / "nested" / "health" / "latest.json"
    assert not artifact.parent.exists()
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    _fresh_manifest(artifact.parent.parent)  # exports_root = .../nested
    mod = _load_script_module()
    mod.main(["--db", str(db)])
    assert artifact.parent.exists()
    assert artifact.exists()


def test_script_unreadable_db_exits_one_without_write(tmp_path, monkeypatch, capsys) -> None:
    # Codex R3 MAJOR #5: a corrupt/non-SQLite file at --db -> concise error + exit
    # 1, NO traceback, NO artifact write (does not overwrite a prior artifact).
    bad_db = tmp_path / "swing.db"
    bad_db.write_bytes(b"this is not a sqlite database at all")
    artifact = tmp_path / "health" / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    mod = _load_script_module()
    rc = mod.main(["--db", str(bad_db)])
    captured = capsys.readouterr()
    assert rc == 1
    # Codex R9 MINOR: operational errors go to STDERR (not stdout / --json output)
    assert "unreadable" in captured.err.lower()
    assert "unreadable" not in captured.out.lower()
    assert not artifact.exists()  # no synthetic envelope written


def test_script_output_is_ascii(tmp_path) -> None:
    db = tmp_path / "swing.db"
    _seed_red_db(db)
    _fresh_manifest(tmp_path)  # exports_root = (out).parent.parent = tmp_path
    out_path = tmp_path / "health" / "latest.json"
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--db", str(db),
         "--out", str(out_path)],
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    # stdout must decode as ASCII (the cp1252 gotcha; capsys is insufficient).
    result.stdout.decode("ascii")
    assert out_path.exists()  # landed at the tmp path, NOT the live path
