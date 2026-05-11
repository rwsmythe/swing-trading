"""Phase 7 Sub-C C.6 — shared state-badge partial + journal + open-positions
wiring + CSS.

Tests for:
  - partial file existence at swing/web/templates/partials/state_badge.html.j2
  - all 5 state CSS color rules in app.css
  - journal page renders state badge per row (replaces bare ``t.status``)
  - dashboard open-positions row renders state badge per row
  - shared partial referenced from >=3 consumer templates (DRY/no
    hand-duplicated markup — pre-empts CLAUDE.md OOB-swap drift gotcha)
  - all 5 state values produce distinct badge classes + labels via the
    macro
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app

# ---------------------------------------------------------------------------
# seed helpers (mirrors _c5_seed_phase7_trade in test_trades_route.py — lifted
# locally so this test file does not cross-import another test module's
# private helpers)
# ---------------------------------------------------------------------------


def _seed_phase7_trade(cfg, *, ticker: str, state: str = "entered") -> int:
    """Insert a Phase 7 trade row with the given state, return id."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=90.0,
                current_stop=90.0, state=state,
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-15T16:00:00",
                current_size=10.0,
            ), event_ts="2026-04-15T16:00:00")
    finally:
        conn.close()
    return tid


def _patch_price_cache(monkeypatch):
    """Stub PriceCache so the dashboard renders without network calls."""
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


# ---------------------------------------------------------------------------
# Static / file-shape tests (no Flask/FastAPI client needed)
# ---------------------------------------------------------------------------


def test_state_badge_partial_exists():
    """C.6: shared state-badge partial file lives at the canonical path.

    Pre-fix discriminator: file does not exist → assertion fails.
    """
    p = Path("swing/web/templates/partials/state_badge.html.j2")
    assert p.exists(), (
        "C.6 expects the shared partial at "
        "swing/web/templates/partials/state_badge.html.j2 "
        "(callers import it as a Jinja macro)"
    )


def test_css_state_badge_rules_present():
    """All 5 state-color rules + base ``.state-badge`` rule live in the
    shared CSS file. CLAUDE.md OOB-swap drift gotcha: badge styling must be
    in ONE CSS file so all renders pick it up consistently.
    """
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    for cls in (
        ".state-badge",
        ".state-entered",
        ".state-managing",
        ".state-partial_exited",
        ".state-closed",
        ".state-reviewed",
    ):
        assert cls in css, f"missing CSS rule: {cls}"


def test_css_entry_textarea_aside_layout_rules_present():
    """3e.7 B.AC.4 — flex-row layout for entry-form textarea + example aside
    pairs. Brief §0.3 #7 binding constraint: aside visible to the right of
    textarea, never toggled. Discriminating: regression that drops the
    flex rule reverts to vertical stacking and the aside falls below the
    textarea — operator-facing UX regression."""
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    assert ".entry-textarea-row" in css, "missing .entry-textarea-row selector"
    assert ".entry-example-aside" in css, "missing .entry-example-aside selector"
    # Layout discriminator: must declare flex (or grid) on the row.
    # Pin display: flex per the brief's preferred shape.
    row_idx = css.find(".entry-textarea-row")
    # Look at the next ~200 chars after the selector for the display: flex rule.
    assert "display: flex" in css[row_idx:row_idx + 300], (
        ".entry-textarea-row must declare `display: flex` (or grid) to "
        "achieve side-by-side layout per brief §0.3 #7"
    )


def test_state_badge_partial_consumed_by_three_or_more_templates():
    """OOB-swap drift gotcha (CLAUDE.md): callers MUST go through the
    SAME include/import target rather than hand-duplicating markup. The
    shared partial should be referenced (via include or macro import) from
    at least 3 consumer templates: trades/detail.html.j2, journal.html.j2,
    and partials/open_positions_row.html.j2.

    Pre-fix discriminator: only one consumer (trades/detail.html.j2) wires
    up via inline span + state-badge class — assertion fails when
    `state_badge.html.j2` is not imported/included from journal +
    open_positions_row.
    """
    template_dir = Path("swing/web/templates")
    consumers: list[Path] = []
    for tmpl in template_dir.rglob("*.j2"):
        if tmpl.name == "state_badge.html.j2":
            continue  # the partial itself does not count as a consumer
        text = tmpl.read_text(encoding="utf-8")
        if "state_badge.html.j2" in text:
            consumers.append(tmpl)
    assert len(consumers) >= 3, (
        "expected >=3 consumer templates to reference "
        "partials/state_badge.html.j2 via include/import; got: "
        f"{[str(p) for p in consumers]}"
    )


# ---------------------------------------------------------------------------
# Journal route — badge replaces bare t.status
# ---------------------------------------------------------------------------


def test_journal_renders_state_badge_per_row(seeded_db):
    """GET /journal renders the badge CSS class per trade row instead of
    the legacy bare-text ``t.status`` (which fails AttributeError post-Sub-A
    because Trade no longer has ``.status``)."""
    cfg, cfg_path = seeded_db
    _seed_phase7_trade(cfg, ticker="JNLCLO", state="closed")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert r.status_code == 200, r.text[:300]
    text = r.text
    assert 'class="state-badge state-closed"' in text, (
        "journal trades table must render the shared state badge for each "
        "row (post-C.6); did not find badge class for the seeded closed "
        "trade. body excerpt: " + text[:500]
    )
    # Badge label rendered as well:
    assert ">Closed<" in text


def test_journal_renders_state_badge_for_managing(seeded_db):
    """Different state surfaces a different badge class — discriminator
    against a hard-coded "closed" template literal."""
    cfg, cfg_path = seeded_db
    _seed_phase7_trade(cfg, ticker="JNLMNG", state="managing")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert r.status_code == 200
    text = r.text
    assert 'class="state-badge state-managing"' in text
    assert ">Managing<" in text


# ---------------------------------------------------------------------------
# Dashboard open-positions row — badge rendered next to ticker
# ---------------------------------------------------------------------------


def test_open_positions_row_renders_state_badge(seeded_db, monkeypatch):
    """Dashboard open-positions table renders state badges per row.

    Pre-C.6: open_positions_row.html.j2 does not include the state-badge
    partial; assertion fails because no ``state-badge state-managing``
    class appears in the rendered dashboard.
    """
    cfg, cfg_path = seeded_db
    _seed_phase7_trade(cfg, ticker="OPMNG", state="managing")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:300]
    text = r.text
    assert 'class="state-badge state-managing"' in text, (
        "dashboard open-positions row must render the shared state badge "
        "(post-C.6). body excerpt: " + text[:500]
    )


def test_open_positions_row_partial_references_shared_partial():
    """OOB-swap drift gotcha (CLAUDE.md): the open-positions row partial
    file MUST reference state_badge.html.j2 — not hand-duplicate the <span>
    markup. partials/open_positions_row.html.j2 is the SAME template
    rendered both by the full-page dashboard and by OOB-swap responses
    (entry POST success, prices refresh, etc.); having it use a shared
    include guarantees byte-for-byte parity across surfaces.

    Pre-fix discriminator: open_positions_row.html.j2 has no reference to
    state_badge.html.j2 → assertion fails.
    """
    p = Path("swing/web/templates/partials/open_positions_row.html.j2")
    text = p.read_text(encoding="utf-8")
    assert "state_badge.html.j2" in text, (
        "open_positions_row.html.j2 must import/include the shared "
        "state_badge.html.j2 partial; instead it appears to hand-duplicate "
        "the <span> markup or omit the badge entirely."
    )


# ---------------------------------------------------------------------------
# Trade detail — DRY: shared partial reused (no inline span hand-duplication)
# ---------------------------------------------------------------------------


def test_trade_detail_uses_shared_state_badge(seeded_db):
    """trade-detail page must source its badge from the shared partial too,
    so the 5 CSS color rules render identically across surfaces.

    Pre-C.6 discriminator: detail.html.j2 hand-rendered the span inline
    (C.5). Post-C.6 the template imports the macro and the rendered output
    must STILL contain the badge — proves the include/import refactor did
    not regress the detail-page render.
    """
    cfg, cfg_path = seeded_db
    tid = _seed_phase7_trade(cfg, ticker="DTLENT", state="entered")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    assert r.status_code == 200
    assert 'class="state-badge state-entered"' in r.text


# ---------------------------------------------------------------------------
# Macro distinguishes all 5 states
# ---------------------------------------------------------------------------


def test_state_badge_macro_renders_all_5_state_classes(seeded_db):
    """All 5 state values produce a distinct ``state-<state>`` CSS class +
    label when rendered via /trades/{id}. Using the route end-to-end so this
    test discriminates a missing macro / misrouted include just as well as
    a Jinja-Environment unit test would.
    """
    cfg, cfg_path = seeded_db
    cases = [
        ("ENTRD", "entered", "Entered"),
        ("MANAG", "managing", "Managing"),
        ("PARTL", "partial_exited", "Partial"),
        ("CLOSD", "closed", "Closed"),
        ("REVWD", "reviewed", "Reviewed"),
    ]
    seeded: list[tuple[int, str, str]] = []
    for tk, st, lbl in cases:
        tid = _seed_phase7_trade(cfg, ticker=tk, state=st)
        seeded.append((tid, st, lbl))

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for tid, st, lbl in seeded:
            r = client.get(f"/trades/{tid}")
            assert r.status_code == 200, (
                f"state={st} did not render: {r.text[:200]!r}"
            )
            text = r.text
            assert f'class="state-badge state-{st}"' in text, (
                f"missing badge class state-{st} in render"
            )
            # The label appears between the > and < of the span:
            assert f">{lbl}<" in text, (
                f"missing badge label {lbl!r} in render for state={st}"
            )
