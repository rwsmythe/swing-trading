"""Spec §3.2a: base.html.j2 must override htmx.config.responseHandling so that
4xx responses swap into the DOM. Phase 3b's trade_form_error.html.j2 fragments
and Phase 3c's new fragments all depend on this."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_dashboard_page_contains_htmx_config_override(test_cfg, seeded_db):
    """Ordered-source check: htmx.min.js comes first, then the config override
    containing both '[45]..' and 'swap: true' tokens."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    htmx_pos = body.find("/static/htmx.min.js")
    cfg_pos = body.find("htmx.config.responseHandling")
    assert htmx_pos > 0, "htmx.min.js script tag missing"
    assert cfg_pos > htmx_pos, (
        "htmx.config.responseHandling override must appear AFTER htmx.min.js "
        "in source order so the config can be applied"
    )
    assert '"[45].."' in body, "override must include 4xx code selector"
    assert "swap: true" in body, "override must enable swapping"


def test_override_changes_4xx_entry_from_default(test_cfg, seeded_db):
    """The override must include the 4xx entry with swap:true (default is swap:false)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    # Default HTMX config has `{code: "[45]..", swap: false, error: true}`.
    # Ours must set swap: true on the 4xx entry.
    body = r.text
    # Allow whitespace variations
    import re
    m = re.search(
        r'\{[^{}]*"?\[45\]\.\."?[^{}]*swap:\s*true[^{}]*\}',
        body, re.DOTALL,
    )
    assert m is not None, (
        "4xx entry with swap: true not found in override — fragment rendering "
        "will not work in browser"
    )
