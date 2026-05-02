"""ConfigPageVM exposes 3 rows with current/default/source/input_kind."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.config_user import write_user_overrides
from swing.web.view_models.config import build_config_vm
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def base_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    return load(cfg_path)


def test_vm_has_three_rows(base_cfg):
    vm = build_config_vm(base_cfg)
    assert len(vm.rows) == 3
    paths = [r.path for r in vm.rows]
    assert paths == [
        "web.chase_factor",
        "pipeline.chart_top_n_watch",
        "account.risk_equity_floor",
    ]


def test_vm_default_source_when_no_overrides(base_cfg):
    """Without user-config overrides, sources reflect project-config tracking.

    The `_write_cfg` helper sets `account.risk_equity_floor = 5000.0`
    (registry default is 7500.0), so that row reports "tracked" per the
    Codex watch-item #4 precedence semantics in `get_field_source`. The
    other two V1 paths are absent from the project config and thus resolve
    to "default".
    """
    vm = build_config_vm(base_cfg)
    by_path = {r.path: r.source for r in vm.rows}
    assert by_path["web.chase_factor"] == "default"
    assert by_path["pipeline.chart_top_n_watch"] == "default"
    assert by_path["account.risk_equity_floor"] == "tracked"


def test_vm_override_source_after_user_config_write(base_cfg):
    write_user_overrides({"web": {"chase_factor": 0.025}})
    vm = build_config_vm(base_cfg)
    cf_row = next(r for r in vm.rows if r.path == "web.chase_factor")
    assert cf_row.source == "override"
    assert cf_row.current_value == 0.025


def test_vm_default_value_per_row(base_cfg):
    vm = build_config_vm(base_cfg)
    by_path = {r.path: r for r in vm.rows}
    assert by_path["web.chase_factor"].default_value == 0.01
    assert by_path["pipeline.chart_top_n_watch"].default_value == 10
    assert by_path["account.risk_equity_floor"].default_value == 7500.0


def test_vm_includes_session_date_for_base_layout(base_cfg):
    vm = build_config_vm(base_cfg)
    assert hasattr(vm, "session_date")
    assert isinstance(vm.session_date, str)


def test_vm_base_layout_banner_fields_safe_defaults(base_cfg):
    """CLAUDE.md base.html.j2 5-VM rule check: although Task 7 confirmed the
    nav link is static (no new field needed), the base layout DOES dereference
    stale_banner / price_source_degraded / ohlcv_source_degraded for banner
    rendering. ConfigPageVM must include these with safe defaults to avoid
    Jinja UndefinedError when /config renders.
    """
    vm = build_config_vm(base_cfg)
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.ohlcv_source_degraded is False
