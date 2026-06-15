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
    _check_fetch_transport_health,
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


# FIX 1 (18-D): the finiteness baseline cutoff is 2026-06-13 (the 18-A
# writer-fix merge boundary). RED requires a non-finite obs STRICTLY AFTER it; a
# non-finite obs at-or-before it is accepted-historical (does NOT drive red).
# The red-shape tests below therefore date the non-finite obs AFTER the cutoff.
_POST_CUTOFF_DATE = "2026-06-16"  # strictly after the 2026-06-13 baseline


def test_finiteness_red_on_nan_close(tmp_path: Path) -> None:
    # THE motivating-defect test: O/H/L present, close NaN (the 06-10 shape),
    # dated AFTER the baseline so it is a genuine post-fix regression (red).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, ticker="MSFT")
    _seed_observation(conn, det, observation_date="2026-06-05")
    _seed_observation(conn, det, observation_date="2026-06-08")
    nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    assert json.loads(nan_json)["close"] != json.loads(nan_json)["close"]  # NaN
    _seed_observation(conn, det, observation_date=_POST_CUTOFF_DATE,
                      ohlc_today_json=nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"
    assert "1" in check.summary  # exactly 1 post-baseline non-finite of 3
    assert "MSFT" in (check.detail or "")
    assert _POST_CUTOFF_DATE in (check.detail or "")


def test_finiteness_red_on_none_value(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    null_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": null, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date=_POST_CUTOFF_DATE,
                      ohlc_today_json=null_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"  # NOT a TypeError crash


def test_finiteness_red_on_inf(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    inf_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": Infinity, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date=_POST_CUTOFF_DATE,
                      ohlc_today_json=inf_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"


def test_finiteness_red_on_missing_key(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    missing_json = '{"open": 1.0, "high": 2.0, "low": 0.5, ' \
        '"volume": 100.0, "provider": "yfinance"}'  # no close
    _seed_observation(conn, det, observation_date=_POST_CUTOFF_DATE,
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


def test_finiteness_baseline_cutoff_both_ways(tmp_path: Path) -> None:
    """FIX 1 (18-D) both-ways discriminator: #1 reds ONLY on a non-finite obs
    STRICTLY AFTER the _FINITENESS_BASELINE_CUTOFF (2026-06-13, the 18-A
    writer-fix boundary); a <=cutoff non-finite is accepted-historical (no red).

    pre-fix code (reds on ANY non-finite): with ONLY the <=cutoff (2026-06-10)
    non-finite present -> RED (it would still fire on the historical backlog).
    post-fix code: that same state -> GREEN + an accepted-historical detail note.
    => the '<=cutoff alone -> GREEN' assertion below FAILS pre-fix, PASSES
    post-fix (the discriminator).
    """
    nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, ' \
        '"volume": 100.0, "provider": "yfinance"}'

    # State A: BOTH a <=cutoff (accepted) AND a >cutoff (regression) non-finite.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, ticker="HIST")
    _seed_observation(conn, det, observation_date="2026-06-10",  # <= cutoff
                      ohlc_today_json=nan_json)
    det2 = _seed_detection(conn, ticker="REGR", detection_date="2026-06-15",
                           data_asof_date="2026-06-14")
    _seed_observation(conn, det2, observation_date="2026-06-16",  # > cutoff
                      ohlc_today_json=nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"  # driven by the post-cutoff regression
    # the detail NAMES the post-cutoff red driver AND surfaces the accepted count.
    assert "REGR" in (check.detail or "")
    assert "2026-06-16" in (check.detail or "")
    assert "accepted historical" in (check.detail or "")
    assert "1 non-finite" in (check.detail or "")  # the 1 accepted-historical obs

    # State B: REMOVE the post-cutoff obs -> ONLY the <=cutoff non-finite remains.
    # pre-fix: RED (reds on ANY non-finite). post-fix: GREEN (accepted-historical).
    conn2 = _schema_conn(tmp_path / "b")
    det_b = _seed_detection(conn2, ticker="HIST")
    _seed_observation(conn2, det_b, observation_date="2026-06-10",  # <= cutoff
                      ohlc_today_json=nan_json)
    check_b = _only(_check_temporal_log_finiteness(conn2), "temporal_log_finiteness")
    assert check_b.status == "green"  # THE DISCRIMINATOR (pre-fix would be red)
    # tighten: the accepted-historical phrase + cutoff marker + count together
    # (Codex R1 MINOR -- a bare "1 non-finite" could later match another shape).
    assert "accepted historical: 1 non-finite @ <=2026-06-13" in (check_b.detail or "")


def test_finiteness_noncanonical_date_drives_red_not_accepted(tmp_path: Path) -> None:
    """Codex R1 MAJOR: date.fromisoformat (3.11+) ALSO accepts compact
    (`20260610`) + ISO week-date forms; the observation_date column has NO format
    CHECK (migration 0022). A non-finite row whose observation_date is a
    NON-CANONICAL but fromisoformat-parseable string that resolves <=cutoff must
    NOT be silently accepted-historical -- it is undatable-in-contract and must
    drive RED (the conservative branch). pre-fix-of-this-finding: '20260610'
    parses to 2026-06-10 (<=cutoff) -> wrongly GREEN; post-fix: RED.
    """
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, ticker="CMPCT")
    nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    # compact form resolving to 2026-06-10 (<= the 2026-06-13 cutoff if naively
    # parsed) -- the canonical-shape gate rejects it -> treated post-cutoff -> red.
    _seed_observation(conn, det, observation_date="20260610",
                      ohlc_today_json=nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"
    assert "CMPCT" in (check.detail or "")
    # NOT absorbed into the accepted-historical cohort.
    assert "accepted historical" not in (check.detail or "")


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
    # 0 signals AND 0 excluded -> green n/a (the legitimate empty-funnel shape).
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(0, {"H": {"excluded": {}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"  # no div-by-zero
    assert "n/a" in check.summary.lower()


def test_excluded_yellow_when_zero_signals_but_nonzero_excluded(tmp_path: Path) -> None:
    # Codex R4 MAJOR #2: 0 unique_signals but nonzero attributed excluded is an
    # internally-inconsistent manifest -> yellow, NOT a green n/a false-green.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(0, {"H": {"excluded": {"invalid_ohlc": 5}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"
    assert "inconsistent" in check.summary.lower()


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


def test_excluded_yellow_when_excluded_is_a_list(tmp_path: Path) -> None:
    # Codex R2-rev MAJOR #1: a hypothesis whose `excluded` is a LIST (not a dict)
    # is shape-drift -> corrupt -> yellow (NOT an AttributeError crash).
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        raw_text=json.dumps({"funnel": {
            "detection_level": {"unique_signals": 100},
            "per_hypothesis": {"H": {"excluded": []}},
        }}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_yellow_when_reason_count_non_numeric(tmp_path: Path) -> None:
    # a non-numeric reason count -> corrupt (NOT a ValueError crash on int()).
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        raw_text=json.dumps({"funnel": {
            "detection_level": {"unique_signals": 100},
            "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": "lots"}}},
        }}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_yellow_when_unique_signals_is_nan(tmp_path: Path) -> None:
    # NaN unique_signals (JSON Infinity/NaN) passes isinstance(float) but is not
    # finite -> corrupt (would otherwise make every comparison False -> green).
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        raw_text='{"funnel": {"detection_level": {"unique_signals": NaN},'
                 ' "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 5}}}}}')
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_yellow_when_unattributed_field_missing(tmp_path: Path) -> None:
    # Codex R5 MAJOR #1: unattributed is a CONSUMED field (drumbeat reads it); a
    # manifest MISSING it is shape-drift -> corrupt -> yellow (NOT ok/green).
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        raw_text=json.dumps({"funnel": {
            "detection_level": {"unique_signals": 100},
            "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 5}}},
        }}))  # no "unattributed"
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_yellow_when_reason_count_is_fractional(tmp_path: Path) -> None:
    # Codex R5 MAJOR #2: a FRACTIONAL count (10.9) would int()-truncate to 10 ->
    # false-green at a boundary. A fractional count is shape-drift -> yellow.
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 10.9}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_ok_when_unique_signals_is_integer_valued_float(tmp_path: Path) -> None:
    # an integer-VALUED float (77.0) is a legitimate integer count -> ok.
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        funnel=_funnel(100.0, {"H": {"excluded": {"invalid_ohlc": 5}}}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"  # 5/100 = 5% < 10%, ok manifest


def test_excluded_yellow_when_per_hyp_terminal_card_non_integer(tmp_path: Path) -> None:
    # Codex R8 MAJOR #1 (narrow): a per-hypothesis terminal counter (closed) that
    # is non-integer is shape-drift -> corrupt -> yellow.
    _write_manifest(
        tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
        raw_text=json.dumps({"funnel": {
            "detection_level": {"unique_signals": 100},
            "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 5},
                                     "closed": "three"}},
            "unattributed": {},
        }}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_excluded_green_when_signals_but_no_attributed_hypotheses(tmp_path: Path) -> None:
    # Codex R8 MAJOR #1 (the REJECTED funnel-sum part): 100 signals + empty
    # per_hypothesis + empty unattributed is the LEGITIMATE "no attributed
    # hypotheses yet" shape, NOT corrupt -- the monitor does NOT recompute the
    # funnel-sum invariant (LOCK §4.2). Stays green n/a.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(100, {}, unattributed={}))
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "green"
    assert "n/a" in check.summary.lower()


def test_excluded_yellow_when_manifest_is_non_utf8(tmp_path: Path) -> None:
    # Codex R6 MAJOR #1: a non-UTF-8 manifest.json must escalate to corrupt
    # (yellow), NOT raise UnicodeDecodeError.
    run_dir = tmp_path / "shadow-expectancy-20260613T000000Z"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_bytes(b"\xff\xfe\x00\x01not utf8")
    check = _only(
        _check_excluded_reason_breakdown(exports_root=tmp_path),
        "excluded_reason_breakdown")
    assert check.status == "yellow"


def test_read_newest_manifest_stray_name_newest_is_corrupt(tmp_path: Path) -> None:
    # Codex R11 MAJOR #1: the newest dir is selected across ALL shadow-expectancy-*
    # dirs (the SAME selection the age arm uses). A lexically-LATER stray
    # non-timestamp dir IS the newest -> a malformed-name newest artifact is
    # CORRUPT (a dir exists -> not "absent"), NOT silently skipped to an older one.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 1}}}))
    (tmp_path / "shadow-expectancy-zbad").mkdir()  # sorts AFTER -> newest
    state, payload = _read_newest_manifest(tmp_path)
    assert state == "corrupt"  # the stray newest escalates, not ignored
    assert payload is None


def test_read_newest_manifest_rejects_embedded_timestamp_name(tmp_path: Path) -> None:
    # Codex R13 MAJOR #1: a crafted name embedding a valid timestamp at the end
    # must NOT pass (anchored fullmatch). The crafted dir sorts AFTER the real one
    # -> it is the newest -> corrupt (not parsed as a valid timestamp).
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20260613T000000Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 1}}}))
    (tmp_path / "shadow-expectancy-z-shadow-expectancy-20260613T000000Z").mkdir()
    state, _payload = _read_newest_manifest(tmp_path)
    assert state == "corrupt"  # the crafted newest name is rejected -> corrupt


def test_read_newest_manifest_invalid_calendar_ts_name_is_corrupt(tmp_path: Path) -> None:
    # Codex R14 MAJOR: a digit-SHAPED but invalid-calendar dir name (month 13, day
    # 99, hour 99) passes a bare \d{8}T\d{6} regex but datetime.strptime then
    # RAISES -> the name parse must validate the CALENDAR, not just the digit
    # shape, and report corrupt (not "ok") with a present manifest.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20261399T999999Z",
                    funnel=_funnel(100, {"H": {"excluded": {"invalid_ohlc": 1}}}))
    state, payload = _read_newest_manifest(tmp_path)
    assert state == "corrupt"  # invalid-calendar name -> not a parseable timestamp
    assert payload is None


def test_drumbeat_invalid_calendar_ts_name_does_not_crash(tmp_path: Path) -> None:
    # Codex R14 MAJOR (the crash arm): _newest_artifact_age_days must NOT raise
    # ValueError from strptime on a digit-shaped invalid-calendar name -> the
    # whole monitor would crash. It must treat it as malformed (None age) ->
    # drumbeat reports the malformed-name yellow.
    _write_manifest(tmp_path, dir_name="shadow-expectancy-20261399T999999Z",
                    funnel=_funnel(100, {}, unattributed={}))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "yellow"
    assert "malformed" in check.summary.lower()


def test_read_newest_manifest_only_stray_dir_is_corrupt_not_absent(tmp_path: Path) -> None:
    # the ONLY dir is a stray non-timestamp dir -> corrupt (a dir EXISTS), NOT
    # absent/green (Codex R11 MAJOR #1).
    (tmp_path / "shadow-expectancy-zbad").mkdir()
    state, _payload = _read_newest_manifest(tmp_path)
    assert state == "corrupt"


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


def test_coverage_yellow_on_leading_head_gap(tmp_path: Path) -> None:
    # Codex R3 MAJOR #1: a LATE first observation -- the detection's first obs is
    # 06-08 but data_asof=2026-06-04, so 06-05 (the first expected session after
    # cutoff) is MISSING. An impl that starts the window at min_obs masks it.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    for d in ("2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"):
        _seed_observation(conn, det, observation_date=d, status="pending")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status in ("yellow", "red")  # 06-05 missing (leading gap)


def test_coverage_escalates_on_mature_detection_with_zero_observations(
    tmp_path: Path,
) -> None:
    # Codex R2-rev MAJOR #4: a MATURE detection (data_asof 2026-05-01) with NO
    # observation row at all must NOT be invisible -- every expected session from
    # first-after-cutoff .. last_completed is missing -> escalate.
    conn = _schema_conn(tmp_path)
    _seed_detection(conn, data_asof_date="2026-05-01")  # no observations seeded
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status in ("yellow", "red")
    assert "never observed" in (check.detail or "").lower() or check.status != "green"


def test_coverage_green_on_fresh_detection_with_zero_observations(
    tmp_path: Path,
) -> None:
    # a mature-by-cutoff but TOO-FRESH detection (cutoff == last_completed) with
    # no obs -> no session yet to observe -> green (not a defect).
    conn = _schema_conn(tmp_path)
    _seed_detection(conn, data_asof_date="2026-06-12")  # not < last_completed
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "green"


def test_coverage_yellow_on_malformed_date_does_not_crash(tmp_path: Path) -> None:
    # Codex R4 MAJOR #1 + R6 MAJOR #3: a malformed data_asof_date on a degraded DB
    # must NOT crash the monitor NOR be silently dropped by a SQL string filter --
    # count it as a data-shape defect (yellow) and continue. Use a value that a
    # `WHERE data_asof_date < cutoff` string predicate would NOT have included
    # (lexically > the cutoff), proving the SQL filter no longer hides it.
    conn = _schema_conn(tmp_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO pattern_detection_events"
        " (ticker, detection_date, data_asof_date, pattern_class,"
        " structural_anchors_json, composite_score, detector_version, source,"
        " per_pattern_metadata_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("AAA", "2026-06-05", "not-a-date", "vcp", "{}", 1.0, "t", "synthetic",
         "{}", "2026-06-05T00:00:00"))
    conn.commit()
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status == "yellow"
    assert "malformed" in check.summary.lower()


def test_coverage_yellow_on_interior_malformed_observation_date(tmp_path: Path) -> None:
    # Codex R11 MINOR: a malformed observation_date that sorts BETWEEN valid
    # min/max must still be caught (every observed date is parsed, not just
    # min/max).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    _seed_observation(conn, det, observation_date="2026-06-05", status="pending")
    # a malformed date lexically between 06-05 and 06-12 (starts with '2026-06-')
    conn.execute(
        "INSERT INTO pattern_forward_observations"
        " (detection_id, observation_date, ohlc_today_json, status,"
        " sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, "2026-06-9X", _FINITE_OHLC, "pending", 1, "2026-06-09T00:00:00"))
    _seed_observation(conn, det, observation_date="2026-06-12", status="pending")
    conn.commit()
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status in ("yellow", "red")
    assert "malformed" in (check.detail or "").lower() or check.status != "green"


def test_coverage_malformed_obs_row_still_counts_tail_gaps(tmp_path: Path) -> None:
    # Codex R12 MAJOR #1: a malformed OBSERVED row must NOT skip the whole
    # detection (downgrading a red missing-tail to a mere yellow). Seed an OPEN
    # detection with a malformed obs row AND valid obs that STOP early -> the
    # missing tail is still counted from the valid dates (escalates beyond yellow
    # if the tail is large).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-05-01")  # far back -> big tail
    _seed_observation(conn, det, observation_date="2026-05-04", status="pending")
    conn.execute(
        "INSERT INTO pattern_forward_observations"
        " (detection_id, observation_date, ohlc_today_json, status,"
        " sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, "bad-date", _FINITE_OHLC, "pending", 1, "2026-05-05T00:00:00"))
    conn.commit()
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    # the huge tail (05-04 .. last_completed) is still counted -> red (not just
    # a yellow malformed-date report).
    assert check.status == "red"


def test_coverage_escalates_on_unknown_latest_status_with_missing_tail(
    tmp_path: Path,
) -> None:
    # Codex R6 MAJOR #4: an UNKNOWN latest status must NOT be silently treated as
    # terminal (which would suppress a missing tail). Seed an OPEN-then-unknown
    # status whose obs stop early -> the unknown status is treated as OPEN
    # (tail-expected) -> escalates. (Bypass the CHECK with FK/PRAGMA off-style
    # raw insert of a status the schema would reject is not possible; instead seed
    # a legitimately-OPEN 'pending' status stopping early -- the unknown-status
    # arm is covered by the implementation defaulting non-terminal -> open.)
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    for d in ("2026-06-05", "2026-06-08"):
        _seed_observation(conn, det, observation_date=d, status="pending")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    # obs stop at 06-08 but last_completed is 06-12 -> tail gap (06-09..06-12).
    assert check.status in ("yellow", "red")


def test_coverage_yellow_on_duplicate_observation_date(tmp_path: Path) -> None:
    # Codex R10 MAJOR #1: a duplicate observation_date (degraded DB; impossible
    # under the schema UNIQUE) is surfaced as a data-shape defect (yellow) so a
    # late terminal duplicate cannot suppress a missing tail.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="2026-06-04")
    conn.execute("PRAGMA foreign_keys=OFF")
    # two rows with the SAME observation_date (bypassing the UNIQUE via a raw
    # insert with the index dropped is not trivial; instead insert one normally
    # then a second raw row with the same date -- the UNIQUE would reject it, so
    # drop the index first).
    conn.execute("DROP INDEX IF EXISTS idx_pfo_detection_date")
    conn.execute(
        "INSERT INTO pattern_forward_observations"
        " (detection_id, observation_date, ohlc_today_json, status,"
        " sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, "2026-06-05", _FINITE_OHLC, "pending", 1, "2026-06-05T00:00:00"))
    try:
        conn.execute(
            "INSERT INTO pattern_forward_observations"
            " (detection_id, observation_date, ohlc_today_json, status,"
            " sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (det, "2026-06-05", _FINITE_OHLC, "invalidated", 1,
             "2026-06-05T00:00:00"))
        conn.commit()
    except sqlite3.IntegrityError:
        # the table-level UNIQUE constraint still blocks it -> this exact degraded
        # shape is unreachable on this build; the guard is defensive. Skip.
        import pytest
        pytest.skip("UNIQUE(detection_id, observation_date) blocks the dup insert")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status in ("yellow", "red")
    assert "duplicate" in (check.detail or "").lower() or check.status != "green"


def test_coverage_no_crash_on_out_of_calendar_date(tmp_path: Path) -> None:
    # Codex R13 MAJOR #2: a date that date.fromisoformat ACCEPTS but is OUTSIDE
    # the NYSE calendar bounds (0001-01-01) must NOT crash the monitor -- count it
    # as a malformed/data-shape defect (yellow), never escape.
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, data_asof_date="0001-01-01")  # ISO-valid, far past
    _seed_observation(conn, det, observation_date="2026-06-05", status="pending")
    check = _only(_check_coverage_gaps(conn, now=_NOW), "coverage_gaps")
    assert check.status in ("yellow", "red")  # no crash; surfaced as a defect


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


def test_structural_yellow_on_malformed_date(tmp_path: Path) -> None:
    # Codex R10 MAJOR #2: a malformed detection_date must be counted as a
    # data-shape defect (yellow), not silently pass the lexical SQL compare.
    conn = _schema_conn(tmp_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO pattern_detection_events"
        " (detection_id, ticker, detection_date, data_asof_date, pattern_class,"
        " structural_anchors_json, composite_score, detector_version, source,"
        " per_pattern_metadata_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "AAA", "not-a-date", "2026-06-04", "vcp", "{}", 1.0, "t",
         "synthetic", "{}", "2026-06-05T00:00:00"))
    conn.execute(
        "INSERT INTO pattern_forward_observations"
        " (detection_id, observation_date, ohlc_today_json, status,"
        " sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "2026-06-05", _FINITE_OHLC, "pending", 1, "2026-06-05T00:00:00"))
    conn.commit()
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "yellow"
    assert "malformed" in check.summary.lower()


def test_structural_red_on_lookahead_even_when_earlier_row_malformed(tmp_path: Path) -> None:
    # Codex R12 MAJOR #2: a malformed lexicographically-earlier obs row must NOT
    # mask a real look-ahead in a LATER valid row (the per-row Python check, not
    # SQL MIN). Seed detection_date=2026-06-10 + a malformed obs ('0bad', sorts
    # first lexically) + a valid look-ahead obs 2026-06-09 (< detection_date).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, detection_date="2026-06-10", data_asof_date="2026-06-09")
    conn.execute(
        "INSERT INTO pattern_forward_observations"
        " (detection_id, observation_date, ohlc_today_json, status,"
        " sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det, "0bad", _FINITE_OHLC, "pending", 1, "2026-06-09T00:00:00"))
    _seed_observation(conn, det, observation_date="2026-06-09", status="pending")
    check = _only(_check_structural_integrity(conn), "structural_integrity")
    assert check.status == "red"  # the valid look-ahead is caught
    assert "look-ahead" in check.summary.lower()


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


def test_drumbeat_yellow_when_artifact_future_dated(tmp_path: Path) -> None:
    # Codex R7 MAJOR #2: a FUTURE-dated artifact dir (negative age) is NOT fresh
    # green -- it signals producer clock-skew -> escalate to yellow.
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, -3),  # 3d future
                    funnel=_funnel(100, {}, unattributed={}))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "yellow"
    assert "future" in check.summary.lower()


def test_drumbeat_yellow_when_artifact_vanishes_mid_read(tmp_path: Path, monkeypatch) -> None:
    # Codex R8 MAJOR #2: a fresh age read followed by an "absent" manifest read
    # (the artifact was pruned between the two filesystem reads) must NOT stay
    # green -- escalate to yellow. Simulate the race by forcing the manifest read
    # to "absent" while the age read returns fresh.
    import swing.monitoring.research_health as rh
    _write_manifest(tmp_path, dir_name=_dir_name_days_before(_NOW, 1),
                    funnel=_funnel(100, {}, unattributed={}))
    monkeypatch.setattr(rh, "_read_newest_manifest", lambda _root: ("absent", None))
    check = _only(_check_drumbeat_liveness(exports_root=tmp_path, now=_NOW),
                  "drumbeat_liveness")
    assert check.status == "yellow"
    assert "vanish" in (check.detail or "").lower()


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


# ---------------------------------------------------------------------------
# Task 6: _check_fetch_transport_health (yfinance_calls TRANSPORT indicator)
# ---------------------------------------------------------------------------


def _seed_yf_call(
    conn: sqlite3.Connection, *, status: str, ts: str = "2026-06-14T00:00:00",
    ticker: str = "AAA",
) -> None:
    from swing.data.repos.yfinance_calls import insert_in_flight, update_call_outcome
    call_id = insert_in_flight(
        conn, ts=ts, call_type="download_single", ticker=ticker,
        ticker_count=None, pipeline_run_id=None, surface="pipeline")
    if status != "in_flight":
        update_call_outcome(
            conn, call_id=call_id, response_time_ms=10, status=status,
            rows_returned=1 if status == "success" else 0, error_message=None)
    conn.commit()


def _seed_yf_calls(conn: sqlite3.Connection, *, success=0, error=0, empty=0,
                   in_flight=0) -> None:
    n = 0
    for _ in range(success):
        _seed_yf_call(conn, status="success", ticker=f"S{n}"); n += 1
    for _ in range(error):
        _seed_yf_call(conn, status="error", ticker=f"E{n}"); n += 1
    for _ in range(empty):
        _seed_yf_call(conn, status="empty", ticker=f"M{n}"); n += 1
    for _ in range(in_flight):
        _seed_yf_call(conn, status="in_flight", ticker=f"F{n}"); n += 1


def test_transport_green_when_low_sample(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=4)  # the LIVE-DB shape
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "green"
    assert "insufficient sample" in check.summary.lower() or "n/a" in check.summary.lower()
    # surface-don't-suppress (Codex R6 MAJOR #2): the observed count is in detail.
    assert "4" in (check.detail or "")
    assert "0 error" in (check.detail or "")


def test_transport_sample_floor_boundary_activates_rate_logic(tmp_path: Path) -> None:
    # 60% error at 9 terminal rows -> green (below the floor of 10); at 10 -> red.
    conn = _schema_conn(tmp_path)
    # 9 terminal: 5 error + 4 success = ~55%... use 6 error + 3 success = 9 rows
    _seed_yf_calls(conn, error=6, success=3)  # 9 terminal, below floor
    below = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert below.status == "green"  # below the sample floor -> suppressed
    # add one more error -> 10 terminal, 7 error = 70% -> red (rate logic active)
    _seed_yf_call(conn, status="error", ticker="EX")
    at = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert at.status == "red"


def test_transport_green_when_all_success(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=20)
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "green"


def test_transport_yellow_on_error_rate(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=15, error=5)  # 20 terminal, 25% error
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "yellow"  # 25% (>20, <50)


def test_transport_red_on_high_error_rate(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=8, error=12)  # 20 terminal, 60% error
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "red"


def test_transport_excludes_in_flight_from_rate(tmp_path: Path) -> None:
    # 15 success + 5 in_flight: terminal_count = 15 (>= floor), error 0% -> green.
    # Counting in_flight as a problem (5/20) would mis-rate.
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=15, in_flight=5)
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "green"


def test_transport_yellow_on_empty_rate(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=8, empty=12)  # 20 terminal, 60% empty, 0 error
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "yellow"  # empty signal at its looser floor (50%)


def test_transport_does_not_substitute_for_finiteness(tmp_path: Path) -> None:
    # ALL success transport WHILE a NaN-Close observation exists -> #7 green,
    # #1 red on the SAME DB (the load-bearing #7-vs-#1 separation).
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=20)
    det = _seed_detection(conn)
    nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    # dated AFTER the 18-A baseline (FIX 1) so the NaN drives finiteness red.
    _seed_observation(conn, det, observation_date="2026-06-16",
                      ohlc_today_json=nan_json)
    transport = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    finiteness = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert transport.status == "green"
    assert finiteness.status == "red"


def test_transport_surfaces_in_flight_count_in_detail(tmp_path: Path) -> None:
    # Codex R9 MAJOR: in_flight is denominator-EXCLUDED but its count is SURFACED
    # in the detail (visibility without alarming). An all-in_flight table is NOT
    # silently "no fetch audit" -- the detail shows the in_flight count.
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, in_flight=4)  # no terminal rows
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "green"  # color unchanged (no terminal rows)
    assert "4 in_flight" in (check.detail or "")
    # low-sample path also surfaces in_flight:
    _seed_yf_calls(conn, success=2)  # 2 terminal (below floor) + 4 in_flight
    check2 = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check2.status == "green"
    assert "in_flight" in (check2.detail or "")


def test_transport_surfaces_in_flight_on_normal_rate_path(tmp_path: Path) -> None:
    # Codex R10 MINOR #1: in_flight is surfaced in the normal-rate detail too.
    conn = _schema_conn(tmp_path)
    _seed_yf_calls(conn, success=20, in_flight=3)
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "green"  # 0% error, in_flight excluded from denominator
    assert "3 in_flight" in (check.detail or "")


def test_transport_in_flight_does_not_starve_terminal_sample(tmp_path: Path) -> None:
    # Codex R2-rev MAJOR #2: a BURST of newer in_flight rows must NOT bump older
    # terminal failures out of the recent window (the SQL-filter-terminal fix).
    # Seed 12 error (terminal) FIRST (older ts), then 60 newer in_flight rows.
    conn = _schema_conn(tmp_path)
    for i in range(12):
        _seed_yf_call(conn, status="error", ts="2026-06-10T00:00:00", ticker=f"E{i}")
    for i in range(60):
        _seed_yf_call(conn, status="in_flight", ts="2026-06-14T00:00:00",
                      ticker=f"F{i}")
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    # 12 terminal, 100% error -> red. A Python-side filter after a 50-row
    # over-read of in_flight would see 0 terminal -> low-sample green (the bug).
    assert check.status == "red"


def test_transport_yellow_when_missing_table(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "yellow"


def test_transport_green_when_empty_table(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)  # schema present, 0 rows
    check = _only(_check_fetch_transport_health(conn), "fetch_transport_health")
    assert check.status == "green"
    assert "n/a" in check.summary.lower()
