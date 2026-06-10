from __future__ import annotations

import json
from pathlib import Path

from research.harness.shadow_expectancy.run import run_harness
from tests.research.shadow_expectancy.testkit import (
    insert_candidate,
    insert_detection,
    insert_observation,
    insert_pipeline_run,
    make_db,
)

# Per-pattern geometric pivots mirroring run 89: vcp/flat_base/htf carry a real level, cup/dbw
# carry 0.0. NONE equals candidate.pivot -- the load-bearing real-shape fact (spec 1.2 / 7.1).
_BULZ_PIVOTS = {
    "vcp": 49.89, "flat_base": 49.89, "high_tight_flag": 49.89,
    "cup_with_handle": 0.0, "double_bottom_w": 0.0,
}
# Two identical frozen bars, both VALID OHLC and BELOW candidate.pivot 56.09. The second bar is
# the real run-89 BULZ observation (2026-06-08 o=43.795 h=44.57 l=42.6 c=43.5); the earlier draft
# used (47.5, 44.57, 44.0, 44.2) which has high < open -> validate_bars would route it to
# invalid_ohlc before the recompute, masking the never_triggered assertion. Both bars satisfy
# low <= min(open,close) and high >= max(open,close).
_BULZ_BARS = [
    ("2026-06-05", 47.0, 48.16, 46.5, 47.8),
    ("2026-06-08", 43.795, 44.57, 42.6, 43.5),
]


def _assert_no_look_ahead(conn):
    # spec 4: every forward observation satisfies data_asof_date < observation_date.
    rows = conn.execute(
        "SELECT e.data_asof_date, o.observation_date "
        "FROM pattern_forward_observations o "
        "JOIN pattern_detection_events e ON e.detection_id = o.detection_id"
    ).fetchall()
    assert rows, "fixture seeded no observations"
    for data_asof_date, observation_date in rows:
        assert data_asof_date < observation_date, (
            f"look-ahead: data_asof_date={data_asof_date} >= "
            f"observation_date={observation_date}")


def _seed_bulz_run89(conn):
    # candidate.pivot 56.09; bucket watch with a proximity_20ma miss -> attributes to H2.
    eval_id = insert_candidate(
        conn, ticker="BULZ", bucket="watch", pivot=56.09, initial_stop=50.0, close=48.16,
        criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    for pattern_class, pivot in _BULZ_PIVOTS.items():
        det_id = insert_detection(
            conn, ticker="BULZ", pipeline_run_id=pr_id, pivot=pivot,
            data_asof_date="2026-06-04", detection_date="2026-06-05",
            pattern_class=pattern_class)
        for (obs_date, o, h, low, close) in _BULZ_BARS:
            insert_observation(conn, det_id, obs_date, o=o, h=h, l=low, c=close,
                               status="pending")
    conn.commit()


def test_bulz_run89_routes_never_triggered_not_no_canonical(tmp_path):
    # Regression for the live bug: the real BULZ shape (5 detections, geometric pivots never ==
    # candidate.pivot, all watch) must route HONESTLY to never_triggered -- never the retired
    # no_canonical_detection -- because no forward high reaches candidate.pivot 56.09.
    conn = make_db(tmp_path)
    _seed_bulz_run89(conn)
    _assert_no_look_ahead(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h2["never_triggered"] == 1
    # the retired reason cannot appear anywhere.
    assert "no_canonical_detection" not in f["unattributed"]
    assert "inconsistent_trigger_state" not in f["unattributed"]
    dl = f["detection_level"]
    assert dl["total_detections"] == 5 and dl["unique_signals"] == 1
    assert dl["collapsed_duplicate_detection"] == 4   # group_size - 1


def _seed_breakout_prices_through(conn):
    # candidate.pivot 50.0; geometric detection pivot 49.89 (!= candidate). bar1 high 49 < 50
    # (pre-entry, skipped); bar2 high 52 >= 50 (entry); bar3 stops out. Hand-verified bracket
    # below.
    eval_id = insert_candidate(
        conn, ticker="BRKT", bucket="watch", pivot=50.0, initial_stop=47.0, close=48.5,
        criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(
        conn, ticker="BRKT", pipeline_run_id=pr_id, pivot=49.89,
        data_asof_date="2026-06-04", detection_date="2026-06-05", pattern_class="vcp")
    insert_observation(conn, det_id, "2026-06-05", o=48.0, h=49.0, l=47.0, c=48.5,
                       status="pending")
    insert_observation(conn, det_id, "2026-06-06", o=50.0, h=52.0, l=49.5, c=51.0,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-07", o=49.0, h=49.2, l=48.0, c=48.5,
                       status="triggered_open")
    conn.commit()


def test_breakout_prices_end_to_end(tmp_path):
    # spec 6.1: a real-shaped fixture where a forward high EXCEEDS candidate.pivot prices a trade
    # all the way through the simulator. Hand-verified:
    #   entry_fill = max(50.0, open 50.0) = 50.0; initial_stop = entry_bar.low = 49.5; rps = 0.5.
    #   forward = [bar3]; bar3.low 48.0 <= stop 49.5 -> initial_stop.
    #   realistic fill = min(stop 49.5, open 49.0) = 49.0 -> R = (49.0-50.0)/0.5 = -2.0
    #   favorable fill = 49.5 -> R = (49.5-50.0)/0.5 = -1.0
    #   entry_bar.close 51.0 >= 50.0 -> NOT weak_close.
    conn = make_db(tmp_path)
    _seed_breakout_prices_through(conn)
    _assert_no_look_ahead(conn)
    out = tmp_path / "out"
    results, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                          source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h2["closed"] == 1
    rows = Path(results).read_text(encoding="utf-8").splitlines()
    # header + one data row; verify the hand-computed bracket and the weak-close flag.
    data = rows[1].split(",")
    header = rows[0].split(",")
    rec = dict(zip(header, data, strict=True))
    assert rec["exit_reason"] == "initial_stop"
    assert float(rec["realistic_r"]) == -2.0
    assert float(rec["favorable_r"]) == -1.0
    assert rec["entry_bar_weak_close"] == "False"


def _seed_mixed_first_trigger(conn):
    # spec 1.3 regression: a cup detection (geometric pivot 0.0, which under the OLD observe-step
    # "triggered" on bar 1) and a vcp detection (geometric pivot 49.89, never) in the same group.
    # The vcp chain is LONGER (2 bars); the cup chain is a 1-bar strict prefix. Entry is
    # recomputed off candidate.pivot 10.0 -> the differing geometric trigger sessions are
    # irrelevant and the signal is NOT excluded.
    eval_id = insert_candidate(
        conn, ticker="MIX", bucket="watch", pivot=10.0, initial_stop=9.0, close=10.0,
        criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    # vcp: 2-bar chain (the canonical bar source).
    vcp_id = insert_detection(
        conn, ticker="MIX", pipeline_run_id=pr_id, pivot=49.89,
        data_asof_date="2026-06-04", detection_date="2026-06-05", pattern_class="vcp")
    insert_observation(conn, vcp_id, "2026-06-05", o=10.0, h=10.5, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, vcp_id, "2026-06-06", o=10.3, h=10.8, l=10.1, c=10.6,
                       status="triggered_open")
    # cup: 1-bar strict prefix (identical bar 1), geometric pivot 0.0.
    cup_id = insert_detection(
        conn, ticker="MIX", pipeline_run_id=pr_id, pivot=0.0,
        data_asof_date="2026-06-04", detection_date="2026-06-05",
        pattern_class="cup_with_handle")
    insert_observation(conn, cup_id, "2026-06-05", o=10.0, h=10.5, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    conn.commit()


def test_mixed_first_trigger_not_excluded_and_longest_chain_is_bar_source(tmp_path):
    conn = make_db(tmp_path)
    _seed_mixed_first_trigger(conn)
    _assert_no_look_ahead(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline", horizon_sessions=1)
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    # NOT excluded: no unattributed reason fired (the retired inconsistent_trigger_state is gone).
    assert f["unattributed"] == {} or sum(f["unattributed"].values()) == 0
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    # entry on bar1 (high 10.5 >= 10.0), one forward bar -> open at horizon=1. The 2-bar (vcp)
    # chain was the bar source; a 1-bar bar source would have been insufficient_forward_depth.
    assert h2["open_at_horizon"] == 1
    assert h2["excluded"].get("insufficient_forward_depth", 0) == 0
    dl = f["detection_level"]
    assert dl["total_detections"] == 2 and dl["unique_signals"] == 1
    assert dl["collapsed_duplicate_detection"] == 1
