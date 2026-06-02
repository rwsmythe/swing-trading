"""F-1 construction-path test: _construct_web_schwab_client resolves creds via
the env > cfg cascade and returns a client (post-fix) or None + a redacted log
on each None-path. NO real schwabdev.Client (construct_authenticated_client is
monkeypatched). Covers the Class-A credential-plumbing fix (Codex R1 Major #2)."""
from __future__ import annotations

import logging

import pytest

import swing.web.app as web_app


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    # Prevent any user-config write/read from leaking to the real ~/swing-data.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Default: no env-tier creds (each test sets what it needs).
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)


def _ladder_active_cfg(*, client_id="", client_secret=""):
    class _Cfg:
        class integrations:
            class schwab:
                environment = "production"
                marketdata_ladder_enabled = True

    _Cfg.integrations.schwab.client_id = client_id
    _Cfg.integrations.schwab.client_secret = client_secret
    return _Cfg()


class _Sentinel:
    pass


def test_env_tier_creds_construct_client(monkeypatch):
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "envid")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "envsecret")
    monkeypatch.setattr(
        web_app, "construct_authenticated_client",
        lambda cfg, env, *, client_id, client_secret: _Sentinel(),
    )
    out = web_app._construct_web_schwab_client(_ladder_active_cfg())
    assert isinstance(out, _Sentinel)


def test_cfg_tier_creds_construct_client(monkeypatch):
    # The post-fix path: the web cfg surfaces user-config creds at the cfg tier.
    monkeypatch.setattr(
        web_app, "construct_authenticated_client",
        lambda cfg, env, *, client_id, client_secret: _Sentinel(),
    )
    cfg = _ladder_active_cfg(client_id="cfgid", client_secret="cfgsecret")
    out = web_app._construct_web_schwab_client(cfg)
    assert isinstance(out, _Sentinel)


def test_creds_absent_all_tiers_returns_none_and_logs(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    out = web_app._construct_web_schwab_client(_ladder_active_cfg())
    assert out is None
    assert any(
        "credentials absent at the env and cfg tiers" in r.message
        for r in caplog.records
    )


def test_partial_env_tier_raises_caught_returns_none(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "onlyid")  # secret missing -> partial
    out = web_app._construct_web_schwab_client(_ladder_active_cfg())
    assert out is None
    assert any("credentials incomplete" in r.message for r in caplog.records)
