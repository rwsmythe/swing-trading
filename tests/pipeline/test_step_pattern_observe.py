"""T-2.5 tests: _advance_status status machine (Step 2) + _step_pattern_observe
integration (Step 6). Fixtures imported from conftest_temporal."""
import pytest

from swing.pipeline.runner import _advance_status

# Shared temporal-log fixtures (plan section L.4).
from tests.pipeline.conftest_temporal import (  # noqa: F401
    _StubOhlcvCache,
    _build_bars,
    _cfg,
    _FakeLease,
    _plant_detection,
    _stub_window,
    tmp_db_v22,
)


class _Det:
    """Minimal detection stub carrying the anchors the status machine reads."""
    def __init__(self, pivot=10.0, invalidation=8.0):
        import json
        self.pattern_class = "vcp"
        self.data_asof_date = "2026-05-28"
        self.structural_anchors_json = json.dumps(
            {"evidence": {"pivot_price": pivot, "base_top_price": pivot,
                          "contractions": [{"low": invalidation}]}})


def _bar(high, low, close, open_=None):
    return {"open": open_ or close, "high": high, "low": low,
            "close": close, "volume": 1_000_000}


def test_pending_stays_pending_within_window():
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


def test_pending_to_triggered_open_on_pivot_breakout():
    status, ev = _advance_status(
        _Det(pivot=10.0), prev=None, bar=_bar(10.5, 9.8, 10.2),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev == "entry_fired"


def test_pending_to_invalidated_on_structural_break():
    status, ev = _advance_status(
        _Det(invalidation=8.0), prev=None, bar=_bar(8.2, 7.5, 7.8),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_pending_to_expired_at_window_threshold():
    # AT threshold (30) without trigger -> expired (>= boundary).
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "time_exit"


def test_pending_below_window_threshold_not_expired():
    # Under threshold (29) -> still pending (distinguishes >= boundary).
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=29, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


class _PrevOpen:
    status = "triggered_open"


def test_triggered_open_to_expired_at_horizon():
    # AT pending+post_trigger (90) -> horizon reached.
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=90, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "observation_horizon_reached"


def test_triggered_open_stays_open_within_horizon():
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=50, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev is None


def test_triggered_open_at_89_stays_open():
    # Immediately UNDER the horizon (89 = max_pending+max_post_trigger-1 = 90-1):
    # 89 >= 90 is False -> stays open. Pins the >= boundary against an off-by-one
    # regression (e.g. > max_pending+max_post_trigger-1 would wrongly expire 89).
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=89, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev is None


# --- Same-bar conflict precedence (Codex chain #2 Major #1 + #3) ---

def test_same_bar_breakout_and_invalidation_resolves_to_invalidated():
    # high 10.5 >= pivot 10.0 (intraday breakout) AND close 7.5 < invalidation
    # 8.0 (confirmed shape break) -> INVALIDATION WINS (failed breakout).
    status, ev = _advance_status(
        _Det(pivot=10.0, invalidation=8.0), prev=None,
        bar=_bar(10.5, 7.4, 7.5),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_breakout_at_max_pending_boundary_fires_not_expires():
    # high >= pivot exactly at sessions == max_pending -> trigger wins over expiry.
    status, ev = _advance_status(
        _Det(pivot=10.0), prev=None, bar=_bar(10.5, 9.8, 10.2),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev == "entry_fired"


def test_invalidation_at_max_pending_boundary_wins_over_expiry():
    status, ev = _advance_status(
        _Det(invalidation=8.0), prev=None, bar=_bar(8.2, 7.5, 7.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_non_triggering_bar_at_max_pending_expires():
    # neither breakout nor invalidation at the boundary -> expired.
    status, ev = _advance_status(
        _Det(pivot=10.0, invalidation=8.0), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "time_exit"


def test_near_miss_breakout_stays_pending():
    # high 9.9 < pivot 10.0 -> NOT a breakout (distinguishes the >= predicate).
    status, ev = _advance_status(
        _Det(pivot=10.0, invalidation=8.0), prev=None, bar=_bar(9.9, 9.0, 9.5),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


def test_terminal_prev_status_raises():
    # Defensive guard (Major #4): a terminal prev status must never reach here.
    class _PrevTerminal:
        status = "invalidated"
    with pytest.raises(ValueError, match="terminal prev status"):
        _advance_status(_Det(), prev=_PrevTerminal(), bar=_bar(9.0, 8.5, 8.8),
                        sessions_since_detection=5, max_pending=30, max_post_trigger=60)


# --- Step 6: _step_pattern_observe integration set ---------------------------

import json  # noqa: E402

from unittest.mock import patch  # noqa: E402

from swing.data.repos.pattern_forward_observations import (  # noqa: E402
    get_observations_for_detection,
)
from swing.pipeline.runner import _step_pattern_observe  # noqa: E402


def test_observation_appended_with_provider_tag(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, provider="yfinance", date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    chain = get_observations_for_detection(conn, det_id)
    assert len(chain) == 1
    bar = json.loads(chain[0].ohlc_today_json)
    assert bar["provider"] == "yfinance"            # OQ-17 by FIELD
    assert set(bar) == {"open", "high", "low", "close", "volume", "provider"}
    assert chain[0].observation_date == "2026-05-29"
    assert chain[0].status == "pending"             # below pivot, above invalidation


def test_pending_to_triggered_open_on_breakout(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28", pivot=10.0)
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, 1, "2026-05-29")
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(10.2, high=10.5, date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=[])
    obs = get_observations_for_detection(conn, det_id)[0]
    assert obs.status == "triggered_open" and obs.status_change_event == "entry_fired"


def test_sessions_since_detection_counts_from_data_asof(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-22")  # Fri
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, 1, "2026-05-29")
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_="2026-05-29")):  # next Fri
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=[])
    obs = get_observations_for_detection(conn, det_id)[0]
    # 5 business days from 2026-05-22 (excl) to 2026-05-29 (incl).
    assert obs.sessions_since_detection == 5


def test_idempotent_same_day_reobservation(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, 1, "2026-05-29")
    stub = _stub_window(9.0, date_="2026-05-29")
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=stub):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
            _step_pattern_observe(cfg=cfg, lease=lease,  # re-run same observation_date
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    assert len(get_observations_for_detection(conn, det_id)) == 1  # no dup; no UNIQUE error


def test_empty_open_pool_warns(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22  # no detections planted
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, 1, "2026-05-29")
    warnings: list[dict] = []
    with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
        _step_pattern_observe(cfg=cfg, lease=lease,
                              ohlcv_cache=_StubOhlcvCache({}), run_warnings=warnings)
    assert any(w["step"] == "pattern_observe" and w["actual_open_pool"] == 0
               for w in warnings)


def test_no_bar_for_date_warns_and_skips(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, 1, "2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    empty = (pd.DataFrame(columns=["asof_date", "open", "high", "low", "close", "volume"]), {})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=empty):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    assert get_observations_for_detection(conn, det_id) == []
    assert any(w.get("reason") == "no bar for observation_date" for w in warnings)


def test_missing_provenance_treated_as_no_bar(tmp_db_v22, tmp_path):
    # Codex chain #1 Major #2: _bar_for_date must NOT fabricate provider
    # provenance. A matching df row WITH an EMPTY provenance dict has no
    # VERIFIED provider -> treat as no-bar (skip + #27 warning), never
    # fabricate "yfinance" into the append-only log.
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    # A real matching row for observation_date BUT empty provenance dict.
    df = pd.DataFrame([{
        "asof_date": "2026-05-29", "open": 9.0, "high": 9.0,
        "low": 9.0, "close": 9.0, "volume": 1_000_000.0}])
    no_prov = (df, {})  # row present, provenance missing for the date
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=no_prov):
        with patch("swing.pipeline.runner.lease_data_asof",
                   return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    # NO observation appended (missing-provenance row treated as no-bar).
    assert get_observations_for_detection(conn, det_id) == []
    assert any(w.get("reason") == "no bar for observation_date" for w in warnings)


def test_terminal_detection_not_observed_at_step_boundary(tmp_db_v22, tmp_path):
    # Codex chain #2 R2 Minor #3: the terminal-guard invariant lives at the
    # STEP boundary -- list_observable_detections excludes a detection whose
    # latest status is terminal, so _step_pattern_observe never appends a new
    # row for it (and _advance_status is never reached -> no ValueError).
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-27")
    from swing.data.models import PatternForwardObservation
    from swing.data.repos.pattern_forward_observations import insert_observation
    with conn:
        insert_observation(conn, PatternForwardObservation(
            observation_id=None, detection_id=det_id, observation_date="2026-05-28",
            ohlc_today_json='{"open":1,"high":1,"low":1,"close":1,"volume":1,"provider":"yfinance"}',
            status="expired", sessions_since_detection=1,
            created_at="2026-05-28T00:00:00Z",
            status_change_event="observation_horizon_reached"))
    cfg = _cfg(tmp_path, db_path)
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 2, "2026-05-29"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=[])
    # Still only the terminal observation -- no new row appended (no raise).
    assert len(get_observations_for_detection(conn, det_id)) == 1


def test_forward_walk_freezes_past_bar(tmp_db_v22, tmp_path):
    # #26/#37-by-construction discriminator: a past observation's frozen
    # ohlc_today_json is NEVER re-read from a later archive.
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-27")
    cfg = _cfg(tmp_path, db_path)
    # Session N = 2026-05-28: record close 9.00.
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.00, date_="2026-05-28")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-28"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 1, "2026-05-28"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    obs_N_before = json.loads(get_observations_for_detection(conn, det_id)[0].ohlc_today_json)

    # Session N+1 = 2026-05-29: the archive NOW reports a DIFFERENT close for N
    # (simulating gotcha #26 drift) -- but observe at N+1 only records N+1.
    def _drifted(ticker, *, start, end, cache_dir):
        import pandas as pd
        rows = [{"asof_date": "2026-05-28", "open": 9.99, "high": 9.99, "low": 9.99,
                 "close": 9.99, "volume": 1e6},  # DRIFTED date-N bar
                {"asof_date": "2026-05-29", "open": 9.10, "high": 9.10, "low": 9.10,
                 "close": 9.10, "volume": 1e6}]
        df = pd.DataFrame([r for r in rows if start <= r["asof_date"] <= end])
        return df, {r["asof_date"]: "yfinance" for _, r in df.iterrows()}
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", side_effect=_drifted):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 2, "2026-05-29"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    chain = get_observations_for_detection(conn, det_id)
    obs_N_after = json.loads(chain[0].ohlc_today_json)  # the date-N row
    assert obs_N_after == obs_N_before          # FROZEN -- #26 cannot occur
    assert obs_N_after["close"] == 9.00         # NOT the drifted 9.99
    assert chain[1].observation_date == "2026-05-29" and json.loads(chain[1].ohlc_today_json)["close"] == 9.10


def test_non_finite_ohlc_skips_with_warning(tmp_db_v22, tmp_path):
    """Phase 18 18-A PRIMARY regression (the REAL 06-10 shape): a completed-session
    bar with Close=NaN, O/H/L/V finite, provider=yfinance must be SKIPPED with a
    `non_finite_ohlc` warning -- NO observation row enters the append-only log.

    PRE-FIX arithmetic: _bar_for_date returns the bar with close=NaN (O/H/L
    finite). With NO finiteness check, _advance_status sees high=11.0 >= pivot=10.0
    (the `close < invalidation` arm is `NaN < 8.0` -> False), returning
    ('triggered_open','entry_fired') -- a NaN-close bar driving a PHANTOM trigger.
    build_ohlc_today_json then serializes `"close": NaN` -> 1 row inserted, NO
    warning. POST-FIX: the caller's is_finite_ohlc pre-check skips BEFORE
    _advance_status -> 0 rows, 1 `non_finite_ohlc` warning. The row-count
    assertion distinguishes the two paths (and the skip also prevents the phantom
    trigger)."""
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")  # pivot 10.0
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    # O/H/L/V finite, Close=NaN, provider yfinance (the exact 06-10 artifact).
    nan_close = (
        pd.DataFrame([{"asof_date": "2026-05-29", "open": 10.0, "high": 11.0,
                       "low": 9.0, "close": float("nan"), "volume": 1_000_000.0}]),
        {"2026-05-29": "yfinance"})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=nan_close):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    assert get_observations_for_detection(conn, det_id) == []   # no NaN row locked
    assert any(w.get("reason") == "non_finite_ohlc" and w.get("ticker") == "AAA"
               for w in warnings)


def test_volume_only_nan_still_observed(tmp_db_v22, tmp_path):
    """Phase 18 18-A discriminator: a completed bar with finite OHLC but NaN
    volume is NOT skipped (Volume-NaN exemption reconciled -- the caller's
    is_finite_ohlc gates OHLC only). One row is appended; the engine ignores
    volume so the NaN volume is inert. An impl that gated volume would FAIL this."""
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    vol_nan = (
        pd.DataFrame([{"asof_date": "2026-05-29", "open": 9.0, "high": 9.0,
                       "low": 9.0, "close": 9.0, "volume": float("nan")}]),
        {"2026-05-29": "yfinance"})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=vol_nan):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    assert len(get_observations_for_detection(conn, det_id)) == 1
    assert not any(w.get("reason") == "non_finite_ohlc" for w in warnings)
