"""D101 -- the per-run detection-count check (`per_run_detections`).

AMBER (the monitor's `yellow`) when the latest COMPLETE pipeline run whose
evaluation has a non-empty aplus|watch pool wrote ZERO pattern_detection_events
for that run AND the pool is not already fully detected for that run's
action_session_date by other runs; GREEN otherwise; an empty pool is GREEN with
its reason. (CHARC ruling B, 2026-11-11, with RD's keying: the cover is compared
on the detect step's own skip key (ticker, detection_date, pattern_class).)

Measured basis for the rerun-aware rule (live, mode=ro, 2026-11-11): since
detection logging began (first pipeline_run_id 89) the complete runs with a
non-empty pool and zero own detections are
  - 103, 120, 121, 123, 124: same-session reruns, every pool ticker already
    detected for the run's action_session_date by earlier runs (101/102,
    118/119) -> FALSE alarms under plain zero-vs-non-zero;
  - 201, 202: no pool ticker covered -> the real failures.
Every (run, ticker) group on live carries exactly 5 rows (1754 of 1754), one
per detector class, so a full cover is all 5 classes per ticker.

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

# Frozen clock anchored to the real wall clock (the aggregate-test convention):
# "yesterday noon" Hawaii-local, so the artifact is never future-dated and never
# stale for the reader's real-clock gate (generated_ts <= 7d).
_NOW = (datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
        - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
_CLASSES = ("vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w")
_KEY = "per_run_detections"


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "swing.db")


def _seed_eval(conn, *, eval_id: int, asof: str, watch: int, aplus: int = 0,
               skip: int = 0, prefix: str = "W",
               session: str | None = None) -> None:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date,"
        " tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count,"
        " error_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (eval_id, f"{asof}T17:30:00", asof, session or asof,
         watch + aplus + skip,
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
              state: str = "complete", finished: bool = True,
              session: str | None = None) -> None:
    started = f"{asof}T17:30:04"
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger,"
        " data_asof_date, action_session_date, state, lease_token,"
        " evaluation_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, started, f"{asof}T17:34:00" if finished else None, "scheduled",
         asof, session or asof, state, f"tok{run_id}", eval_id))


def _seed_detections(conn, *, run_id: int | None, tickers: list[str],
                     session: str, asof: str,
                     classes: tuple[str, ...] = _CLASSES,
                     source: str = "pipeline") -> None:
    for t in tickers:
        for cls in classes:
            conn.execute(
                "INSERT INTO pattern_detection_events (ticker, detection_date,"
                " data_asof_date, pattern_class, structural_anchors_json,"
                " composite_score, detector_version, source,"
                " per_pattern_metadata_json, pipeline_run_id, created_at)"
                " VALUES (?, ?, ?, ?, '{}', 0.5, 'v', ?, '{}', ?, ?)",
                (t, session, asof, cls, source, run_id, f"{asof}T17:33:00"))


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


def test_aplus_only_pool_with_zero_detections_is_amber(tmp_path):
    """The pool is aplus|watch (the production detect predicate); a watch-only
    count would read this aplus-only night as an empty pool -> GREEN."""
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=0, aplus=3, skip=10)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "3 aplus + 0 watch" in c.detail


def test_a_single_detection_is_green(tmp_path):
    """Zero-vs-non-zero, no threshold: ONE detection over the run-201 pool is
    GREEN (a per-ticker or five-class threshold would read it as zero)."""
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12, skip=32)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    conn.execute(
        "INSERT INTO pattern_detection_events (ticker, detection_date,"
        " data_asof_date, pattern_class, structural_anchors_json,"
        " composite_score, detector_version, source,"
        " per_pattern_metadata_json, pipeline_run_id, created_at)"
        " VALUES ('WW000', '2026-10-28', '2026-10-27', 'vcp', '{}', 0.5, 'v',"
        " 'pipeline', '{}', 201, '2026-10-27T17:33:00')")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "green"
    assert "1 detection(s)" in c.summary


def test_latest_is_by_completion_not_by_id(tmp_path):
    """The most recent COMPLETED row by finished_ts. Here the higher id (and the
    later start) finished EARLIER; ordering by id or started_ts would read
    run 202 (healthy) and report GREEN."""
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    _seed_eval(conn, eval_id=188, asof="2026-10-27", watch=5, prefix="N")
    _seed_run(conn, run_id=202, eval_id=188, asof="2026-10-27")
    _seed_detections(conn, run_id=202, tickers=_watch_tickers(conn, 188),
                     session="2026-10-28", asof="2026-10-27")
    conn.execute("UPDATE pipeline_runs SET started_ts = '2026-10-27T17:00:00',"
                 " finished_ts = '2026-10-27T19:00:00' WHERE id = 201")
    conn.execute("UPDATE pipeline_runs SET started_ts = '2026-10-27T17:10:00',"
                 " finished_ts = '2026-10-27T18:00:00' WHERE id = 202")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 201" in c.summary


def test_completion_tie_breaks_to_the_higher_id(tmp_path):
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=188, asof="2026-10-27", watch=5, prefix="N")
    _seed_run(conn, run_id=201, eval_id=188, asof="2026-10-27")
    _seed_detections(conn, run_id=201, tickers=_watch_tickers(conn, 188),
                     session="2026-10-28", asof="2026-10-27")
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=12)
    _seed_run(conn, run_id=202, eval_id=187, asof="2026-10-27")
    conn.commit()
    (fin201,) = conn.execute(
        "SELECT finished_ts FROM pipeline_runs WHERE id = 201").fetchone()
    (fin202,) = conn.execute(
        "SELECT finished_ts FROM pipeline_runs WHERE id = 202").fetchone()
    assert fin201 == fin202  # a genuine tie
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 202" in c.summary


# ---------------------------------------------------------------- rerun-aware (B)

_RERUN_SESSION = "2026-07-06"
_RERUN_ASOF = "2026-07-02"


def _seed_live_121_shape(conn, *, cover_118: int = 19, cover_119: int = 2,
                         classes_118: tuple[str, ...] = _CLASSES,
                         session_118: str = _RERUN_SESSION,
                         source_118: str = "pipeline") -> list[str]:
    """The live run-121 shape: 21 watch (98 skip), action session 2026-07-06,
    asof 2026-07-02, zero own detections; the pool covered by run 118 (19
    tickers x 5 classes = 95 rows) and run 119 (2 tickers x 5 = 10 rows)."""
    _seed_eval(conn, eval_id=108, asof=_RERUN_ASOF, watch=21, skip=98,
               session=_RERUN_SESSION)
    pool = _watch_tickers(conn, 108)
    _seed_run(conn, run_id=118, eval_id=None, asof=_RERUN_ASOF,
              session=_RERUN_SESSION)
    _seed_run(conn, run_id=119, eval_id=None, asof=_RERUN_ASOF,
              session=_RERUN_SESSION)
    _seed_run(conn, run_id=121, eval_id=108, asof=_RERUN_ASOF,
              session=_RERUN_SESSION)
    conn.execute("UPDATE pipeline_runs SET finished_ts = '2026-07-02T16:09:50'"
                 " WHERE id = 118")
    conn.execute("UPDATE pipeline_runs SET finished_ts = '2026-07-03T18:00:00'"
                 " WHERE id = 119")
    conn.execute("UPDATE pipeline_runs SET finished_ts = '2026-07-03T21:56:17'"
                 " WHERE id = 121")
    _seed_detections(conn, run_id=118, tickers=pool[:cover_118],
                     session=session_118, asof=_RERUN_ASOF,
                     classes=classes_118, source=source_118)
    _seed_detections(conn, run_id=119,
                     tickers=pool[cover_118:cover_118 + cover_119],
                     session=_RERUN_SESSION, asof=_RERUN_ASOF)
    conn.commit()
    return pool


def test_live_121_rerun_fully_covered_is_green_naming_the_covering_runs(tmp_path):
    conn = _conn(tmp_path)
    pool = _seed_live_121_shape(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM pattern_detection_events WHERE pipeline_run_id = 121"
    ).fetchone()[0] == 0
    c = _only(_check_per_run_detections(conn))
    assert c.status == "green"
    assert "run 121" in c.summary           # the run it judged (RD's condition)
    assert "rerun" in c.summary
    assert "118, 119" in c.summary          # NAMES the covering runs
    assert "pool of 21" in c.summary
    assert _RERUN_SESSION in c.detail
    # the per-ticker (date, class) cover, naming each ticker and its run
    assert f"{pool[0]} 5/5 [118]" in c.detail
    assert f"{pool[19]} 5/5 [119]" in c.detail
    assert c.detail.count("5/5 [") == 21


def test_rerun_partially_covered_pool_is_amber_naming_the_uncovered(tmp_path):
    conn = _conn(tmp_path)
    pool = _seed_live_121_shape(conn, cover_119=1)   # 20 of 21 covered
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "run 121" in c.summary
    assert pool[-1] in c.detail             # the one uncovered ticker is named
    assert "1 of 21" in c.detail


def test_cover_on_ticker_and_date_but_not_class_is_amber(tmp_path):
    """RD's keying: run 118 left only 'vcp' for its 19 tickers (a partial
    detect, then a raise). Every pool ticker HAS a row on the session, so a
    ticker-and-date cover reads GREEN; the (ticker, date, class) cover does
    not."""
    conn = _conn(tmp_path)
    _seed_live_121_shape(conn, classes_118=("vcp",))
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "19 of 21" in c.detail


def test_cover_on_another_session_is_amber(tmp_path):
    """The cover is keyed on THIS run's action_session_date: run 118's rows on
    a different session do not cover a ticker (a ticker-only cover would)."""
    conn = _conn(tmp_path)
    _seed_live_121_shape(conn, session_118="2026-07-03")
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "19 of 21" in c.detail


def test_cover_from_a_non_pipeline_source_is_amber(tmp_path):
    """The detect step's skip key includes source='pipeline'; a backfill row
    would not have stopped it writing, so it is not a cover."""
    conn = _conn(tmp_path)
    _seed_live_121_shape(conn, source_118="backfill")
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert "19 of 21" in c.detail


def test_amber_names_each_uncovered_tickers_missing_classes_in_registry_order(
        tmp_path):
    """CHARC condition 2: the YELLOW names the MISSING classes per ticker, in
    _DETECT_PATTERN_CLASSES order (NOT alphabetical, NOT insertion order). The 19
    run-118 tickers carry only flat_base + double_bottom_w, seeded in REVERSE
    registry order, so the missing set is exactly vcp, cup_with_handle and
    high_tight_flag."""
    conn = _conn(tmp_path)
    pool = _seed_live_121_shape(
        conn, classes_118=("double_bottom_w", "flat_base"))
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    missing = "missing [vcp, cup_with_handle, high_tight_flag]"
    assert f"{pool[0]} {missing}" in c.detail
    assert f"{pool[9]} {missing}" in c.detail     # the last name under the cap
    assert c.detail.count("missing [") == 10      # the cap; the covered 2 never
    assert "(+9 more)" in c.detail
    assert pool[19] not in c.detail and pool[20] not in c.detail


def test_amber_partial_cover_unions_classes_across_other_runs(tmp_path):
    """A ticker covered in part by run 118 and in part by run 119 is missing
    only what NEITHER wrote -- the class cover is a union over other runs."""
    conn = _conn(tmp_path)
    pool = _seed_live_121_shape(conn, classes_118=("vcp",), cover_119=0)
    _seed_detections(conn, run_id=119, tickers=pool[:1],
                     session=_RERUN_SESSION, asof=_RERUN_ASOF,
                     classes=("cup_with_handle", "double_bottom_w"))
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert f"{pool[0]} missing [flat_base, high_tight_flag]" in c.detail
    assert f"{pool[1]} missing [flat_base, cup_with_handle, high_tight_flag,"\
        " double_bottom_w]" in c.detail


def test_amber_zero_cover_ticker_reads_missing_all_five(tmp_path):
    """A ticker with no cover at all reads `missing all 5` (the run-201 shape:
    every pool ticker is uncovered)."""
    conn = _conn(tmp_path)
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=3, skip=5)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    conn.commit()
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    for t in _watch_tickers(conn, 187):
        assert f"{t} missing all 5" in c.detail
    assert "missing [" not in c.detail


def test_amber_missing_class_names_keep_the_cap_and_more_tail(tmp_path):
    """Truncation is unchanged: at most _UNCOVERED_NAME_CAP tickers are named,
    in ticker order, then `(+N more)`."""
    from swing.monitoring.research_health import _UNCOVERED_NAME_CAP

    conn = _conn(tmp_path)
    n = _UNCOVERED_NAME_CAP + 2
    _seed_eval(conn, eval_id=187, asof="2026-10-27", watch=n, skip=5)
    _seed_run(conn, run_id=201, eval_id=187, asof="2026-10-27")
    conn.commit()
    pool = _watch_tickers(conn, 187)
    c = _only(_check_per_run_detections(conn))
    assert c.status == "yellow"
    assert c.detail.count("missing all 5") == _UNCOVERED_NAME_CAP
    assert f"{pool[_UNCOVERED_NAME_CAP - 1]} missing all 5" in c.detail
    assert pool[_UNCOVERED_NAME_CAP] not in c.detail
    assert "(+2 more)" in c.detail


def test_detect_class_mirror_matches_the_detector_registry():
    """The drift comparator for the monitor's class mirror: the classes a full
    cover requires must be the classes the detect step writes."""
    from swing.monitoring.research_health import _DETECT_PATTERN_CLASSES
    from swing.pipeline.runner import _pattern_detect_registry

    assert _DETECT_PATTERN_CLASSES == tuple(
        cls for _, cls, _ in _pattern_detect_registry())


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
    ts = (_NOW.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
          .astimezone(ZoneInfo("UTC")) - timedelta(days=1))
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
        status = compute_research_health(conn, exports_root=exports_root, now=_NOW)
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
