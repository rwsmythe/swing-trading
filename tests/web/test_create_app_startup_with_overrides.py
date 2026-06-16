"""F-1 (Codex R1 Major #1): create_app startup tolerates the overridden cfg.
apply_overrides now reaches create_app -> the risk-policy divergence hook sees
the EFFECTIVE risk_equity_floor; assert no crash + the Schwab creds survive +
_install_web_marketdata_caches is reached with the creds-bearing cfg."""
from __future__ import annotations

from dataclasses import replace

import swing.web.app as web_app


def _effective_cfg_with_schwab_creds_and_divergent_policy(cfg):
    """Mirror apply_overrides' effect: surface user-config Schwab creds + a
    risk_equity_floor that diverges from the seeded risk_policy, via frozen-
    dataclass replace (apply_overrides itself needs a user-config.toml; this
    builds the same EFFECTIVE shape directly)."""
    new_schwab = replace(
        cfg.integrations.schwab, client_id="cfgid", client_secret="cfgsecret",
    )
    new_integrations = replace(cfg.integrations, schwab=new_schwab)
    new_account = replace(cfg.account, risk_equity_floor=99999.0)
    return replace(cfg, integrations=new_integrations, account=new_account)


def test_create_app_with_overridden_cfg_constructs_and_reaches_install(
    seeded_db, tmp_path, monkeypatch,
):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    base_cfg, cfg_path = seeded_db
    cfg = _effective_cfg_with_schwab_creds_and_divergent_policy(base_cfg)

    install_calls = {}

    def _spy_install(cfg_arg, price_cache, ohlcv_cache, app):
        # 18-H.4.1: _install_web_marketdata_caches now also receives `app` (the
        # mutable holder the ladder closures resolve at call time).
        install_calls["cfg"] = cfg_arg
        install_calls["app"] = app
        return None  # no real Schwab client in this startup test

    monkeypatch.setattr(web_app, "_install_web_marketdata_caches", _spy_install)

    app = web_app.create_app(cfg, cfg_path=cfg_path)

    assert app is not None
    # _install_web_marketdata_caches was reached with a creds-bearing cfg
    # (create_app passes the RAW cfg, not the reconciled app.state.cfg).
    assert install_calls["cfg"].integrations.schwab.client_id == "cfgid"
    # 18-H.4.1: install received the app (the mutable schwab_client holder the
    # ladder closures resolve at call time).
    assert install_calls["app"] is app
    # app.state.cfg is set (risk-policy reconciliation did not crash).
    assert getattr(app.state, "cfg", None) is not None
