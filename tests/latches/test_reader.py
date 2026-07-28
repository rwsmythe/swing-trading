"""The reader adapter: DB + on-disk archive, defensive at every boundary (A6)."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.latches.reader import (
    build_latch_derivation,
    load_bars,
    load_entry_records,
    load_fire_rows,
)


def _cfg(tmp_path):
    cache = tmp_path / "prices"
    cache.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        paths=SimpleNamespace(prices_cache_dir=cache, db_path=tmp_path / "t.db"),
        pipeline=SimpleNamespace(observe_max_pending_window_sessions=30),
    )


def _run(conn, rid, asof, action, *, pipeline_run_id=None):
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
        (rid, f"{asof}T17:30:05", asof, action))
    if pipeline_run_id is not None:
        conn.execute(
            "INSERT INTO pipeline_runs (id, started_ts, trigger, state, "
            "lease_token, data_asof_date, action_session_date, evaluation_run_id) "
            "VALUES (?, ?, 'manual', 'complete', ?, ?, ?, ?)",
            (pipeline_run_id, f"{asof}T17:00:00", f"lease-{pipeline_run_id}",
             asof, action, rid))


def _candidate(conn, rid, ticker, bucket, pivot, stop):
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (?, ?, ?, 17.76, ?, ?, 'universe')",
        (rid, ticker, bucket, pivot, stop))
    return int(cur.lastrowid)


@pytest.fixture
def ftre_db(tmp_path):
    """The REAL FTRE geometry: run 121 is the A+ FIRE (18.34 / 14.88); runs
    122-125 are `bucket='watch'` rows whose stop DRIFTS to 16.515 and whose
    pivot walks to 20.19. A latest-row read renders 16.51."""
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        _run(conn, 121, "2026-07-17", "2026-07-20", pipeline_run_id=135)
        _candidate(conn, 121, "FTRE", "aplus", 18.34, 14.88)
        for rid, asof, action, pivot, stop in (
            (122, "2026-07-20", "2026-07-21", 18.34, 15.195),
            (123, "2026-07-21", "2026-07-22", 18.34, 15.25),
            (124, "2026-07-22", "2026-07-23", 18.59, 16.515),
            (125, "2026-07-23", "2026-07-24", 20.19, 16.515),
        ):
            _run(conn, rid, asof, action)
            _candidate(conn, rid, "FTRE", "watch", pivot, stop)
    yield conn
    conn.close()


def test_load_fire_rows_returns_only_aplus_rows_with_both_identities(ftre_db):
    """Runs 121 (aplus) and 122-125 (watch, drifted) all present; only 121 is
    returned, and it carries the pipeline_run_id from the pipeline_runs join."""
    fires = load_fire_rows(ftre_db)
    assert len(fires) == 1
    (fire,) = fires
    assert fire.evaluation_run_id == 121
    assert (fire.pivot, fire.initial_stop) == (18.34, 14.88)
    assert fire.action_session_date == "2026-07-20"     # the DETECTION identity
    assert fire.pipeline_run_id == 135                  # the pipeline id space


def test_load_fire_rows_tolerates_a_missing_pipeline_runs_link(tmp_path):
    """SLDB-era fires have no pipeline_runs row: pipeline_run_id is None, not
    an exception. Null-twin tolerance is the NORMAL case (plan A.8) -- the latch
    corpus starts 2026-04-20, the detection corpus 2026-06-05."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 9, "2026-04-21", "2026-04-22")   # NO pipeline_runs row
            _candidate(conn, 9, "SLDB", "aplus", 8.866, 6.40)
        (fire,) = load_fire_rows(conn)
        assert fire.pipeline_run_id is None
        assert fire.ticker == "SLDB"
    finally:
        conn.close()


def test_load_fire_rows_returns_a_null_pivot_aplus_row_for_the_service_to_degrade(
        tmp_path):
    """The reader must NOT silently drop a malformed fire -- `derive_latches`
    owns the degradation so the operator SEES that a fire existed. Planted via
    RAW conn.execute (the write-barrier-bypass technique)."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 50, "2026-04-30", "2026-05-01")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(50, 'BAD', 'aplus', 5.0, NULL, 4.0, 'universe')")
        (fire,) = load_fire_rows(conn)
        assert fire.pivot is None
    finally:
        conn.close()


def test_load_entry_records_short_circuits_the_empty_ticker_set(ftre_db):
    """No `IN ()` -- invalid SQL (the dynamic-placeholder gotcha)."""
    assert load_entry_records(ftre_db, []) == {}
    assert load_entry_records(ftre_db, set()) == {}


def test_load_entry_records_returns_the_candidate_link_and_the_date(tmp_path):
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 99, "2026-06-24", "2026-06-25")
            cid = _candidate(conn, 99, "VSTS", "aplus", 13.56, 11.62)
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at, candidate_id) VALUES "
                "(17, 'VSTS', '2026-06-25', 13.61, 15, 11.62, 11.62, 'entered', "
                "'pipeline_aplus', '2026-06-24T20:06:25', ?)",
                (cid,))
        out = load_entry_records(conn, ["VSTS"])
        (rec,) = out["VSTS"]
        assert rec.trade_id == 17
        assert rec.entry_date == date(2026, 6, 25)
        assert rec.candidate_id == cid
    finally:
        conn.close()


def test_load_entry_records_skips_a_malformed_entry_date_rather_than_raising(tmp_path):
    """A malformed TEXT date must never be allowed to clear a latch, and must
    never crash the panel (A6). Planted via RAW insert."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) VALUES "
                "(4, 'VSTS', 'not-a-date', 13.61, 15, 11.62, 11.62, 'entered', "
                "'pipeline_aplus', '2026-06-24T20:06:25')")
        assert load_entry_records(conn, ["VSTS"]) == {}
    finally:
        conn.close()


def _write_archive(cache_dir, ticker, rows):
    pd.DataFrame(rows).to_parquet(cache_dir / f"{ticker}.yfinance.parquet")


def test_load_bars_returns_empty_for_an_absent_archive(tmp_path):
    """A6: a missing parquet degrades to [], never raises."""
    cfg = _cfg(tmp_path)
    assert load_bars(cfg, "NOPE", start=date(2026, 7, 20),
                     end=date(2026, 7, 24)) == []


def test_load_bars_reads_the_window_ascending(tmp_path):
    cfg = _cfg(tmp_path)
    _write_archive(cfg.paths.prices_cache_dir, "FTRE", [
        {"asof_date": "2026-07-22", "open": 18.0, "high": 18.5, "low": 17.8,
         "close": 18.2, "volume": 100.0},
        {"asof_date": "2026-07-20", "open": 17.6, "high": 17.9, "low": 17.4,
         "close": 17.76, "volume": 90.0},
        {"asof_date": "2026-07-27", "open": 19.0, "high": 19.5, "low": 18.8,
         "close": 19.2, "volume": 80.0},           # OUTSIDE the window
    ])
    bars = load_bars(cfg, "FTRE", start=date(2026, 7, 20), end=date(2026, 7, 24))
    assert [b.session for b in bars] == [date(2026, 7, 20), date(2026, 7, 22)]
    assert bars[0].close == 17.76


def test_load_bars_skips_rows_with_a_non_finite_close(tmp_path):
    """A ragged archive row (the F6-addendum trailing-NaN shape) must not be
    read as an invalidation -- a NaN close compares False against any stop, but
    a downstream float() would poison the walk."""
    cfg = _cfg(tmp_path)
    _write_archive(cfg.paths.prices_cache_dir, "RAG", [
        {"asof_date": "2026-07-20", "open": 17.6, "high": 17.9, "low": 17.4,
         "close": 17.76, "volume": 90.0},
        {"asof_date": "2026-07-21", "open": 17.7, "high": 18.0, "low": 17.5,
         "close": float("nan"), "volume": 95.0},
    ])
    bars = load_bars(cfg, "RAG", start=date(2026, 7, 20), end=date(2026, 7, 24))
    assert [b.session for b in bars] == [date(2026, 7, 20)]


def test_build_latch_derivation_uses_forward_and_backward_anchors(ftre_db, tmp_path):
    """horizon_session == action_session_for_run(now);
       derivation_session == session_offset(horizon_session, -1)
       == last_completed_session(now)."""
    from swing.evaluation.dates import action_session_for_run, last_completed_session
    cfg = _cfg(tmp_path)
    now = datetime(2026, 7, 25, 12, 0)
    d = build_latch_derivation(ftre_db, cfg, now=now)
    assert d.horizon_session == action_session_for_run(now) == date(2026, 7, 27)
    assert d.derivation_session == last_completed_session(now) == date(2026, 7, 24)
    assert d.horizon_sessions == 30                       # DERIVED from cfg


def test_the_horizon_tracks_the_configured_observe_window(ftre_db, tmp_path):
    """The parity binding is live in the READER, not just in the constant: a
    different observe window must move the expiry."""
    cfg = _cfg(tmp_path)
    cfg.pipeline.observe_max_pending_window_sessions = 20
    d = build_latch_derivation(ftre_db, cfg, now=datetime(2026, 7, 25, 12, 0))
    assert d.horizon_sessions == 20
    assert d.latches[0].horizon_expiry == date(2026, 8, 17)


def test_the_panel_derivation_freezes_the_fire_time_stop(ftre_db, tmp_path):
    """End-to-end through the REAL SQL: the drifted watch rows are present and
    must not reach the latch. A latest-row read renders 16.515."""
    cfg = _cfg(tmp_path)
    d = build_latch_derivation(ftre_db, cfg, now=datetime(2026, 7, 25, 12, 0))
    assert len(d.latches) == 1
    assert d.latches[0].latched_initial_stop == 14.88
    assert d.latches[0].latched_pivot == 18.34
    assert d.latches[0].horizon_expiry == date(2026, 8, 31)


def test_horizon_session_override_rebuilds_the_whole_context_from_the_anchor(
        ftre_db, tmp_path):
    """Codex R3-1: with an override, `now` must influence NOTHING. Call twice
    with the same override and two wildly different `now` values; both
    LatchDerivations must be equal."""
    cfg = _cfg(tmp_path)
    a = build_latch_derivation(
        ftre_db, cfg, now=datetime(2026, 7, 25, 12, 0),
        horizon_session_override=date(2026, 7, 27))
    b = build_latch_derivation(
        ftre_db, cfg, now=datetime(2027, 1, 4, 3, 0),
        horizon_session_override=date(2026, 7, 27))
    assert a == b
    assert a.horizon_session == date(2026, 7, 27)
    assert a.derivation_session == date(2026, 7, 24)


def test_build_latch_derivation_never_raises_on_a_malformed_row(tmp_path):
    """A NULL-pivot aplus row planted via RAW conn.execute (bypassing any
    writer) yields a DegradedFire, not an exception."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 50, "2026-04-30", "2026-05-01")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(50, 'BAD', 'aplus', 5.0, NULL, 4.0, 'universe')")
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 5, 1, 9, 0))
        assert d.latches == ()
        assert [x.reason for x in d.degraded] == ["pivot_missing"]
    finally:
        conn.close()


def test_build_latch_derivation_on_an_empty_db_returns_an_empty_derivation(tmp_path):
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 7, 25, 12, 0))
        assert d.latches == () and d.degraded == ()
    finally:
        conn.close()


def test_the_as_of_derivation_excludes_a_fire_newer_than_the_anchor(tmp_path):
    """Codex executing R1. `load_fire_rows` returns EVERY A+ fire, so without
    an as-of scope a beacon POST carrying yesterday's anchor would rebuild the
    derivation using TODAY's newer fire. With a different pivot that newer fire
    SUPERSEDES the latch the operator was actually looking at, so the view he
    genuinely performed is never recorded -- the telemetry silently under-counts
    in the flattering direction.

    Geometry: fire A 2026-07-20 @ 18.34 (what the page showed); fire B
    2026-07-28 @ 20.19 (landed after). As of 2026-07-27, only A exists."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 121, "2026-07-17", "2026-07-20")
            _candidate(conn, 121, "FTRE", "aplus", 18.34, 14.88)
            _run(conn, 130, "2026-07-27", "2026-07-28")
            _candidate(conn, 130, "FTRE", "aplus", 20.19, 16.515)

        as_of = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 27))
        assert len(as_of.latches) == 1
        assert as_of.latches[0].state == "armed"          # NOT superseded
        assert as_of.latches[0].latched_pivot == 18.34

        later = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 28))
        assert len(later.latches) == 2
        assert later.latches[0].state == "superseded"
    finally:
        conn.close()


def test_an_unparseable_fire_session_is_kept_so_it_can_degrade_visibly(tmp_path):
    """The as-of filter must not become a silent drop: a fire whose session TEXT
    is malformed cannot be placed in time, so it is KEPT and surfaces as a
    degraded row (A6)."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) VALUES "
                "(60, '2026-05-01T17:30:05', '2026-04-30', '2026-5-01', "
                "1, 1, 0, 0, 0, 0)")
            _candidate(conn, 60, "BADD", "aplus", 10.0, 8.0)
        d = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 27))
        assert d.latches == ()
        assert [x.reason for x in d.degraded] == ["bad_session_date"]
    finally:
        conn.close()


def test_a_non_numeric_price_degrades_visibly_rather_than_vanishing(tmp_path):
    """Codex executing R4. SQLite is dynamically typed: a REAL column happily
    stores the TEXT 'bad' (verified: `typeof(p)` == 'text'). An eager `float()`
    in the reader raised and DROPPED the whole fire, so the operator saw
    NOTHING -- contradicting both the reader's own contract and A6. The raw
    value must reach `derive_latches`, which reports it as a degraded fire."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 70, "2026-04-30", "2026-05-01")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(70, 'TXT', 'aplus', 5.0, 'bad', 4.0, 'universe')")
        assert conn.execute(
            "SELECT typeof(pivot) FROM candidates").fetchone()[0] == "text"
        (fire,) = load_fire_rows(conn)
        assert fire.pivot == "bad"          # carried RAW, not coerced
        d = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 5, 1))
        assert d.latches == ()
        assert [x.reason for x in d.degraded] == ["pivot_missing"]
    finally:
        conn.close()


def test_a_voided_phantom_trade_does_not_clear_a_latch(tmp_path):
    """Codex executing R7. A VOIDED trade is a PHANTOM that never executed at
    the broker (the D25 SATL trade-11 case). It is never deleted -- only
    annotated with a `trade_events` note carrying `"voided": true` -- so a naive
    `FROM trades` read picks it up and marks the latch `filled`, SILENCING the
    very no-resting-order alarm this arc exists to raise, for a fire the
    operator never acted on. The reader routes through the single-source
    exclusion predicate every other cohort/stat reader already uses."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 121, "2026-07-17", "2026-07-20")
            cid = _candidate(conn, 121, "FTRE", "aplus", 18.34, 14.88)
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at, candidate_id) VALUES "
                "(11, 'FTRE', '2026-07-21', 18.40, 3, 14.88, 14.88, 'entered', "
                "'pipeline_aplus', '2026-07-17T17:30:05', ?)", (cid,))

        # Before the void annotation it DOES clear the latch...
        pre = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 27))
        assert pre.latches[0].state == "filled"

        with conn:
            conn.execute(
                "INSERT INTO trade_events (trade_id, ts, event_type, "
                "payload_json) VALUES "
                "(11, '2026-07-22T10:00:00', 'note', '{\"voided\": true}')")

        # ...and after it, the mandate is correctly still ARMED.
        post = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 27))
        assert post.latches[0].state == "armed"
        assert post.latches[0].clear_trade_id is None
        assert load_entry_records(conn, ["FTRE"]) == {}
    finally:
        conn.close()
