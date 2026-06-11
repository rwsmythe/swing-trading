from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from swing.data.db import run_migrations


def make_db(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=27, backup_dir=tmp_path)
    return c


def insert_candidate(conn, *, ticker, bucket, pivot, initial_stop, close=None,
                     criteria=()):
    cur = conn.execute(
        "INSERT INTO evaluation_runs (run_ts, data_asof_date, action_session_date,"
        " finviz_csv_path, tickers_evaluated, aplus_count, watch_count, skip_count,"
        " excluded_count, error_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("2026-05-29T00:00:00Z", "2026-05-28", "2026-05-29", None, 1, 1, 0, 0, 0, 0),
    )
    eval_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot,"
        " initial_stop, rs_method) VALUES (?,?,?,?,?,?,?)",
        (eval_id, ticker, bucket, close, pivot, initial_stop, "fallback_spy"),
    )
    cid = int(cur.lastrowid)
    for name, layer, result in criteria:
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer,"
            " result) VALUES (?,?,?,?)",
            (cid, name, layer, result),
        )
    conn.commit()
    return eval_id


def insert_pipeline_run(conn, eval_run_id, *, state="complete"):
    """INSERT a pipeline_runs row bound to eval_run_id; return its id."""
    cur = conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date,"
        " action_session_date, state, lease_token, evaluation_run_id)"
        " VALUES (?,?,?,?,?,?,?)",
        ("2026-05-29T00:00:00Z", "manual", "2026-05-28", "2026-05-29", state,
         f"tok-{eval_run_id}", eval_run_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_detection(conn, *, ticker, pipeline_run_id, pivot, data_asof_date,
                     detection_date, pattern_class="vcp", structural_low=None):
    evidence = {"pivot_price": pivot}
    if structural_low is not None:
        evidence["structural_low"] = structural_low
    anchors = json.dumps({"window": {}, "evidence": evidence})
    cur = conn.execute(
        "INSERT INTO pattern_detection_events (ticker, detection_date, data_asof_date,"
        " pattern_class, structural_anchors_json, composite_score, detector_version,"
        " source, per_pattern_metadata_json, pipeline_run_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ticker, detection_date, data_asof_date, pattern_class, anchors, 0.7,
         "vcp_v1", "pipeline", "{}", pipeline_run_id, "2026-05-29T00:00:00Z"),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_observation(conn, detection_id, observation_date, *, o, h, l, c,  # noqa: E741
                       status, event=None, sessions_since=0, v=1000.0,
                       provider="yfinance"):
    ohlc = json.dumps({"open": o, "high": h, "low": l, "close": c, "volume": v,
                       "provider": provider})
    conn.execute(
        "INSERT INTO pattern_forward_observations (detection_id, observation_date,"
        " ohlc_today_json, status, status_change_event, sessions_since_detection,"
        " created_at) VALUES (?,?,?,?,?,?,?)",
        (detection_id, observation_date, ohlc, status, event, sessions_since,
         "2026-05-29T00:00:00Z"),
    )
    conn.commit()
