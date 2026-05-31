"""Phase 14 SB4 Slice 5 Task 5.3: per-source chronology contract suite.

Field-map per source (daily_management split by record_type; trades review),
supersession-excluded (UNIQUE markers on BOTH the superseded + active rows),
review_log-never-leaks (cadence table, NO trade_id), malformed-payload
best-effort, malformed-ts-sorts-last, empty-source no-error, timestamp-precision
co-sortable. MFE/MAE are R-multiples (NOT %).
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


def _insert_dmr(conn, trade_id, *, record_type, review_date, is_superseded=0,
                **cols):
    """Insert one daily_management_records row. Only the columns the
    chronology reads need realistic values; the rest get NOT-NULL-satisfying
    defaults. ``cols`` overrides any column by exact name."""
    base = {
        "trade_id": trade_id,
        "record_type": record_type,
        "review_date": review_date,
        "data_asof_session": review_date,
        "created_at": f"{review_date}T20:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "is_superseded": is_superseded,
    }
    base.update(cols)
    keys = list(base.keys())
    placeholders = ", ".join("?" * len(keys))
    sql = (f"INSERT INTO daily_management_records ({', '.join(keys)}) "
           f"VALUES ({placeholders})")
    conn.execute(sql, tuple(base[k] for k in keys))


@dataclass
class _TradeRef:
    id: int


@dataclass
class _MarkerTradeRef:
    id: int
    notes_marker: str


@dataclass
class _SupersededRef:
    id: int
    superseded_marker: str
    active_marker: str


@dataclass
class _ReviewLogRef:
    trade_id: int


@dataclass
class _ReviewTradeRef:
    id: int
    mistake_tag_text: str


@pytest.fixture
def trade_with_daily_snapshot(conn):
    with conn:
        tid = _seed_trade(conn)
        _insert_dmr(
            conn, tid, record_type="daily_snapshot",
            review_date="2026-04-22",
            open_MFE_R_to_date=1.8, open_MAE_R_to_date=0.4,
            maturity_stage="+1.5R_to_+2R",
            trail_MA_eligibility_flag=1, trail_MA_candidate_price=12.0)
    return _TradeRef(id=tid)


@pytest.fixture
def trade_with_event_log_context(conn):
    marker = "MGMT_NOTE_MARKER_q7z"
    with conn:
        tid = _seed_trade(conn)
        _insert_dmr(
            conn, tid, record_type="event_log", review_date="2026-04-23",
            thesis_status="intact",
            volume_behavior="confirming",
            relative_strength_status="improving",
            market_regime_change=1,
            management_notes=marker)
    return _MarkerTradeRef(id=tid, notes_marker=marker)


@pytest.fixture
def trade_with_stop_adjust_event_log(conn):
    with conn:
        tid = _seed_trade(conn)
        _insert_dmr(
            conn, tid, record_type="event_log", review_date="2026-04-24",
            stop_changed=1, prior_stop=9.0, new_stop=10.0,
            stop_change_reason="trail to breakeven")
    return _TradeRef(id=tid)


@pytest.fixture
def trade_with_superseded_row(conn):
    superseded_marker = "SUPERSEDED_MARKER_xyz"
    active_marker = "ACTIVE_MARKER_abc"
    with conn:
        tid = _seed_trade(conn)
        # Superseded event_log (is_superseded=1) carrying the unique marker.
        _insert_dmr(
            conn, tid, record_type="event_log", review_date="2026-04-22",
            is_superseded=1, management_notes=superseded_marker)
        # Active event_log carrying its own unique marker.
        _insert_dmr(
            conn, tid, record_type="event_log", review_date="2026-04-23",
            is_superseded=0, management_notes=active_marker)
    return _SupersededRef(id=tid, superseded_marker=superseded_marker,
                          active_marker=active_marker)


@pytest.fixture
def trade_and_unrelated_review_log_row(conn):
    """A cadence review_log row (NO trade_id column) co-resident with a trade.

    review_log is the Phase 6 cadence table; it has no trade_id so it can
    never be associated with a trade's chronology. Seed one + a trade.
    """
    with conn:
        tid = _seed_trade(conn)
        conn.execute(
            "INSERT INTO review_log (review_type, scheduled_date, "
            "period_start, period_end, created_at) VALUES "
            "('daily', '2026-04-23', '2026-04-23', '2026-04-23', "
            "'2026-04-23T18:00:00')")
    return _ReviewLogRef(trade_id=tid)


@pytest.fixture
def trade_with_completed_review(conn):
    tag_text = "oversized_position"
    with conn:
        tid = _seed_trade(conn, state="managing")
        conn.execute(
            "UPDATE trades SET state='reviewed', reviewed_at=?, "
            "process_grade=?, lesson_learned=?, mistake_tags=? WHERE id=?",
            ("2026-05-01T12:00:00", "B",
             "Sized too large for the setup.\nSecond line.",
             f'["{tag_text}"]', tid))
    return _ReviewTradeRef(id=tid, mistake_tag_text=tag_text)


@pytest.fixture
def trade_with_garbage_fill_ts(conn):
    with conn:
        tid = _seed_trade(conn)
        # Plant a fill with a non-empty GARBAGE fill_datetime (must flag +
        # sort last, never raise). Inserted directly to bypass any validation.
        # The garbage value sorts LEXICALLY EARLY among the ISO keys ('0000-...'
        # < '2026-...') so the "all malformed sort last" assertion genuinely
        # depends on _sorted's malformed_last primary key, not on string order:
        # drop that key and this entry would interleave at the FRONT.
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reason) VALUES (?, '0000-garbage', 'exit', 5.0, 11.0, "
            "'manual')", (tid,))
    return _TradeRef(id=tid)


@pytest.fixture
def bare_trade_only_fills(conn):
    with conn:
        tid = _seed_trade(conn)
    return _TradeRef(id=tid)


@pytest.fixture
def trade_mixed_sources(conn):
    with conn:
        tid = _seed_trade(conn)
        # exit fill (datetime precision)
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-28T15:00:00", action="exit",
                 quantity=10.0, price=11.5, reason="manual"),
            event_ts="2026-04-28T15:00:00")
        # trade_event (datetime precision)
        conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
            "rationale) VALUES (?, '2026-04-21T10:00:00', 'flag', '{}', 'flag')",
            (tid,))
        # daily_management snapshot (date precision)
        _insert_dmr(
            conn, tid, record_type="daily_snapshot", review_date="2026-04-24",
            open_MFE_R_to_date=1.0, open_MAE_R_to_date=0.2,
            trail_MA_eligibility_flag=0)
        # post-trade review (datetime precision)
        conn.execute(
            "UPDATE trades SET state='reviewed', reviewed_at=?, "
            "process_grade='A', lesson_learned='ok', mistake_tags=? WHERE id=?",
            ("2026-05-02T12:00:00", '["none"]', tid))
    return _TradeRef(id=tid)


def test_daily_snapshot_field_map(conn, trade_with_daily_snapshot):
    chron = build_trade_chronology(conn, trade_with_daily_snapshot.id)
    snap = next(e for e in chron.entries if e.kind == "snapshot")
    # FIX-4: MFE/MAE live in the summary now (de-duplicated out of detail).
    assert "MFE" in (snap.summary or "") and "MAE" in (snap.summary or "")
    # MFE/MAE are R-multiples (rendered with an 'R' suffix), NOT percentages.
    assert "R" in (snap.summary or "")
    # WP-R3 M#3: trail-MA eligibility is spec-locked into snapshot detail.
    assert "trail_MA_eligible" in (snap.detail or "")


def test_event_log_detail_carries_volume_rs_regime(
        conn, trade_with_event_log_context):
    chron = build_trade_chronology(conn, trade_with_event_log_context.id)
    ev = next(e for e in chron.entries
              if e.source == "daily_management" and e.kind != "snapshot")
    d = ev.detail or ""
    assert "vol=" in d and "rs=" in d and "regime_change=" in d
    assert trade_with_event_log_context.notes_marker in d  # management_notes


def test_event_log_stop_adjust_precedence(
        conn, trade_with_stop_adjust_event_log):
    chron = build_trade_chronology(conn, trade_with_stop_adjust_event_log.id)
    e = next(e for e in chron.entries if e.kind == "stop_adjust")
    assert "->" in e.summary  # "{prior_stop}->{new_stop}"


def test_superseded_daily_management_excluded(conn, trade_with_superseded_row):
    marker = trade_with_superseded_row.superseded_marker
    active_marker = trade_with_superseded_row.active_marker
    chron = build_trade_chronology(conn, trade_with_superseded_row.id)
    blob = " ".join((e.summary or "") + " " + (e.detail or "")
                    for e in chron.entries)
    assert marker not in blob          # superseded row excluded
    assert active_marker in blob       # active row included (not over-filtered)


def test_review_log_cadence_row_never_in_chronology(
        conn, trade_and_unrelated_review_log_row):
    chron = build_trade_chronology(
        conn, trade_and_unrelated_review_log_row.trade_id)
    assert all(e.source != "review_log" for e in chron.entries)


def test_trades_review_source(conn, trade_with_completed_review):
    chron = build_trade_chronology(conn, trade_with_completed_review.id)
    rev = next(e for e in chron.entries if e.source == "review")
    assert rev.kind == "review" and rev.ts  # reviewed_at
    # WP-R3 M#4: detail must carry the mistake tags (selected but previously
    # dropped).
    assert trade_with_completed_review.mistake_tag_text in (rev.detail or "")


def test_malformed_timestamp_sorts_last_with_flag(
        conn, trade_with_garbage_fill_ts):
    chron = build_trade_chronology(conn, trade_with_garbage_fill_ts.id)
    bad = [e for e in chron.entries if e.ts_malformed]
    assert bad, "garbage-ts entry must be flagged ts_malformed"
    assert all(e.ts_malformed
               for e in chron.entries[len(chron.entries) - len(bad):])


def test_empty_sources_no_error(conn, bare_trade_only_fills):
    chron = build_trade_chronology(conn, bare_trade_only_fills.id)
    assert chron.entries  # fills only; daily_management/review empty -> no err


def test_timestamp_precision_normalized_sortable(conn, trade_mixed_sources):
    chron = build_trade_chronology(conn, trade_mixed_sources.id)
    # date-only (daily_management) + datetime (fills/events/review) co-sort.
    assert all(chron.entries[i].ts <= chron.entries[i + 1].ts
               for i in range(len(chron.entries) - 1)
               if not chron.entries[i + 1].ts_malformed)
