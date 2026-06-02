"""Phase 14 close-out (P14.N1) — render-direct lazy thumbnail route for hyp-rec
candidate rows. Drives the REAL route handler + REAL render_watchlist_thumbnail_svg
+ REAL Jinja partial; only the external OHLCV-fetch boundary is controlled (a
fake app.state.ohlcv_cache). Render-direct: NO chart_renders write (L5).
"""
from __future__ import annotations

import re

import pandas as pd
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _make_bars(rows: int = 60) -> pd.DataFrame:
    idx = pd.bdate_range(start="2026-01-02", periods=rows)
    opens = [100.0 + i for i in range(rows)]
    return pd.DataFrame(
        {
            "Open": opens,
            "High": [o + 2 for o in opens],
            "Low": [o - 2 for o in opens],
            "Close": [o + 0.5 for o in opens],
            "Volume": [1_000_000.0 for _ in opens],
        },
        index=idx,
    )


class _FakeCache:
    """Records get_or_fetch calls; returns a fixed frame (or None/empty)."""

    def __init__(self, bars):
        self._bars = bars
        self.calls = []

    def get_or_fetch(self, *, ticker, window_days=180):
        self.calls.append((ticker, window_days))
        return self._bars


def _app_with_cache(seeded_db, cache):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    return app, cache, cfg


def _count_chart_renders(cfg, *, surface: str, ticker: str) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM chart_renders WHERE surface=? AND ticker=?",
            (surface, ticker),
        )
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def test_hyprec_thumbnail_returns_svg(seeded_db):
    app, cache, cfg = _app_with_cache(seeded_db, _FakeCache(_make_bars(60)))
    with TestClient(app) as client:
        app.state.ohlcv_cache = cache
        resp = client.get(
            "/hyp-recs/NVDA/thumbnail", headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "<svg" in resp.text
        assert resp.headers["Cache-Control"] == "private, max-age=60"


def test_hyprec_thumbnail_unavailable_on_no_bars(seeded_db):
    empty = pd.DataFrame()
    app, cache, cfg = _app_with_cache(seeded_db, _FakeCache(empty))
    with TestClient(app) as client:
        app.state.ohlcv_cache = cache
        resp = client.get(
            "/hyp-recs/NVDA/thumbnail", headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "chart-unavailable" in resp.text
        assert "<tr" not in resp.text  # fragment root is span/svg, never bare <tr>


def test_hyprec_thumbnail_does_not_write_chart_renders(seeded_db):
    app, cache, cfg = _app_with_cache(seeded_db, _FakeCache(_make_bars(60)))
    with TestClient(app) as client:
        app.state.ohlcv_cache = cache
        client.get("/hyp-recs/NVDA/thumbnail", headers={"HX-Request": "true"})
    assert _count_chart_renders(cfg, surface="watchlist_row", ticker="NVDA") == 0
    assert _count_chart_renders(cfg, surface="watchlist_row", ticker="NVDA") == 0


def test_hyprec_thumbnail_invalid_ticker_does_not_fetch(seeded_db):
    cache = _FakeCache(_make_bars(60))
    app, cache, cfg = _app_with_cache(seeded_db, cache)
    with TestClient(app) as client:
        app.state.ohlcv_cache = cache
        # "BAD_TICKER" fails _TICKER_RE (underscore). A single invalid path
        # segment (Codex R3 m#1) -- not an encoded-slash path.
        resp = client.get(
            "/hyp-recs/BAD_TICKER/thumbnail", headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "chart-unavailable" in resp.text
    assert cache.calls == []  # get_or_fetch never invoked for an invalid ticker


# -- Task B.4: hyp-rec table column shape -------------------------------------

from tests.web.test_routes.test_hyp_recs_expand_route import (  # noqa: E402
    _patch_price_cache,
    _seed_hyp_recs_fixture,
)


def _hyprec_section(body: str) -> str:
    m = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*>.*?</section>',
        body, flags=re.DOTALL,
    )
    assert m is not None, "hyp-recs section not found"
    return m.group(0)


def test_hyprec_column_counts_align(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        body = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        ).text
        section = _hyprec_section(body)
        thead = re.search(r"<thead>.*?</thead>", section, flags=re.DOTALL).group(0)
        assert len(re.findall(r"<th\b[^>]*>", thead)) == 10
        row = re.search(
            r'<tr\b[^>]*id="hyp-rec-row-NVDA"[^>]*>.*?</tr>',
            section, flags=re.DOTALL,
        ).group(0)
        assert len(re.findall(r"<td\b[^>]*>", row)) == 10
        expanded = client.get(
            "/hyp-recs/NVDA/expand", headers={"HX-Request": "true"},
        ).text
    assert 'colspan="10"' in expanded


def test_hyprec_row_lazy_cell_but_tr_trigger_free(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        body = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        ).text
    # the lazy thumbnail cell hx-gets the ticker route
    assert 'hx-get="/hyp-recs/NVDA/thumbnail"' in body
    assert 'hx-trigger="revealed"' in body
    # the <tr> OPEN TAG itself must remain trigger-free (discriminator)
    m = re.search(r'<tr\b[^>]*\bid="hyp-rec-row-NVDA"[^>]*>', body)
    assert m and "hx-get" not in m.group(0) and "hx-trigger" not in m.group(0)
