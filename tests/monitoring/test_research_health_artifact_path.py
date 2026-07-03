"""19-B Task 3 -- the cfg-aware research_health_artifact_path accessor (LOCK #4).

When cfg is supplied the artifact resolves from cfg.paths.exports_dir (config-
derived, launch-context-consistent); cfg=None keeps the __file__ constant.
"""
from __future__ import annotations

from pathlib import Path

from swing.monitoring.stoplights import (
    RESEARCH_HEALTH_ARTIFACT_PATH,
    research_health_artifact_path,
)


class _Paths:
    def __init__(self, exports_dir):
        self.exports_dir = exports_dir


class _Cfg:
    def __init__(self, exports_dir):
        self.paths = _Paths(exports_dir)


def test_artifact_path_cfg_derives_from_exports_dir(tmp_path):
    # cfg -> cfg.paths.exports_dir/research/health/latest.json (NOT the __file__
    # constant). Pre-fix (no param): the accessor ignores cfg -> the constant.
    cfg = _Cfg(tmp_path / "x" / "exports")
    got = research_health_artifact_path(cfg)
    assert got == tmp_path / "x" / "exports" / "research" / "health" / "latest.json"
    assert got != RESEARCH_HEALTH_ARTIFACT_PATH


def test_artifact_path_cfg_none_returns_file_constant():
    assert research_health_artifact_path() == RESEARCH_HEALTH_ARTIFACT_PATH
    assert research_health_artifact_path(None) == RESEARCH_HEALTH_ARTIFACT_PATH
