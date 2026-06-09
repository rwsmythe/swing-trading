from __future__ import annotations

from research.harness.minervini_primary_base_recall import scorecard as sc


def test_raw_recall_fraction_reported_as_explicit_counts():
    # 2 of 3 sub_floor evaluable fired (sweep): raw fraction FIRST (R1.m4).
    rec = sc.recall_fraction([("amzn", True), ("body", True), ("dks", False)])
    assert rec.successes == 2
    assert rec.n == 3
    assert abs(rec.rate - 2 / 3) < 1e-9


def test_wilson_is_a_mechanical_interval_passthrough():
    w = sc.wilson(2, 3)
    # Reuses the frozen wilson_interval; at n=3 it is a wide mechanical interval, labeled as such.
    assert w.n == 3
    assert 0.0 <= w.lower <= w.p_hat <= w.upper <= 1.0


def test_first_rejection_histogram_counts_misses_by_criterion():
    hist = sc.first_rejection_histogram(
        [("amzn", None), ("dks", "depth"), ("body", "no_emergence"), ("x", "depth")]
    )
    # WRONG-PATH (count fired too) would include a None key; RIGHT-PATH counts only misses.
    assert hist == {"depth": 2, "no_emergence": 1}


def test_precision_contrast_single_session_primary_vs_window_separate():
    # Exemplar single fire vs control single fire-rate is the PRIMARY contrast; window reported
    # separately, NEVER conflated (R1.M9).
    contrast = sc.precision_contrast(
        exemplar_single_fired=True,
        exemplar_window_fired=True,
        control_single_flags=[False, False, True, False],   # 1/4
        control_window_flags=[True, False, True, False],     # 2/4
    )
    assert abs(contrast.control_single_rate - 0.25) < 1e-9
    assert abs(contrast.control_window_rate - 0.50) < 1e-9
    assert contrast.exemplar_single_fired is True
    assert contrast.primary_estimand == "single_session_per_anchor"


def test_precision_contrast_no_controls_is_na_not_zero():
    contrast = sc.precision_contrast(
        exemplar_single_fired=False, exemplar_window_fired=True,
        control_single_flags=[], control_window_flags=[],
    )
    assert contrast.control_single_rate is None   # NA, not 0.0 (spec section 6)
    assert contrast.control_window_rate is None
