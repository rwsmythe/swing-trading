"""F-1 propagation test: `swing web` applies user-config overrides before
handing the cfg to run_server (mirrors the pipeline_run_cmd propagation
contract). Without this the web Schwab client cannot resolve creds."""
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from swing.cli import main


def test_web_cmd_applies_overrides_before_run_server(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    captured = {}

    def _fake_run_server(*, cfg, cfg_path, host, port, reload):
        captured["cfg"] = cfg

    sentinel_cfg = object()

    with patch("swing.web.cli_cmd.run_server", _fake_run_server), \
         patch(
             "swing.config_overrides.apply_overrides",
             return_value=sentinel_cfg,
         ) as ov:
        runner = CliRunner()
        result = runner.invoke(main, ["web"])

    assert ov.called, "web_cmd must call apply_overrides"
    assert captured.get("cfg") is sentinel_cfg, (
        "run_server must receive the OVERRIDDEN cfg"
    )
    assert result.exit_code == 0, result.output
