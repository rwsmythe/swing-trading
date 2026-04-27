"""Task 4.0 — cfg.web.flag_pattern_display_threshold default 0.0.

Spec §3.8: filters watchlist flag-tag rendering. Default 0.0 = show every
detected flag (V1 starting point — no labeled-example calibration data
exists yet; suppressing flags before chart-validation would short-circuit
the encoding-into-feedback-loop framing). Operator dials up after
operational experience reveals which confidence bands map to chart-
validated flags.
"""
from __future__ import annotations


def test_web_config_has_flag_pattern_display_threshold():
    """Discriminating-test: pre-fix, AttributeError raises (field absent
    on the dataclass). Post-fix, the field exists with default 0.0."""
    from swing.config import Web
    assert Web().flag_pattern_display_threshold == 0.0


def test_web_config_flag_pattern_display_threshold_is_float():
    """Type contract: the field is a float (downstream comparison
    `cls.confidence >= display_threshold` requires numeric type)."""
    from swing.config import Web
    assert isinstance(Web().flag_pattern_display_threshold, float)


def test_web_config_flag_pattern_display_threshold_overridable():
    """Operator-tunable per spec §3.8. Constructing Web with an explicit
    value lifts the default — the migration path for post-calibration
    re-tune."""
    from swing.config import Web
    w = Web(flag_pattern_display_threshold=0.50)
    assert w.flag_pattern_display_threshold == 0.50
