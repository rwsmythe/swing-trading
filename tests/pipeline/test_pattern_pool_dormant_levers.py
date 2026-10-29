from __future__ import annotations
import pytest
from tests.pipeline.conftest_temporal import (  # noqa
    tmp_db_at_head, _build_bars, _StubOhlcvCache, _drive_detect,
    _seed_aplus_watch_skip_candidates_and_run)


def test_lever1_dormant_default_no_cap_no_audit(tmp_db_at_head):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_at_head, aplus=("AAA",), watch=("W1", "W2", "W3"), skip=())
    assert cfg.pipeline.detect_watch_pool_cap is None     # dormant default
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    got = {r[0] for r in conn.execute(
        "SELECT DISTINCT ticker FROM pattern_evaluations").fetchall()}
    assert got == {"AAA", "W1", "W2", "W3"}               # uncapped
    assert not [w for w in warnings if w.get("dropped_count")]  # no cap audit


def test_lever1_active_cap_audit_accuracy(tmp_db_at_head):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_at_head, aplus=("AAA",), watch=("W1", "W2", "W3"), skip=())
    cfg.pipeline.detect_watch_pool_cap = 1                 # cap watch to 1
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    audit = next(w for w in warnings
                 if w["step"] == "pattern_detect" and "dropped_count" in w)
    assert audit["expected_detect_pool"] == 4             # 1 aplus + 3 watch
    assert audit["actual_pool"] == 2                      # 1 aplus + 1 watch
    assert audit["dropped_count"] == 2                    # 4 - 2
    assert audit["dropped_bucket"] == "watch"
    assert audit["expected_pool_by_bucket"] == {"aplus": 1, "watch": 3}
    assert audit["actual_pool_by_bucket"] == {"aplus": 1, "watch": 1}
    # WHICH watch name survived: the helper default plants an equal excess
    # (12.0) on every row, so the ticker-ASC tiebreak decides -> W1 kept.
    assert _detected(conn) == {"AAA", "W1"}
    assert audit["rank_key"] == "rs_return_12w_vs_spy desc"
    assert audit["dropped_tickers"] == ["W2", "W3"]


# --- Lever 1 rank key: the LIVE shape --------------------------------------
# TT8 runs on the SPY fallback, so every live watch row carries
# rs_rank=None, rs_method='fallback_spy' and a fractional excess return in
# rs_return_12w_vs_spy. The cap ranks watch by that excess DESC, None LAST,
# ticker ASC -- never by rs_rank.
_LIVE = "fallback_spy"


def _detected(conn) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT ticker FROM pattern_evaluations").fetchall()}


@pytest.fixture
def lever1_db(request):
    # tmp_db_at_head under another name: a test parameter named after the
    # imported fixture is an F811 redefinition in this module.
    return request.getfixturevalue("tmp_db_at_head")


def _run_capped(db, *, watch, rs, cap, aplus=("AAA",)):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            db, aplus=aplus, watch=watch, skip=(), rs_overrides=rs)
    cfg.pipeline.detect_watch_pool_cap = cap
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    audit = next(w for w in warnings
                 if w["step"] == "pattern_detect" and "dropped_count" in w)
    return conn, audit


def test_lever1_cap_live_shape_null_rs_rank_ranks_by_excess_desc(lever1_db):
    # (a) Every row rs_rank=None (the live shape). The old rs_rank key raised
    # TypeError here. W2 carries the highest excess and is not first by
    # ticker, so neither ticker order nor an ascending sort keeps it.
    rs = {"AAA": (None, 0.20, _LIVE), "W1": (None, 0.083, _LIVE),
          "W2": (None, 1.145, _LIVE), "W3": (None, 0.40, _LIVE)}
    conn, audit = _run_capped(lever1_db, watch=("W1", "W2", "W3"),
                              rs=rs, cap=1)
    assert _detected(conn) == {"AAA", "W2"}
    assert audit["rank_key"] == "rs_return_12w_vs_spy desc"
    assert audit["dropped_tickers"] == ["W1", "W3"]
    assert audit["dropped_count"] == 2
    assert audit["actual_pool_by_bucket"] == {"aplus": 1, "watch": 1}


def test_lever1_cap_none_excess_sorts_last(lever1_db):
    # (b) A None excess sorts LAST: it is dropped before any numeric row,
    # including a NEGATIVE one (so a None-as-0.0 key would wrongly keep W1
    # over W3's -0.20).
    rs = {"AAA": (None, 0.20, _LIVE), "W1": (None, None, _LIVE),
          "W2": (None, 0.50, _LIVE), "W3": (None, -0.20, _LIVE)}
    conn, audit = _run_capped(lever1_db, watch=("W1", "W2", "W3"),
                              rs=rs, cap=2)
    assert _detected(conn) == {"AAA", "W2", "W3"}
    assert audit["dropped_tickers"] == ["W1"]
    assert audit["dropped_count"] == 1


def test_lever1_cap_zero_excess_is_a_value_not_none(lever1_db):
    # (e) An excess of exactly 0.0 is a VALUE, not a missing one: it ranks
    # above a negative excess and above None. A truthiness key such as
    # (not x, -(x or 0.0), ticker) would put 0.0 in the None group and keep W2.
    rs = {"AAA": (None, 0.20, _LIVE), "W1": (None, 0.0, _LIVE),
          "W2": (None, -0.10, _LIVE), "W3": (None, None, _LIVE)}
    conn, audit = _run_capped(lever1_db, watch=("W1", "W2", "W3"),
                              rs=rs, cap=1)
    assert _detected(conn) == {"AAA", "W1"}
    assert audit["dropped_tickers"] == ["W2", "W3"]


def test_lever1_cap_equal_excess_tiebreak_ticker_asc(lever1_db, monkeypatch):
    # (c) Equal excess -> ticker ASC decides. The production reader returns
    # rows ORDER BY ticker, which would hide a missing tiebreak behind a
    # stable sort, so the reader is wrapped to hand rows back REVERSED.
    import swing.data.repos.candidates as cand_repo
    real = cand_repo.fetch_candidates_for_run
    monkeypatch.setattr(cand_repo, "fetch_candidates_for_run",
                        lambda conn, run_id: list(reversed(real(conn, run_id))))
    rs = {"AAA": (None, 0.20, _LIVE), "W1": (None, 0.30, _LIVE),
          "W2": (None, 0.30, _LIVE), "W3": (None, 0.30, _LIVE)}
    conn, audit = _run_capped(lever1_db, watch=("W1", "W2", "W3"),
                              rs=rs, cap=2)
    assert _detected(conn) == {"AAA", "W1", "W2"}
    assert audit["dropped_tickers"] == ["W3"]


@pytest.mark.parametrize("rs_ranks", [
    # rs_rank DESC would keep W1 (95); the excess winner is W2.
    {"W1": 95, "W2": 10},
    # rs_rank ASC (the pre-fix key) would keep W1 (10); the winner is W2.
    {"W1": 10, "W2": 95},
], ids=["rs_rank_desc_disagrees", "rs_rank_asc_disagrees"])
def test_lever1_cap_rs_rank_populated_is_not_the_key(lever1_db, rs_ranks):
    # (d) rs_rank POPULATED and disagreeing with the excess in BOTH directions:
    # the excess decides either way, so rs_rank is not the key.
    rs = {"AAA": (50, 0.20, "universe"),
          "W1": (rs_ranks["W1"], 0.05, "universe"),
          "W2": (rs_ranks["W2"], 0.90, "universe")}
    conn, audit = _run_capped(lever1_db, watch=("W1", "W2"), rs=rs, cap=1)
    assert _detected(conn) == {"AAA", "W2"}
    assert audit["dropped_tickers"] == ["W1"]


def test_lever1_cap_must_be_positive():
    # Codex R2 MAJOR: cap=0 is rejected by the real frozen PipelineConfig
    # (None = uncapped; >=1 = a real cap). Prevents the cap from colliding with
    # the empty-pool audit.
    from swing.config import PipelineConfig
    with pytest.raises(ValueError):
        PipelineConfig(detect_watch_pool_cap=0)
    assert PipelineConfig(detect_watch_pool_cap=1).detect_watch_pool_cap == 1
    assert PipelineConfig().detect_watch_pool_cap is None


# --- Lever 2: dormant OBSERVE-side watch-origin pre-fetch shed ---------------
from unittest.mock import patch  # noqa: E402

from swing.data.models import PatternForwardObservation  # noqa: E402
from swing.data.repos.pattern_forward_observations import (  # noqa: E402
    get_observations_for_detection, insert_observation)
from tests.pipeline.conftest_temporal import (  # noqa: E402
    _cfg, _FakeLease, _plant_detection, _stub_window)

_OBS = "2026-05-29"   # the run DATA cutoff (observation_date)


def _drive_observe(cfg, lease, warnings, cache_tickers=("AAA",)):
    cache = _StubOhlcvCache({t: _build_bars() for t in cache_tickers})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_=_OBS)):
        with patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS):
            from swing.pipeline.runner import _step_pattern_observe
            _step_pattern_observe(cfg=cfg, lease=lease, ohlcv_cache=cache,
                                  run_warnings=warnings)


def test_lever2_dormant_default_no_shed(tmp_db_at_head, tmp_path):
    # Both watch-window knobs None -> a watch-origin detection (sessions=10) is
    # still observed under the inherited aplus window (30); no shed audit.
    conn, db_path = tmp_db_at_head
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-15",
                              bucket="watch")  # 10 sessions to _OBS
    cfg = _cfg(tmp_path, db_path)
    assert cfg.pipeline.observe_max_pending_window_sessions_watch is None
    warnings: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), warnings)
    assert len(get_observations_for_detection(conn, det_id)) == 1   # observed
    assert not [w for w in warnings if w.get("shed_count")]         # no shed


def test_lever2_active_shed_pending_state(tmp_db_at_head, tmp_path, monkeypatch):
    # pending_watch=5; a PENDING watch detection at sessions=10 (>5) is shed:
    # no fetch, no observation row, a shed audit.
    conn, db_path = tmp_db_at_head
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-15",
                              bucket="watch")  # 10 sessions
    cfg = _cfg(tmp_path, db_path)
    cfg.pipeline.observe_max_pending_window_sessions_watch = 5
    calls: list[str] = []
    import swing.pipeline.runner as R
    real = R._bar_for_date
    monkeypatch.setattr(R, "_bar_for_date",
                        lambda *a, **k: calls.append(a[2]) or real(*a, **k))
    warnings: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), warnings)
    assert get_observations_for_detection(conn, det_id) == []   # no obs row
    assert "AAA" not in calls                                   # no fetch
    audit = next(w for w in warnings
                 if w["step"] == "pattern_observe" and "shed_count" in w)
    assert audit["shed_count"] == 1


def test_lever2_triggered_open_uses_pending_plus_post_horizon(tmp_db_at_head, tmp_path):
    # pending_watch=5 + post_watch=5 -> horizon 10 for a triggered_open watch
    # detection. At sessions=8 (<10): NOT shed (observed). At sessions=12 (>10):
    # shed. (status-aware horizon -- Codex R1 MAJOR #4.)
    conn, db_path = tmp_db_at_head

    def _seed_triggered(ticker, data_asof):
        det_id = _plant_detection(conn, ticker=ticker, data_asof_date=data_asof,
                                  bucket="watch")
        with conn:
            insert_observation(conn, PatternForwardObservation(
                observation_id=None, detection_id=det_id,
                observation_date="2026-05-22",
                ohlc_today_json='{"open":10.2,"high":10.5,"low":9.8,'
                                '"close":10.2,"volume":1,"provider":"yfinance"}',
                status="triggered_open", sessions_since_detection=3,
                created_at="2026-05-22T00:00:00Z",
                status_change_event="entry_fired"))
        return det_id

    # Scenario A: sessions=8 (data_asof 2026-05-19) < horizon 10 -> NOT shed.
    det_a = _seed_triggered("AAA", "2026-05-19")
    cfg = _cfg(tmp_path, db_path)
    cfg.pipeline.observe_max_pending_window_sessions_watch = 5
    cfg.pipeline.observe_max_post_trigger_window_sessions_watch = 5
    warnings_a: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), warnings_a)
    # New observation appended (prior + new = 2); not shed.
    assert len(get_observations_for_detection(conn, det_a)) == 2
    assert not [w for w in warnings_a if w.get("shed_count")]

    # Scenario B: sessions=12 (data_asof 2026-05-13) > horizon 10 -> shed.
    det_b = _seed_triggered("BBB", "2026-05-13")
    warnings_b: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 2, _OBS), warnings_b,
                   cache_tickers=("AAA", "BBB"))
    # det_b shed: still only the seeded prior observation (no new row).
    assert len(get_observations_for_detection(conn, det_b)) == 1
    shed = next(w for w in warnings_b
                if w["step"] == "pattern_observe" and "shed_count" in w)
    assert shed["shed_count"] == 1


def test_lever2_repeated_runs_do_not_refetch_shed(tmp_db_at_head, tmp_path, monkeypatch):
    # Two observe runs with the shed active: _bar_for_date never called for the
    # shed detection on EITHER run (cheap re-skip; no fetch).
    conn, db_path = tmp_db_at_head
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-15",
                              bucket="watch")  # 10 sessions
    cfg = _cfg(tmp_path, db_path)
    cfg.pipeline.observe_max_pending_window_sessions_watch = 5
    calls: list[str] = []
    import swing.pipeline.runner as R
    real = R._bar_for_date
    monkeypatch.setattr(R, "_bar_for_date",
                        lambda *a, **k: calls.append(a[2]) or real(*a, **k))
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), [])
    _drive_observe(cfg, _FakeLease(db_path, 2, _OBS), [])
    assert calls == []                                          # never fetched
    assert get_observations_for_detection(conn, det_id) == []
