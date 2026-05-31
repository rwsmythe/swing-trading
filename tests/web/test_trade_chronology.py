"""Phase 14 SB4 Slice 5 Tasks 5.1/5.2: trade chronology assembly.

Fills source (5.1) + trade_events source (5.2). The substantive per-source
contract suite lives in test_trade_chronology_contracts.py (Task 5.3).
"""
from __future__ import annotations

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


def _seed_trade(conn, *, ticker="ABC", entry_date="2026-04-20",
                entry_price=10.0, state="managing") -> int:
    """Insert a trade row + its entry fill (explicit, not relying on the
    autouse conftest fixture which the direct-imported symbol bypasses)."""
    tid = insert_trade_with_event(
        conn,
        Trade(
            id=None, ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, initial_shares=10, initial_stop=9.0,
            current_stop=9.0, state=state,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, trade_origin="manual_off_pipeline",
            pre_trade_locked_at=f"{entry_date}T09:30:00"),
        event_ts=f"{entry_date}T09:30:00")
    insert_fill_with_event(
        conn,
        Fill(fill_id=None, trade_id=tid,
             fill_datetime=f"{entry_date}T09:30:00", action="entry",
             quantity=10.0, price=entry_price),
        event_ts=f"{entry_date}T09:30:00")
    return tid


@dataclass
class _TradeRef:
    id: int


@pytest.fixture
def trade_with_two_fills(conn):
    with conn:
        tid = _seed_trade(conn)
        # The autouse fixture already wrote the entry fill; add an exit fill.
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-25T15:00:00", action="exit",
                 quantity=10.0, price=11.5, reason="manual"),
            event_ts="2026-04-25T15:00:00")
    return _TradeRef(id=tid)


@pytest.fixture
def trade_with_event(conn):
    with conn:
        tid = _seed_trade(conn)
        conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
            "rationale) VALUES (?, ?, 'flag', ?, ?)",
            (tid, "2026-04-22T10:00:00", '{"k": "v"}', "flagged for review"))
    return _TradeRef(id=tid)


@pytest.fixture
def trade_with_malformed_event_payload(conn):
    with conn:
        tid = _seed_trade(conn)
        conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
            "rationale) VALUES (?, ?, 'note', ?, ?)",
            (tid, "2026-04-23T10:00:00", "{not valid json", None))
    return _TradeRef(id=tid)


def test_chronology_fills_only(conn, trade_with_two_fills):
    chron = build_trade_chronology(conn, trade_with_two_fills.id)
    kinds = [e.kind for e in chron.entries]
    assert kinds[0] == "fill:entry"
    assert all(chron.entries[i].ts <= chron.entries[i + 1].ts
               for i in range(len(chron.entries) - 1))
    entry = chron.entries[0]
    # entry fill: action='entry', quantity=10.0, price=10.0 (field is quantity)
    assert entry.summary == "entry 10.0 @ 10.0"


def test_chronology_includes_trade_events(conn, trade_with_event):
    chron = build_trade_chronology(conn, trade_with_event.id)
    assert any(e.source == "trade_event" and e.kind.startswith("event:")
               for e in chron.entries)


def test_chronology_malformed_event_payload_does_not_raise(
        conn, trade_with_malformed_event_payload):
    chron = build_trade_chronology(conn, trade_with_malformed_event_payload.id)
    ev = next(e for e in chron.entries if e.source == "trade_event")
    assert ev is not None  # entry present despite unparseable payload_json
