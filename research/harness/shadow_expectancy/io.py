from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from swing.data.models import Candidate
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.pattern_detection_events import list_detection_events
from swing.data.repos.pattern_forward_observations import (
    get_observations_for_detection,
)

_OHLC_KEYS = ("open", "high", "low", "close", "volume", "provider")


@dataclass(frozen=True)
class Bar:
    session: str   # ISO observation_date
    open: float
    high: float
    low: float
    close: float


def parse_bar(ohlc_today_json: str, *, session: str) -> Bar:
    d = json.loads(ohlc_today_json)
    missing = [k for k in _OHLC_KEYS if k not in d]
    if missing:
        raise KeyError(f"ohlc_today_json missing keys: {missing}")
    return Bar(
        session=session,
        open=float(d["open"]), high=float(d["high"]),
        low=float(d["low"]), close=float(d["close"]),
    )


def open_ro(db_path) -> sqlite3.Connection:
    """Read-only connection (mode=ro URI) -- harness never writes (L2-light)."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _eval_run_for_pipeline(conn, pipeline_run_id) -> int | None:
    row = conn.execute(
        "SELECT evaluation_run_id FROM pipeline_runs WHERE id = ?",
        (pipeline_run_id,),
    ).fetchone()
    return int(row[0]) if row is not None and row[0] is not None else None


def resolve_candidate(conn, *, pipeline_run_id, ticker) -> Candidate | None:
    """Join detection -> pipeline_runs.evaluation_run_id -> candidates (ticker).

    NOTE (spec ambiguity #1): candidates are keyed by evaluation_run_id, NOT
    pipeline_run_id; pipeline_runs.evaluation_run_id bridges them.
    """
    if pipeline_run_id is None:
        return None
    eval_run_id = _eval_run_for_pipeline(conn, pipeline_run_id)
    if eval_run_id is None:
        return None
    cands = [c for c in fetch_candidates_for_run(conn, eval_run_id) if c.ticker == ticker]
    if not cands:
        return None
    if len(cands) > 1:  # candidates has UNIQUE(evaluation_run_id, ticker); defensive
        cands.sort(key=lambda c: c.ticker)
    return cands[0]


def read_observation_chain(conn, detection_id):
    """The full ASC forward-observation chain (one row per session)."""
    return get_observations_for_detection(conn, detection_id)


def list_pipeline_detections(conn, *, source):
    """All detections for a temporal-log source, oldest-first deterministic."""
    events = list_detection_events(conn, source=source)
    return sorted(events, key=lambda d: (d.pipeline_run_id or -1, d.ticker, d.detection_id))
