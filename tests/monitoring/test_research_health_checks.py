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
    _check_candidate_completeness,
    _check_coverage_gaps,
    _check_drumbeat_liveness,
    _check_excluded_reason_breakdown,
    _check_structural_integrity,
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


# ---------------------------------------------------------------------------
# Task 4a: _check_coverage_gaps (NYSE-aware observation holes incl. missing tail)
# ---------------------------------------------------------------------------

# Frozen clock: a Sunday, so last_completed_session(NOW) == Fri 2026-06-12.
_NOW = datetime(2026, 6, 14, 12, 0, 0)
# NYSE sessions 2026-06-05..2026-06-12: Fri, Mon, Tue, Wed, Thu, Fri (06-06/07
# weekend excluded).
_SESSIONS = ("2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10",
             "2026-06-11", "2026-06-12")


def test_coverage_green_when_contiguous(tmp_path: Path) -> None:
    # OPEN mature detection with obs on EVERY NYSE session up to last_completed;
    # the weekend (06-06/07) is NOT a gap (calendar-aware).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    for d in _SESSIONS:
        _seed_observation(conn, det, observation_date=d, status="pending")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "green"


def test_coverage_yellow_on_one_hole(tmp_path: Path) -> None:
    # TERMINAL detection (upper bound = max_obs) with an INTERIOR hole: obs on
    # 06-05, 06-08, 06-10 -- skips the NYSE session 06-09 -> 1 missing.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    _seed_observation(conn, det, observation_date="2026-06-05", status="pending")
    _seed_observation(conn, det, observation_date="2026-06-08", status="pending")
    _seed_observation(conn, det, observation_date="2026-06-10", status="invalidated")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "yellow"  # 1 hole (06-09)


def test_coverage_red_on_many_holes(tmp_path: Path) -> None:
    # An OPEN mature detection with a single obs far in the past -> the whole
    # tail (06-08..06-12 etc) is missing -> > _COVERAGE_RED_GAPS.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-05-01")
    _seed_observation(conn, det, observation_date="2026-05-04", status="pending")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "red"


def test_coverage_green_when_no_mature_detections(tmp_path: Path) -> None:
    # data_asof_date == last_completed_session -> NOT mature (no tradable session
    # since its cutoff).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-12")
    _seed_observation(conn, det, observation_date="2026-06-12", status="pending")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "green"
    assert "n/a" in check.summary.lower() or "0" in check.summary


def test_coverage_yellow_on_missing_tail_for_open_detection(tmp_path: Path) -> None:
    # OPEN mature detection, CONTIGUOUS obs that STOP 2 NYSE sessions before
    # last_completed (06-12): obs through 06-10 -> 06-11 + 06-12 missing tail.
    # An interior-only impl sees 0 holes -> green (the bug). The maturity-boundary
    # impl counts the 2 tail sessions.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    for d in ("2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"):
        _seed_observation(conn, det, observation_date=d, status="triggered_open")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status in ("yellow", "red")  # 2 tail gaps >= 1


def test_coverage_green_on_terminal_detection_stopped_early(tmp_path: Path) -> None:
    # TERMINAL (invalidated) detection whose newest obs is well before
    # last_completed -> green (it legitimately stopped; NO tail expected).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    _seed_observation(conn, det, observation_date="2026-06-05", status="pending")
    _seed_observation(conn, det, observation_date="2026-06-08", status="invalidated")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "green"  # contiguous + terminal -> no tail expected


def test_coverage_yellow_when_missing_table(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "yellow"


# ---------------------------------------------------------------------------
# Task 4b: _check_structural_integrity (orphans + look-ahead)
# ---------------------------------------------------------------------------


def test_structural_green_when_clean(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, detection_date="2026-06-05", data_asof_date="2026-06-04")
    _seed_observation(conn, det, observation_date="2026-06-05", status="pending")
    _seed_observation(conn, det, observation_date="2026-06-08", status="pending")
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "green"


def test_structural_red_on_look_ahead(tmp_path: Path) -> None:
    # first obs (06-09) precedes detection_date (06-10) -> look-ahead.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, detection_date="2026-06-10", data_asof_date="2026-06-09")
    _seed_observation(conn, det, observation_date="2026-06-09", status="pending")
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "red"
    assert "look" in check.summary.lower() or "ahead" in check.summary.lower()


def test_structural_green_on_obs_equal_detection_date(tmp_path: Path) -> None:
    # first obs == detection_date -> NOT a violation (`<` is strict).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, detection_date="2026-06-10", data_asof_date="2026-06-09")
    _seed_observation(conn, det, observation_date="2026-06-10", status="pending")
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "green"


def test_structural_red_on_orphan(tmp_path: Path) -> None:
    # FK ON DELETE RESTRICT + NOT NULL blocks a normal orphan insert; seed with
    # FK off (the migration runner runs FK off too) to exercise the probe.
    conn = _schema_conn(tmp_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO pattern_forward_observations "
        "(detection_id, observation_date, ohlc_today_json, status, "
        "sessions_since_detection, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (99999, "2026-06-05", _FINITE_OHLC, "pending", 1, "2026-06-05T00:00:00"),
    )
    conn.commit()
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "red"
    assert "orphan" in check.summary.lower()


def test_structural_yellow_when_missing_table(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "yellow"


# ---------------------------------------------------------------------------
# Task 5a: _check_drumbeat_liveness (artifact age + total_unattributed)
# ---------------------------------------------------------------------------


def _now_utc_for(now_naive_local: datetime) -> datetime:
    """The aggregator converts naive-Hawaii-local now -> UTC by attaching
    Pacific/Honolulu. Mirror that to compute dir timestamps relative to `now`."""
    from datetime import UTC
    from zoneinfo import ZoneInfo
    return now_naive_local.replace(tzinfo=ZoneInfo("Pacific/Honolulu")).astimezone(UTC)


def _dir_name_days_before(now_naive_local: datetime, days: int) -> str:
    from datetime import timedelta
    ts = _now_utc_for(now_naive_local) - timedelta(days=days)
    return "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"


def test_drumbeat_green_when_fresh_and_attributed(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                    funnel=_funnel(100, {}, unattributed={}))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "green"


def test_drumbeat_yellow_when_stale(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 5),
                    funnel=_funnel(100, {}, unattributed={}))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "yellow"  # 5 days (>4, <=8)


def test_drumbeat_red_when_very_stale(tmp_path: Path) -> None:
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 9),
                    funnel=_funnel(100, {}, unattributed={}))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "red"  # 9 days (>8)


def test_drumbeat_red_when_no_artifacts(tmp_path: Path) -> None:
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "red"
    assert "never" in check.summary.lower() or "no " in check.summary.lower()


def test_drumbeat_yellow_when_unattributed_nonzero(tmp_path: Path) -> None:
    # FRESH (1 day) but total_unattributed=42 -> yellow (funnel-honesty escalates
    # a fresh-but-dishonest run; the worse-of of age-green and unattributed-yellow).
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                    funnel=_funnel(100, {}, unattributed={"matched_no_hypothesis": 42}))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "yellow"


def test_drumbeat_age_uses_injected_now(tmp_path: Path) -> None:
    # Two different injected now values produce different colors deterministically.
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                    funnel=_funnel(100, {}, unattributed={}))
    fresh = _check_drumbeat_liveness(exports_root=tmp_path, now=_NOW)[0]
    from datetime import timedelta
    much_later = _NOW + timedelta(days=10)
    stale = _check_drumbeat_liveness(exports_root=tmp_path, now=much_later)[0]
    assert fresh.status == "green"
    assert stale.status in ("yellow", "red")  # 11 days old vs much_later


def test_drumbeat_yellow_when_newest_manifest_corrupt(tmp_path: Path) -> None:
    # FRESH dir (age->green via the dir-name regex) but a malformed manifest ->
    # at-least yellow (unattributed unknown; a corrupt newest is surfaced).
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                    raw_text="{not valid json")
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status in ("yellow", "red")


# ---------------------------------------------------------------------------
# Task 5b: _check_candidate_completeness (sentinel-filtered null pivots + errors)
# ---------------------------------------------------------------------------


def _seed_eval_run(conn: sqlite3.Connection, *, error_count: int = 0) -> int:
    cur = conn.execute(
        "INSERT INTO evaluation_runs (run_ts, data_asof_date, action_session_date,"
        " tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count,"
        " error_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-06-12T00:00:00", "2026-06-12", "2026-06-15", 1, 0, 0, 0, 0,
         error_count),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_candidate(
    conn: sqlite3.Connection, run_id: int, *, ticker: str, bucket: str,
    pivot: float | None,
) -> None:
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, pivot, rs_method)"
        " VALUES (?, ?, ?, ?, ?)",
        (run_id, ticker, bucket, pivot, "universe"),
    )
    conn.commit()


def test_candidate_green_when_complete(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    run = _seed_eval_run(conn)
    _seed_candidate(conn, run, ticker="AAA", bucket="aplus", pivot=10.0)
    _seed_candidate(conn, run, ticker="BBB", bucket="watch", pivot=20.0)
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "green"


def test_candidate_red_on_null_actionable_pivot(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    run = _seed_eval_run(conn)
    _seed_candidate(conn, run, ticker="WWW", bucket="watch", pivot=None)
    # an excluded null pivot in the SAME run must NOT contribute:
    _seed_candidate(conn, run, ticker="XXX", bucket="excluded", pivot=None)
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "red"


def test_candidate_green_when_null_pivot_only_in_sentinel_buckets(tmp_path: Path) -> None:
    # THE gotcha-#25 test: nulls ONLY in error/excluded (the LIVE-DB shape) -> green.
    conn = _schema_conn(tmp_path)
    run = _seed_eval_run(conn)
    _seed_candidate(conn, run, ticker="AAA", bucket="aplus", pivot=10.0)
    _seed_candidate(conn, run, ticker="ERR", bucket="error", pivot=None)
    _seed_candidate(conn, run, ticker="EXC", bucket="excluded", pivot=None)
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "green"


def test_candidate_yellow_on_error_bucket(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    run = _seed_eval_run(conn)
    for i in range(10):  # 10 error-bucket (>5, <=25)
        _seed_candidate(conn, run, ticker=f"E{i}", bucket="error", pivot=None)
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "yellow"


def test_candidate_red_on_error_spike(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    run = _seed_eval_run(conn)
    for i in range(30):  # 30 error-bucket (>25)
        _seed_candidate(conn, run, ticker=f"E{i}", bucket="error", pivot=None)
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "red"


def test_candidate_green_when_no_eval_run(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)  # no evaluation_runs row
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "green"
    assert "n/a" in check.summary.lower()


def test_candidate_yellow_when_missing_table(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    check = _only(_check_candidate_completeness(conn), "candidate_completeness")
    assert check.status == "yellow"


# Shared 3-state manifest matrix (Codex R4 MAJOR #3): BOTH manifest-consuming
# checks classify all 3 states consistently.
@pytest.mark.parametrize(
    "state",
    ["no_dir", "dir_without_manifest", "dir_with_malformed_manifest"],
)
def test_manifest_three_state_matrix_excluded_and_drumbeat(
    tmp_path: Path, state: str,
) -> None:
    if state == "no_dir":
        pass  # empty tmp_path
    elif state == "dir_without_manifest":
        _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                        omit_manifest=True)
    else:
        _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                        raw_text="{bad json")
    excluded = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    drumbeat = _only(
        _check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
        "drumbeat_liveness")
    if state == "no_dir":
        assert excluded.status == "green"  # absent -> n-a
        assert drumbeat.status == "red"    # never ran
    else:
        assert excluded.status == "yellow"  # corrupt
        # the dir is FRESH (age green) but the manifest content is corrupt:
        assert drumbeat.status in ("yellow", "red")
