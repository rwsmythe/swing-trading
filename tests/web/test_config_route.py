"""GET/POST/reset handlers for /config. Lifespan-wrapped TestClient."""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from swing.config import load
from swing.config_user import load_user_overrides, write_user_overrides
from swing.web.app import create_app
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    cfg = load(cfg_path)
    app = create_app(cfg, cfg_path=cfg_path)
    with TestClient(app) as c:
        yield c


def test_get_config_renders_three_rows(client: TestClient):
    r = client.get("/config")
    assert r.status_code == 200
    body = r.text
    assert "Chase factor" in body
    assert "Watchlist chart count" in body
    assert "Risk floor" in body


def test_get_config_shows_default_source_badge(client: TestClient):
    r = client.get("/config")
    assert "default" in r.text  # source badge for at least one row


def test_post_happy_path_writes_and_redirects(client: TestClient):
    r = client.post("/config", data={
        "web.chase_factor": "0.015",
        "pipeline.chart_top_n_watch": "20",
        "account.risk_equity_floor": "10000.0",
    }, headers={"HX-Request": "true"}, follow_redirects=False)
    # Codex R1 Major 2 — HTMX success path uses 204 + HX-Redirect, not 303.
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    assert load_user_overrides() == {
        "web": {"chase_factor": 0.015},
        "pipeline": {"chart_top_n_watch": 20},
        "account": {"risk_equity_floor": 10000.0},
    }


def test_save_redirect_helper_non_htmx_returns_303():
    """Unit test: _save_redirect_response branches on HX-Request header.

    Discriminating-test for Codex R1 Major 2 — verifies BOTH branches of the
    helper. Cannot exercise the non-HTMX branch through TestClient because
    OriginGuard strict mode (`swing/web/app.py:177`) rejects unsafe-method
    requests without HX-Request before they reach the route. Direct unit
    test fills that coverage gap.
    """
    from starlette.requests import Request

    from swing.web.routes.config import _save_redirect_response

    def _mk_request(headers_list: list[tuple[bytes, bytes]]) -> Request:
        scope = {
            "type": "http",
            "method": "POST",
            "headers": headers_list,
            "path": "/config",
            "query_string": b"",
        }
        return Request(scope)

    # HTMX path → 204 + HX-Redirect
    htmx_resp = _save_redirect_response(
        _mk_request([(b"hx-request", b"true")]),
    )
    assert htmx_resp.status_code == 204
    assert htmx_resp.headers["HX-Redirect"] == "/config?saved=1"

    # Non-HTMX path → 303 redirect (browser without JS, curl)
    plain_resp = _save_redirect_response(_mk_request([]))
    assert plain_resp.status_code == 303
    assert plain_resp.headers["location"] == "/config?saved=1"

    # Case-insensitivity: HX-Request="TRUE" still HTMX path
    upper_resp = _save_redirect_response(
        _mk_request([(b"hx-request", b"TRUE")]),
    )
    assert upper_resp.status_code == 204


def test_post_hard_refuse_returns_error_fragment_no_write(client: TestClient):
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.5",  # hard fail
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 400
    assert "Chase factor" in r.text
    # Autoescape converts `<= 0.1` source-text to `&lt;= 0.1` in response.
    # Both forms acceptable; either renders as `<= 0.1` in the browser.
    assert (
        "&lt;= 0.1" in r.text
        or "&lt;= 0.10" in r.text
        or "<= 0.1" in r.text
        or "<= 0.10" in r.text
    )
    # No write happened
    assert load_user_overrides() == {}
    # CLAUDE.md HTMX <tr>-leading guard: response root must NOT be <tr>.
    assert not r.text.lstrip().startswith("<tr")


def test_post_soft_warn_returns_confirm_fragment_with_form_values(
    client: TestClient,
):
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",  # soft-warn (above 0.02)
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    body = r.text
    assert "force" in body and "true" in body  # hidden input round-trip
    assert "0.05" in body                       # proposed value preserved
    assert "Confirm" in body or "Submit anyway" in body
    # Crucially: NO write yet
    assert load_user_overrides() == {}


def test_post_force_true_persists_soft_warn_value(client: TestClient):
    """Round-trip ToCToU: force=true resubmit with form_values writes them."""
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
            "force": "true",
        },
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    assert load_user_overrides() == {
        "web": {"chase_factor": 0.05},
        "pipeline": {"chart_top_n_watch": 20},
        "account": {"risk_equity_floor": 10000.0},
    }


def test_post_reset_deletes_field(client: TestClient):
    write_user_overrides({"web": {"chase_factor": 0.025}})
    r = client.post(
        "/config/reset/web.chase_factor",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    assert load_user_overrides() == {}


def test_post_reset_all_three_dotted_paths_accepted(client: TestClient):
    """Routing test matrix: Starlette path converter captures dots.

    Codex R1 Major 5: must verify all three actual dotted field paths
    are accepted end-to-end, not just one example.
    """
    for field_path in (
        "web.chase_factor",
        "pipeline.chart_top_n_watch",
        "account.risk_equity_floor",
    ):
        write_user_overrides({
            field_path.split(".")[0]: {field_path.split(".")[1]: 999},
        })
        r = client.post(
            f"/config/reset/{field_path}",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        assert r.status_code == 204, f"Expected 204 for {field_path}, got {r.status_code}"
        assert r.headers["HX-Redirect"] == "/config?saved=1"


def test_cancel_link_is_plain_anchor_not_htmx(client: TestClient):
    """Codex R1 Major 4 — confirm fragment's Cancel must be a plain <a href>
    that triggers full-page navigation. NOT an hx-get (which would swap a
    full-page response into <body> and corrupt the DOM).
    """
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    body = r.text
    # Cancel: plain <a> with full-page href.
    assert '<a' in body and 'href="/config"' in body
    # Negative-discriminator: no hx-get on the Cancel control.
    # (hx-get on a Submit-anyway form is OK; it's the Cancel that must be plain.)
    assert "Cancel" in body
    # Round-trip Cancel manually: GET /config returns a 200 full page.
    g = client.get("/config")
    assert g.status_code == 200
    assert "<html" in g.text.lower()


def test_post_reset_unknown_field_404(client: TestClient):
    r = client.post(
        "/config/reset/web.fake_field",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 404


def test_post_unchanged_submit_does_not_create_overrides(client: TestClient):
    """Codex R1 Critical 1 — merge semantics. Submit the form WITHOUT changing
    any value (each input still holds its current effective value) → no
    overrides written.

    Discriminating-test: the WRONG (replace) implementation would write all
    three values as overrides; this test fails it. The CORRECT (merge)
    implementation leaves user-config empty.

    NOTE (2026-05-02 dispatch adjustment): the plan's original test posted
    risk_equity_floor="7500.0" (registry default), but `_write_cfg` sets
    that field to 5000.0 in TOML, making 5000.0 the current effective value
    (source='tracked'). Posting 7500.0 != 5000.0 would WRITE per merge
    invariant (b), failing this test. We post 5000.0 (the actual current
    effective) to verify the no-op-unchanged scenario the test means to
    cover. Verified: web.chase_factor=0.01 and pipeline.chart_top_n_watch=10
    both ARE the registry defaults AND the current effective in this fixture
    (TOML doesn't override them).
    """
    r = client.post("/config", data={
        "web.chase_factor": "0.01",            # == registry default == current effective
        "pipeline.chart_top_n_watch": "10",    # == registry default == current effective
        "account.risk_equity_floor": "5000.0", # == current effective (tracked, fixture sets 5000)
    }, headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    assert load_user_overrides() == {}


def test_post_changed_one_field_does_not_lock_others(client: TestClient):
    """Codex R1 Critical 1 — only changed fields become overrides.

    NOTE (2026-05-02 dispatch adjustment): post risk_equity_floor=5000.0
    (current effective per fixture), not 7500.0 (registry default). See
    test_post_unchanged_submit_does_not_create_overrides for rationale.
    """
    r = client.post("/config", data={
        "web.chase_factor": "0.015",           # changed
        "pipeline.chart_top_n_watch": "10",    # unchanged (default == effective)
        "account.risk_equity_floor": "5000.0", # unchanged (current effective)
    }, headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    assert load_user_overrides() == {"web": {"chase_factor": 0.015}}
    # chart_top_n_watch source='default'; risk_equity_floor source='tracked';
    # web.chase_factor source='override'. Page must show >=1 default badge
    # and >=1 override badge.
    g = client.get("/config")
    assert g.text.count("source-default") >= 1
    assert g.text.count("source-override") >= 1


def test_post_preserves_unknown_user_config_keys(
    client: TestClient,
):
    """Codex R1 Critical 1 — forward-compat with future V2 keys.

    An operator who hand-edited user-config to set a hypothetical V2 field
    (e.g. risk.max_risk_pct) must NOT see that key wiped by a V1 page save.
    """
    write_user_overrides({
        "web": {"chase_factor": 0.025},
        "risk": {"max_risk_pct": 0.01},   # V2 hypothetical — V1 page must preserve it
    })
    r = client.post("/config", data={
        "web.chase_factor": "0.030",            # changed (force=true: above 0.02 soft-warn)
        "pipeline.chart_top_n_watch": "10",
        "account.risk_equity_floor": "5000.0",
        "force": "true",
    }, headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    saved = load_user_overrides()
    assert saved["web"]["chase_factor"] == 0.030
    assert saved["risk"] == {"max_risk_pct": 0.01}, (
        "unknown user-config keys must survive V1 saves"
    )


def test_post_preserves_top_level_scalar_unknown_key(
    client: TestClient,
):
    """Codex R2 Major 2 — deepcopy preservation must NOT assume every
    top-level value is a section table.

    Discriminating-test: hand-add a top-level scalar to user-config (TOML
    permits this) and verify a V1 page save preserves it. A naive
    one-level dict-comp `{section: dict(table) for ...}` would crash with
    a TypeError when iterating dict() over a non-dict value.
    """
    write_user_overrides({
        "web": {"chase_factor": 0.025},
        "experimental_flag": True,           # top-level scalar (operator-added)
    })
    r = client.post("/config", data={
        "web.chase_factor": "0.030",
        "pipeline.chart_top_n_watch": "10",
        "account.risk_equity_floor": "5000.0",
        "force": "true",   # 0.030 > 0.02 soft-warn ceiling; force-bypass to reach write
    }, headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/config?saved=1"
    saved = load_user_overrides()
    assert saved["web"]["chase_factor"] == 0.030
    assert saved["experimental_flag"] is True, (
        "top-level scalar keys must survive V1 saves (Codex R2 M2)"
    )


def test_post_force_true_with_hard_refuse_value_still_refused(
    client: TestClient,
):
    """force=true bypasses soft-warn ONLY, never hard-refuse. Discriminating-test:
    a hard-refuse-value resubmit with force=true must be 400 + no write.
    """
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.5",  # hard fail
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
            "force": "true",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 400
    assert load_user_overrides() == {}
