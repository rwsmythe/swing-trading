"""The 7 per-check helpers (discriminating boundary arithmetic, grounded
fixtures). Seeds the real schema + real repos so the production read path is
exercised (anti-drift); plants legacy NaN rows by writing the ohlc_today_json
text directly (the production write barrier rejects NaN -- the DEFECT rows
predate that barrier).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.monitoring.research_health import (
    ResearchHealthCheck,
    _check_excluded_reason_breakdown,
    _check_temporal_log_finiteness,
    _read_newest_manifest,
)

_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'


def _schema_conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    return conn


def _seed_detection(
    conn: sqlite3.Connection,
    *,
    ticker: str = "AAA",
    detection_date: str = "2026-06-05",
    data_asof_date: str = "2026-06-04",
) -> int:
    det = PatternDetectionEvent(
        detection_id=None,
        ticker=ticker,
        detection_date=detection_date,
        data_asof_date=data_asof_date,
        pattern_class="vcp",
        structural_anchors_json="{}",
        composite_score=1.0,
        detector_version="t",
        source="synthetic",
        per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00",
    )
    det_id = insert_detection_event(conn, det)
    conn.commit()
    return det_id


def _seed_observation(
    conn: sqlite3.Connection,
    det_id: int,
    *,
    observation_date: str,
    ohlc_today_json: str = _FINITE_OHLC,
    status: str = "pending",
    sessions_since_detection: int = 1,
) -> None:
    obs = PatternForwardObservation(
        observation_id=None,
        detection_id=det_id,
        observation_date=observation_date,
        ohlc_today_json=ohlc_today_json,
        status=status,
        sessions_since_detection=sessions_since_detection,
        created_at="2026-06-05T00:00:00",
    )
    insert_observation(conn, obs)
    conn.commit()


def _only(checks: list[ResearchHealthCheck], key: str) -> ResearchHealthCheck:
    matches = [c for c in checks if c.key == key]
    assert len(matches) == 1, f"expected exactly one {key}, got {len(matches)}"
    return matches[0]


def _write_manifest(
    exports_root: Path,
    *,
    dir_name: str,
    funnel: dict | None = None,
    raw_text: str | None = None,
    omit_manifest: bool = False,
) -> Path:
    """Build a tmp shadow-expectancy-*/manifest.json from the REAL shape
    (funnel.detection_level.unique_signals + funnel.per_hypothesis.<H>.excluded).
    `raw_text` writes the file verbatim (malformed-JSON tests); `omit_manifest`
    creates the dir WITHOUT a manifest.json (the crashed-mid-write run)."""
    run_dir = exports_root / dir_name
    run_dir.mkdir(parents=True, exist_ok=True)
    if omit_manifest:
        return run_dir
    path = run_dir / "manifest.json"
    if raw_text is not None:
        path.write_text(raw_text, encoding="utf-8")
        return path
    manifest = {"harness_version": "0.1.0"}
    if funnel is not None:
        manifest["funnel"] = funnel
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _funnel(unique_signals: int, per_hypothesis: dict, unattributed=None) -> dict:
    return {
        "detection_level": {"unique_signals": unique_signals},
        "per_hypothesis": per_hypothesis,
        "unattributed": unattributed if unattributed is not None else {},
    }


# ---------------------------------------------------------------------------
# Task 2: _check_temporal_log_finiteness (the data-USABILITY authority)
# ---------------------------------------------------------------------------


def test_finiteness_green_when_all_finite(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    for d in ("2026-06-05", "2026-06-08", "2026-06-09"):
        _seed_observation(conn, det, observation_date=d)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "green"
    assert "0" in check.summary or "no non-finite" in check.summary.lower()


def test_finiteness_red_on_nan_close(tmp_path: Path) -> None:
    # THE motivating-defect test: O/H/L present, close NaN (the 06-10 shape).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, ticker="MSFT")
    _seed_observation(conn, det, observation_date="2026-06-05")
    _seed_observation(conn, det, observation_date="2026-06-08")
    nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    assert json.loads(nan_json)["close"] != json.loads(nan_json)["close"]  # NaN
    _seed_observation(conn, det, observation_date="2026-06-09", ohlc_today_json=nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"
    assert "1" in check.summary  # exactly 1 non-finite of 3
    assert "MSFT" in (check.detail or "")
    assert "2026-06-09" in (check.detail or "")


def test_finiteness_red_on_none_value(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    null_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": null, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date="2026-06-05", ohlc_today_json=null_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"  # NOT a TypeError crash


def test_finiteness_red_on_inf(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    inf_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": Infinity, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date="2026-06-05", ohlc_today_json=inf_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"


def test_finiteness_red_on_missing_key(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    missing_json = '{"open": 1.0, "high": 2.0, "low": 0.5, ' \
        '"volume": 100.0, "provider": "yfinance"}'  # no close
    _seed_observation(conn, det, observation_date="2026-06-05",
                      ohlc_today_json=missing_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"


def test_finiteness_green_when_empty_table(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)  # schema present, 0 observations
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "green"
    assert "observations yet" in check.summary.lower() or "no " in check.summary.lower()


def test_finiteness_yellow_when_missing_table(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")  # NO pattern_forward_observations table
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "yellow"
    assert "unavailable" in check.summary.lower() or "schema" in check.summary.lower()


def test_finiteness_volume_nan_is_exempt(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    vol_nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
        '"volume": NaN, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date="2026-06-05",
                      ohlc_today_json=vol_nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "green"  # Volume EXEMPT (Arc-8)


# ---------------------------------------------------------------------------
# Task 3: _check_excluded_reason_breakdown (read the manifest; never recompute)
# ---------------------------------------------------------------------------


def test_excluded_green_when_no_manifest(tmp_path: Path) -> None:
    # No shadow-expectancy-* dir -> ("absent", None) -> green/n-a.
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"
    assert "n/a" in check.summary.lower()


def test_excluded_green_when_under_threshold(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 5}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"  # 5/100 = 5% < 10%


def test_excluded_yellow_at_threshold(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 15}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"  # 15% (>10, <=25)


def test_excluded_red_over_threshold(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 30}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "red"  # 30% > 25


def test_excluded_sums_across_hypotheses(tmp_path: Path) -> None:
    # 8 + 8 summed across hypotheses = 16/100 = 16% -> yellow. A single-hypothesis
    # read sees 8% -> green (wrong).
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        funnel=_funnel(100, {
            "H1": {"excluded": {"missing_observations": 8}},
            "H2": {"excluded": {"missing_observations": 8}},
        }))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_green_when_zero_signals(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(0, {"H": {"excluded": {"invalid_ohlc": 5}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"  # no div-by-zero
    assert "n/a" in check.summary.lower()


def test_excluded_green_when_no_hypotheses(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        funnel=_funnel(42, {}, unattributed={"matched_no_hypothesis": 42}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"  # per_hypothesis={} -> 0 excluded


def test_excluded_yellow_when_newest_manifest_corrupt(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    raw_text="{not valid json")
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"  # corrupt newest, NOT green/n-a
    assert "unreadable" in check.summary.lower() or "corrupt" in check.summary.lower()


def test_excluded_green_when_no_dir_at_all(tmp_path: Path) -> None:
    # absent stays n-a; pairs with the corrupt test to pin the distinction.
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"


def test_excluded_yellow_when_newest_manifest_shape_drifted(tmp_path: Path) -> None:
    # valid JSON + a dict but MISSING the funnel schema -> corrupt.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    raw_text=json.dumps({"harness_version": "0.1.0"}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_yellow_when_newest_dir_missing_manifest(tmp_path: Path) -> None:
    # a NEWEST dir with NO manifest.json inside (crashed-mid-write) -> corrupt.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    omit_manifest=True)
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"  # NOT green/absent


def test_read_newest_manifest_picks_newest_by_dir_name(tmp_path: Path) -> None:
    # older valid manifest + newest dir corrupt -> the reader returns the NEWEST
    # (corrupt) state, not the older valid one.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260101T000000Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 1}}}))
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    raw_text="{bad")
    state, payload = _read_newest_manifest(tmp_path)
    assert state == "corrupt"
    assert payload is None
