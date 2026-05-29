"""Phase 14 Sub-bundle 2 T-2.6 -- cross-step temporal-log e2e.

Forward-walk integration across the detect + observe steps (plan section
"Task T-2.6" Step 1). The detect step appends a FROZEN detection (+ a captured
chart whose chain resolves to non-empty bytes); the observe step forward-walks
open detections across simulated sessions with the correct status transitions;
and the detection FACTS are unchanged across observe runs (append-only).

Anti-drift: the seed helpers use the REAL candidate/eval-run/detection repos
and the steps are driven through the production ``_step_pattern_detect`` /
``_step_pattern_observe`` (NOT hand-built INSERTs).

Note (deviation from the plan section "Task T-2.6" Step 1 LITERAL listing): the
shared ``_build_bars`` fixture (a seeded mild uptrend) drives the production
detectors to freeze ``pivot_price = 0.0`` with empty contractions for every
emitted class -- so a real detect-step detection's status machine triggers
immediately (``high >= 0.0``) and can NEVER sit at ``pending``. The literal
listing assumed a single ``vcp`` detection with ``pivot_price = 10.0``, which
the fixture does not produce. To exercise a GENUINE ``pending ->
triggered_open`` transition with meaningful structural thresholds, the
forward-walk assertions run against a PLANTED detection (``_plant_detection``,
pivot 10.0 / invalidation 8.0, ``source='pipeline'``) -- the same status
machine, with real anchors. The detect-step detection still carries the
chart-chain + append-only frozen-fact assertions. This keeps every Step-1
acceptance behavior (frozen detection + chart_render_id, chart chain resolves,
pending -> triggered_open with entry_fired, append-only facts) while staying
correct against the production detector output.
"""
from __future__ import annotations

from unittest.mock import patch

from swing.data.repos.pattern_detection_events import list_detection_events
from swing.data.repos.pattern_forward_observations import (
    get_observations_for_detection,
)
from swing.pipeline.runner import _step_pattern_observe

# Reuse the proven harness from the shared temporal conftest module
# (one shared fixture set across T-2.4 / T-2.5 / T-2.6).
from tests.pipeline.conftest_temporal import (  # noqa: F401  (tmp_db_v22 fixture)
    _FakeLease,
    _StubOhlcvCache,
    _build_bars,
    _drive_detect,
    _plant_detection,
    _seed_aplus_candidate_and_run,
    _stub_window,
    tmp_db_v22,
)


def test_detect_then_forward_walk_e2e(tmp_db_v22):
    conn, db_path = tmp_db_v22

    # 1. Detect: one aplus candidate -> frozen detections + captured charts.
    _conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(
        (conn, db_path), ticker="AAA", data_asof_date="2026-05-27")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    det = list_detection_events(conn, ticker="AAA")[0]
    assert det.chart_render_id is not None
    facts_before = (det.structural_anchors_json, det.composite_score,
                    det.data_asof_date)
    # The chart chain resolves to non-empty bytes.
    blen = conn.execute(
        "SELECT length(chart_svg_bytes) FROM chart_renders WHERE id = ?",
        (det.chart_render_id,)).fetchone()[0]
    assert blen and blen > 0

    # Plant a detection with REAL structural thresholds so the status machine
    # can exhibit a genuine pending -> triggered_open transition (see module
    # docstring: the _build_bars detect-step detections freeze pivot 0.0).
    planted_id = _plant_detection(
        conn, ticker="BBB", data_asof_date="2026-05-27",
        pivot=10.0, invalidation=8.0)

    bars = {"AAA": _build_bars(), "BBB": _build_bars()}

    # 2. Session N (close 9.0: below pivot 10.0, above invalidation 8.0)
    #    -> 'pending'.
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_="2026-05-28")):
        with patch("swing.pipeline.runner.lease_data_asof",
                   return_value="2026-05-28"):
            _step_pattern_observe(
                cfg=cfg, lease=_FakeLease(db_path, 2, "2026-05-28"),
                ohlcv_cache=_StubOhlcvCache(bars), run_warnings=[])
    chain = get_observations_for_detection(conn, planted_id)
    assert chain[-1].status == "pending"
    assert chain[-1].status_change_event is None

    # 3. Session N+1 (high 10.9 >= pivot 10.0) -> 'triggered_open' /
    #    'entry_fired'.
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(10.5, high=10.9, date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof",
                   return_value="2026-05-29"):
            _step_pattern_observe(
                cfg=cfg, lease=_FakeLease(db_path, 3, "2026-05-29"),
                ohlcv_cache=_StubOhlcvCache(bars), run_warnings=[])
    chain = get_observations_for_detection(conn, planted_id)
    assert chain[-1].status == "triggered_open"
    assert chain[-1].status_change_event == "entry_fired"
    # The forward-walk is APPEND-ONLY: both sessions are retained in order.
    assert [o.observation_date for o in chain] == ["2026-05-28", "2026-05-29"]

    # 4. The detect-step detection FACTS are unchanged across observe runs
    #    (the observe step appends observations; it never recomputes detection
    #    facts).
    det_after = list_detection_events(conn, ticker="AAA")[0]
    assert (det_after.structural_anchors_json, det_after.composite_score,
            det_after.data_asof_date) == facts_before
    # No detection rows were added/removed by the observe runs.
    assert len(list_detection_events(conn, ticker="AAA")) == 5


def test_e2e_module_ascii_only():
    """Per gotcha #32/#16 -- this test module is ASCII-only."""
    import pathlib
    pathlib.Path(__file__).read_text(encoding="utf-8").encode("ascii")
