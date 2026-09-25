"""22-F R2-04 (Reviewer A round 2; CHARC-ruled, group 3, option (b)) -- the
WEB caller of `apply_tier2_resolution` (`POST /reconcile/discrepancy/{id}/
resolve`) binds `durable` from `CorrectionResult.wrote`.  PRE-FIX it bound
`durable = True` unconditionally; the route's 409 pre-check refuses a row
already terminal BEFORE the call, so the service's step-2 idempotent return
is reachable only through a race -- a concurrent resolution between the
pre-check and the service's `BEGIN IMMEDIATE`.  Driven by a wrapper at the
name the route resolves at call time (`swing.web.routes.reconcile.
apply_tier2_resolution`) that commits the terminal resolution on a SEPARATE
connection and then calls the REAL service.  The CLI caller and the service
are in `tests/cli/test_22f_r2_04_tier2_wrote.py`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app
from tests.cli.test_22f_r2_04_tier2_wrote import _corrections, _racing
from tests.web.test_22f_close_after_durable_roots import (
    _HX,
    _fail_nth_close,
    _helper_records,
)
from tests.web.test_reconcile_resolve_post_route import _seed_discrepancy

_TARGET = "swing.web.routes.reconcile.open_connection"
_FORM = {"choice_code": "keep_journal_as_is",
         "resolution_reason": "r2-04 probe",
         "ambiguity_kind_at_render": "multi_partial_vs_consolidated"}


def test_r2_04_web_race_to_terminal_is_not_durable(
        seeded_db: tuple[Config, Path], monkeypatch, caplog):
    cfg, cfg_path = seeded_db
    db = cfg.paths.db_path
    did = _seed_discrepancy(db)
    import swing.web.routes.reconcile as route
    wrapper = _racing(route.apply_tier2_resolution, db, did)
    monkeypatch.setattr(route, "apply_tier2_resolution", wrapper)
    before = _corrections(db)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        built = _fail_nth_close(monkeypatch, _TARGET, 1)
        with caplog.at_level(logging.ERROR):
            resp = tc.post(f"/reconcile/discrepancy/{did}/resolve",
                           headers=_HX, data=_FORM)
    assert wrapper.calls == 1  # did-it-fire (the race)
    assert built and built[0].calls["close"] >= 1  # did-it-fire
    assert _helper_records(caplog) == []
    assert "IS recorded" not in resp.text
    assert resp.status_code == 500, (resp.status_code, resp.text[:600])
    assert _corrections(db) == before


def test_r2_04_web_write_path_with_failing_close_is_success_control(
        seeded_db: tuple[Config, Path], monkeypatch, caplog):
    """CONTROL (both trees): the handler writes -> 204 with the helper's
    one ERROR record; the correction is durable on a fresh read."""
    cfg, cfg_path = seeded_db
    db = cfg.paths.db_path
    did = _seed_discrepancy(db)
    before = _corrections(db)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        built = _fail_nth_close(monkeypatch, _TARGET, 1)
        with caplog.at_level(logging.ERROR):
            resp = tc.post(f"/reconcile/discrepancy/{did}/resolve",
                           headers=_HX, data=_FORM)
    assert built and built[0].calls["close"] >= 1
    assert resp.status_code == 204, (resp.status_code, resp.text[:600])
    assert len(_helper_records(caplog)) == 1
    assert _corrections(db) == before + 1


def test_r2_04_web_already_terminal_409_control(
        seeded_db: tuple[Config, Path], monkeypatch):
    """CONTROL (both trees): a row ALREADY terminal before the POST is
    refused 409 before the service is called (`reconcile.py`'s pre-check);
    nothing is written."""
    cfg, cfg_path = seeded_db
    db = cfg.paths.db_path
    did = _seed_discrepancy(db, resolution="operator_resolved_ambiguity",
                            resolved_by="operator",
                            resolved_at="2026-05-18T12:00:00")
    before = _corrections(db)
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.post(f"/reconcile/discrepancy/{did}/resolve", headers=_HX,
                       data=_FORM)
    assert resp.status_code == 409, (resp.status_code, resp.text[:600])
    assert _corrections(db) == before
