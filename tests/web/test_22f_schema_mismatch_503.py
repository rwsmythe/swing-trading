"""22-F T-C1 -- F-F7 web half (C1-14): `SchemaVersionMismatchError` is an
operator-actionable state, not an internal error.  A registered handler for
the type (Starlette resolves the most specific class; the `Exception` handler
stays) renders the actionable message at 503 through the same three-way
template branch as the generic handler.

The drive: the app starts on a current DB, then the DB's `schema_version` is
set to 40 by raw sqlite3 -- the "migrated under a running server" shape
reversed; any mismatch makes `swing.data.db.connect` raise the type.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app

_HX = {"HX-Request": "true"}


def _set_version(db_path: Path, version: int) -> None:
    c = sqlite3.connect(str(db_path))
    try:
        c.execute("UPDATE schema_version SET version = ?", (version,))
        c.commit()
    finally:
        c.close()


def _get(seeded_db, *, stale: bool, headers=None):
    cfg, cfg_path = seeded_db
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        if stale:
            _set_version(cfg.paths.db_path, 40)
        return tc.get("/journal", headers=headers or {})


def test_C1a_stale_schema_full_page_is_503_naming_db_migrate(
        seeded_db: tuple[Config, Path]):
    """C1-a. PRE-FIX: 500, the generic error page.  POST-FIX: 503, the
    body names `swing db-migrate`."""
    resp = _get(seeded_db, stale=True)
    assert resp.status_code == 503, (resp.status_code, resp.text[:300])
    assert "swing db-migrate" in resp.text


def test_C1b_stale_schema_htmx_is_a_503_fragment(
        seeded_db: tuple[Config, Path]):
    """C1-b. PRE-FIX: a 500 fragment.  POST-FIX: a 503 fragment carrying the
    message."""
    resp = _get(seeded_db, stale=True, headers=_HX)
    assert resp.status_code == 503, (resp.status_code, resp.text[:300])
    assert "swing db-migrate" in resp.text
    assert "<html" not in resp.text.lower()


def test_C1c_control_current_schema_is_200(seeded_db: tuple[Config, Path]):
    """C1-c CONTROL: a current DB serves 200, both trees."""
    assert _get(seeded_db, stale=False).status_code == 200


def test_C1d_control_unrelated_error_is_still_the_generic_500(
        seeded_db: tuple[Config, Path], monkeypatch):
    """C1-d CONTROL: an unrelated `RuntimeError` planted in the route's
    `build_journal` (bound by `swing.web.routes.journal`'s module-level
    import, resolved per call) still reaches the generic `Exception` handler
    at 500, both trees."""
    from tests._22f_proxies import raising
    planted = raising(RuntimeError("planted unrelated"))
    monkeypatch.setattr("swing.web.routes.journal.build_journal", planted)
    resp = _get(seeded_db, stale=False)
    assert planted.calls >= 1  # did-it-fire
    assert resp.status_code == 500
    assert "planted unrelated" in resp.text
