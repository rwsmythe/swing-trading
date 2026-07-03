"""19-B Task 7 -- the 18-F web reader threads cfg (LOCK #4 co-anchor).

read_validated_research_envelope(cfg) resolves the artifact from the SAME launch
cfg the writer used; cfg=None keeps the __file__ fallback (backward-compat).
"""
from __future__ import annotations

from pathlib import Path

from swing.monitoring.research_health import (
    ResearchHealthCheck,
    ResearchHealthStatus,
    write_research_health_artifact,
)
from swing.monitoring.stoplights import (
    RESEARCH_HEALTH_ARTIFACT_PATH,
    _research_stoplight,
    read_validated_research_envelope,
)


class _Paths:
    def __init__(self, exports_dir):
        self.exports_dir = exports_dir


class _Cfg:
    def __init__(self, exports_dir):
        self.paths = _Paths(exports_dir)


def _write_valid_envelope(exports_dir: Path) -> Path:
    out = exports_dir / "research" / "health" / "latest.json"
    status = ResearchHealthStatus(
        overall="green",
        checks=[ResearchHealthCheck(key="k", status="green", summary="s",
                                    detail=None)])
    return write_research_health_artifact(status, out_path=out)


def test_web_reader_reads_cfg_derived_artifact(tmp_path):
    # A valid envelope at the cfg-derived exports path is returned via cfg; the
    # __file__-path artifact is NOT consulted. Pre-fix: the reader ignores cfg ->
    # reads the __file__ path -> None/other -> FAILS.
    exports_dir = tmp_path / "exports"
    _write_valid_envelope(exports_dir)
    cfg = _Cfg(exports_dir)
    got = read_validated_research_envelope(cfg)
    assert got is not None
    overall, env = got
    assert overall == "green"
    # the cfg path is NOT the __file__ constant path
    assert (exports_dir / "research" / "health" / "latest.json") != \
        RESEARCH_HEALTH_ARTIFACT_PATH


def test_web_reader_cfg_none_unchanged(tmp_path, monkeypatch):
    # cfg=None still resolves the __file__ accessor (backward-compat): point the
    # cfg-less accessor at a tmp artifact and confirm the reader reads THAT.
    out = tmp_path / "health" / "latest.json"
    status = ResearchHealthStatus(
        overall="green",
        checks=[ResearchHealthCheck(key="k", status="green", summary="s",
                                    detail=None)])
    write_research_health_artifact(status, out_path=out)
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda cfg=None: out)
    assert read_validated_research_envelope() is not None


def test_research_stoplight_lights_from_cfg_derived_artifact(tmp_path):
    # LOCK #4 end-to-end: the provider lights from the cfg-derived artifact
    # (reader/writer co-anchored).
    exports_dir = tmp_path / "exports"
    _write_valid_envelope(exports_dir)
    light = _research_stoplight(_Cfg(exports_dir))
    assert light.color == "green"
