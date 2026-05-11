"""3e.10 dark theme — Task B nav-bar toggle + FOUC-free script contracts.

Pins six contracts on base.html.j2 (rendered via TestClient GET `/`):

  B.1 — `<button id="theme-toggle">` element present in topbar.
  B.2 — inline `<script>` reads localStorage key `swing-trading-theme`
        AND validates the value against a `["light","dark"]` allowlist
        before applying.
  B.3 — toggle button has NO `onclick=` inline attribute; handler is
        attached via `addEventListener` per dispatch brief §0.3 #7
        (CSP-clean pattern).
  B.4 — FOUC-prevention script appears in `<head>` BEFORE the opening
        `<body>` tag (string-position assertion).
  B.5 — localStorage access is wrapped in try/catch (private-browsing
        fallback) per dispatch brief §0.3 #7.
  B.6 — toggle button accessible: `aria-label` attribute present and
        initially reflects the "switch to dark" copy (since light is
        the default theme).

Visual rendering + interactive flip behavior remain operator-witnessed
(§5 surfaces 1-6); these tests pin the structural contract.
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _client(cfg, cfg_path, monkeypatch):
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    app = create_app(cfg, cfg_path)
    return app, TestClient(app)


def _get_html(seeded_db, monkeypatch) -> str:
    cfg, cfg_path = seeded_db
    app, client = _client(cfg, cfg_path, monkeypatch)
    with client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    return r.text


def test_b1_toggle_button_present_in_nav(seeded_db, monkeypatch):
    """B.1 — `<button id="theme-toggle">` inside the topbar."""
    html = _get_html(seeded_db, monkeypatch)
    # Slice topbar nav to ensure button is INSIDE the nav, not elsewhere
    # on the page.
    m = re.search(r'<nav class="topbar">(.*?)</nav>', html, flags=re.DOTALL)
    assert m, "Could not find <nav class=\"topbar\">...</nav>"
    nav_html = m.group(1)
    assert 'id="theme-toggle"' in nav_html, (
        "<button id=\"theme-toggle\"> not found inside topbar."
    )
    # It should be a <button>, not e.g. an <a>.
    assert re.search(r'<button[^>]*\bid="theme-toggle"', nav_html), (
        "theme-toggle is not a <button> element."
    )


def test_b2_inline_script_reads_localstorage_with_allowlist(
    seeded_db, monkeypatch
):
    """B.2 — inline script references the `swing-trading-theme` key AND
    validates against a `["light","dark"]` allowlist before applying.

    Allowlist check tolerates either array form `["light","dark"]`,
    `["dark","light"]`, an `=== "dark"`/`=== "light"` comparison pair,
    or an explicit `t === 'dark' || t === 'light'` form.
    """
    html = _get_html(seeded_db, monkeypatch)
    assert "swing-trading-theme" in html, (
        "localStorage key 'swing-trading-theme' not found in rendered HTML."
    )
    # At least one form of allowlist validation must be present.
    forms = [
        r'\[\s*["\']light["\']\s*,\s*["\']dark["\']\s*\]',
        r'\[\s*["\']dark["\']\s*,\s*["\']light["\']\s*\]',
        # paired equality comparisons (any quoting style; any order)
        r'===\s*["\']dark["\']',
    ]
    assert any(re.search(p, html) for p in forms), (
        "No allowlist / equality validation for localStorage theme value "
        "found in rendered HTML."
    )


def test_b3_toggle_button_no_inline_onclick(seeded_db, monkeypatch):
    """B.3 — theme-toggle button MUST NOT have an inline onclick= attribute."""
    html = _get_html(seeded_db, monkeypatch)
    m = re.search(r"<button[^>]*\bid=\"theme-toggle\"[^>]*>", html)
    assert m, "theme-toggle button not found"
    tag = m.group(0)
    assert "onclick" not in tag.lower(), (
        f"theme-toggle button has inline onclick attribute (CSP unsafe): {tag}"
    )


def test_b4_fouc_script_appears_in_head_before_body(seeded_db, monkeypatch):
    """B.4 — FOUC-prevention script (the one that reads localStorage) must
    appear inside <head> and BEFORE the <body> opening tag.

    Robust position search: identifies all `<script>...</script>` blocks
    and excludes literal `<body>` matches inside them (those are JS
    comments mentioning the body tag, not the real tag).
    """
    html = _get_html(seeded_db, monkeypatch)
    script_spans = [
        (m.start(), m.end())
        for m in re.finditer(
            r"<script\b[^>]*>.*?</script>",
            html, flags=re.DOTALL | re.IGNORECASE,
        )
    ]

    def in_script(pos: int) -> bool:
        return any(s <= pos < e for s, e in script_spans)

    # First `<body[\s>]` that is NOT inside a script block.
    real_body_start = None
    for m in re.finditer(r"<body[\s>]", html, flags=re.IGNORECASE):
        if not in_script(m.start()):
            real_body_start = m.start()
            break
    assert real_body_start is not None, "no actual <body> tag found"

    head_end = html.lower().find("</head>")
    assert head_end != -1, "</head> not found"

    ls_pos = html.find("swing-trading-theme")
    assert ls_pos != -1, "swing-trading-theme key not found in rendered HTML"

    assert ls_pos < head_end, (
        "swing-trading-theme localStorage read does not appear inside <head>; "
        "FOUC will result because body renders before the dark class applies."
    )
    assert ls_pos < real_body_start, (
        "swing-trading-theme localStorage read appears AFTER the actual "
        "<body> opening tag (FOUC risk)."
    )


def test_b5_localstorage_access_wrapped_in_try_catch(seeded_db, monkeypatch):
    """B.5 — localStorage access wrapped in try/catch (private-browsing /
    storage-disabled fallback) per dispatch brief §0.3 #7.

    Heuristic: the rendered HTML must contain at least one `try` ... `catch`
    construct (case-insensitive) co-located with the localStorage reference.
    """
    html = _get_html(seeded_db, monkeypatch)
    # Locate window where localStorage is touched and assert try/catch
    # appears within the same script element.
    # Cheap proxy: any of the inline <script> blocks that mentions
    # localStorage must also mention `try` and `catch`.
    scripts = re.findall(
        r"<script\b[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE,
    )
    touching = [s for s in scripts if "localStorage" in s]
    assert touching, "No inline <script> touches localStorage."
    assert any(("try" in s and "catch" in s) for s in touching), (
        "Inline script accesses localStorage without a try/catch wrapper; "
        "private-browsing / storage-disabled modes will throw."
    )


def test_b7_body_class_sync_contract(seeded_db, monkeypatch):
    """B.7 — the end-of-body toggle script MUST (a) initialize body.dark
    via the two-arg `classList.toggle('dark', <bool>)` form on initial
    load AND (b) keep body.dark in sync with html.dark INSIDE the click
    handler (not as an unrelated independent toggle elsewhere). Pins the
    body.dark sync contract added in the Codex R1 Major #1 fix so future
    edits can't silently remove it.

    Robustness pass (Codex R3 Minor #1/#2/#3): asserts the two-argument
    toggle form (one-way `.add()` was R2's regression-risk pattern) AND
    extracts the click-handler body specifically to ensure the sync is
    INSIDE the handler (not just present somewhere in the script).
    """
    html = _get_html(seeded_db, monkeypatch)
    scripts = re.findall(
        r"<script\b[^>]*>(.*?)</script>",
        html, flags=re.DOTALL | re.IGNORECASE,
    )
    candidates = [
        s for s in scripts
        if "document.body" in s or "body.classList" in s
    ]
    assert candidates, "no inline script touches body.classList"
    toggle_script = max(candidates, key=len)

    # (a) initial-load body-sync — assert the TWO-ARG toggle form
    #     `body.classList.toggle('dark', html.classList.contains('dark'))`.
    #     R2 specifically resolved the one-way `.add()` regression by
    #     adopting this form; allowing `.add()` would let that regression
    #     re-creep in.
    assert re.search(
        r"body\.classList\.toggle\(\s*['\"]dark['\"]\s*,\s*"
        r"(?:html|document\.documentElement)\.classList\.contains\(",
        toggle_script,
    ), (
        "End-of-body script does not call the two-arg form "
        "body.classList.toggle('dark', <html-contains-dark>) for "
        "initial sync — one-way add() was the R2 regression pattern."
    )

    # (b) click-handler body-sync — extract the click-handler body and
    #     assert the body-class update lives INSIDE it, paired with the
    #     html.dark toggle whose return value drives the body update
    #     (so they can't diverge).
    click_handler = re.search(
        r"addEventListener\(\s*['\"]click['\"]\s*,\s*function\s*\("
        r"[^)]*\)\s*\{(.*?)\}\s*\)\s*;",
        toggle_script, flags=re.DOTALL,
    )
    assert click_handler, "could not locate click handler body in toggle script"
    handler_body = click_handler.group(1)
    # Click handler MUST toggle html.dark and capture the boolean.
    assert re.search(
        r"(?:html|document\.documentElement)\.classList\.toggle\(\s*"
        r"['\"]dark['\"]\s*\)",
        handler_body,
    ), "Click handler does not toggle html.dark class."
    # Click handler MUST update body.classList using the two-arg form
    # so the body update is driven by the same boolean as the html toggle
    # (or an alias for it). This prevents the divergence Codex R3 Minor #3
    # warns about: a future edit toggling html one way and body the
    # other.
    assert re.search(
        r"body\.classList\.toggle\(\s*['\"]dark['\"]\s*,\s*\w+\s*\)",
        handler_body,
    ), (
        "Click handler does not call body.classList.toggle('dark', "
        "<isDark>) — the html ↔ body sync MUST be paired off the same "
        "boolean to prevent divergence."
    )


def test_b6_toggle_button_has_aria_label(seeded_db, monkeypatch):
    """B.6 — theme-toggle button carries an `aria-label` so screen readers
    + accessibility tooling can interpret it. Server-render-side this
    defaults to the "Switch to dark theme" copy (light is the default).
    """
    html = _get_html(seeded_db, monkeypatch)
    m = re.search(r"<button[^>]*\bid=\"theme-toggle\"[^>]*>", html)
    assert m, "theme-toggle button not found"
    tag = m.group(0)
    assert "aria-label" in tag.lower(), (
        f"theme-toggle button missing aria-label: {tag}"
    )
    # Initial state: light theme default → button offers "switch to dark"
    assert "dark" in tag.lower(), (
        f"theme-toggle initial aria-label does not reference 'dark' "
        f"(operator default is light → button should offer dark): {tag}"
    )
