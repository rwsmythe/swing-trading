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
    _tool_stoplight,
    research_health_artifact_path,
)
from swing.monitoring.tool_health import ToolHealthCheck, ToolHealthStatus


class _FakeCfg:
    """Minimal cfg stub exposing `.paths.prices_cache_dir` (the only field the
    tool provider reads)."""

    class _Paths:
        prices_cache_dir = "/tmp/prices"

    paths = _Paths()


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


# ---------------------------------------------------------------- Task 2


@pytest.mark.parametrize("color", ["green", "yellow", "red"])
def test_tool_stoplight_maps_overall_to_color(monkeypatch, color):
    status = ToolHealthStatus(
        overall=color,
        checks=[ToolHealthCheck(key="k", status=color, summary="s")],
    )
    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health",
        lambda conn, **kw: status,
    )
    s = _tool_stoplight(None, _FakeCfg())
    assert s.color == color
    assert s.id == "tool"
    assert s.drilldown_path == "/health/tool"


def test_tool_stoplight_grey_when_compute_raises(monkeypatch, caplog):
    def _boom(conn, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health", _boom,
    )
    with caplog.at_level("WARNING"):
        s = _tool_stoplight(None, _FakeCfg())  # must NOT raise
    assert s.color == "grey"
    assert any("grey" in r.message.lower() for r in caplog.records)


def test_tool_stoplight_grey_when_cfg_none():
    s = _tool_stoplight(None, None)  # no prices_cache_dir derivable; defensive
    assert s.color == "grey"


def test_tool_stoplight_passes_prices_cache_dir(monkeypatch):
    calls = {}

    def _record(conn, **kw):
        calls.update(kw)
        return ToolHealthStatus(
            overall="green",
            checks=[ToolHealthCheck(key="k", status="green", summary="s")],
        )

    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health", _record,
    )
    cfg = _FakeCfg()
    _tool_stoplight(None, cfg)
    assert calls["cfg"] is cfg
    assert calls["prices_cache_dir"] == cfg.paths.prices_cache_dir
