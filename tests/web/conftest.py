"""Shared fixtures for Phase 3a web tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Config, load
from swing.data.db import ensure_schema


@pytest.fixture
def test_cfg(tmp_path: Path) -> tuple[Config, Path]:
    """Return (cfg, cfg_path) for a fresh test project."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    return cfg, cfg_path


@pytest.fixture
def seeded_db(test_cfg) -> tuple[Config, Path]:
    """Ensure schema is applied; return (cfg, cfg_path). Subtests may seed rows."""
    cfg, cfg_path = test_cfg
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path
