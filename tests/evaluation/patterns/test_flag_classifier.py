import pandas as pd
import numpy as np
from swing.evaluation.patterns.flag_classifier import classify_flag


def _flat_bars(n: int, start_close: float = 100.0) -> pd.DataFrame:
    """Build n bars with constant OHLCV — used as a no-detect baseline."""
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": start_close, "High": start_close, "Low": start_close,
         "Close": start_close, "Volume": 1_000_000.0}, index=idx,
    )


def test_module_imports():
    from swing.evaluation.patterns.flag_classifier import (
        FlagClassificationResult,
        classify_flag,
    )

    assert callable(classify_flag)
    assert FlagClassificationResult is not None


def test_data_window_gate_below_threshold_returns_none():
    res = classify_flag(_flat_bars(35))
    assert res.detected is False
    assert res.pattern == "none"


def test_data_window_gate_at_threshold_enters_search():
    # 36 bars — minimum. Flat bars still fail later gates, but classify_flag
    # MUST run the search instead of short-circuiting.
    res = classify_flag(_flat_bars(36))
    assert res.detected is False
    # components_json must populate (best-attempted baseline) — proof the
    # search ran and was not short-circuited by data_window.
    assert "pole_M" in res.components


from tests.evaluation.patterns._synthetic import make_flag_bars


def test_default_synthetic_flag_is_detected():
    bars = make_flag_bars()
    res = classify_flag(bars)
    assert res.detected is True
    assert res.pattern == "flag"
    assert 0.0 < res.confidence <= 1.0


def test_pole_gain_gate_at_threshold_below_rejects():
    bars = make_flag_bars(pole_gain_pct=0.299)
    res = classify_flag(bars)
    assert res.detected is False
    assert res.pattern == "none"


def test_pole_gain_gate_at_threshold_above_passes():
    bars = make_flag_bars(pole_gain_pct=0.301)
    res = classify_flag(bars)
    assert res.detected is True
    assert res.pattern == "flag"


def test_pole_gain_gate_is_threshold_sensitive():
    """Discriminating-test discipline: passing a tightened threshold via
    cfg argument must flip a previously-passing fixture to rejection.
    Proves the test pair is actually sensitive to the threshold value."""
    from swing.config import ClassifierConfig
    bars = make_flag_bars(pole_gain_pct=0.31)
    # Default cfg → passes.
    assert classify_flag(bars).detected is True
    # Tightened cfg → rejects.
    cfg = ClassifierConfig(flag_pole_gain_min=0.40)
    assert classify_flag(bars, cfg=cfg).detected is False


def test_pullback_depth_gate_above_threshold_rejects():
    bars = make_flag_bars(pullback_pct=0.151)
    res = classify_flag(bars)
    assert res.detected is False


def test_pullback_depth_gate_below_threshold_passes():
    bars = make_flag_bars(pullback_pct=0.149)
    res = classify_flag(bars)
    assert res.detected is True


def test_pullback_depth_gate_is_threshold_sensitive():
    """Discriminating-test discipline (Codex R2 M2 follow-up): proves
    gate 6 (pullback_depth ≤ 0.15) is what enforces the threshold by
    cfg-injection. Tightening cfg.flag_pullback_depth_max below the
    measured pullback at the winning candidate must flip the same
    fixture from pass → reject.
    """
    from swing.config import ClassifierConfig
    bars = make_flag_bars()  # default → detected
    res_default = classify_flag(bars)
    assert res_default.detected is True
    measured = res_default.components["pullback_depth"]
    # Tighten cfg threshold below measured. Add a small safety margin
    # so the threshold falls below all passing candidates' pullback
    # values (search must not escape to a smaller-pullback window).
    cfg = ClassifierConfig(flag_pullback_depth_max=measured * 0.5)
    res_tight = classify_flag(bars, cfg=cfg)
    assert res_tight.detected is False, (
        f"Tightening flag_pullback_depth_max to {measured * 0.5:.4f} "
        f"(measured pullback={measured:.4f}) should reject the fixture"
    )


# tightness_ratio gate threshold = 0.6 (cfg.flag_tightness_ratio_max).
# Empirical mapping: measured tightness_ratio = flag_tightness_factor *
# (pole_close_avg / flag_close_avg) ≈ flag_tightness_factor * 0.9 in this
# fixture (pole avg close ≈ 117.5, flag avg close ≈ 130 at default pullback).
# So flag_tightness_factor ≈ 0.667 lands measured tightness ≈ 0.5998 (passes
# 0.6 gate) and 0.668 lands measured ≈ 0.5892 but search shifts to a window
# that fails (rejected). Verified at the REPL across [0.65, 0.70].
def test_tightness_ratio_gate_above_threshold_rejects():
    """Detection-outcome regression test at flag_tightness_factor=0.668.
    NOT a direct gate-threshold test — the parameter does not map 1:1
    to measured tightness_ratio (close-relative true-range scaling),
    so this asserts the search-path-resolved detection outcome at this
    fixture parameter, not the gate boundary itself. The
    `test_tightness_ratio_gate_is_threshold_sensitive` test is the
    actual gate-correctness verification.
    """
    bars = make_flag_bars(flag_tightness_factor=0.668)
    res = classify_flag(bars)
    assert res.detected is False


def test_tightness_ratio_gate_below_threshold_passes():
    """Detection-outcome regression test at flag_tightness_factor=0.667
    (companion to ..._above_threshold_rejects). NOT a direct
    gate-threshold test — see docstring on the rejecting-side test
    for explanation; `test_tightness_ratio_gate_is_threshold_sensitive`
    is the actual gate-correctness verification.
    """
    bars = make_flag_bars(flag_tightness_factor=0.667)
    res = classify_flag(bars)
    assert res.detected is True


def test_tightness_ratio_gate_is_threshold_sensitive():
    """Discriminating-test discipline (Codex R1 M1 follow-up): the
    `flag_tightness_factor` parameter does NOT map 1:1 to measured
    tightness_ratio because tightness uses close-relative true ranges
    (pole_close_avg ~117.5 vs flag_close_avg ~130 → ~0.9 scaling).
    The 0.667/0.668 threshold pair test validates DETECTION outcome at
    a search-path-dependent boundary; this test validates the GATE
    THRESHOLD is what's actually being enforced. Tightening
    cfg.flag_tightness_ratio_max via cfg-injection must reject the
    fixture — and to truly exercise gate 7 (rather than have the search
    escape to a tighter (M, N)), the threshold must be tightened below
    the MINIMUM measured tightness_ratio across all passing candidates.
    """
    from swing.config import ClassifierConfig  # noqa: I001  # in-function import keeps test setup self-contained
    from swing.evaluation.patterns.flag_classifier import (
        _evaluate_candidate, _detection_passes,
        M_RANGE, N_RANGE, _DEFAULT_CFG,
    )
    bars = make_flag_bars()
    # Default cfg → passes (all gates clear).
    res_default = classify_flag(bars)
    assert res_default.detected is True
    # Enumerate ALL passing candidates' tightness_ratio at default cfg.
    # The search may pick any of them depending on tie-break — to exercise
    # gate 7 we must tighten below the MIN across the entire passing set,
    # otherwise the search escapes to a tighter candidate.
    n_bars = len(bars)
    passing_tightness = []
    for N_ in N_RANGE:  # noqa: N806  # M, N spec-canonical (§3.1)
        flag_end = n_bars
        flag_start = n_bars - N_
        if flag_start <= 0:
            continue
        for M_ in M_RANGE:  # noqa: N806  # M, N spec-canonical (§3.1)
            pole_start = flag_start - M_
            if pole_start < 0:
                continue
            c = _evaluate_candidate(bars, pole_start, flag_start, flag_end)
            if _detection_passes(c, _DEFAULT_CFG):
                passing_tightness.append(c["tightness_ratio"])
    assert passing_tightness, "Test setup error: must have ≥1 passing candidate"
    min_passing = min(passing_tightness)
    # Tighten gate 7 threshold below every passing candidate's measured
    # tightness — proves the gate is genuinely enforced (not a search-path
    # artifact).
    new_threshold = min_passing - 0.01
    cfg = ClassifierConfig(flag_tightness_ratio_max=new_threshold)
    res_tight = classify_flag(bars, cfg=cfg)
    assert res_tight.detected is False, (
        f"Tightening flag_tightness_ratio_max from "
        f"{_DEFAULT_CFG.flag_tightness_ratio_max} to {new_threshold:.4f} "
        f"(min passing tightness across {len(passing_tightness)} candidates "
        f"= {min_passing:.4f}) must reject the fixture"
    )


def test_volume_contraction_gate_above_threshold_rejects():
    bars = make_flag_bars(flag_volume_factor=0.701)
    res = classify_flag(bars)
    assert res.detected is False


def test_volume_contraction_gate_below_threshold_passes():
    bars = make_flag_bars(flag_volume_factor=0.699)
    res = classify_flag(bars)
    assert res.detected is True


def test_volume_contraction_gate_is_threshold_sensitive():
    """Discriminating-test discipline (Codex R2 M2 follow-up): proves
    gate 8 (volume_ratio ≤ 0.7) is what enforces the threshold by
    cfg-injection. Tightening cfg.flag_volume_ratio_max below the
    measured volume_ratio at the winning candidate must flip the same
    fixture from pass → reject.
    """
    from swing.config import ClassifierConfig
    bars = make_flag_bars()  # default → detected at volume_ratio ≈ 0.565
    res_default = classify_flag(bars)
    assert res_default.detected is True
    measured = res_default.components["volume_ratio"]
    # Tighten cfg threshold below measured by enough margin to exclude
    # all passing candidates' volume_ratio (search must not escape).
    cfg = ClassifierConfig(flag_volume_ratio_max=measured * 0.5)
    res_tight = classify_flag(bars, cfg=cfg)
    assert res_tight.detected is False, (
        f"Tightening flag_volume_ratio_max to {measured * 0.5:.4f} "
        f"(measured volume_ratio={measured:.4f}) should reject the fixture"
    )


def test_ma_structure_not_stacked_rejects():
    # Override the full pre-run window (50 bars) with a steep downtrend so
    # SMA50 dominates and prevents SMA10 > SMA20 > SMA50 stacking. Plan's
    # n_pre=30 leaves 20 flat bars at start_close which preserves stacking;
    # n_pre=50 + linspace(180, 100, 50) flips the order at flag_start.
    bars = make_flag_bars()
    closes = bars["Close"].to_numpy().copy()
    n_pre = 50
    closes[:n_pre] = np.linspace(180.0, 100.0, n_pre)  # downtrend into pole
    bars = bars.assign(Close=closes, Open=closes)
    res = classify_flag(bars)
    assert res.detected is False


def test_ma_structure_stacked_and_rising_passes():
    bars = make_flag_bars()
    res = classify_flag(bars)
    assert res.detected is True


def test_flag_floor_holds_gate_drifting_floor_rejects():
    bars = make_flag_bars(floor_holds=False)
    res = classify_flag(bars)
    assert res.detected is False
    # Discriminating verification: flag_floor_holds component must be 0.0.
    assert res.components.get("flag_floor_holds", 1.0) == 0.0


def test_flag_floor_holds_gate_holding_floor_passes():
    bars = make_flag_bars(floor_holds=True)
    res = classify_flag(bars)
    assert res.detected is True


def test_confidence_is_min_of_continuous_clearances():
    """Codex R3 Minor 1 follow-up: recompute clearances from the
    returned components against default cfg, then assert exact equality
    (1e-9) to res.confidence. Catches clamp / normalization regressions
    that the prior < 0.05 tolerance allowed.
    """
    from swing.config import ClassifierConfig
    bars = make_flag_bars(
        pole_gain_pct=0.31,           # tight on pole_gain → smallest clearance
        pullback_pct=0.05,
        flag_tightness_factor=0.3,
        flag_volume_factor=0.3,
    )
    res = classify_flag(bars)
    assert res.detected is True
    # Recompute the four continuous-gate clearances from the returned
    # components against the default cfg, mirroring spec §3.1.4.
    cfg = ClassifierConfig()
    pg = res.components["pole_gain"]
    pd_ = res.components["pullback_depth"]
    tr = res.components["tightness_ratio"]
    vr = res.components["volume_ratio"]
    cl_pg = max(0.0, min(1.0, (pg - cfg.flag_pole_gain_min) / 0.70))
    cl_pd = max(
        0.0, min(1.0, (cfg.flag_pullback_depth_max - pd_) / cfg.flag_pullback_depth_max)
    )
    cl_tr = max(
        0.0, min(1.0, (cfg.flag_tightness_ratio_max - tr) / cfg.flag_tightness_ratio_max)
    )
    cl_vr = max(
        0.0, min(1.0, (cfg.flag_volume_ratio_max - vr) / cfg.flag_volume_ratio_max)
    )
    expected = min(cl_pg, cl_pd, cl_tr, cl_vr)
    assert abs(res.confidence - expected) < 1e-9, (
        f"confidence {res.confidence:.10f} != min(clearances) {expected:.10f}"
    )


def test_search_prefers_higher_confidence_then_lower_N_then_lower_M():  # noqa: N802  # M, N spec-canonical (§3.1)
    """Codex R1 M2 follow-up: original test only asserted determinism
    across two calls. This stronger version also verifies the chosen
    (M, N) is THE highest-confidence passing candidate (with tie-break
    by lower N, then lower M) — by enumerating all candidates and
    cross-checking against a reference computation."""
    bars = make_flag_bars(flag_bars=15)  # multiple N could pass
    res = classify_flag(bars)
    assert res.detected is True
    # Determinism: two calls return the same (M, N).
    res2 = classify_flag(bars)
    assert res.components["flag_N"] == res2.components["flag_N"]
    assert res.components["pole_M"] == res2.components["pole_M"]
    # Correctness: the chosen (M, N) maximizes confidence with tie-break
    # (-N, -M). Enumerate all passing candidates via direct calls.
    from swing.evaluation.patterns.flag_classifier import (  # noqa: I001  # in-function import keeps reference enumeration colocated
        _evaluate_candidate, _detection_passes, _continuous_clearances,
        M_RANGE, N_RANGE, _DEFAULT_CFG,
    )
    n_bars = len(bars)
    passing = []
    for N_ in N_RANGE:  # noqa: N806  # M, N spec-canonical (§3.1)
        flag_end = n_bars
        flag_start = n_bars - N_
        if flag_start <= 0:
            continue
        for M_ in M_RANGE:  # noqa: N806  # M, N spec-canonical (§3.1)
            pole_start = flag_start - M_
            if pole_start < 0:
                continue
            c = _evaluate_candidate(bars, pole_start, flag_start, flag_end)
            if _detection_passes(c, _DEFAULT_CFG):
                conf = min(_continuous_clearances(c, _DEFAULT_CFG))
                passing.append((conf, -N_, -M_, M_, N_))
    assert passing, "Test setup error: fixture must produce ≥1 passing candidate"
    # Sort by (conf desc, -N desc, -M desc) — i.e., the search's tie-break.
    passing.sort(reverse=True)
    expected_M = passing[0][3]  # noqa: N806  # M, N spec-canonical (§3.1)
    expected_N = passing[0][4]  # noqa: N806  # M, N spec-canonical (§3.1)
    assert res.components["pole_M"] == float(expected_M), (
        f"Search picked M={res.components['pole_M']}, "
        f"reference computation says highest-confidence passing M={expected_M}"
    )
    assert res.components["flag_N"] == float(expected_N), (
        f"Search picked N={res.components['flag_N']}, "
        f"reference computation says highest-confidence passing N={expected_N}"
    )


def test_best_attempted_uses_max_min_soft_clearance():
    """Codex R1 M2 follow-up: original test asserted only a broad pole_gain
    range. This stronger version verifies the best-attempted candidate
    matches the EXACT (M, N) that maximizes min-soft-clearance via a
    reference enumeration."""
    bars = make_flag_bars(pole_gain_pct=0.20)  # all candidates fail pole_gain
    res = classify_flag(bars)
    assert res.detected is False
    assert "pole_gain" in res.components
    # Reference enumeration: find (M, N) that maximizes
    # min(soft_clearances) and verify components matches.
    from swing.evaluation.patterns.flag_classifier import (  # noqa: I001  # in-function import keeps reference enumeration colocated
        _evaluate_candidate, _soft_clearances, M_RANGE, N_RANGE, _DEFAULT_CFG,
    )
    n_bars = len(bars)
    best_soft = None  # (soft_min, M, N, components)
    for N_ in N_RANGE:  # noqa: N806  # M, N spec-canonical (§3.1)
        flag_end = n_bars
        flag_start = n_bars - N_
        if flag_start <= 0:
            continue
        for M_ in M_RANGE:  # noqa: N806  # M, N spec-canonical (§3.1)
            pole_start = flag_start - M_
            if pole_start < 0:
                continue
            c = _evaluate_candidate(bars, pole_start, flag_start, flag_end)
            soft_min = min(_soft_clearances(c, _DEFAULT_CFG))
            if best_soft is None or soft_min > best_soft[0]:
                best_soft = (soft_min, M_, N_, c)
    assert best_soft is not None
    expected_M, expected_N, expected_c = best_soft[1], best_soft[2], best_soft[3]  # noqa: N806  # M, N spec-canonical (§3.1)
    assert res.components["pole_M"] == float(expected_M), (
        f"Best-attempted reported M={res.components['pole_M']}, "
        f"reference says max-min-soft-clearance M={expected_M}"
    )
    assert res.components["flag_N"] == float(expected_N), (
        f"Best-attempted reported N={res.components['flag_N']}, "
        f"reference says max-min-soft-clearance N={expected_N}"
    )
    # And the reported pole_gain matches the reference candidate's pole_gain.
    assert abs(res.components["pole_gain"] - expected_c["pole_gain"]) < 1e-9


def test_ma_structure_stacked_but_flat_rejects():
    """Codex R3 M1 follow-up: gate 5 requires SMA10>SMA20>SMA50 AND each
    rising over 5-bar lookback. Plan Task 1.8 originally specified three
    cases (not-stacked, stacked-but-flat, stacked-and-rising); only two
    were committed in `1f285c5`. This adds the missing 'stacked-but-flat'
    case via a DIRECT unit test of _ma_structure_passes that constructs
    its own SMAs in-test without reusing classifier helpers — also
    addresses R2 M1's lockstep concern for gate 5 by providing
    independent verification of the rising condition.
    """
    from swing.evaluation.patterns.flag_classifier import _ma_structure_passes
    # Build closes: 30 bars rising 70→100, 15 bars rising 100→140, 16 bars
    # flat at 140 (idx 45..60). At idx 60 the SMAs are stacked because of
    # the past rise, but SMA10 is computed entirely from the flat plateau
    # (bars 51..60) AND from the same plateau 5 bars earlier (bars 46..55),
    # so SMA10@60 == SMA10@55 → not rising → gate 5 must reject.
    closes = np.empty(61)
    closes[:30] = np.linspace(70.0, 100.0, 30)
    closes[30:45] = np.linspace(100.0, 140.0, 15)
    closes[45:61] = 140.0
    # Sanity: SMAs are stacked at idx 60.
    sma10 = float(np.mean(closes[51:61]))
    sma20 = float(np.mean(closes[41:61]))
    sma50 = float(np.mean(closes[11:61]))
    assert sma10 > sma20 > sma50, (
        f"Test setup invariant: stacked SMAs at idx 60 "
        f"(s10={sma10:.4f}, s20={sma20:.4f}, s50={sma50:.4f})"
    )
    # Sanity: SMA10 is flat over 5-bar lookback.
    sma10_earlier = float(np.mean(closes[46:56]))
    assert sma10 == sma10_earlier, (
        f"Test setup invariant: SMA10@60 ({sma10:.4f}) == "
        f"SMA10@55 ({sma10_earlier:.4f}) — flat plateau"
    )
    # Gate 5 must reject this configuration.
    assert _ma_structure_passes(closes, 60) is False, (
        "Gate 5 regression: _ma_structure_passes accepted a stacked-"
        "but-flat configuration. The 5-bar rising condition is "
        "no longer enforced."
    )


def test_pattern_None_distinct_from_string_none_in_dataclass():  # noqa: N802  # `None` is the literal Python sentinel, not a class
    """Future-proofing: pattern is `str | None`, NOT `str`. Pipeline-level
    classifier-error path constructs a result with pattern=None (NoneType)
    that persists as SQL NULL, distinguishing it from pattern='none'
    (evaluated negative). This test guards against accidental
    `pattern: str = 'none'` field re-typing."""
    from swing.evaluation.patterns.flag_classifier import FlagClassificationResult
    err_result = FlagClassificationResult(
        detected=False, confidence=0.0, pattern=None,
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        pole_high=None, flag_low=None, pivot=None,
        components={"error": "boom"},
    )
    assert err_result.pattern is None
    assert err_result.pattern != "none"
