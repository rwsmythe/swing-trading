"""Phase 18 Arc 18-F: the GUI health-stoplight framework.

Tests for `swing/monitoring/stoplights.py` — the `Stoplight` render dataclass,
the shared research-artifact contract constants, the two providers, and the
`health_stoplights` aggregator. The framework is DEFENSIVE: every layer degrades
to grey, never raises (LOCK #2); grey is render-only (LOCK #3).
"""
from __future__ import annotations

import pytest

from swing.monitoring.stoplights import (
    RESEARCH_ARTIFACT_MAX_AGE_DAYS,
    RESEARCH_HEALTH_ARTIFACT_PATH,
    RESEARCH_MONITOR_ID,
    Stoplight,
    research_health_artifact_path,
)


# ---------------------------------------------------------------- Task 1


def test_stoplight_dataclass_fields_and_color_enum():
    s = Stoplight(
        id="tool", label="Tool health", color="green",
        drilldown_path="/health/tool",
    )
    assert s.id == "tool"
    assert s.label == "Tool health"
    assert s.color == "green"
    assert s.drilldown_path == "/health/tool"


def test_stoplight_rejects_bad_color():
    # Both-ways: a no-validation impl would NOT raise; the assert distinguishes.
    with pytest.raises(ValueError):
        Stoplight(id="tool", label="x", color="blue", drilldown_path="/health/tool")


def test_stoplight_accepts_grey():
    # grey is a valid render-only Stoplight color (LOCK #3).
    s = Stoplight(id="tool", label="x", color="grey", drilldown_path="/health/tool")
    assert s.color == "grey"


def test_stoplight_rejects_empty_drilldown_path():
    with pytest.raises(ValueError):
        Stoplight(id="tool", label="x", color="green", drilldown_path="")


def test_research_health_artifact_path_constant():
    path = research_health_artifact_path()
    assert path.parts[-3:] == ("research", "health", "latest.json")
    assert path.parts[-4] == "exports"
    assert RESEARCH_HEALTH_ARTIFACT_PATH == path


def test_research_monitor_id_constant():
    assert RESEARCH_MONITOR_ID == "research_measurement"


def test_research_artifact_max_age_days_constant():
    assert RESEARCH_ARTIFACT_MAX_AGE_DAYS == 7
