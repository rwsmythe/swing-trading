"""The reader adapter: DB + on-disk archive, defensive at every boundary (A6)."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.latches.reader import (
    build_latch_derivation,
    count_session_recorded_closes,
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


# --- the derivation-session RECORDED-CLOSE count (PENDING vs PERMANENT) -----
#
# The panel's mandate-form check needs a close stamped on the derivation
# session. When it has none, "nothing has been recorded for that session yet"
# and "that session's closes exist and this ticker has none of them" call for
# opposite operator responses (wait / it will not clear on its own), and NOTHING
# already read by the panel distinguishes them. This is the one read that does.
def test_count_session_recorded_closes_counts_the_session_that_was_recorded(
        ftre_db):
    assert count_session_recorded_closes(ftre_db, date(2026, 7, 23)) == 1


def test_count_session_recorded_closes_is_zero_for_an_unrecorded_session(
        ftre_db):
    """ZERO is the load-bearing signal. `ftre_db`'s newest run is stamped
    `data_asof_date='2026-07-23'`, so 2026-07-24 has nothing recorded at all --
    exactly the state of every trading day between the market close and the
    nightly pipeline run."""
    assert count_session_recorded_closes(ftre_db, date(2026, 7, 24)) == 0


def test_count_session_recorded_closes_mirrors_the_usable_close_predicate(
        tmp_path):
    """Codex y1 MAJOR 1. This read MUST agree with `load_last_closes` about what
    "usable" means -- it filters `close IS NOT NULL` and drops non-finite values.
    A session whose only rows carry a NULL or a NaN close has recorded NOTHING
    the form check can use, so counting those rows would flip every waiting
    latch from calm status to a warning. Planted via RAW conn.execute."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 70, "2026-07-24", "2026-07-27")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(70, 'FTRE', 'watch', NULL, 18.34, 14.88, 'universe')")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(70, 'NANC', 'skip', 'nan', 13.0, 11.0, 'universe')")
        assert count_session_recorded_closes(conn, date(2026, 7, 24)) == 0
        with conn:
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(70, 'AMN', 'skip', 12.0, 13.0, 11.0, 'universe')")
        assert count_session_recorded_closes(conn, date(2026, 7, 24)) == 1
    finally:
        conn.close()


def test_count_session_recorded_closes_does_not_ask_where_the_row_came_from(
        tmp_path):
    """Codex y1 MAJOR 1. An `evaluation_runs` row is NOT the finviz screen: the
    evaluator appends HELD open positions (`bucket='excluded'`) and pinned
    tickers to the same run. Those rows carry a close, and a close is exactly
    what the form check needs -- so they count, and no label may claim screen
    membership from this read."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 71, "2026-07-24", "2026-07-27")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method, notes) VALUES "
                "(71, 'HELD', 'excluded', 9.5, NULL, NULL, 'universe', "
                "'open position')")
        assert count_session_recorded_closes(conn, date(2026, 7, 24)) == 1
    finally:
        conn.close()


def test_count_session_recorded_closes_counts_a_ticker_once_across_runs(
        tmp_path):
    """Codex y1 MAJOR 2. Several `evaluation_runs` can share one
    `data_asof_date` (an ad-hoc `swing eval` alongside the nightly). The count is
    rendered to the operator as evidence, so it counts DISTINCT tickers -- a
    ticker present in two same-date runs is one ticker, not two."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 72, "2026-07-24", "2026-07-27")
            _run(conn, 73, "2026-07-24", "2026-07-27")
            _candidate(conn, 72, "AMN", "watch", 13.0, 11.0)
            _candidate(conn, 73, "AMN", "watch", 13.0, 11.0)
            _candidate(conn, 73, "VSTS", "watch", 14.0, 12.0)
        assert count_session_recorded_closes(conn, date(2026, 7, 24)) == 2
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


def _write_legacy_archive(cache_dir, ticker, rows):
    """The PRE-Shape-A `{TICKER}.parquet` file. 1168 of these exist on the
    operator's box and V1 deliberately LEAVES them in place (the
    `read_or_fetch_archive` consumers read only that path), so the
    `_backward_compat_rename` both-exist MERGE branch is the STEADY state, not
    a one-shot."""
    pd.DataFrame(rows).to_parquet(cache_dir / f"{ticker}.parquet")


def _dir_state(cache_dir):
    """(name, size, mtime_ns) for every file -- the on-disk fingerprint."""
    return sorted(
        (p.name, p.stat().st_size, p.stat().st_mtime_ns)
        for p in cache_dir.iterdir()
    )


def _freeze_mtimes(cache_dir, when_ns=1_600_000_000_000_000_000):
    """Stamp every archive file far in the past so ANY rewrite is unambiguous
    (immune to coarse filesystem timestamp resolution)."""
    import os
    for p in cache_dir.iterdir():
        os.utime(p, ns=(when_ns, when_ns))


def test_the_panel_bar_read_writes_NOTHING_to_the_archive_directory(tmp_path):
    """A4 CARVE-OUT (CHARC-authorised): `GET /latches` must write NOTHING.

    `resolve_ohlcv_window` migrates legacy `{TICKER}.parquet` -> Shape A on
    every call, and because V1 leaves the legacy file in place the both-exist
    MERGE branch re-writes `{TICKER}.yfinance.parquet` on EVERY read -- so the
    panel's bar read fired a filesystem write per latched ticker per page load.
    The panel path now passes `migrate=False`.

    Discriminating: under the pre-fix code the yfinance parquet is rewritten,
    so its mtime moves off the frozen 2020 stamp.

    The fixture is DIVERGENT on purpose (the legacy file carries a bar Shape A
    lacks). `_backward_compat_rename` skips the rewrite when the merge output
    already equals the Shape-A content, so an identical-content fixture would
    pass against the UNFIXED code and prove nothing. Divergence is the real
    shape: on the operator's live cache 6 of a 60-ticker both-shapes sample
    (AAPL, AESI, AMD, BLNK, COST, CRWD) rewrite on every single read."""
    cfg = _cfg(tmp_path)
    cache = cfg.paths.prices_cache_dir
    shape_a_rows = [
        {"asof_date": "2026-07-20", "open": 17.6, "high": 17.9, "low": 17.4,
         "close": 17.76, "volume": 90.0},
        {"asof_date": "2026-07-22", "open": 18.0, "high": 18.5, "low": 17.8,
         "close": 18.20, "volume": 100.0},
    ]
    # BOTH shapes present -- the live FTRE/VSTS geometry and the steady state
    # (V1 never removes the legacy file).
    _write_legacy_archive(cache, "FTRE", shape_a_rows + [
        {"asof_date": "2026-07-23", "open": 18.3, "high": 18.9, "low": 18.1,
         "close": 18.55, "volume": 110.0},
    ])
    _write_archive(cache, "FTRE", shape_a_rows)
    _freeze_mtimes(cache)
    before = _dir_state(cache)

    bars = load_bars(cfg, "FTRE", start=date(2026, 7, 20), end=date(2026, 7, 24))

    assert _dir_state(cache) == before, (
        "GET /latches wrote to the OHLCV archive: the panel bar read must pass "
        "migrate=False to resolve_ohlcv_window")
    # The accepted read consequence, stated rather than hidden: the panel now
    # sees Shape-A rows ONLY, so a bar living only in the legacy file is not
    # read. Refactoring the legacy consumers onto Shape A is the banked V2.
    assert [b.session for b in bars] == [date(2026, 7, 20), date(2026, 7, 22)]


def test_the_panel_leaves_a_legacy_only_archive_UNMIGRATED_and_reports_no_bars(
        tmp_path):
    """The accepted, SAFE-direction consequence of the carve-out.

    A ticker whose archive is legacy-only is not migrated BY THE PANEL, so the
    panel sees no Shape-A rows and the derivation reports `bars_available=False`
    ("invalidation NOT evaluated - no bars") rather than a silent "not
    invalidated". The migration duty stays with the nightly pipeline's observe
    step, which still calls `resolve_ohlcv_window` at the default
    `migrate=True`."""
    cfg = _cfg(tmp_path)
    cache = cfg.paths.prices_cache_dir
    _write_legacy_archive(cache, "SLDB", [
        {"asof_date": "2026-07-20", "open": 17.6, "high": 17.9, "low": 17.4,
         "close": 17.76, "volume": 90.0},
    ])
    _freeze_mtimes(cache)
    before = _dir_state(cache)

    assert load_bars(cfg, "SLDB", start=date(2026, 7, 20),
                     end=date(2026, 7, 24)) == []
    assert _dir_state(cache) == before


def test_an_existing_resolve_caller_STILL_migrates_the_legacy_archive(tmp_path):
    """THE OTHER HALF OF THE CARVE-OUT, and the reason it is not a one-sided
    test: `migrate` is opt-OUT with a `True` default, so every pre-existing
    caller (the pipeline observe step, `swing/pipeline/runner.py`) keeps the
    legacy -> Shape A migration duty. A future refactor cannot silently flip the
    default and re-introduce the GET-time write without turning this red."""
    import inspect

    from swing.data.ohlcv_archive import resolve_ohlcv_window

    signature = inspect.signature(resolve_ohlcv_window)
    assert signature.parameters["migrate"].default is True
    assert signature.parameters["migrate"].kind is inspect.Parameter.KEYWORD_ONLY

    cache = tmp_path / "prices"
    cache.mkdir(parents=True, exist_ok=True)
    _write_legacy_archive(cache, "SLDB", [
        {"asof_date": "2026-07-20", "open": 17.6, "high": 17.9, "low": 17.4,
         "close": 17.76, "volume": 90.0},
    ])

    # NO migrate= argument: exactly how every pre-existing caller invokes it.
    df, _prov = resolve_ohlcv_window(
        "SLDB", start="2026-07-20", end="2026-07-24", cache_dir=cache)

    assert (cache / "SLDB.yfinance.parquet").exists(), (
        "the default path must STILL migrate the legacy archive")
    assert list(df["asof_date"]) == ["2026-07-20"]


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


def test_a_non_session_bar_cannot_invalidate_a_mandate(tmp_path):
    """Codex executing R8. The whole derivation is session-based, so a bar dated
    on a NON-session is a category error rather than a datum -- letting one
    through would clear a mandate on a day the market never traded, silencing
    the no-resting-order alarm. Skipping loses no real bar.

    2026-07-26 is a Sunday; 2026-07-24 is a Friday session."""
    from swing.evaluation.dates import is_trading_session
    cfg = _cfg(tmp_path)
    assert not is_trading_session(date(2026, 7, 26))
    _write_archive(cfg.paths.prices_cache_dir, "SUN", [
        {"asof_date": "2026-07-24", "open": 17.9, "high": 18.3, "low": 17.6,
         "close": 17.91, "volume": 90.0},
        {"asof_date": "2026-07-26", "open": 15.0, "high": 15.2, "low": 14.0,
         "close": 14.00, "volume": 95.0},      # a Sunday "close" below any stop
    ])
    bars = load_bars(cfg, "SUN", start=date(2026, 7, 20), end=date(2026, 7, 27))
    assert [b.session for b in bars] == [date(2026, 7, 24)]


def test_a_non_session_entry_date_is_logged_but_NOT_dropped(tmp_path, caplog):
    """The deliberate ASYMMETRY with bars. A trade is ground truth about a REAL
    position; refusing to see it because its date is a non-session would leave
    the mandate armed for a position the operator actually holds and tell him to
    place an order he does not need. The anomaly is surfaced without discarding
    the fact."""
    import logging
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) VALUES "
                "(21, 'SUN', '2026-07-26', 18.40, 3, 14.88, 14.88, 'entered', "
                "'pipeline_aplus', '2026-07-17T17:30:05')")
        with caplog.at_level(logging.WARNING):
            out = load_entry_records(conn, ["SUN"])
        assert [r.trade_id for r in out["SUN"]] == [21]      # NOT dropped
        assert "non-session entry_date" in caplog.text        # but LOUD
    finally:
        conn.close()


def test_a_malformed_entry_price_does_not_drop_an_authoritative_fill(tmp_path):
    """Codex executing R10. `entry_price REAL NOT NULL` is an AFFINITY
    declaration, not a type CHECK, so SQLite holds the TEXT 'bad'. Coercing it
    as row-fatal DROPPED the whole trade -- leaving the mandate `armed` and
    telling the operator to place an order for a position he ALREADY HOLDS,
    which is a double-buy instruction.

    Degrading to None composes correctly with the price-band rule: the EXACT
    candidate_id rung still recognises the fill (an explicit link is
    authoritative), while the WINDOWED rung would refuse an unverifiable
    price."""
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
                "(31, 'FTRE', '2026-07-21', 'bad', 'bad', 14.88, 14.88, "
                "'entered', 'pipeline_aplus', '2026-07-17T17:30:05', ?)", (cid,))
        assert conn.execute(
            "SELECT typeof(entry_price) FROM trades").fetchone()[0] == "text"

        (rec,) = load_entry_records(conn, ["FTRE"])["FTRE"]
        assert rec.trade_id == 31
        assert rec.entry_price is None and rec.shares is None

        d = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 27))
        assert d.latches[0].state == "filled"
        assert d.latches[0].clear_trade_id == 31
        assert d.latches[0].fill_link_basis == "candidate_id"
    finally:
        conn.close()


def test_a_malformed_price_on_a_null_candidate_trade_still_refuses_to_fill(tmp_path):
    """The composed half: unverifiable price + no explicit link = no fill."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 121, "2026-07-17", "2026-07-20")
            _candidate(conn, 121, "FTRE", "aplus", 18.34, 14.88)
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) VALUES "
                "(32, 'FTRE', '2026-07-21', 'bad', 3, 14.88, 14.88, "
                "'entered', 'pipeline_aplus', '2026-07-17T17:30:05')")
        d = build_latch_derivation(
            conn, cfg, horizon_session_override=date(2026, 7, 27))
        assert d.latches[0].state == "armed"
    finally:
        conn.close()


# --- Arc 21-G Task 2: the witness map, DECOUPLED from the invalidation walk --
def _fire(conn, rid, asof, action, ticker, pivot, stop):
    _run(conn, rid, asof, action)
    _candidate(conn, rid, ticker, "aplus", pivot, stop)


def test_the_derivation_surfaces_the_archive_window_and_excludes_look_ahead(
        tmp_path):
    """The map holds every LOADED session and stops at the derivation session.
    A look-ahead bar the archive legitimately holds (the nightly warm writes
    one at 17:30 for the NEXT session) is EXCLUDED, because a bar newer than
    the page horizon cannot date a price the page is describing."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(cfg.paths.db_path)
    try:
        with conn:
            # anchor S-2 == 2026-07-22 (S == 2026-07-24)
            _fire(conn, 121, "2026-07-21", "2026-07-22", "FTRE", 18.34, 14.88)
        _write_archive(cfg.paths.prices_cache_dir, "FTRE", [
            {"asof_date": "2026-07-22", "open": 18.0, "high": 18.5, "low": 17.8,
             "close": 18.21, "volume": 100.0},
            {"asof_date": "2026-07-23", "open": 18.2, "high": 19.6, "low": 18.1,
             "close": 19.52, "volume": 100.0},
            {"asof_date": "2026-07-24", "open": 19.5, "high": 19.7, "low": 17.5,
             "close": 17.76, "volume": 100.0},
            {"asof_date": "2026-07-27", "open": 17.8, "high": 18.9, "low": 17.7,
             "close": 18.80, "volume": 100.0},        # LOOK-AHEAD
        ])
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 7, 25, 12, 0))
        assert d.archive_closes["FTRE"] == {
            date(2026, 7, 22): 18.21,
            date(2026, 7, 23): 19.52,
            date(2026, 7, 24): 17.76,
        }
        assert d.archive_status["FTRE"] == "ok"
    finally:
        conn.close()


def test_a_latch_fired_for_tomorrow_still_gets_its_derivation_session_witness(
        tmp_path):
    """Codex R4 MAJOR 1 -- the FRESH-LATCH reachability lock, in the reader.

    A latch fires on the nightly for action session T+1, so its anchor is T+1
    while that same evening the derivation session is T. The invalidation
    walk's ELIGIBLE set [anchor, derivation_session] is therefore EMPTY --
    correctly, no session has elapsed since the fire. If the WITNESS were taken
    from that set (or if the shipped start-after-derivation short-circuit
    stayed), the NEWEST latch in the system, the one the operator is about to
    act on tonight, could never be corroborated and could never print an
    affirmative all-clear.

    Both halves are asserted TOGETHER: an implementation that fixes
    reachability by widening `_eligible_bars` instead of the LOAD window would
    let a pre-anchor bar invalidate a mandate that did not yet exist, and fails
    the second half."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(cfg.paths.db_path)
    try:
        with conn:
            # anchor 2026-07-27 > derivation session 2026-07-24
            _fire(conn, 140, "2026-07-24", "2026-07-27", "NEWL", 18.34, 14.88)
        _write_archive(cfg.paths.prices_cache_dir, "NEWL", [
            {"asof_date": "2026-07-24", "open": 17.5, "high": 17.9, "low": 17.4,
             "close": 17.76, "volume": 90.0},
        ])
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 7, 25, 12, 0))
        # the WITNESS reaches the derivation session...
        assert d.archive_closes["NEWL"] == {date(2026, 7, 24): 17.76}
        # ...and the invalidation walk is untouched.
        (latch,) = d.latches
        assert latch.anchor == date(2026, 7, 27)
        assert latch.bars_available is False
        assert latch.bars_through is None
        assert latch.state == "armed"
    finally:
        conn.close()


def test_the_widened_load_window_does_not_move_a_normal_invalidation(tmp_path):
    """The other half of the eligible-set lock: with the load window widened, a
    latch whose anchor PRECEDES the derivation session must still invalidate on
    exactly the session it did before, and a pre-anchor bar below the stop must
    still be history rather than an invalidation."""
    cfg = _cfg(tmp_path)
    conn = ensure_schema(cfg.paths.db_path)
    try:
        with conn:
            _fire(conn, 121, "2026-07-21", "2026-07-22", "FTRE", 18.34, 14.88)
        _write_archive(cfg.paths.prices_cache_dir, "FTRE", [
            # BEFORE the anchor and below the stop -- history, not invalidation.
            {"asof_date": "2026-07-20", "open": 15.0, "high": 15.2, "low": 14.0,
             "close": 14.10, "volume": 100.0},
            {"asof_date": "2026-07-22", "open": 18.0, "high": 18.5, "low": 17.8,
             "close": 18.21, "volume": 100.0},
            {"asof_date": "2026-07-23", "open": 15.0, "high": 15.2, "low": 14.0,
             "close": 14.20, "volume": 100.0},
        ])
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 7, 25, 12, 0))
        (latch,) = d.latches
        assert latch.state == "invalidated"
        assert latch.clear_session == date(2026, 7, 23)
        assert latch.bars_through == date(2026, 7, 23)
        # The widening is `min(earliest_anchor, derivation_session)`, so it
        # moves NOTHING for a latch whose anchor already precedes the
        # derivation session: the pre-anchor bar is neither loaded nor walked.
        assert date(2026, 7, 20) not in d.archive_closes["FTRE"]
    finally:
        conn.close()


def test_an_unreadable_archive_is_unavailable_and_an_empty_one_is_ok(
        tmp_path, monkeypatch):
    """Codex R5 MAJOR 2 -- the status lock. An implementation that INFERS the
    status from an empty close map cannot pass both halves."""
    import swing.latches.reader as reader_mod
    cfg = _cfg(tmp_path)
    conn = ensure_schema(cfg.paths.db_path)
    try:
        with conn:
            _fire(conn, 121, "2026-07-17", "2026-07-20", "FTRE", 18.34, 14.88)
        # (a) readable, genuinely empty -> "ok" + an empty map. That is a FACT
        # about the data, not our ignorance of it.
        d = build_latch_derivation(conn, cfg, now=datetime(2026, 7, 25, 12, 0))
        assert d.archive_closes["FTRE"] == {}
        assert d.archive_status["FTRE"] == "ok"

        # (b) the read RAISES -> "unavailable" + the same empty map.
        def _boom(*_a, **_k):
            raise OSError("parquet is corrupt")

        monkeypatch.setattr(
            "swing.data.ohlcv_archive.resolve_ohlcv_window", _boom)
        d2 = build_latch_derivation(conn, cfg, now=datetime(2026, 7, 25, 12, 0))
        assert d2.archive_closes["FTRE"] == {}
        assert d2.archive_status["FTRE"] == "unavailable"
        # ...and the shipped `load_bars` signature and contract are untouched.
        assert reader_mod.load_bars(
            cfg, "FTRE", start=date(2026, 7, 20), end=date(2026, 7, 24)) == []
    finally:
        conn.close()


def test_latest_recorded_close_stamp_is_the_newest_stamp_with_a_usable_close(
        tmp_path):
    """The SELF-LIMITING half of the alarm gate (plan B.2.1 condition 2): `L`
    says whether the whole system is fresher than this ticker. It mirrors the
    usability predicate `load_last_closes` and `count_session_recorded_closes`
    already share -- a run whose only closes are NULL / non-finite has recorded
    nothing the form check can use, so it must not raise `L`."""
    from swing.latches.reader import latest_recorded_close_stamp
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            _run(conn, 121, "2026-07-20", "2026-07-21")
            _candidate(conn, 121, "FTRE", "aplus", 18.34, 14.88)
            _run(conn, 122, "2026-07-24", "2026-07-27")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(122, 'AMN', 'watch', NULL, 13.0, 11.0, 'universe')")
        assert latest_recorded_close_stamp(conn) == "2026-07-20"
        with conn:
            _run(conn, 123, "2026-07-23", "2026-07-24")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(123, 'AMN', 'watch', 12.0, 13.0, 11.0, 'universe')")
        assert latest_recorded_close_stamp(conn) == "2026-07-23"
    finally:
        conn.close()


def test_latest_recorded_close_stamp_is_none_on_an_empty_db(tmp_path):
    """No usable close anywhere -> None, which WITHDRAWS alarm authority
    (permission is not obligation) rather than granting it by default."""
    from swing.latches.reader import latest_recorded_close_stamp
    conn = ensure_schema(tmp_path / "t.db")
    try:
        assert latest_recorded_close_stamp(conn) is None
    finally:
        conn.close()
