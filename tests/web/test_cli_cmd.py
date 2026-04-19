"""`swing web` CLI + run_server guards."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.web.cli_cmd import run_server


def test_refuses_non_loopback_host(test_cfg, capsys):
    cfg, cfg_path = test_cfg
    with pytest.raises(SystemExit) as exc:
        run_server(cfg=cfg, cfg_path=cfg_path, host="0.0.0.0", port=None, reload=None)
    assert exc.value.code == 1
    out = capsys.readouterr().err
    assert "loopback" in out.lower() or "127.0.0.1" in out


def test_refuses_non_loopback_from_config(test_cfg, capsys, tmp_path):
    """The [web].host config value is also enforced — user cannot bypass via config."""
    from swing.config import Config, Web
    cfg, cfg_path = test_cfg
    # Replace the web config with a non-loopback host.
    import dataclasses
    bad_web = dataclasses.replace(cfg.web, host="0.0.0.0")
    bad_cfg = dataclasses.replace(cfg, web=bad_web)
    with pytest.raises(SystemExit) as exc:
        run_server(cfg=bad_cfg, cfg_path=cfg_path, host=None, port=None, reload=None)
    assert exc.value.code == 1


def test_cli_overrides_config(test_cfg, monkeypatch):
    cfg, cfg_path = test_cfg
    captured = {}

    def fake_run(app, *, host, port, reload, **_):
        captured["host"] = host
        captured["port"] = port
        captured["reload"] = reload

    monkeypatch.setattr("uvicorn.run", fake_run)
    run_server(cfg=cfg, cfg_path=cfg_path, host=None, port=9191, reload=True)
    assert captured["port"] == 9191
    assert captured["reload"] is True
    assert captured["host"] == "127.0.0.1"


def test_swing_web_cli_registered():
    """The `web` subcommand is visible via `swing web --help`."""
    from click.testing import CliRunner
    from swing.cli import main
    r = CliRunner().invoke(main, ["web", "--help"])
    assert r.exit_code == 0
    assert "web" in r.output.lower()
