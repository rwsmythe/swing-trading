"""Precedence chain smoke: default → tracked → override (per locked decision §2.2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_user import write_user_overrides
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    return tmp_path


def test_chase_factor_precedence_default(isolated: Path):
    cfg_path = _write_cfg(isolated / "project", isolated / "home")
    base = load(cfg_path)
    eff = apply_overrides(base)
    assert eff.web.chase_factor == 0.01  # registry default
    assert get_field_source(base, "web.chase_factor") == "default"


def test_chase_factor_precedence_tracked(isolated: Path):
    cfg_path = _write_cfg(
        isolated / "project", isolated / "home",
        extra="[web]\nchase_factor = 0.015\n",
    )
    base = load(cfg_path)
    eff = apply_overrides(base)
    assert eff.web.chase_factor == 0.015
    assert get_field_source(base, "web.chase_factor") == "tracked"


def test_chase_factor_precedence_override_beats_tracked(isolated: Path):
    cfg_path = _write_cfg(
        isolated / "project", isolated / "home",
        extra="[web]\nchase_factor = 0.015\n",
    )
    base = load(cfg_path)
    write_user_overrides({"web": {"chase_factor": 0.025}})
    eff = apply_overrides(base)
    assert eff.web.chase_factor == 0.025
    assert get_field_source(base, "web.chase_factor") == "override"
