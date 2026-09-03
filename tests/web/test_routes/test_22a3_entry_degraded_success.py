"""22-A3 -- the entry route consumes the `EntryResult`.

`record_entry` returns *a statement about the DURABLE STATE OF THE LEDGER* and
before this arc NOBODY READ IT.  A post-commit render failure then reached the
app-wide handler, which -- because `entry-form-` is in `_ROW_TARGET_PREFIXES`
(`swing/web/app.py:38-45`) and `base.html.j2` overrides
`htmx.config.responseHandling` so 5xx SWAPS -- painted `trade_form_error` into
the entry form's OWN ROW at status 500: **the identical surface, class and
position a duplicate/hard-cap REFUSAL uses.**

The distinction is not rhetorical.  A bare 500 is a system fault the operator
investigates; a refusal in the form's row is an answer he ACTS on, by entering
again.

Every test below states its value under BOTH the pre-fix and the post-fix
path, and the PRE-fix values are NOT uniform -- an executor who assumes
"pre-fix means 500" writes several wrong tests.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from swing.web.app import create_app

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "swing" / "web" / "templates"

_INCLUDE_RE = re.compile(r"{%-?\s*include\s+[\"']([^\"']+)[\"']")


def _patch_price_cache(monkeypatch):
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_minimal_dashboard_state(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17', '2026-04-20',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""")
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 't')""")
    finally:
        conn.close()


# ===========================================================================
# (h) -- the container exists wherever the entry form is reachable.
# ===========================================================================


def test_h1_the_notice_container_is_LIVE_on_both_entry_surfaces(
        seeded_db, monkeypatch):
    """PRE-fix `id="entry-notice"` is absent from both; POST-fix present."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        root = client.get("/")
        watchlist = client.get("/watchlist")

    assert root.status_code == 200, root.text[:400]
    assert watchlist.status_code == 200, watchlist.text[:400]
    assert 'id="entry-notice"' in root.text
    assert 'id="entry-notice"' in watchlist.text, (
        "the entry form is reachable from /watchlist and that page carries "
        "NONE of the four OOB ids the entry response swaps into -- a notice "
        "delivered there would be silently dropped")


def test_h2_every_PAGE_reaching_the_entry_form_extends_base(seeded_db):
    """A STATIC CLOSURE WALK, not a membership count.

    Build the set of templates whose source contains the entry-form URL, walk
    `{% include %}` edges BACKWARDS to every page that reaches one, and assert
    the `extends` PROPERTY -- so a third entry surface added later is COVERED
    rather than merely counted.

    A static walk is preferred to a runtime trace: a trace only sees the
    branches a fixture happened to take, which is how a roster hole survives.
    Its limits are declared (plan S7.18): it cannot see an affordance reached
    through a route-composed fragment, a computed URL, or a macro.
    """
    sources = {
        p: p.read_text(encoding="utf-8")
        for p in TEMPLATES_DIR.rglob("*.html.j2")
    }
    by_name = {
        p.relative_to(TEMPLATES_DIR).as_posix(): p for p in sources
    }

    # reverse edges: included-name -> {including paths}
    includers: dict[str, set[Path]] = {}
    for path, text in sources.items():
        for name in _INCLUDE_RE.findall(text):
            includers.setdefault(name, set()).add(path)

    frontier = [p for p, t in sources.items() if "/trades/entry/form" in t]
    assert frontier, "no template references the entry-form URL at all"
    reachable: set[Path] = set(frontier)
    while frontier:
        current = frontier.pop()
        name = current.relative_to(TEMPLATES_DIR).as_posix()
        for parent in includers.get(name, ()):
            if parent not in reachable:
                reachable.add(parent)
                frontier.append(parent)

    pages = [p for p in reachable if "{% extends" in sources[p]]
    assert pages, "the walk found no page template reaching the entry form"
    for page in pages:
        assert 'extends "base.html.j2"' in sources[page], (
            f"{page.relative_to(TEMPLATES_DIR).as_posix()} reaches the entry "
            f"form but does not extend base.html.j2, so the #entry-notice "
            f"container is absent there and the notice is silently dropped")
    assert "base.html.j2" in by_name


# ===========================================================================
# (j) -- the notice partial renders, escapes, and carries its OOB contract.
# ===========================================================================


def test_j_the_notice_partial_renders_escapes_and_carries_its_OOB_contract(
        seeded_db):
    """Without this, Task 5's only other test checks container presence and
    would stay green over a partial with a Jinja syntax error, a wrong id, or
    a missing OOB attribute."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    html = app.state.templates.get_template(
        "partials/entry_notice.html.j2"
    ).render(trade_id=7,
             warnings=["<script>alert(1)</script> & co"],
             render_failure=None)

    stripped = html.lstrip()
    assert stripped.startswith("<div"), stripped[:120]
    assert 'id="entry-notice"' in stripped.split(">", 1)[0]
    assert 'hx-swap-oob="true"' in stripped.split(">", 1)[0]
    assert "Trade #7" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "could not be refreshed" not in html, (
        "render_failure is None -- the refresh SUCCEEDED and the notice must "
        "not claim otherwise")
