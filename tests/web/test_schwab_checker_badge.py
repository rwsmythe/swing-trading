"""Slice 3 — web checker-health badge helper + base-VM field fan-out + render."""
from __future__ import annotations

import json
import time

from swing.integrations.schwab import checker_resilience as cr
from swing.web.view_models.schwab_checker_badge import (
    SchwabCheckerBadgeVM,
    build_schwab_checker_badge,
)


def test_badge_none_when_sidecar_absent(tmp_path, monkeypatch, seeded_db):
    cfg, _ = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert build_schwab_checker_badge(cfg) is None  # hidden when no sidecar


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


def test_dashboard_hides_badge_when_sidecar_absent(tmp_path, monkeypatch, seeded_db):
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    from fastapi.testclient import TestClient

    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "schwab-health-badge" not in resp.text


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
