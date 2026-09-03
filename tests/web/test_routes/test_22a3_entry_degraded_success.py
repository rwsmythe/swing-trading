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


# ===========================================================================
# Shared machinery for the route tests.
# ===========================================================================

SENTINEL = "22-A3 PROBE: the entry is DURABLE -- do NOT retry."


def _post_entry(client, ticker="ZZZ", **fields):
    from tests.web.conftest import full_phase7_entry_payload
    base = full_phase7_entry_payload(
        ticker=ticker, entry_date="2026-05-19", entry_price="150.25",
        shares="100", initial_stop="140.00", rationale="aplus-setup",
        notes="")
    base.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
    return client.post(
        "/trades/entry", data=base, headers={"HX-Request": "true"})


def _trade_count(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    finally:
        conn.close()


def _only_trade_id(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute("SELECT id FROM trades ORDER BY id").fetchall()
        assert len(rows) == 1, rows
        return int(rows[0][0])
    finally:
        conn.close()


def _inject_post_commit_warnings(monkeypatch, *warnings):
    """Wrap the REAL service and add ONLY the field under test.

    THE LOAD-BEARING FIXTURE CHOICE: it produces a REAL durable row through
    the REAL production path, so the test cannot pass because a stub
    fabricated a result.
    """
    import dataclasses

    import swing.web.routes.trades as routes
    real = routes.record_entry

    def _wrapped(*a, **kw):
        result = real(*a, **kw)
        return dataclasses.replace(
            result, post_commit_warnings=tuple(warnings))

    monkeypatch.setattr(routes, "record_entry", _wrapped)


def _raise_from_build_dashboard(monkeypatch, exc):
    import swing.web.routes.trades as routes

    def _raiser(*a, **kw):
        raise exc

    monkeypatch.setattr(routes, "build_dashboard", _raiser)


def _break_notice_template_only(app, exc):
    """Raise ONLY for `partials/entry_notice.html.j2`; delegate otherwise.

    PRE-FIX this wrapper NEVER FIRES -- the route does not ask for that
    template at all, because the result is discarded -- so the pre-fix
    response is an ordinary 200 with FOUR chunks, NOT a 500.
    """
    templates = app.state.templates
    real = templates.get_template

    def _wrapped(name, *a, **kw):
        if name == "partials/entry_notice.html.j2":
            raise exc
        return real(name, *a, **kw)

    templates.get_template = _wrapped


class _RaisingHandler:
    """Attach a raising ERROR handler to a NAMED logger, as a context manager,
    so the (m)/(r) injections cannot leak into sibling tests."""

    def __init__(self, logger_name):
        import logging
        self._logger = logging.getLogger(logger_name)

        class _Sink(logging.Handler):
            def emit(self, record):
                raise RuntimeError("22-A3 PROBE: route log sink failed")

        self._handler = _Sink(level=logging.ERROR)

    def __enter__(self):
        self._logger.addHandler(self._handler)
        return self

    def __exit__(self, *exc):
        self._logger.removeHandler(self._handler)
        return False


class _CloseRaises:
    """A forwarding proxy over the REAL connection whose `close()` performs
    the real close and THEN raises.

    The real transaction still commits, so the trade is genuinely durable --
    which is the whole premise of (b2).  The wording of the resulting warning
    is OBSERVATION-ONLY for exactly this reason: `close()` can TAKE EFFECT and
    then raise.
    """

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def __enter__(self):
        object.__getattribute__(self, "_real").__enter__()
        return self

    def __exit__(self, *a):
        return object.__getattribute__(self, "_real").__exit__(*a)

    def close(self):
        import sqlite3
        object.__getattribute__(self, "_real").close()
        raise sqlite3.OperationalError("22-A3 PROBE: close failed")


def _patch_connect_to_raise_on_close(monkeypatch):
    import swing.web.routes.trades as routes
    real_connect = routes.connect

    def _wrapped(*a, **kw):
        return _CloseRaises(real_connect(*a, **kw))

    monkeypatch.setattr(routes, "connect", _wrapped)


def _notice_chunk(text):
    """The `#entry-notice` OOB chunk, sliced out of the response body."""
    start = text.find('<div id="entry-notice"')
    assert start >= 0, "no #entry-notice chunk in the response"
    return text[start:]


# ===========================================================================
# (a) -- a post-commit warning reaches the operator through the response.
# ===========================================================================


def test_a_a_post_commit_warning_reaches_the_web_response(
        seeded_db, monkeypatch):
    """PRE-fix the sentinel is ABSENT from a 200 (the result is discarded at
    the `record_entry` call site); POST-fix it is present."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _inject_post_commit_warnings(monkeypatch, SENTINEL)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]   # CONTROL, both paths
    assert SENTINEL in resp.text
    assert 'id="entry-notice"' in resp.text
    assert resp.text.lstrip().startswith('<div id="entry-notice"'), (
        "this is the ONE path where the notice travels beside OOB <table> "
        "chunks, so it is the one path where a <tr> at fragment root would "
        "fire Bug B")
    assert _trade_count(cfg) == 1                     # CONTROL, both paths


# ===========================================================================
# (b) -- a `build_dashboard` failure becomes a DEGRADED SUCCESS.
# ===========================================================================


def test_b_a_build_dashboard_failure_is_a_degraded_success(
        seeded_db, monkeypatch):
    """PRE-fix 500 with the refusal-shaped `trade_form_error` fragment painted
    into the entry form's own row; POST-fix 200 naming the trade.

    `raise_server_exceptions=False` is REQUIRED: with the default the
    `ServerErrorMiddleware` re-raises after the app's handler runs, so the
    PRE-fix run would raise the probe out of `client.post(...)` and the test
    would assert on an exception rather than a status.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _raise_from_build_dashboard(
        monkeypatch, RuntimeError("22-A3 PROBE: dashboard rebuild failed"))

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(client)

    assert _trade_count(cfg) == 1, (
        "the premise: the row was durable in the pre-fix run too")
    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text
    assert "do NOT" in resp.text
    assert "<tr" not in resp.text, (
        "S2.1: never a <tr> at fragment root on the degraded path")


# ===========================================================================
# (b2) -- a `conn.close()` failure AFTER a durable entry (web half).
# ===========================================================================


def test_b2_a_close_failure_after_a_durable_entry_is_a_degraded_success(
        seeded_db, monkeypatch):
    """PRE-fix 500 over one durable row; POST-fix 200 naming the trade, with
    the contained close REPORTED rather than swallowed."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _patch_connect_to_raise_on_close(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(client)

    assert _trade_count(cfg) == 1, "the whole premise"
    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text
    assert "close failed" in resp.text


def test_b2_control_a_REFUSAL_still_propagates_its_close_failure(
        seeded_db, monkeypatch):
    """THE ASYMMETRY, KEPT HONEST. `result` is None on a refusal, so the close
    failure must STILL propagate -- 500, unchanged from today.

    On the WEB path this control genuinely DISCRIMINATES (its CLI twin does
    not): the duplicate handler RETURNS a 400 from inside the `try`, so an
    implementation containing the close UNCONDITIONALLY would swallow the
    close error and let that 400 stand. 400 versus 500 is the discriminator.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        first = _post_entry(client)
        assert first.status_code == 200, first.text[:400]
        _patch_connect_to_raise_on_close(monkeypatch)
        second = _post_entry(client)

    assert second.status_code == 500, (
        "a refusal has no durable result to protect, so the close failure "
        "must propagate; a 400 here means the containment is unconditional")
    assert _trade_count(cfg) == 1


# ===========================================================================
# (f) -- an ordinary success carries an EMPTY notice chunk.
# ===========================================================================


def test_f_an_ordinary_success_carries_an_EMPTY_notice_chunk(
        seeded_db, monkeypatch):
    """PRE-fix FOUR OOB chunks and no notice; POST-fix FIVE, the fifth EMPTY.

    This flipped from an invariant into a discriminator when the notice
    container was found to be STATEFUL: a prior warning response replaces the
    empty container with a visible banner and KEEPS THE ID, so an ordinary
    entry must emit the wrapper (to clear it) with no content.

    The four-refresh-chunk half is a pure blast-radius pin and passes under
    BOTH paths; the count and the notice's presence are what discriminate.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]
    assert resp.text.count('hx-swap-oob="true"') == 5
    assert 'id="entry-notice"' in resp.text
    chunk = _notice_chunk(resp.text)
    assert "banner-degraded" not in chunk
    assert "WAS RECORDED" not in resp.text

    # blast radius: the four refresh chunks, unchanged in identity, count and
    # order (true under BOTH paths).
    idents = ('id="status-strip"', 'id="open-positions"',
              'id="watchlist-top5"', 'id="hypothesis-recommendations"')
    for ident in idents:
        assert resp.text.count(ident) == 1, ident
    positions = [resp.text.index(i) for i in idents]
    assert positions == sorted(positions)


# ===========================================================================
# (l) -- the notice CLEARS itself across two requests.
# ===========================================================================


def test_l_a_warning_entry_followed_by_an_ORDINARY_entry_clears_the_banner(
        seeded_db, monkeypatch):
    """PRE-fix the second response contains NO notice chunk at all; POST-fix
    it is present and EMPTY.

    WHAT THIS DOES NOT PROVE: TestClient applies no HTMX swaps and holds no
    DOM, so this establishes only the SERVER-SIDE CONTRACT across two
    requests. That the operator's browser actually REPLACES the old banner is
    provable only at gate Step 5b.
    """
    import dataclasses

    import swing.web.routes.trades as routes

    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    real = routes.record_entry
    inject = [True]

    def _wrapped(*a, **kw):
        result = real(*a, **kw)
        if inject[0]:
            return dataclasses.replace(
                result, post_commit_warnings=(SENTINEL,))
        return result

    monkeypatch.setattr(routes, "record_entry", _wrapped)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = _post_entry(client, ticker="AAA")
        assert first.status_code == 200, first.text[:400]
        assert SENTINEL in first.text
        inject[0] = False
        second = _post_entry(client, ticker="BBB")

    assert second.status_code == 200, second.text[:400]
    assert 'id="entry-notice"' in second.text
    chunk = _notice_chunk(second.text)
    assert SENTINEL not in chunk
    assert "banner-degraded" not in chunk


# ===========================================================================
# (g) -- the notice helper is TOTAL when ONLY the notice partial fails.
# ===========================================================================


def test_g_the_notice_helper_is_total_when_only_the_notice_partial_fails(
        seeded_db, monkeypatch):
    """THE REACHABLE CASE: the dashboard and all four partials render, the
    result carries warnings, and only the notice render fails.

    THE PRE-FIX VALUE IS 200, NOT 500: pre-fix the route never asks for
    `partials/entry_notice.html.j2` at all, so the raising wrapper never fires
    and the response is an ordinary 200 with FOUR chunks. Status is a CONTROL
    here; the chunk count and the sentinel are the discriminators.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _inject_post_commit_warnings(monkeypatch, "<script>" + SENTINEL)

    app = create_app(cfg, cfg_path)
    _break_notice_template_only(
        app, RuntimeError("22-A3 PROBE: notice render failed"))
    with TestClient(app) as client:
        resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]      # CONTROL
    assert resp.text.count('hx-swap-oob="true"') == 5
    assert SENTINEL in resp.text, (
        "the literal fallback must CARRY the warnings; dropping them ships "
        "this arc's own failure mode inside the fix for it")
    assert "could not be refreshed" not in resp.text, (
        "the refresh did NOT fail, and a fallback that says it did is a "
        "false statement to the operator")
    assert "&lt;" in resp.text, "the fallback escapes with html.escape"
    assert "notice render failed" in resp.text, (
        "the fallback NAMES what failed rather than discarding the cause")


def test_g3_only_the_notice_partial_fails_and_there_is_nothing_else_to_say(
        seeded_db, monkeypatch, caplog):
    """An ordinary entry whose ONLY problem is that the notice template broke.

    An earlier draft returned an EMPTY wrapper in exactly this posture, so a
    degraded event rendered as an ordinary success with no banner and no log
    -- the arc's own failure mode, reached through its own fallback.
    """
    import logging

    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    _break_notice_template_only(
        app, RuntimeError("22-A3 PROBE: notice render failed"))
    with caplog.at_level(logging.ERROR, logger="swing.web.routes.trades"):
        with TestClient(app) as client:
            resp = _post_entry(client)

    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]      # CONTROL
    assert f"Trade #{trade_id}" in resp.text
    assert "notice render failed" in resp.text
    assert "could not be refreshed" not in resp.text
    assert "could not be rendered" in caplog.text, caplog.text


def test_g2_the_notice_helper_is_total_when_the_whole_template_layer_fails(
        seeded_db, monkeypatch):
    """PRE-fix 500; POST-fix 200 naming the trade, via the LITERAL.

    The phrase asserted below exists ONLY in the literal, so it discriminates
    against a half-fix in which the guard exists but the helper is not total.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)

    def _raiser(*a, **kw):
        raise RuntimeError("22-A3 PROBE: the template layer failed")

    monkeypatch.setattr(app.state.templates, "get_template", _raiser)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(client)

    assert _trade_count(cfg) == 1
    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text
    # PLAN DEFECT, reported: S3(g2) states this assertion in lowercase while
    # the plan's own Task-6 helper code emits the sentence-initial capital
    # ("This notice could not be rendered"). The production string is the
    # authority; a lowercase mid-sentence phrase would be the wrong fix.
    assert "This notice could not be rendered" in resp.text


# ===========================================================================
# (m) -- the ROUTE's degraded path really uses `log_contained`.
# ===========================================================================


def test_m_the_degraded_path_contains_its_OWN_error_log(
        seeded_db, monkeypatch):
    """A half-fix writing a plain `log.error(...)` there passes (a), (b),
    (b2), (f), (g), (g2) and (k) -- and then a raising handler converts the
    durable entry straight back into a 500, which is this arc's subject."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _raise_from_build_dashboard(
        monkeypatch, RuntimeError("22-A3 PROBE: dashboard rebuild failed"))

    app = create_app(cfg, cfg_path)
    with _RaisingHandler("swing.web.routes.trades"):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = _post_entry(client)

    assert _trade_count(cfg) == 1
    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text
    assert "could not be emitted" in resp.text, (
        "the log failure is surfaced as a second warning, not swallowed")


# ===========================================================================
# (r) -- the notice render AND the route logger fail TOGETHER.
# ===========================================================================


def test_r_the_notice_render_and_the_route_logger_fail_together(
        seeded_db, monkeypatch):
    """Without this, a version that DROPS `log_contained`'s return value in
    the notice helper passes every other test -- and the operator sees the
    first failure and nothing at all about the second.

    POST-fix only; PRE this path returns the ordinary 200 that (g3)'s control
    establishes.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    _break_notice_template_only(
        app, RuntimeError("22-A3 PROBE: notice render failed"))
    with _RaisingHandler("swing.web.routes.trades"):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = _post_entry(client)

    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text
    assert "notice render failed" in resp.text
    assert "could not be emitted" in resp.text, (
        "the SECONDARY diagnostic was discarded: log_contained RETURNS the "
        "sink's failure precisely so a caller does not trade one invisible "
        "failure for another")


# ===========================================================================
# (k) and (n) -- the lone surrogate, at TWO DIFFERENT call sites.
# ===========================================================================


class _SurrogateRepr(RuntimeError):
    """A LEGAL custom `__repr__` returning a string containing a lone
    surrogate. MEASURED: `html.escape` PRESERVES it and `HTMLResponse` then
    raises `UnicodeEncodeError` encoding the body -- one frame OUTSIDE every
    guard in the route."""

    def __repr__(self):
        return "bad \ud800 repr"


def test_k_a_lone_surrogate_repr_cannot_break_the_degraded_response(
        seeded_db, monkeypatch):
    """PRE-fix 500; POST-fix 200, and a REAL `HTMLResponse` is constructed.

    End-to-end rather than a unit test: the failure it pins happens when
    Starlette ENCODES the body, inside `HTMLResponse`, which is outside every
    guard the route can install.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _raise_from_build_dashboard(monkeypatch, _SurrogateRepr("probe"))

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(client)

    assert _trade_count(cfg) == 1
    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text
    assert "ud800" in resp.text


def test_n_a_lone_surrogate_IN_A_WARNING_cannot_break_the_SUCCESS_response(
        seeded_db, monkeypatch):
    """A DIFFERENT CALL SITE from (k)'s. (k) drives the surrogate through the
    `build_dashboard` exception, which exercises `safe_text(post_bind_error)`
    -- NOT the warning-assembly coercion. A half-fix that drops `ascii_safe`
    from the warning assembly passes every other specified web test.

    PRE-fix the status is 200 and NOT a 500: pre-fix the route DISCARDS the
    result, so the injected warning is never read, never rendered and never
    encoded. THE 500 BELONGS TO THE MUTATION, not to the pre-fix path.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _inject_post_commit_warnings(
        monkeypatch, "22-A3 PROBE: a warning carrying \ud800 directly")

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]      # CONTROL
    assert 'id="entry-notice"' in resp.text
    assert "ud800" in resp.text
    assert resp.text.count('hx-swap-oob="true"') == 5
    assert _trade_count(cfg) == 1


# ===========================================================================
# (e) -- the belt is still the belt. **A CONTROL, NOT A FIX.**
# ===========================================================================


def test_e_CONTROL_the_belt_still_refuses_a_same_ticker_retry(
        seeded_db, monkeypatch):
    """**THIS TEST PASSES UNDER BOTH PATHS ON PURPOSE AND IS NOT COUNTED AS A
    DISCRIMINATING TEST.**

    Its job is to prove the arc did not perturb the one structural mitigation
    the declared residual leans on: `ux_trades_one_open_per_ticker`
    (`swing/data/migrations/0014_phase7_state_machine_and_fills.sql`, which
    DROPS migration 0004's `WHERE status = 'open'` form and recreates it over
    `state IN ('entered','managing','partial_exited')`), with the service-level
    pre-check in `swing/trades/entry.py` and the race re-map behind it.

    NOTE THE MESSAGE NAMES THE TICKER, NOT A TRADE ID. The commissioning
    brief's test (e) asked for "a message naming the existing trade"; the code
    says `Already an open position in {ticker}`. This test asserts what the
    code does -- widening the belt's copy is 22-A4's neighbourhood and this
    arc's envelope opens `entry.py` for containment only.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = _post_entry(client, ticker="ZZZ")
        assert first.status_code == 200, first.text[:400]
        second = _post_entry(client, ticker="ZZZ")

    assert second.status_code == 400, second.text[:400]
    assert "Already an open position in ZZZ" in second.text
    assert _trade_count(cfg) == 1


# ===========================================================================
# CODEX ROUND 1 -- the route-side halves.
# ===========================================================================


class _PoisonStr(str):
    """A `str` SUBCLASS overriding `encode`; `__repr__` may legally return
    one, because a subclass IS a `str`."""

    def encode(self, *a, **k):
        class _Decoded:
            def decode(self, *aa, **kk):
                return "bad \ud800 surrogate"
        return _Decoded()


class _PoisonReprError(RuntimeError):
    def __repr__(self):
        return _PoisonStr("poison-repr")


def test_A3_AR_01_a_hostile_str_subclass_repr_cannot_break_the_degraded_response(
        seeded_db, monkeypatch):
    """Codex A3-AR-01 (MAJOR) end-to-end.

    The unit half lives in tests/trades. THIS is why it was a MAJOR: pre-fix
    `safe_text(post_bind_error)` returned a non-ASCII string, it reached
    `HTMLResponse` from INSIDE the outer `except` -- where nothing catches it
    -- and the durable-row-plus-500 outcome the whole arc exists to remove
    came straight back.

    PRE-fix 500; POST-fix 200 naming the trade.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _raise_from_build_dashboard(monkeypatch, _PoisonReprError("probe"))

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = _post_entry(client)

    assert _trade_count(cfg) == 1
    trade_id = _only_trade_id(cfg)
    assert resp.status_code == 200, resp.text[:400]
    assert f"Trade #{trade_id}" in resp.text


def test_A3_AR_05_a_close_failure_leaves_a_DURABLE_TRACE_in_the_log(
        seeded_db, monkeypatch, caplog):
    """Codex A3-AR-05 (MINOR).

    When the close fails but the REFRESH SUCCEEDS the route returns an
    ordinary 200 carrying the warning -- and before the fix it emitted no
    ERROR record at all, so the declared limitation "the ERROR log is the only
    durable trace" was FALSE for that reachable path: there was no durable
    trace whatsoever. A notice is transient; the log is not.

    PRE-fix `caplog` carries no ERROR from this logger; POST-fix it does.
    """
    import logging

    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _patch_connect_to_raise_on_close(monkeypatch)

    app = create_app(cfg, cfg_path)
    with caplog.at_level(logging.ERROR, logger="swing.web.routes.trades"):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]
    assert _trade_count(cfg) == 1
    assert "CLOSING the database" in caplog.text, caplog.text
    assert "close failed" in caplog.text, caplog.text


def test_A3_AR_06_the_route_log_failure_wording_is_OBSERVATION_ONLY(
        seeded_db, monkeypatch):
    """Codex A3-AR-06 (MINOR), on the route's own two warning strings.

    `logger.error` raising proves a HANDLER raised, not that no sink received
    the record. PRE-fix the operator-facing text asserted the outcome; POST-fix
    it reports the observation.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)
    _raise_from_build_dashboard(
        monkeypatch, RuntimeError("22-A3 PROBE: dashboard rebuild failed"))

    app = create_app(cfg, cfg_path)
    with _RaisingHandler("swing.web.routes.trades"):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]
    assert "a logging handler RAISED" in resp.text
    assert "Some sinks may have received" in resp.text
