# tests/research/minervini_exemplar_recall/test_detector_eval.py
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing.patterns.foundation import current_stage


def _uptrend_bars(n=300, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    closes = []
    price = 50.0
    for i in range(n):
        # gentle zig-zag uptrend so generate_candidate_windows emits down-swings.
        # Tuned: 1.006/0.994 (not 1.004/0.996) gives ~4.1% per-half-cycle swing,
        # above zigzag's adaptive 3% threshold so the fixture emits >= 2 windows.
        price *= 1.006 if (i // 7) % 2 == 0 else 0.994
        closes.append(price)
    return pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
         "Close": closes, "Volume": [1_000_000] * n},
        index=idx,
    )


def _fake_registry_stage_gated():
    # A fake "vcp" detector: geometric_score = 1.0 iff Stage 2, else 0.0.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Ev:
        geometric_score: float

    def _fake_vcp(bars, window, *, conn=None, ticker=None, asof_date=None):
        score = 1.0 if current_stage(conn, ticker, asof_date) == "stage_2" else 0.0
        return _Ev(geometric_score=score)

    return ((_fake_vcp, "vcp", "fake@v1"),)


def test_selects_last_window(monkeypatch):
    from research.harness.minervini_exemplar_recall import detector_eval

    bars = _uptrend_bars()
    from swing.patterns.foundation import generate_candidate_windows
    windows = generate_candidate_windows(bars, "zigzag_pivot", ticker="AAA", timeframe="daily")
    assert len(windows) >= 2  # fixture must yield multiple windows for this to discriminate
    selected = detector_eval.select_window(windows)
    # WRONG-PATH (windows[0] / all windows): a different anchor.  RIGHT-PATH (windows[-1]).
    assert selected.anchor_date == windows[-1].anchor_date


def test_stage_gate_isolation(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    monkeypatch.setattr(detector_eval, "_REGISTRY", _fake_registry_stage_gated())
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "VCP", "vcp", session, "day", None, "S", "P", "n")

    iso_conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(iso_conn, ticker="AAA", session=session,
                          tt_results=_forced_fail_tt(), mode="isolated")
    v_iso = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=iso_conn)
    assert v_iso.fired_expected_class is True  # isolated -> stage_2 -> fires

    faith_conn = stage_db.build_stage_db(tmp_path / "faith.db")
    stage_db.seed_session(faith_conn, ticker="AAA", session=session,
                          tt_results=_seven_pass_tt(), mode="faithful")
    v_faith = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=faith_conn)
    # 7/8 TT -> undefined stage -> the Stage-2 hard gate zeros the score.
    assert v_faith.fired_expected_class is False


def test_unmapped_has_no_expected_class(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    monkeypatch.setattr(detector_eval, "_REGISTRY", _fake_registry_stage_gated())
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "primary base", "unmapped", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated")
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    assert v.fired_expected_class is None  # unmapped -> excluded from per-detector recall


def test_anchor_mode_limited_flag_for_cup_miss(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    # Fake registry where the cup detector never fires.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Ev:
        geometric_score: float

    def _never(bars, window, *, conn=None, ticker=None, asof_date=None):
        return _Ev(0.0)

    monkeypatch.setattr(detector_eval, "_REGISTRY", ((_never, "cup_with_handle", "fake@v1"),))
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "cup", "cup_with_handle", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated")
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    assert v.fired_expected_class is False
    assert v.h2_anchor_mode_limited_possible is True
    assert "zigzag" in v.h2_anchor_mode_limited_reason.lower()


def test_no_windows_skip_is_not_silent(monkeypatch, tmp_path):
    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    monkeypatch.setattr(detector_eval, "_REGISTRY", _fake_registry_stage_gated())
    # Strictly monotonic up with no down-swing >=3% -> zigzag emits no windows.
    idx = pd.bdate_range(start="2009-01-02", periods=120)
    closes = [100.0 + i for i in range(120)]
    bars = pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                         "Volume": [1_000] * 120}, index=idx)
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "VCP", "vcp", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated")
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    assert v.skip_reason == "no_windows"
    assert v.fired_expected_class is False


# --- helpers ---
def _forced_fail_tt():
    from swing.data.models import CriterionResult
    return tuple(CriterionResult(f"TT{i+1}", "trend_template", "fail") for i in range(8))


def _seven_pass_tt():
    from swing.data.models import CriterionResult
    res = ["pass"] * 7 + ["fail"]
    return tuple(CriterionResult(f"TT{i+1}", "trend_template", res[i]) for i in range(8))


def test_expected_detector_error_surfaced_not_silent(monkeypatch, tmp_path):
    # The documented (expected-class) detector RAISES while another detector returns a positive
    # score. The verdict must surface the error as a distinct skip_reason, NOT silently record a
    # geometry miss (Codex executing-plans R1 major; gotcha #27 never-silent).
    from dataclasses import dataclass

    from research.harness.minervini_exemplar_recall import detector_eval, stage_db
    from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow

    @dataclass(frozen=True)
    class _Ev:
        geometric_score: float

    def _raise_vcp(bars, window, *, conn=None, ticker=None, asof_date=None):
        raise ValueError("vcp detector blew up")

    def _ok_flat(bars, window, *, conn=None, ticker=None, asof_date=None):
        return _Ev(1.0)

    # expected class 'vcp' RAISES; 'flat_base' fires -> failures(1) < attempts(2), so the old code
    # would leave skip_reason None and fired_expected_class False (a SILENT miss).
    monkeypatch.setattr(
        detector_eval,
        "_REGISTRY",
        ((_raise_vcp, "vcp", "fake@v1"), (_ok_flat, "flat_base", "fake@v1")),
    )
    bars = _uptrend_bars()
    session = bars.index[-1].date()
    ex = ExemplarRow("id", "AAA", "AAA", "VCP", "vcp", session, "day", None, "S", "P", "n")
    conn = stage_db.build_stage_db(tmp_path / "iso.db")
    stage_db.seed_session(
        conn, ticker="AAA", session=session, tt_results=_forced_fail_tt(), mode="isolated"
    )
    v = detector_eval.evaluate_h2(exemplar=ex, session=session, exemplar_full=bars, stage_conn=conn)
    # WRONG-PATH (silent): skip_reason None.  RIGHT-PATH: distinct expected_detector_error.
    assert v.skip_reason == "expected_detector_error"
    assert v.fired_expected_class is False
