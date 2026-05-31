"""Phase 14 SB4 gate-fix FIX-4 — chronology verbiage de-duplication.

Gate finding: each chronology entry double-printed its type and/or values
(kind='event:stop_adjust' + summary='stop_adjust'; kind='fill:entry' +
summary='entry ...'; snapshot MFE/MAE in BOTH summary and detail; review
lesson in BOTH summary and detail).

This is PRESENTATION-only: sources, order, source precedence, and the
review_log-excluded rule are unchanged (covered by the existing contract
suite). Here we assert each entry renders the TYPE once and VALUES once:
  - the kind token does not reappear (whole-word) in the summary;
  - snapshot MFE/MAE appear in exactly one of summary/detail;
  - review lesson appears in exactly one of summary/detail.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from swing.config import Config, load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.view_models.trade_chronology import build_trade_chronology


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


@pytest.fixture
def conn(cfg):
    c = connect(cfg.paths.db_path)
    yield c
    c.close()


def _seed_trade(conn, *, state="managing") -> int:
    tid = insert_trade_with_event(
        conn,
        Trade(
            id=None, ticker="ABC", entry_date="2026-04-20",
            entry_price=10.0, initial_shares=10, initial_stop=9.0,
            current_stop=9.0, state=state,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-04-20T09:30:00"),
        event_ts="2026-04-20T09:30:00")
    insert_fill_with_event(
        conn,
        Fill(fill_id=None, trade_id=tid, fill_datetime="2026-04-20T09:30:00",
             action="entry", quantity=10.0, price=10.0),
        event_ts="2026-04-20T09:30:00")
    return tid


def _insert_dmr(conn, trade_id, *, record_type, review_date, **cols):
    base = {
        "trade_id": trade_id, "record_type": record_type,
        "review_date": review_date, "data_asof_session": review_date,
        "created_at": f"{review_date}T20:00:00",
        "mfe_mae_precision_level": "daily_approximate", "is_superseded": 0,
    }
    base.update(cols)
    keys = list(base.keys())
    placeholders = ", ".join("?" * len(keys))
    conn.execute(
        f"INSERT INTO daily_management_records ({', '.join(keys)}) "
        f"VALUES ({placeholders})", tuple(base[k] for k in keys))


@dataclass
class _Ref:
    id: int


def _kind_repeats_in_summary(kind: str, summary: str) -> bool:
    """The kind token appearing as a whole word inside the summary == the
    double-print bug (substrings like 'flag' in 'flagged' don't count)."""
    return bool(re.search(rf"\b{re.escape(kind)}\b", summary or ""))


@pytest.fixture
def trade_with_fill_and_event(conn):
    with conn:
        tid = _seed_trade(conn)
        # stop_adjust trade_event with a rationale (no payload reuse).
        conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
            "rationale) VALUES (?, '2026-04-22T10:00:00', 'stop_adjust', '{}', "
            "'trail to breakeven')", (tid,))
    return _Ref(id=tid)


def test_fill_entry_type_once_value_once(conn, trade_with_fill_and_event):
    chron = build_trade_chronology(conn, trade_with_fill_and_event.id)
    entry = next(e for e in chron.entries if e.source == "fill")
    # kind no longer carries the 'fill:' prefix; the action is the type.
    assert entry.kind == "entry"
    # summary carries the VALUES (qty @ price) without repeating the type.
    assert not _kind_repeats_in_summary(entry.kind, entry.summary)
    assert entry.summary == "10.0 @ 10.0"


def test_trade_event_type_not_repeated(conn, trade_with_fill_and_event):
    chron = build_trade_chronology(conn, trade_with_fill_and_event.id)
    # (insert_trade_with_event also emits an auto 'entry' trade_event; target
    # the stop_adjust one explicitly.)
    ev = next(e for e in chron.entries
              if e.source == "trade_event" and e.kind == "stop_adjust")
    # kind is the bare event_type (no 'event:' prefix), shown once.
    assert ev.kind == "stop_adjust"
    assert not ev.kind.startswith("event:")
    assert not _kind_repeats_in_summary(ev.kind, ev.summary)


@pytest.fixture
def trade_with_snapshot(conn):
    with conn:
        tid = _seed_trade(conn)
        _insert_dmr(
            conn, tid, record_type="daily_snapshot", review_date="2026-04-22",
            open_MFE_R_to_date=1.8, open_MAE_R_to_date=0.4,
            maturity_stage="+1.5R_to_+2R",
            trail_MA_eligibility_flag=1, trail_MA_candidate_price=12.0)
    return _Ref(id=tid)


def test_snapshot_mfe_mae_not_double_printed(conn, trade_with_snapshot):
    chron = build_trade_chronology(conn, trade_with_snapshot.id)
    snap = next(e for e in chron.entries if e.kind == "snapshot")
    summary = snap.summary or ""
    detail = snap.detail or ""
    # MFE/MAE appear in EXACTLY ONE of summary/detail (no duplicate).
    assert ("MFE" in summary) ^ ("MFE" in detail)
    assert ("MAE" in summary) ^ ("MAE" in detail)
    # The kind token 'snapshot' is not repeated in the summary.
    assert not _kind_repeats_in_summary("snapshot", summary)
    # The non-MFE/MAE context (maturity / trail) lives in detail, not summary.
    assert "trail_MA_eligible" in detail


@pytest.fixture
def trade_with_review(conn):
    with conn:
        tid = _seed_trade(conn, state="managing")
        conn.execute(
            "UPDATE trades SET state='reviewed', reviewed_at=?, "
            "process_grade=?, lesson_learned=?, mistake_tags=? WHERE id=?",
            ("2026-05-01T12:00:00", "B",
             "Sized too large for the setup.", '["oversized_position"]', tid))
    return _Ref(id=tid)


def test_review_lesson_not_double_printed(conn, trade_with_review):
    chron = build_trade_chronology(conn, trade_with_review.id)
    rev = next(e for e in chron.entries if e.source == "review")
    summary = rev.summary or ""
    detail = rev.detail or ""
    lesson = "Sized too large for the setup."
    # The lesson appears in EXACTLY ONE of summary/detail.
    assert (lesson in summary) ^ (lesson in detail)
    # 'review' is the kind (shown once); not repeated in summary.
    assert not _kind_repeats_in_summary("review", summary)
    # The mistake tags remain reachable (carried in detail per WP-R3 M#4).
    assert "oversized_position" in detail
