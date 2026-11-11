"""D101 -- the per-run detection-count check (`per_run_detections`).

AMBER (the monitor's `yellow`) when the latest COMPLETE pipeline run whose
evaluation has a non-empty aplus|watch pool wrote ZERO pattern_detection_events
for that run; GREEN otherwise; an empty pool is GREEN with its reason.

Every seed mirrors the LIVE shape read mode=ro on 2026-11-11:
  - run 201 (eval 187): 12 watch, 0 aplus, 0 detections (the cap episode);
  - run 202 (eval 188): 20 watch, 0 aplus, 0 detections (the cap episode);
  - run 203 (eval 189): 22 watch, 0 aplus, 110 detections (5 classes x 22);
  - watch rows carry a non-NULL pivot and rs_rank NULL / rs_method fallback_spy;
  - detections key to their run by pattern_detection_events.pipeline_run_id
    (source 'pipeline', detection_date = action session, data_asof = asof).
The brief quoted run 201 as "20 watch"; the live DB has 20 on run 202 and 12 on
run 201, so both are seeded at their real values.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from swing.data.db import ensure_schema
from swing.monitoring.research_health import (
    _check_per_run_detections,
    compute_research_health,
    write_research_health_artifact,
)

_CLASSES = ("vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w")
_KEY = "per_run_detections"


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "swing.db")


def _seed_eval(conn, *, eval_id: int, asof: str, watch: int, aplus: int = 0,
               skip: int = 0, prefix: str = "W") -> None:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date,"
        " tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count,"
        " error_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (eval_id, f"{asof}T17:30:00", asof, asof, watch + aplus + skip,
         aplus, watch, skip, 0, 0))
    rows = (
        [("aplus", i) for i in range(aplus)]
        + [("watch", i) for i in range(watch)]
        + [("skip", i) for i in range(skip)]
    )
    for bucket, i in rows:
        # live shape: watch pivot non-NULL, rs_rank NULL, rs_method fallback_spy
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot,"
            " rs_rank, rs_method) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (eval_id, f"{prefix}{bucket[0].upper()}{i:03d}", bucket, 10.0, 11.0,
             None, "fallback_spy"))


def _seed_run(conn, *, run_id: int, eval_id: int | None, asof: str,
              state: str = "complete", finished: bool = True) -> None:
    started = f"{asof}T17:30:04"
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger,"
        " data_asof_date, action_session_date, state, lease_token,"
        " evaluation_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, started, f"{asof}T17:34:00" if finished else None, "scheduled",
         asof, asof, state, f"tok{run_id}", eval_id))


def _seed_detections(conn, *, run_id: int, tickers: list[str], session: str,
                     asof: str) -> None:
    for t in tickers:
        for cls in _CLASSES:
            conn.execute(
                "INSERT INTO pattern_detection_events (ticker, detection_date,"
                " data_asof_date, pattern_class, structural_anchors_json,"
                " composite_score, detector_version, source,"
                " per_pattern_metadata_json, pipeline_run_id, created_at)"
                " VALUES (?, ?, ?, ?, '{}', 0.5, 'v', 'pipeline', '{}', ?, ?)",
                (t, session, asof, cls, run_id, f"{asof}T17:33:00"))


def _watch_tickers(conn, eval_id: int) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT ticker FROM candidates WHERE evaluation_run_id = ?"
        " AND bucket IN ('aplus','watch') ORDER BY ticker", (eval_id,))]


def _seed_run_200_healthy(conn) -> None:
    """An OLDER complete run with detections, so a CUMULATIVE count is > 0 (a
    cumulative-count implementation would read GREEN on every case below)."""
    _seed_eval(conn, eval_id=186, asof="2026-10-26", watch=12, prefix="P")
    _seed_run(conn, run_id=200, eval_id=186, asof="2026-10-26")
    _seed_detections(conn, run_id=200, tickers=_watch_tickers(conn, 186),
                     session="2026-10-27", asof="2026-10-26")


def _only(checks):
    assert len(checks) == 1
    assert checks[0].key == _KEY
    return checks[0]


# ---------------------------------------------------------------- (1) run 201


def test_run_201_shape_zero_detections_over_watch_pool_is_amber(tmp_path):
    conn = _conn(tmp_path)
    _seed_run_200_healthy(conn)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12, skip=32)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 201" in c.summary
    assert "12" in c.summary          # the pool size is in the envelope
    assert "0 detection" in c.summary
    assert c.detail is not None and "evaluation 187" in c.detail


def test_run_202_shape_twenty_watch_zero_detections_is_amber(tmp_path):
    conn = _conn(tmp_path)
    _seed_run_200_healthy(conn)
    _seed_eval(conn, eval_id=188, asof="2026-10-28", watch=20, skip=114)
    _seed_run(conn, run_id=202, eval_id=188, asof="2026-10-28")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 202" in c.summary
    assert "20" in c.summary


# ---------------------------------------------------------------- (2) run 203


def test_run_203_shape_110_detections_over_22_watch_is_green(tmp_path):
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12, prefix="A")
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    _seed_eval(conn, eval_id=189, asof="2026-10-29", watch=22, skip=113)
    _seed_run(conn, run_id=203, eval_id=189, asof="2026-10-29")
    _seed_detections(conn, run_id=203, tickers=_watch_tickers(conn, 189),
                     session="2026-10-30", asof="2026-10-29")
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM pattern_detection_events WHERE pipeline_run_id = 203"
    ).fetchone()[0] == 110
    c = _only(_check_per_run_detections(conn))
    assert c.status == "green"
    assert "run 203" in c.summary
    assert "110" in c.summary
    assert "22" in c.summary


def test_detections_are_counted_for_the_runs_own_id_not_a_neighbour(tmp_path):
    """Detections written under ANOTHER run id must not satisfy the latest run
    (a join on asof/date rather than the run's own id would read GREEN)."""
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12)
    _seed_run(conn, run_id=200, eval_id=None, asof="2026-10-27")
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    # same asof + session, but attributed to run 200
    _seed_detections(conn, run_id=200, tickers=_watch_tickers(conn, 187),
                     session="2026-10-28", asof="2026-10-27")
    conn.execute("UPDATE pipeline_runs SET finished_ts = '2026-10-27T17:31:00'"
                 " WHERE id = 200")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 201" in c.summary


# ---------------------------------------------------------------- (3) empty pool


def test_empty_pool_is_green_with_its_reason(tmp_path):
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=190, asof="2026-10-30", watch=0, aplus=0, skip=40)
    _seed_run(conn, run_id=204, eval_id=190, asof="2026-10-30")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "green"
    assert "run 204" in c.summary
    assert "empty" in c.summary
    assert c.detail is not None and "0 aplus" in c.detail and "0 watch" in c.detail


def test_no_complete_run_is_green_na(tmp_path):
    conn = _conn(tmp_path)
    c = _only(_check_per_run_detections(conn))
    assert c.status == "green"
    assert "n/a" in c.summary


# ---------------------------------------------------------------- (4) masking


@pytest.mark.parametrize("newer_state", ["running", "failed", "force_cleared"])
def test_newer_non_complete_run_does_not_mask_older_complete(tmp_path, newer_state):
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12, skip=32)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    # a NEWER run, mid-flight: its own pool AND its detections already written,
    # so an ORDER BY started_ts DESC (or id DESC) without the state filter
    # would read it and report GREEN.
    _seed_eval(conn, eval_id=188, asof="2026-10-28", watch=20, prefix="N")
    _seed_run(conn, run_id=202, eval_id=188, asof="2026-10-28",
              state=newer_state, finished=(newer_state != "running"))
    _seed_detections(conn, run_id=202, tickers=_watch_tickers(conn, 188),
                     session="2026-10-29", asof="2026-10-28")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 201" in c.summary


# ---------------------------------------------------------------- degrade paths


def test_unlinked_latest_complete_run_is_yellow_not_silent(tmp_path):
    """A complete run with NULL evaluation_run_id (legacy pre-binding rows only on
    live: 13 rows, max id 20) cannot have its pool read -> yellow, never a
    silent green and never a skip-back to an older linked run."""
    conn = _conn(tmp_path)
    _seed_run_200_healthy(conn)
    _seed_run(conn, run_id=201, eval_id=None, asof="2026-10-27")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 201" in c.summary


def test_pre_schema_conn_degrades_to_yellow(tmp_path):
    conn = sqlite3.connect(":memory:")
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "schema unavailable" in c.summary


# ---------------------------------------------------------------- aggregator


def test_check_is_in_the_aggregate(tmp_path):
    conn = _conn(tmp_path)
    status = compute_research_health(conn, exports_root=tmp_path / "none")
    assert _KEY in {c.key for c in status.checks}


# ---------------------------------------------------------------- (5) topbar


def _fresh_manifest_root(root: Path) -> Path:
    """A fresh shadow-expectancy-* dir + an attributed, zero-unattributed
    manifest -> drumbeat + excluded checks green."""
    ts = datetime.now(ZoneInfo("UTC")) - timedelta(hours=2)
    run_dir = root / ("shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 1}}},
        "unattributed": {},
    }}), encoding="utf-8")
    return root


def test_amber_reaches_the_topbar_through_the_context_processor(tmp_path, monkeypatch):
    """The run-201 shape lights the research topbar stoplight AMBER through the
    EXISTING path: compute -> write_research_health_artifact -> the base-wide
    context processor -> health_stoplights -> _research_stoplight. No base-VM
    field is involved (the processor injects `health_stoplights`)."""
    from swing.config import load
    from swing.monitoring.stoplights import research_health_artifact_path
    from swing.web.app import _health_stoplights_context_processor
    from tests.cli.test_cli_eval import _minimal_config

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg = load(_minimal_config(project, home))
    conn = ensure_schema(cfg.paths.db_path)
    try:
        _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12, skip=32)
        _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
        conn.commit()
        exports_root = _fresh_manifest_root(cfg.paths.exports_dir / "research")
        status = compute_research_health(conn, exports_root=exports_root)
    finally:
        conn.close()
    by_key = {c.key: c.status for c in status.checks}
    # attribution: the per-run check is the ONLY non-green check
    assert by_key[_KEY] == "yellow"
    assert [k for k, s in by_key.items() if s != "green"] == [_KEY]
    write_research_health_artifact(status, research_health_artifact_path(cfg))

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=cfg)))
    out = _health_stoplights_context_processor(request)
    research = {s.id: s for s in out["health_stoplights"]}["research"]
    assert research.color == "yellow"
    assert research.drilldown_path == "/health/research"
