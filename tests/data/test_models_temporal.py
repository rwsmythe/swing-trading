import pytest
from swing.data.models import (
    PatternDetectionEvent, PatternForwardObservation,
    _PATTERN_DETECTION_SOURCE_VALUES, _FORWARD_OBSERVATION_STATUS_VALUES,
)


def _valid_detection(**kw):
    base = dict(
        detection_id=None, ticker="AAA", detection_date="2026-05-29",
        data_asof_date="2026-05-28", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=0.7,
        detector_version="v1", source="pipeline",
        per_pattern_metadata_json="{}", created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    return PatternDetectionEvent(**base)


def test_detection_rejects_bad_pattern_class():
    with pytest.raises(ValueError, match="pattern_class"):
        _valid_detection(pattern_class="bogus")


def test_detection_rejects_bad_source():
    with pytest.raises(ValueError, match="source"):
        _valid_detection(source="bogus")


def test_detection_accepts_all_enum_sources():
    for s in _PATTERN_DETECTION_SOURCE_VALUES:
        _valid_detection(source=s)  # no raise


def test_observation_rejects_bad_status():
    with pytest.raises(ValueError, match="status"):
        PatternForwardObservation(
            observation_id=None, detection_id=1, observation_date="2026-05-29",
            ohlc_today_json="{}", status="bogus", sessions_since_detection=1,
            created_at="2026-05-29T00:00:00Z",
        )


def test_observation_rejects_bad_status_change_event():
    with pytest.raises(ValueError, match="status_change_event"):
        PatternForwardObservation(
            observation_id=None, detection_id=1, observation_date="2026-05-29",
            ohlc_today_json="{}", status="pending", sessions_since_detection=1,
            created_at="2026-05-29T00:00:00Z", status_change_event="bogus",
        )


def test_validator_mirrors_schema_check_value_domain():
    """The Python enum constants MUST equal the schema CHECK value domain
    (gotcha #11 mirror). Hard-code the CHECK lists here so a drift in either
    side fails the test."""
    assert set(_PATTERN_DETECTION_SOURCE_VALUES) == {
        "pipeline", "v2_cohort", "d2_baseline", "backfill", "synthetic"}
    assert set(_FORWARD_OBSERVATION_STATUS_VALUES) == {
        "pending", "triggered_open", "triggered_closed_at_target",
        "triggered_closed_at_stop", "invalidated", "expired"}
