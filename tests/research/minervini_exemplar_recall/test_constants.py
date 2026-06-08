# tests/research/minervini_exemplar_recall/test_constants.py
from __future__ import annotations


def test_screenable_floor_is_221_for_default_config():
    from swing.config import Config
    from research.harness.minervini_exemplar_recall.constants import screenable_floor

    cfg = Config.from_defaults()
    # 200 + rising_ma_period_days (=21) -> 221. This is the full-TT-evaluability
    # floor: below it TT3 (200MA rising) is an UNALLOWED na and forces skip.
    assert screenable_floor(cfg) == 221


def test_module_constants_present():
    from research.harness.minervini_exemplar_recall import constants

    assert constants.H2_MIN_BARS == 60
    assert constants.CONTROL_GAP_BARS == 120
    assert constants.EQUITY_FLOOR_SURROGATE == 7500.0
    assert isinstance(constants.DEFAULT_CONTROL_SEED, int)


def test_exceptions_subclass_base():
    from research.harness.minervini_exemplar_recall import exceptions as exc

    for name in (
        "TiingoArchiveMissingError",
        "TiingoCoverageError",
        "MalformedExemplarRowError",
        "MalformedAsofDateError",
    ):
        cls = getattr(exc, name)
        assert issubclass(cls, exc.MinerviniRecallError)
