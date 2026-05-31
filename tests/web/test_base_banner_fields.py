"""Phase 14 SB4 Slice 5 Task 5.0: the shared `_base_banner_fields` helper.

The helper returns every base-banner key so a base-layout page VM can splat it
(Codex R1 M#11 — no hand-copy avoids a 500 when a base field is later added).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Config, load
from swing.data.db import connect, ensure_schema
from swing.web.view_models.journal import _base_banner_fields


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


@pytest.fixture
def conn(cfg):
    c = connect(cfg.paths.db_path)
    yield c
    c.close()


def test_base_banner_fields_complete(conn, cfg):
    fields = _base_banner_fields(conn, cfg)
    required = {"session_date", "stale_banner", "price_source_degraded",
                "price_source_degraded_until", "ohlcv_source_degraded",
                "unresolved_material_discrepancies_count",
                "recent_multi_leg_auto_correction_count", "banner_resolve_link"}
    assert required <= set(fields)


def test_base_banner_fields_types(conn, cfg):
    fields = _base_banner_fields(conn, cfg)
    assert isinstance(fields["session_date"], str) and fields["session_date"]
    assert isinstance(fields["unresolved_material_discrepancies_count"], int)
    assert isinstance(fields["recent_multi_leg_auto_correction_count"], int)
    # banner_resolve_link is None or a path starting with '/'.
    link = fields["banner_resolve_link"]
    assert link is None or (isinstance(link, str) and link.startswith("/"))
