"""Slice 3 — web checker-health badge helper + base-VM field fan-out + render."""
from __future__ import annotations

import json
import time
import types

import pytest

from swing.integrations.schwab import checker_resilience as cr
from swing.web.view_models.schwab_checker_badge import (
    SchwabCheckerBadgeVM,
    build_schwab_checker_badge,
)


def _make_cfg(*, environment: str, marketdata_ladder_enabled: bool):
    """Minimal cfg tree for build_schwab_checker_badge / _is_ladder_active.

    Both consume the config via getattr on
    ``cfg.integrations.schwab.{environment,marketdata_ladder_enabled}``, so a
    SimpleNamespace tree is sufficient (no real Config load needed).
    """
    return types.SimpleNamespace(
        integrations=types.SimpleNamespace(
            schwab=types.SimpleNamespace(
                environment=environment,
                marketdata_ladder_enabled=marketdata_ladder_enabled,
            )
        )
    )


def test_badge_unknown_when_sidecar_absent_and_expected(tmp_path, monkeypatch, seeded_db):
    # Phase 14 close-out (A-7): the seeded test cfg defaults to
    # production + ladder-enabled, so a MISSING sidecar now renders the UNKNOWN
    # (Schwab?, warn) badge instead of vanishing (the old buggy behavior). This
    # is the real-Config complement to
    # test_badge_unknown_when_ladder_active_and_no_sidecar (SimpleNamespace cfg).
    cfg, _ = seeded_db
    assert cfg.integrations.schwab.environment == "production"
    assert cfg.integrations.schwab.marketdata_ladder_enabled is True
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    vm = build_schwab_checker_badge(cfg)
    assert vm is not None and vm.state == "UNKNOWN" and vm.css_class == "warn"


def test_badge_none_when_cfg_is_none():
    # Broad population across builders is safe even where a caller lacks a
    # resolved Config: None cfg yields None (no AttributeError).
    assert build_schwab_checker_badge(None) is None


def test_badge_alive(tmp_path, monkeypatch, seeded_db):
    cfg, _ = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    env = cfg.integrations.schwab.environment
    p = cr.checker_liveness_sidecar_path(env)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(), "consecutive_failures": 0}
    ), encoding="ascii")
    badge = build_schwab_checker_badge(cfg)
    assert isinstance(badge, SchwabCheckerBadgeVM)
    assert badge.state == "ALIVE"
    assert badge.label.isascii() and badge.title.isascii() and badge.css_class.isascii()


def test_every_base_layout_vm_has_badge_field_with_safe_default():
    # COMPLETE set: BaseLayoutVM (Family A -- covers the metrics/account/pattern
    # VMs by inheritance) + all 16 Family B VMs.
    from dataclasses import fields

    from swing.web.view_models.config import ConfigPageVM
    from swing.web.view_models.dashboard import DashboardVM
    from swing.web.view_models.error import PageErrorVM
    from swing.web.view_models.journal import JournalVM, TradeDrilldownVM
    from swing.web.view_models.metrics.shared import BaseLayoutVM
    from swing.web.view_models.pipeline import PipelineVM
    from swing.web.view_models.reconcile import (
        ReconcileDiscrepancyErrorVM,
        ReconcileDiscrepancyResolveVM,
    )
    from swing.web.view_models.schwab import (
        SchwabSetupErrorVM,
        SchwabSetupVM,
        SchwabStatusVM,
    )
    from swing.web.view_models.trades import (
        CadenceCompleteVM,
        ReviewsPendingVM,
        ReviewVM,
        TradeDetailVM,
    )
    from swing.web.view_models.watchlist import WatchlistVM
    for vm_cls in (
        BaseLayoutVM, DashboardVM, PipelineVM, JournalVM, TradeDrilldownVM,
        WatchlistVM, PageErrorVM, ConfigPageVM, SchwabSetupVM, SchwabSetupErrorVM,
        SchwabStatusVM, ReconcileDiscrepancyResolveVM, ReconcileDiscrepancyErrorVM,
        ReviewVM, ReviewsPendingVM, CadenceCompleteVM, TradeDetailVM,
    ):
        names = {f.name for f in fields(vm_cls)}
        assert "schwab_checker_badge" in names, vm_cls.__name__


def test_dashboard_renders_badge_when_sidecar_present(tmp_path, monkeypatch, seeded_db):
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    p = cr.checker_liveness_sidecar_path(cfg.integrations.schwab.environment)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(), "consecutive_failures": 0}
    ), encoding="ascii")
    from fastapi.testclient import TestClient

    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "schwab-health-badge" in resp.text


def test_dashboard_shows_unknown_badge_when_expected_and_no_sidecar(
    tmp_path, monkeypatch, seeded_db,
):
    # Phase 14 close-out (A-7): production + ladder-enabled (the seeded default)
    # with NO constructible Schwab client (tmp HOME, no creds) installs no
    # checker and writes no sidecar -> the topbar shows the UNKNOWN (warn) badge
    # rather than nothing. Real Config + real create_app render (production path).
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    import swing.web.app as web_app
    monkeypatch.setattr(web_app, "_construct_web_schwab_client", lambda cfg: None)
    from fastapi.testclient import TestClient

    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "schwab-health-badge--warn" in resp.text
    assert "Schwab?" in resp.text


def test_unpopulated_base_extending_route_renders_200_with_sidecar(tmp_path, monkeypatch, seeded_db):
    # Regression: a base-extending route whose VM does NOT populate the badge
    # MUST still render 200 EVEN WHEN a sidecar exists (the truthiness {% if %}
    # guard handles the missing/None field). /reviews/pending is such a route
    # (ReviewsPendingVM is not populated in V1).
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    p = cr.checker_liveness_sidecar_path(cfg.integrations.schwab.environment)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(), "consecutive_failures": 0}
    ), encoding="ascii")
    from fastapi.testclient import TestClient

    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/reviews/pending")
    assert resp.status_code == 200  # no Jinja UndefinedError despite the un-populated VM


@pytest.mark.parametrize(
    "path",
    ["/pipeline", "/watchlist", "/metrics", "/schwab/status", "/schwab/setup"],
)
def test_primary_nav_route_populates_badge_when_sidecar_present(
    path, tmp_path, monkeypatch, seeded_db,
):
    # Codex R1 MAJOR: these primary base-layout builders never populated the
    # badge, so with a valid sidecar the pages silently hid it. Each must now
    # render the topbar badge. (Pre-fix: badge field defaulted None -> absent.)
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    p = cr.checker_liveness_sidecar_path(cfg.integrations.schwab.environment)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(), "consecutive_failures": 0}
    ), encoding="ascii")
    from fastapi.testclient import TestClient

    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(path)
    assert resp.status_code == 200, resp.text[:500]
    assert "schwab-health-badge" in resp.text, f"badge absent on {path}"


def test_badge_unknown_when_ladder_active_and_no_sidecar(monkeypatch, tmp_path):
    # Isolate HOME so checker_liveness_sidecar_path resolves under tmp (no real
    # sidecar). Production + ladder enabled -> the checker is EXPECTED, so a
    # missing sidecar renders UNKNOWN rather than hiding (A-7).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = _make_cfg(environment="production", marketdata_ladder_enabled=True)
    vm = build_schwab_checker_badge(cfg)
    assert vm is not None
    assert vm.state == "UNKNOWN"
    assert vm.label == "Schwab?"
    assert vm.css_class == "warn"
    # reason-text refinement: not the misleading default
    assert "web server not running" not in vm.title
    assert "check credentials/tokens" in vm.title
    assert vm.title.isascii()


def test_badge_hidden_when_ladder_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = _make_cfg(environment="production", marketdata_ladder_enabled=False)
    assert build_schwab_checker_badge(cfg) is None


def test_badge_hidden_in_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = _make_cfg(environment="sandbox", marketdata_ladder_enabled=True)
    assert build_schwab_checker_badge(cfg) is None
