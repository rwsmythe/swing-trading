"""Production-path regression (gotcha #15 / plan §C.5): GET /schwab/status renders
token-health off the v3 SQLite reader -- a REAL on-disk v3 DB, not a stub.

Mirrors tests/web/test_routes/test_schwab_status.py's _isolate_home + seeded_db +
create_app fixtures, but seeds a v3 SQLite tokens DB (via the new writer) instead of the
legacy JSON. Placed under tests/web/test_routes/ because `seeded_db` lives in
tests/web/conftest.py (the plan's tests/integration/ path lacks that fixture).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from swing.integrations.schwab import auth
from swing.web.app import create_app


def _isolate_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


def _seed_v3_tokens_db(tmp_path, env: str = "production") -> None:
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    tokens_path = swing_data / f"schwab-tokens.{env}.db"
    auth._write_schwabdev_tokens_db(
        tokens_path=tokens_path,
        token_dictionary={"access_token": "AToken-SENTINEL", "refresh_token": "RToken-SENTINEL",
                          "id_token": "ID", "expires_in": 1800, "token_type": "Bearer",
                          "scope": "api"},
        issued_at=datetime.now(timezone.utc), fernet_key=None)


def test_status_page_renders_off_v3_reader(seeded_db, monkeypatch, tmp_path) -> None:
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_v3_tokens_db(tmp_path, "production")
    app = create_app(cfg, cfg_path)
    # Pre-fix: the status VM's _read_tokens_metadata json.load on a v3 SQLite file ->
    # the page degrades/errs. Post-fix: it reads the v3 row -> the page renders the
    # token-health section. Lifespan-entered client (app.state).
    with TestClient(app) as client:
        resp = client.get("/schwab/status?environment=production")
    assert resp.status_code == 200
    body = resp.text
    # The PRESERVED at-a-glance page renders (NOT a new widget).
    assert "Schwab integration status" in body
    # And NO secret bytes leak into the page (the presence-only reader never holds them).
    assert "AToken-SENTINEL" not in body and "RToken-SENTINEL" not in body
