"""Task 5.4 — chevron column + row-partial extraction regression tests.

Discriminating contracts (spec §3.5.5 Q-C resolution + plan line 1701):
- The chevron BUTTON is the HTMX trigger; the <tr> itself is NOT a trigger.
- The row partial is the single source of truth — refresh route and full-page
  render both flow through the SAME `{% include %}` chain, preventing
  HTMX OOB-swap drift (CLAUDE.md gotcha).
- The collapsed row carries `id="hyp-rec-row-{ticker}"` so the close button +
  404/500 unavailable partials can target it back.
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from swing.web.app import create_app

from .test_routes.test_hyp_recs_expand_route import (
    _patch_price_cache,
    _seed_hyp_recs_fixture,
)


def _extract_tr_open_tag(body: str, ticker: str) -> str:
    """Return the literal opening <tr ...> tag for the row whose id matches.

    Anchored on `id="hyp-rec-row-{ticker}"`. Returns the substring from `<tr `
    up to and including the closing `>` of the OPEN tag (NOT the whole row).
    """
    # Match `<tr ...id="hyp-rec-row-NVDA"...>` — capture the open tag only.
    pattern = re.compile(
        r"<tr\b[^>]*\bid=\"hyp-rec-row-" + re.escape(ticker) + r"\"[^>]*>",
    )
    m = pattern.search(body)
    assert m is not None, (
        f"could not find <tr> open tag with id=hyp-rec-row-{ticker} in body"
    )
    return m.group(0)


def test_chevron_column_header_present(seeded_db, monkeypatch):
    """Sanity (test 1) — the new chevron <th> appears in the table head."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert '<th aria-label="Expand"' in body, (
        "chevron column header must be present (first <th> in thead)"
    )


def test_chevron_button_markup(seeded_db, monkeypatch):
    """Sanity (test 2) — chevron BUTTON has the expected HTMX attributes."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert 'class="expand-toggle"' in body, "chevron button must have class"
    assert 'hx-get="/hyp-recs/NVDA/expand"' in body, (
        "chevron button must hx-get the expand route for the row's ticker"
    )
    assert 'hx-target="closest tr"' in body, (
        "chevron button must hx-target='closest tr' so the row is the swap target"
    )
    assert 'hx-swap="outerHTML"' in body, (
        "chevron button must use outerHTML swap to replace the entire <tr>"
    )


def test_tr_has_no_hx_get_attribute(seeded_db, monkeypatch):
    """Discriminating contract (test 3) — per spec §3.5.5 Q-C resolution,
    the hyp-recs <tr> is NOT itself an HTMX trigger; only the chevron BUTTON
    is. Hand-extract the <tr> opening tag and assert no hx-get inside it.

    A regression where the <tr> grows hx-get/hx-trigger attributes would
    fail this test; the watchlist row IS a trigger by contrast.
    """
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    tr_open = _extract_tr_open_tag(body, "NVDA")
    # Only the chevron BUTTON inside the row may carry hx-get/hx-target/etc.
    # The <tr> open tag itself MUST be free of those attributes.
    assert "hx-get" not in tr_open, (
        f"<tr> must NOT have hx-get (chevron BUTTON is the trigger). Got: {tr_open}"
    )
    assert "hx-target" not in tr_open, (
        f"<tr> must NOT have hx-target. Got: {tr_open}"
    )
    assert "hx-trigger" not in tr_open, (
        f"<tr> must NOT have hx-trigger. Got: {tr_open}"
    )
    # And the body MUST contain a chevron BUTTON with hx-get for the same
    # ticker — otherwise the trigger is missing entirely.
    assert 'hx-get="/hyp-recs/NVDA/expand"' in body


def test_row_has_id_for_close_target(seeded_db, monkeypatch):
    """Sanity (test 4) — the <tr> carries id='hyp-rec-row-{ticker}' so the
    close button + 404/500 unavailable partials can target it via swap."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert 'id="hyp-rec-row-NVDA"' in body
    assert 'id="hyp-rec-row-AMD"' in body


def test_chevron_drift_equivalence_refresh_vs_full_page(seeded_db, monkeypatch):
    """Discriminating regression (test 5) — both routes must include the
    SAME row partial, so the chevron BUTTON markup is byte-equivalent
    across the two renders. CLAUDE.md HTMX OOB-swap drift gotcha: hand-
    duplicated row markup will diverge here.
    """
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        full_resp = client.get("/")
        refresh_resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert full_resp.status_code == 200
    assert refresh_resp.status_code == 200

    # Extract the literal chevron BUTTON tag for NVDA from each render.
    btn_pattern = re.compile(
        r'<button[^>]*class="expand-toggle"[^>]*'
        r'hx-get="/hyp-recs/NVDA/expand"[^>]*>[^<]*</button>',
    )
    full_btn = btn_pattern.search(full_resp.text)
    refresh_btn = btn_pattern.search(refresh_resp.text)
    assert full_btn is not None, (
        "full-page render missing chevron BUTTON for NVDA"
    )
    assert refresh_btn is not None, (
        "refresh route render missing chevron BUTTON for NVDA"
    )
    assert full_btn.group(0) == refresh_btn.group(0), (
        "chevron BUTTON markup drifts between full-page and refresh-route"
        f" renders.\nfull={full_btn.group(0)}\nrefresh={refresh_btn.group(0)}"
    )


def test_existing_seven_columns_preserved(seeded_db, monkeypatch):
    """Sanity (test 6) — the original 7 columns still render. Guards against
    the chevron-column patch accidentally clobbering existing <th> entries.
    """
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    body = resp.text
    # Anchor on the hyp-recs section's thead.
    section_thead = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*>.*?</thead>',
        body, flags=re.DOTALL,
    )
    assert section_thead is not None
    section = section_thead.group(0)
    for label in (
        "Ticker", "Price", "Pivot", "Hypothesis",
        "Progress", "Tripwire", "Suggested label",
    ):
        assert f">{label}<" in section, (
            f"existing column header '{label}' missing from thead"
        )
    # Column count = 8 at the end of Task 5.4 (chevron + 7 existing).
    th_pattern = re.compile(r"<th\b[^>]*>", flags=re.DOTALL)
    th_count = len(th_pattern.findall(section))
    assert th_count == 8, (
        f"expected 8 thead <th> elements (chevron + 7 originals), got {th_count}"
    )
