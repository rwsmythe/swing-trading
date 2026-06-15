"""Phase 18 Arc 18-F: the GUI health-stoplight framework.

Tests for `swing/monitoring/stoplights.py` — the `Stoplight` render dataclass,
the shared research-artifact contract constants, the two providers, and the
`health_stoplights` aggregator. The framework is DEFENSIVE: every layer degrades
to grey, never raises (LOCK #2); grey is render-only (LOCK #3).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from swing.monitoring.stoplights import (
    RESEARCH_ARTIFACT_MAX_AGE_DAYS,
    RESEARCH_HEALTH_ARTIFACT_PATH,
    RESEARCH_MONITOR_ID,
    Stoplight,
    _research_stoplight,
    _tool_stoplight,
    health_stoplights,
    read_validated_research_envelope,
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


# ---------------------------------------------------------------- Task 3


@pytest.fixture
def artifact_path(tmp_path, monkeypatch):
    """Point the research-artifact accessor at a tmp file (no real exports/)."""
    p = tmp_path / "latest.json"
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: p,
    )
    return p


def _valid_envelope(color="green", generated_ts=None):
    return {
        "monitor": RESEARCH_MONITOR_ID,
        "generated_ts": generated_ts or datetime.now().isoformat(),
        "overall": color,
        "checks": [{"key": "k", "status": color, "summary": "s", "detail": None}],
    }


def test_research_stoplight_grey_when_artifact_absent(artifact_path, caplog):
    # artifact_path file does NOT exist.
    with caplog.at_level("WARNING"):
        s = _research_stoplight()  # must NOT raise
    assert s.color == "grey"
    assert s.id == "research"
    assert s.drilldown_path == "/health/research"
    assert s.label  # non-empty ASCII
    # absence is the expected pre-18-D state -> NO warning log-spam every render.
    assert not [r for r in caplog.records if "research" in r.message.lower()]


@pytest.mark.parametrize("color", ["green", "yellow", "red"])
def test_research_stoplight_maps_overall(artifact_path, color):
    artifact_path.write_text(json.dumps(_valid_envelope(color)), encoding="utf-8")
    assert _research_stoplight().color == color


def test_research_stoplight_grey_on_malformed_json(artifact_path, caplog):
    artifact_path.write_text("{ not json", encoding="utf-8")
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records


@pytest.mark.parametrize(
    "env",
    [
        {"monitor": RESEARCH_MONITOR_ID, "checks": []},  # no overall
        {"monitor": RESEARCH_MONITOR_ID, "overall": "purple",
         "generated_ts": datetime.now().isoformat()},  # invalid overall
    ],
)
def test_research_stoplight_grey_on_missing_or_invalid_overall(
    artifact_path, caplog, env,
):
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records


@pytest.mark.parametrize(
    "env",
    [
        {"monitor": "shadow_expectancy", "overall": "green",
         "generated_ts": datetime.now().isoformat(), "checks": []},
        {},  # no monitor at all
    ],
)
def test_research_stoplight_grey_on_monitor_mismatch(artifact_path, caplog, env):
    # Both-ways: an impl that maps overall WITHOUT the monitor-id gate returns
    # green for the first case (a false-green from a wrong object).
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records


def test_research_stoplight_grey_on_stale_generated_ts(artifact_path, caplog):
    stale = (datetime.now() - timedelta(days=30)).isoformat()
    artifact_path.write_text(
        json.dumps(_valid_envelope("green", generated_ts=stale)),
        encoding="utf-8",
    )
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records
    # Both-ways: the SAME envelope with a fresh ts returns green.
    artifact_path.write_text(json.dumps(_valid_envelope("green")), encoding="utf-8")
    assert _research_stoplight().color == "green"


@pytest.mark.parametrize(
    "ts",
    [
        None,  # absent generated_ts
        "not-a-date",  # unparseable
    ],
)
def test_research_stoplight_grey_on_undated_or_unparseable(artifact_path, ts):
    env = _valid_envelope("green")
    if ts is None:
        env.pop("generated_ts")
    else:
        env["generated_ts"] = ts
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    assert _research_stoplight().color == "grey"


def test_research_stoplight_grey_on_just_over_7_days(artifact_path):
    # Codex R3 MAJOR — the `.days`-floor boundary.
    over = (datetime.now() - timedelta(days=7, hours=23)).isoformat()
    artifact_path.write_text(
        json.dumps(_valid_envelope("green", generated_ts=over)),
        encoding="utf-8",
    )
    # Both-ways: a FLOORED `age.days > 7` impl yields 7>7==False -> green (bug);
    # the EXACT timedelta(days=7) compare yields 7d23h>7d==True -> grey.
    assert _research_stoplight().color == "grey"
    # Bound the threshold from below: just under 7 days -> green.
    under = (datetime.now() - timedelta(days=6, hours=23)).isoformat()
    artifact_path.write_text(
        json.dumps(_valid_envelope("green", generated_ts=under)),
        encoding="utf-8",
    )
    assert _research_stoplight().color == "green"


def test_research_stoplight_grey_on_future_generated_ts(artifact_path, caplog):
    # Codex R1 MAJOR — a FUTURE generated_ts (bad clock / tampered same-monitor
    # artifact) must NOT false-green. The staleness gate `now - parsed > 7d` is
    # FALSE for a future ts (negative delta), so a future-dated artifact stays
    # green up to 7d past that future time without a future-rejection gate.
    future = (datetime.now() + timedelta(days=30)).isoformat()
    env = _valid_envelope("green", generated_ts=future)
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    # Both-ways: a no-future-check impl returns green here (false-green);
    # rejecting `parsed > now` -> grey (correct).
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records
    # The shared validating reader also rejects (the VM consumes this too).
    assert read_validated_research_envelope() is None


def test_research_stoplight_grey_when_overall_understates_checks(
    artifact_path, caplog,
):
    # Codex R2 MAJOR — a same-monitor, fresh, valid-overall envelope whose
    # `overall` is BETTER than the worst check is a false-green vector: the
    # topbar would light green while the drill-down lists a red check. The tool
    # path is protected by ToolHealthStatus.__post_init__; the research path
    # ingests raw JSON, so the reader must cross-check overall vs the worst check.
    env = _valid_envelope("green")
    env["checks"] = [
        {"key": "a", "status": "green", "summary": "s", "detail": None},
        {"key": "b", "status": "red", "summary": "s", "detail": None},  # worst
    ]
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    # Both-ways: an impl trusting `overall` blindly returns green here (the bug);
    # a worst-severity cross-check yields grey (reject the inconsistent artifact).
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records
    assert read_validated_research_envelope() is None


def test_research_stoplight_consistent_overall_equals_worst_check(artifact_path):
    # The complement: when `overall` == the worst check severity, the artifact is
    # consistent and lights normally (bounds the gate from the trusting side).
    env = _valid_envelope("yellow")
    env["checks"] = [
        {"key": "a", "status": "green", "summary": "s", "detail": None},
        {"key": "b", "status": "yellow", "summary": "s", "detail": None},  # worst
    ]
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    assert _research_stoplight().color == "yellow"


@pytest.mark.parametrize(
    "bad_check",
    [
        {"status": "green"},  # status-only — no key/summary (the Codex R3 case)
        {"status": "green", "summary": "s"},  # missing key
        {"key": "a", "status": "green"},  # missing summary
        {"key": "", "status": "green", "summary": "s"},  # empty key
        {"key": "a", "status": "green", "summary": ""},  # empty summary
        {"key": "a", "status": "green", "summary": 5},  # non-string summary
        {"key": 5, "status": "green", "summary": "s"},  # non-string key
        {"key": "a", "status": "green", "summary": "s", "detail": 5},  # bad detail
    ],
)
def test_research_stoplight_grey_on_malformed_check_schema(
    artifact_path, caplog, bad_check,
):
    # Codex R3 MAJOR — a check passing the severity gate (valid `status`) but
    # missing/invalid the render-contract fields (`key`/`summary`/`detail`) is an
    # unverifiable artifact; the drill-down would silently drop it while the
    # topbar lights green. The shared reader must validate the FULL check schema.
    env = _valid_envelope("green")
    env["checks"] = [bad_check]
    artifact_path.write_text(json.dumps(env), encoding="utf-8")
    # Both-ways: a status-only severity check returns green (the bug); full-schema
    # validation greys.
    with caplog.at_level("WARNING"):
        s = _research_stoplight()
    assert s.color == "grey"
    assert caplog.records
    assert read_validated_research_envelope() is None


# ---------------------------------------------------------------- Task 4


def test_health_stoplights_returns_tool_then_research(monkeypatch, artifact_path):
    # tool -> green via patched compute; research -> grey via absent artifact.
    status = ToolHealthStatus(
        overall="green",
        checks=[ToolHealthCheck(key="k", status="green", summary="s")],
    )
    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health",
        lambda conn, **kw: status,
    )
    result = health_stoplights(None, _FakeCfg())
    assert [s.id for s in result] == ["tool", "research"]
    assert result[0].color == "green"
    assert result[1].color == "grey"


def test_health_stoplights_never_raises_when_a_provider_raises(monkeypatch):
    def _boom(conn, cfg):
        raise RuntimeError("provider defect")

    monkeypatch.setattr("swing.monitoring.stoplights._tool_stoplight", _boom)
    result = health_stoplights(None, _FakeCfg())  # must NOT raise
    assert [s.id for s in result] == ["tool", "research"]
    assert result[0].color == "grey"  # tool slot degraded but present


def test_health_stoplights_returns_tuple_not_list(monkeypatch, artifact_path):
    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health",
        lambda conn, **kw: ToolHealthStatus(
            overall="green",
            checks=[ToolHealthCheck(key="k", status="green", summary="s")],
        ),
    )
    assert isinstance(health_stoplights(None, _FakeCfg()), tuple)
