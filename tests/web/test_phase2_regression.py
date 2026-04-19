"""Confirm the [web] extra is purely additive on top of Phase 2."""
from __future__ import annotations

import importlib

import pytest


PHASE2_PACKAGES = [
    "swing.config",
    "swing.data.db",
    "swing.pipeline",
    "swing.trades.advisory",
    "swing.trades.equity",
    "swing.evaluation.dates",
    "swing.journal.stats",
    "swing.rendering.briefing",
]


def test_phase2_packages_import_without_web_stack(monkeypatch):
    """Simulate `[web]` extra NOT installed: pretend fastapi/uvicorn are missing.

    If any Phase 2 module accidentally imports the web stack, this test fails.
    """
    # Note: jinja2 is a BASE dependency (pyproject.toml [project].dependencies),
    # so it is not hidden here. Only fastapi/uvicorn/starlette are web-extra-only.
    hidden = ("fastapi", "uvicorn", "starlette")
    for name in hidden:
        monkeypatch.setitem(__import__("sys").modules, name, None)

    for mod in PHASE2_PACKAGES:
        # Force a fresh import (drop cached copies that may have loaded the stack).
        import sys
        sys.modules.pop(mod, None)
        try:
            importlib.import_module(mod)
        except ImportError as exc:
            if any(s in str(exc) for s in ("fastapi", "uvicorn", "starlette")):
                pytest.fail(
                    f"Phase 2 module {mod} imports the web stack (via: {exc})"
                )
            raise


def test_web_extra_install_starts_app(test_cfg):
    """With the web extra installed (this test already running through pytest
    under the [web] extra), create_app must boot without ImportError."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert app is not None
    assert app.state.cfg is cfg


def test_cli_import_does_not_pull_in_web_stack(monkeypatch):
    """Proves `from swing.cli import main` does not transitively import
    fastapi/uvicorn/starlette. Regression guard for R1 Major 3: the
    base install must continue to run the CLI even without the [web] extra.

    The test works by replacing the web-stack modules with None in
    sys.modules BEFORE importing swing.cli fresh. If swing.cli (or any
    module it transitively imports at module-import time) touches one of
    those names, Python will surface an ImportError during import."""
    import sys
    # Note: jinja2 is a BASE dependency (pyproject.toml [project].dependencies),
    # so it is not hidden here. Only fastapi/uvicorn/starlette are web-extra-only.
    hidden = ("fastapi", "uvicorn", "starlette")
    for name in hidden:
        monkeypatch.setitem(sys.modules, name, None)
    # Drop any cached Phase 2 / CLI modules so the import goes through fresh.
    for name in list(sys.modules):
        if name == "swing" or name.startswith("swing."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    # Clean import — must succeed regardless of the [web] extra.
    importlib.import_module("swing.cli")


def test_cli_help_lists_all_subcommands_without_web_stack(monkeypatch, capsys):
    """Even with the web stack hidden, `swing --help` must enumerate every
    subcommand (including `web`, because the command's backing import is
    inside its function body, not at module top). Proves the lazy-import
    contract from T8."""
    import sys
    # Note: jinja2 is a BASE dependency (pyproject.toml [project].dependencies),
    # so it is not hidden here. Only fastapi/uvicorn/starlette are web-extra-only.
    hidden = ("fastapi", "uvicorn", "starlette")
    for name in hidden:
        monkeypatch.setitem(sys.modules, name, None)
    for name in list(sys.modules):
        if name == "swing" or name.startswith("swing."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    from click.testing import CliRunner
    from swing.cli import main
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0
    assert "web" in r.output.lower()
