"""Trade routes: GET /trades/entry/sizing-hint (tolerant contract) for now."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_sizing_hint_happy_path(seeded_db, monkeypatch):
    """Valid entry/stop with feasible sizing → numbers fragment, always 200.

    Uses entry=10.0, stop=9.0 so that with test equity ($1200) and
    max_risk_pct=0.005 ($6 budget, rps=$1) → 6 shares → feasible.
    seeded_db ensures schema exists so connect() succeeds.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=10.0&initial_stop=9.0")
    assert r.status_code == 200
    assert "sizing-hint" in r.text
    # Feasible result: text should include "sh".
    assert "sh" in r.text.lower()


def test_sizing_hint_missing_params(test_cfg):
    """Missing query params → 200 with dim guidance."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_blank_params(test_cfg):
    """Blank query params → 200 with dim guidance."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=&initial_stop=")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_non_numeric(test_cfg):
    """Non-numeric values → 200 with dim guidance (no 422)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=abc&initial_stop=xyz")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_stop_ge_entry(test_cfg):
    """stop >= entry → 200 with dim guidance (no compute_shares call, so no ValueError)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=100.0&initial_stop=100.0")
    assert r.status_code == 200
    assert "stop &lt; entry" in r.text or "valid entry price" in r.text.lower()


def test_sizing_hint_zero_equity(seeded_db, monkeypatch):
    """Zero equity → 200 with feasible=False guidance, not 500."""
    cfg, cfg_path = seeded_db
    # Force equity=0 by patching current_equity where the route reads it.
    monkeypatch.setattr("swing.web.routes.trades.current_equity", lambda **_kw: 0.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=180.0&initial_stop=170.0")
    assert r.status_code == 200
    assert "no equity" in r.text.lower() or "unavailable" in r.text.lower()


def test_get_entry_form_renders(seeded_db, monkeypatch):
    """GET /trades/entry/form?ticker=X → trade_entry_form fragment with prefills."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    assert r.status_code == 200
    assert "AAPL" in r.text
    # Entry price prefilled from live snapshot.
    assert "180.95" in r.text
    # Initial stop prefilled from watchlist.
    assert "170.00" in r.text


def test_get_entry_form_sizing_hint_has_explicit_hx_target(seeded_db, monkeypatch):
    """Bug 2 root-cause fix: the sizing-hint span MUST carry an explicit hx-target
    so it does not inherit hx-target='closest tr' from the parent <form>. Without
    the explicit target, the sizing-hint hx-get response (a <span>) swaps into
    the entry-form <tr>, replacing the entire form with just the sizing hint —
    which is exactly what the operator reported.

    Network trace evidence (2026-04-25): operator typed entry_price, blurred,
    sizing-hint GET fired (200, 0.3 kB), form vanished leaving only
    'Suggested max: 6 sh (~$5.64 risk = 0.43%)'. That string is the entire
    contents of partials/sizing_hint.html.j2 — confirming the swap targeted
    the entire form (via inherited closest-tr) instead of just the span.
    """
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    assert r.status_code == 200
    # Locate the sizing-hint span tag and assert hx-target="this" is in its
    # opening attribute set. Pre-fix: this attribute was absent and the span
    # silently inherited hx-target="closest tr" from the parent <form>.
    import re
    span_match = re.search(
        r'<span\s+id="sizing-hint"[^>]*?>',
        r.text,
        re.DOTALL,
    )
    assert span_match is not None, (
        "sizing-hint span not found in rendered entry form"
    )
    span_open_tag = span_match.group(0)
    assert 'hx-target="this"' in span_open_tag, (
        f"sizing-hint span missing explicit hx-target='this'. "
        f"Got opening tag: {span_open_tag!r}. "
        f"Without explicit hx-target, the span inherits 'closest tr' "
        f"from the parent form and the sizing-hint response replaces "
        f"the entire entry form on every change event."
    )


def test_post_entry_success_emits_row_and_oobs(seeded_db, monkeypatch):
    """POST /trades/entry success → primary row + #status-strip OOB + #watchlist-top5 OOB."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL",
                "entry_date": "2026-04-18",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
            },
        )
    assert r.status_code == 200
    # Primary target: a new open-position row with id.
    assert "open-position-" in r.text
    assert "AAPL" in r.text
    # OOB fragments present.
    assert "hx-swap-oob" in r.text
    assert 'id="status-strip"' in r.text
    assert 'id="watchlist-top5"' in r.text


def test_post_entry_soft_warn_2step(seeded_db, monkeypatch):
    """First submit at soft cap → confirm fragment; second with force=true → success."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade, WatchlistEntry
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    # Seed open trades up to soft_warn_open (default 4).
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, t in enumerate(("MSFT", "NVDA", "GOOG", "META")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=t, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-15T09:{30+i}:00")
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    form_data = {
        "ticker": "AAPL", "entry_date": "2026-04-18",
        "entry_price": "180.95", "shares": "1", "initial_stop": "170.00",
        "rationale": "aplus-setup",
    }
    with TestClient(app) as client:
        # First submit — no force. Should get soft_warn_confirm fragment.
        r1 = client.post("/trades/entry", headers={"HX-Request": "true"}, data=form_data)
        assert r1.status_code == 200
        assert "Soft cap reached" in r1.text
        assert 'name="force" value="true"' in r1.text
        # Second submit — with force=true. Should succeed.
        form_data2 = dict(form_data)
        form_data2["force"] = "true"
        r2 = client.post("/trades/entry", headers={"HX-Request": "true"}, data=form_data2)
        assert r2.status_code == 200
        assert "open-position-" in r2.text


def test_post_entry_hard_cap_error(seeded_db, monkeypatch):
    """Hard cap reached → 400 trade_form_error fragment, no UI bypass."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    # Seed to hard_cap (default 6).
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, t in enumerate(("A", "B", "C", "D", "E", "F")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=t, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-15T09:{30+i}:00")
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "180.0", "shares": "1",
                "initial_stop": "170.0", "rationale": "aplus-setup",
                "force": "true",   # bypass soft-warn; but hard cap still blocks
            },
        )
    assert r.status_code == 400
    assert "hard cap" in r.text.lower() or "hard_cap" in r.text.lower()


def test_post_entry_duplicate_error(seeded_db, monkeypatch):
    """Duplicate open position → 400 fragment with drift-recovery wording."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=5, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "182.0", "shares": "3",
                "initial_stop": "175.0", "rationale": "aplus-setup",
            },
        )
    assert r.status_code == 400
    assert "already" in r.text.lower() or "open trade" in r.text.lower()


def test_get_exit_form_renders(seeded_db, monkeypatch):
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(
                ticker="NVDA", price=932.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/exit/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "NVDA" in r.text
    assert "932.00" in r.text  # exit price prefilled
    assert "stop-hit" in r.text  # reasons select populated


def test_get_exit_form_for_closed_trade_returns_404_fragment(seeded_db):
    """Missing/closed trade → HTMX-aware 404 <tr> fragment (§5.1 case 4 + §5.2).

    HX-Target-aware handler (spec §3.3): row-prefix targets (`open-position-*`,
    etc.) render trade_form_error.html.j2 (<tr>). Production HTMX resolves
    `hx-target="closest tr"` to the open-position row id, so the header value
    is `open-position-{id}`.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/trades/99999/exit/form",
            headers={"HX-Request": "true", "HX-Target": "open-position-99999"},
        )
    assert r.status_code == 404
    # Not JSON — HTMX-aware fragment.
    assert "banner" in r.text
    assert "not found" in r.text.lower() or "not open" in r.text.lower()
    # HX-Target-aware handler: row-prefix → <tr>-shaped fragment.
    assert "<tr" in r.text.lower()


def test_post_exit_full_close_removes_row(seeded_db, monkeypatch):
    """Full close → row disappears; #status-strip OOB only (no watchlist OOB)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=932.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "5", "reason": "manual"},
        )
    assert r.status_code == 200
    # Full close: no <tr> for the now-closed position; empty/hidden stub OK.
    assert f"open-position-{trade.id}" not in r.text or 'display:none' in r.text.lower()
    # Status-strip OOB present.
    assert 'id="status-strip"' in r.text
    assert "hx-swap-oob" in r.text
    # Watchlist OOB NOT emitted on exit.
    assert 'id="watchlist-top5"' not in r.text


def test_post_exit_partial_updates_row(seeded_db, monkeypatch):
    """Partial close → row re-rendered with reduced remaining_shares."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=10, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=932.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "3", "reason": "partial"},
        )
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    # Remaining shares: 10 - 3 = 7.
    assert "7 / 10" in r.text or ">7<" in r.text


def test_post_exit_shares_too_many_400(seeded_db, monkeypatch):
    """Shares > remaining → 400 error fragment (§5.1 case 2)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "10", "reason": "manual"},  # over-exit
        )
    assert r.status_code == 400
    assert "remaining" in r.text.lower() or "exceed" in r.text.lower()


def test_get_stop_form_renders(seeded_db):
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/stop/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "NVDA" in r.text
    assert "860.00" in r.text


def test_post_stop_adjust_success(seeded_db, monkeypatch):
    """Stop-adjust success → row re-render; no OOB."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "912.00", "rationale": "trail-10ma"},
        )
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    assert "912.00" in r.text
    # Stop-adjust emits NO OOB.
    assert 'id="status-strip"' not in r.text


def test_post_stop_persists_notes_field(seeded_db, monkeypatch):
    """Bug 3b: POST /trades/{id}/stop with a `notes` form field writes
    trade_events.notes alongside rationale."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import (
        insert_trade_with_event, list_open_trades, list_events_for_trade,
    )
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={
                "new_stop": "912.00",
                "rationale": "trail-10ma",
                "notes": "low-volume up-day",
            },
        )
    assert r.status_code == 200

    conn = connect(cfg.paths.db_path)
    try:
        adj = next(
            e for e in list_events_for_trade(conn, trade.id) if e.event_type == "stop_adjust"
        )
    finally:
        conn.close()
    assert adj.rationale == "trail-10ma"
    assert adj.notes == "low-volume up-day"


def test_get_stop_form_includes_notes_textarea(seeded_db):
    """Bug 3b: GET /trades/{id}/stop/form renders a <textarea name='notes'>
    so the operator can attach free-form context at submit time."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/stop/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert 'name="notes"' in r.text


def test_post_stop_regression_400_with_updated_current(seeded_db):
    """Lowering stop → 400 fragment with updated current_stop prefilled (§5.1 case 3)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=900.0, status="open",  # someone already trailed to BE
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "880.00", "rationale": "manual-trail"},
        )
    assert r.status_code == 400
    # Error message names the actual current_stop.
    assert "900" in r.text
    assert "force" in r.text.lower()  # CLI hint


def test_get_trade_cancel_returns_normal_row(seeded_db, monkeypatch):
    """GET /trades/{id}/cancel → normal open-positions row."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/cancel",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    # The row has Exit + Adjust stop buttons (normal state).
    assert "Exit" in r.text
    assert "Adjust stop" in r.text


def test_post_exit_shares_too_many_renders_form_with_updated_max(seeded_db, monkeypatch):
    """§5.1 case 2 — 400 re-renders exit form with authoritative max= on shares input."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "10", "reason": "manual"},
        )
    assert r.status_code == 400
    # Error banner still present.
    assert "remaining" in r.text.lower() or "exceed" in r.text.lower()
    # Form re-rendered inside the error fragment.
    assert 'name="shares"' in r.text
    # Authoritative max reflects actual remaining shares (5).
    assert 'max="5"' in r.text


def test_post_stop_regression_renders_form_with_updated_current(seeded_db):
    """§5.1 case 3 — 400 re-renders stop form with authoritative current_stop prefilled."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=900.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "880.00", "rationale": "manual-trail"},
        )
    assert r.status_code == 400
    # Error message names the actual current_stop.
    assert "900" in r.text
    # Form re-rendered inside the error fragment.
    assert 'name="new_stop"' in r.text
    # T7: the user's typed new_stop (880) is preserved on error re-render,
    # not reset to the authoritative 900. The operator can now either tick
    # Force or adjust the value — losing their input on every mistake is
    # hostile UX.
    assert 'value="880.00"' in r.text


def test_post_stop_for_closed_trade_returns_404_fragment(seeded_db):
    """POST /trades/{id}/stop for a missing trade → 404 HTMX <tr> fragment (Major 2).

    adjust_stop raises ValueError when the trade_id is not found; the route
    must catch that and re-raise as HTTPException(404) so the HTMX-aware
    HX-Target-aware handler renders trade_form_error.html.j2 (a <tr>) rather
    than http_error_fragment.html.j2 (a <div>), since the adjust-stop form's
    `hx-target='closest tr'` resolves to `open-position-{id}` (row prefix).
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/99999/stop",
            headers={"HX-Request": "true", "HX-Target": "open-position-99999"},
            data={"new_stop": "880.00", "rationale": "manual-trail"},
        )
    assert r.status_code == 404
    assert "banner" in r.text
    assert "not" in r.text.lower()
    # HX-Target-aware handler (spec §3.3): row-prefix → <tr>-shaped fragment.
    assert "<tr" in r.text.lower()


def test_post_entry_duplicate_renders_form_preserved(seeded_db, monkeypatch):
    """Duplicate open position → 400 with error banner AND form re-rendered (Major 1)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=5, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "182.0", "shares": "3",
                "initial_stop": "175.0", "rationale": "aplus-setup",
            },
        )
    assert r.status_code == 400
    # Banner mentions the duplicate.
    assert "already" in r.text.lower() or "open trade" in r.text.lower()
    # Form is re-rendered inside the error fragment.
    assert 'name="ticker"' in r.text
    # Submitted values preserved (R2 Major 2 fix: dataclasses.replace).
    # T4: rationale is now a <select>; the submitted enum value becomes the
    # selected option on re-render.
    assert 'value="aplus-setup" selected' in r.text
    assert 'value="175.00"' in r.text          # initial_stop echoed back
    assert 'value="182.00"' in r.text          # entry_price echoed back
    # R5 fix: input value reflects user's submitted shares (shares=3 was submitted).
    assert 'name="shares"' in r.text
    assert 'value="3"' in r.text


def test_post_entry_stop_ge_entry_renders_form_preserved(seeded_db, monkeypatch):
    """Bug 2 (2026-04-25): stop >= entry must NOT bubble ValueError to the
    generic 500 handler. The route must catch ValueError and re-render the
    entry form with an error banner inside a ``<tr id="entry-form-…">`` —
    otherwise the generic handler returns a bare ``<div>``, which the HTML
    parser hoists out of ``<tbody>`` and the operator's row vanishes from
    the watchlist until refresh.

    Operator-reported reproduction: click watchlist Enter button → form
    appears, adjust entry_price to match initial_stop → submit (Enter key
    or Submit button) → row collapses, watchlist entry disappears.

    Pre-fix evidence: status=500, body=``<div class="banner banner-degraded"
    …>Error (request …): stop must be < entry; got entry=170.0, stop=170.0</div>``
    — NO ``<tr>``, NO form markup. Browser HTML parser hoists the bare
    ``<div>`` out of ``<tbody>`` (only ``<tr>`` is a valid tbody child),
    leaving the row position empty. Refresh restores because the watchlist
    DB row is untouched.

    Post-fix expectation: status=400, response is the trade_entry_form
    fragment wrapped in ``<tr id="entry-form-AAPL">`` with the error banner
    and submitted values preserved (entry_price, initial_stop, shares,
    rationale).
    """
    from datetime import datetime

    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=170.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true", "HX-Target": "entry-form-AAPL"},
            data={
                "ticker": "AAPL",
                "entry_date": "2026-04-18",
                "entry_price": "170.00",
                "shares": "5",
                "initial_stop": "170.00",  # stop == entry → ValueError pre-fix
                "rationale": "aplus-setup",
            },
        )
    # Pre-fix this is 500; post-fix it must be 400 (validation failure shape
    # mirroring DuplicateOpenPositionException).
    assert r.status_code == 400, (
        f"Expected 400 (validation failure re-render), got {r.status_code}.\n"
        f"Body[:500]: {r.text[:500]!r}"
    )
    # Strongest discriminator: response must be a row-shaped fragment so the
    # outerHTML swap into the entry-form <tr> stays inside <tbody>. Pre-fix
    # the body is a bare <div> with no <tr> wrapper.
    assert '<tr id="entry-form-AAPL"' in r.text, (
        "Response must be wrapped in the entry-form <tr> so the closest-tr "
        "swap target stays valid inside <tbody>. Pre-fix the generic "
        "exception handler returns a bare <div> which the HTML parser hoists "
        "out of <tbody>, vanishing the row."
    )
    # Form must be re-rendered so the operator can correct and resubmit.
    assert 'name="entry_price"' in r.text
    assert 'name="initial_stop"' in r.text
    # Banner with the validation message.
    assert "banner-degraded" in r.text
    assert "stop" in r.text and "entry" in r.text  # the ValueError message
    # Submitted values preserved (mirrors duplicate-error preservation).
    assert 'value="170.00"' in r.text
    assert 'value="aplus-setup" selected' in r.text
    # Bug 1 fix preservation: stale check that nothing in the form template
    # silently regressed (the form is re-rendered from the canonical partial).
    assert 'hx-post="/trades/entry"' in r.text
    # Negative discriminator: the bare-div generic-error fragment
    # (partials/error_fragment.html.j2) carries data-request-id; the form's
    # inline banner does not. Asserting its absence rules out a regression
    # where the route falls back to the generic 500 path.
    assert "data-request-id" not in r.text


def test_post_entry_stop_gt_entry_also_caught(seeded_db, monkeypatch):
    """Bug 2 follow-up: stop > entry (not just ==) is also caught at the
    request boundary and re-renders the row-shaped form fragment.

    Guards the boundary against a future change that might narrow the
    pre-check to equality only. Comprehensive shape assertions mirror
    the == case so the row-shape contract is locked down for both
    invalid-input branches.
    """
    from datetime import datetime

    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=170.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true", "HX-Target": "entry-form-AAPL"},
            data={
                "ticker": "AAPL",
                "entry_date": "2026-04-18",
                "entry_price": "170.00",
                "shares": "5",
                "initial_stop": "175.00",  # stop > entry
                "rationale": "aplus-setup",
            },
        )
    assert r.status_code == 400
    assert '<tr id="entry-form-AAPL"' in r.text
    assert 'value="170.00"' in r.text       # entry_price preserved
    assert 'value="175.00"' in r.text       # initial_stop preserved
    # Form re-rendered from canonical partial.
    assert 'hx-post="/trades/entry"' in r.text
    assert 'name="entry_price"' in r.text
    assert 'name="initial_stop"' in r.text
    # Banner present (form's inline banner, not the generic error fragment).
    assert "banner-degraded" in r.text
    # Negative discriminator: rule out the bare-div generic-error fallback.
    assert "data-request-id" not in r.text


def test_post_entry_stop_ge_entry_unhandled_value_error_still_500(
    seeded_db, monkeypatch,
):
    """Bug 2 contract guard: the route's pre-boundary check handles the
    operator-facing stop>=entry case explicitly. Any OTHER ValueError
    raised by record_entry (a future deeper-layer invariant or a real
    server defect) MUST surface as 500 — not be silently masked as form
    validation. Codex R1 Major 1: this prevents the catch from masking
    server defects as user input errors.

    We monkeypatch record_entry to raise an unrelated ValueError and
    assert the response is 500 + the generic error_fragment shape,
    confirming the route does NOT swallow the exception via a stale
    blanket except clause.
    """
    from datetime import datetime

    import swing.web.routes.trades as trades_route
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=180.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    def _boom(*_a, **_kw):
        raise ValueError("synthetic deep-layer invariant violation")
    monkeypatch.setattr(trades_route, "record_entry", _boom)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true", "HX-Target": "entry-form-AAPL"},
            data={
                "ticker": "AAPL",
                "entry_date": "2026-04-18",
                "entry_price": "180.00",
                "shares": "5",
                "initial_stop": "170.00",   # valid (entry > stop) — passes pre-check
                "rationale": "aplus-setup",
            },
        )
    # The pre-check passes; record_entry's synthetic ValueError must NOT be
    # swallowed by an over-broad except — it must surface as 500.
    assert r.status_code == 500
    # 3e Bug 2 follow-up (T7): unhandled non-HTTPExceptions on row-target
    # HTMX requests now render `partials/trade_form_error.html.j2` (a <tr>)
    # rather than `partials/error_fragment.html.j2` (a <div>) so the HTML
    # parser does not hoist a <div> out of <tbody>. The 500 status is
    # preserved (NOT silently masked as 400 form-validation), and the
    # body is structurally NOT the form re-render. Codex R2 M1: still do
    # NOT assert the raw exception message; trade_form_error does embed
    # error_message inline today, but locking that in would block future
    # sanitization. Test the structural shape only.
    body = r.text.lstrip()
    assert body.startswith("<tr"), (
        f"row-target 500 must be <tr> shape (trade_form_error), got: "
        f"{body[:80]!r}"
    )
    assert 'class="trade-form-error"' in body
    # Negative discriminator: must NOT be the form-rerender shape.
    assert '<tr id="entry-form-AAPL"' not in r.text
    assert 'hx-post="/trades/entry"' not in r.text


def test_post_entry_duplicate_sizing_hint_not_lying(seeded_db, monkeypatch):
    """R5 regression: on drift-recovery, the sizing hint must NOT claim the user's
    entered shares is the server's recommendation. The 'Suggested max' text
    reflects the server's actual compute_shares output."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade, WatchlistEntry
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Seed watchlist row so build_entry_form_vm can compute a server sizing.
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            # Seed an existing open AAPL trade to trigger duplicate error.
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=5, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.95,
                                   asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # User enters an absurdly high share count that server would never suggest.
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={"ticker": "AAPL", "entry_date": "2026-04-18",
                  "entry_price": "182.00", "shares": "9999",
                  "initial_stop": "175.00", "rationale": "aplus-setup"},
        )
    assert r.status_code == 400
    # Input value reflects user's attempted entry.
    assert 'value="9999"' in r.text
    # Sizing hint text must NOT claim "Suggested max: 9999 sh" — that would
    # be the server echoing the user's own number as a recommendation.
    assert "Suggested max: <strong>9999 sh</strong>" not in r.text
    assert "Suggested max: 9999" not in r.text


def test_post_stop_for_actually_closed_trade_returns_404_fragment(seeded_db):
    """Trade that was open then fully closed → 404 <tr> fragment on stop POST (§5.1 case 4).

    Verifies the path-aware 404 handler (R2 Major 1) for a real closed trade,
    not just a nonexistent id.
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
        with conn:
            record_exit(conn, ExitRequest(
                trade_id=trade.id, exit_date="2026-04-17",
                exit_price=910.0, shares=5, reason=ExitReason.MANUAL,
                notes=None, rationale="full close",
                event_ts="2026-04-17T10:00:00",
            ))
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop",
            headers={"HX-Request": "true", "HX-Target": f"open-position-{trade.id}"},
            data={"new_stop": "900.00", "rationale": "manual-trail"},
        )
    assert r.status_code == 404
    # HX-Target-aware handler (spec §3.3): row-prefix → <tr>-shaped fragment.
    assert "<tr" in r.text.lower()
    assert "banner" in r.text


def test_post_trades_without_hx_request_403(test_cfg):
    """Strict OriginGuard: POST /trades/entry without HX-Request → 403 with X-Request-ID."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            data={"ticker": "AAPL", "entry_date": "2026-04-18",
                  "entry_price": "180.0", "shares": "1",
                  "initial_stop": "170.0", "rationale": "aplus-setup"},
            # NO HX-Request header.
        )
    assert r.status_code == 403
    assert "strict" in r.text.lower()
    assert "x-request-id" in {h.lower() for h in r.headers.keys()}


def test_post_exit_shares_too_many_is_single_tr_no_orphan(seeded_db, monkeypatch):
    """After R4 fix: error response is a SINGLE <tr> (banner inlined), not
    banner <tr> + form <tr> siblings. Prevents orphaned banner on retry."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "10", "reason": "manual"},
        )
    assert r.status_code == 400
    # Exactly one top-level <tr — the form with inline banner.
    opening_tr_count = r.text.lower().count("<tr")
    assert opening_tr_count == 1, (
        f"Expected exactly 1 <tr tag (form+banner inlined), got {opening_tr_count}. "
        f"Response: {r.text[:500]}"
    )
    # Banner is present.
    assert "banner" in r.text.lower()
    # Form fields are present.
    assert 'name="shares"' in r.text


# ---------------------------------------------------------------------------
# Tranche B-ops T4 — EntryRationale closed taxonomy
# ---------------------------------------------------------------------------

def test_get_entry_form_renders_rationale_select_with_seven_options(
    seeded_db, monkeypatch,
):
    """T4: the entry form must render rationale as a <select> (not a textarea)
    with all seven options in spec §3 declared order. Pre-T4 the template used
    <textarea name="rationale">."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.95,
                                   asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    assert r.status_code == 200
    assert '<select name="rationale"' in r.text
    # All seven values appear in spec order.
    expected = [
        "aplus-setup", "near-trigger-breakout", "vcp-breakout",
        "pivot-breakout", "post-earnings-continuation",
        "relative-strength", "other",
    ]
    positions = [r.text.find(f'value="{v}"') for v in expected]
    assert all(p >= 0 for p in positions), positions
    assert positions == sorted(positions), (
        f"<option> order does not match spec-declared order: {list(zip(expected, positions))}"
    )
    # Human-readable label for the first option (apostrophe survives Jinja
    # auto-escaping as &#39;).
    assert ("A+ setup (today's decision)" in r.text
            or "A+ setup (today&#39;s decision)" in r.text)


def test_post_entry_unknown_rationale_rejected_with_preserved_fields(
    seeded_db, monkeypatch,
):
    """T4: POST /trades/entry with a free-text rationale outside the closed
    taxonomy → 400 + form re-rendered with the submitted values preserved.
    Pre-T4 this succeeded (wrote free text to trade_events.rationale)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.trades import list_open_trades
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.95,
                                   asof=datetime.now(),
                                   is_stale=False, source="live"),
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "180.95", "shares": "5",
                "initial_stop": "170.00",
                "rationale": "VCP entry",       # pre-T4 free-text phrasing
                "notes": "Keep this on re-render",
            },
        )
    assert r.status_code == 400
    assert "invalid rationale" in r.text.lower()
    # Form re-rendered with preserved values.
    assert '<select name="rationale"' in r.text
    assert "Keep this on re-render" in r.text
    # No trade inserted.
    conn2 = connect(cfg.paths.db_path)
    try:
        assert list_open_trades(conn2) == []
    finally:
        conn2.close()


def test_post_entry_other_without_notes_rejected(seeded_db, monkeypatch):
    """T4: rationale=other without non-empty notes → 400 with
    'notes required' message. Pre-T4 free-text would have accepted it."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.trades import list_open_trades
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.95,
                                   asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "180.95", "shares": "5",
                "initial_stop": "170.00",
                "rationale": "other",
                # no notes
            },
        )
    assert r.status_code == 400
    assert "notes are required" in r.text.lower()
    # Rationale=other selected state is preserved on re-render.
    assert 'value="other" selected' in r.text
    # No trade inserted.
    conn2 = connect(cfg.paths.db_path)
    try:
        assert list_open_trades(conn2) == []
    finally:
        conn2.close()


def test_post_entry_other_with_notes_succeeds(seeded_db, monkeypatch):
    """T4: rationale=other with non-empty notes → trade recorded normally
    with rationale='other' written to trade_events.rationale."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.trades import list_open_trades
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=180.95, asof=datetime.now(),
                             is_stale=False, source="live") for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "180.95", "shares": "5",
                "initial_stop": "170.00",
                "rationale": "other",
                "notes": "post-earnings gap with high ADR",
            },
        )
    assert r.status_code == 200
    assert "open-position-" in r.text
    # Verify persistence.
    from swing.data.repos.trades import list_events_for_trade
    conn2 = connect(cfg.paths.db_path)
    try:
        trades = list_open_trades(conn2)
        assert len(trades) == 1
        events = list_events_for_trade(conn2, trades[0].id)
        entry_ev = next(e for e in events if e.event_type == "entry")
        assert entry_ev.rationale == "other"
    finally:
        conn2.close()


# ---------------------------------------------------------------------------
# Tranche B-ops T5 — StopAdjustRationale closed taxonomy
# ---------------------------------------------------------------------------

def test_get_stop_form_renders_rationale_select_with_seven_options(seeded_db):
    """T5: the stop-adjust form must render rationale as a <select> (not a
    textarea) with all seven options in spec §3 order. Pre-T5 the template
    used <textarea name="rationale">."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/stop/form")
    assert r.status_code == 200
    assert '<select name="rationale"' in r.text
    expected = [
        "breakeven", "trail-10ma", "trail-20ma", "weather-tighten",
        "manual-trail", "news", "other",
    ]
    positions = [r.text.find(f'value="{v}"') for v in expected]
    assert all(p >= 0 for p in positions), positions
    assert positions == sorted(positions), (
        f"<option> order does not match spec: {list(zip(expected, positions))}"
    )
    assert "Move to breakeven (system advisory)" in r.text


def test_post_stop_unknown_rationale_rejected(seeded_db, monkeypatch):
    """T5: POST /trades/{id}/stop with a non-enum rationale → 400 with error
    banner. Pre-T5 this would write the free text to trade_events."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_events_for_trade, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "910.00", "rationale": "freeform gut feel"},
        )
    assert r.status_code == 400
    assert "invalid rationale" in r.text.lower()
    # Form re-rendered, not the full-page error banner.
    assert '<select name="rationale"' in r.text
    # Stop NOT updated.
    conn2 = connect(cfg.paths.db_path)
    try:
        t = next(t for t in list_open_trades(conn2) if t.id == trade.id)
        assert t.current_stop == 860.0
        # No stop_adjust event written.
        events = list_events_for_trade(conn2, trade.id)
        assert not any(e.event_type == "stop_adjust" for e in events)
    finally:
        conn2.close()


def test_exit_form_has_no_rationale_input(seeded_db, monkeypatch):
    """T6: GET /trades/{id}/exit/form no longer renders a rationale input.
    Pre-T6 the template had <textarea name="rationale" required>."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=930.0,
                                   asof=datetime.now(), is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/exit/form")
    assert r.status_code == 200
    assert 'name="rationale"' not in r.text
    # Reason <select> is still present.
    assert 'name="reason"' in r.text


def test_post_exit_writes_reason_value_as_rationale(seeded_db, monkeypatch):
    """T6: POST /trades/{id}/exit writes req.reason.value into
    trade_events.rationale automatically; the request body no longer carries
    a rationale field. Pre-T6 rationale was free text from the form."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_events_for_trade, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=930.0,
                                   asof=datetime.now(), is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={
                "exit_date": "2026-04-17", "exit_price": "930.00",
                "shares": "5", "reason": "stop-hit",
                # NO rationale field — T6 drops it from the form.
                "notes": "hit stop at close",
            },
        )
    assert r.status_code == 200
    conn2 = connect(cfg.paths.db_path)
    try:
        exit_ev = next(
            e for e in list_events_for_trade(conn2, trade.id)
            if e.event_type == "exit"
        )
    finally:
        conn2.close()
    # rationale synthesized from reason.value — NOT from any form input.
    assert exit_ev.rationale == "stop-hit"


def test_get_stop_form_renders_force_checkbox_unchecked(seeded_db):
    """T7: GET /trades/{id}/stop/form renders a Force checkbox, NOT ticked
    by default. Pre-T7 the stop form had no Force control (operators had to
    drop to CLI)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/stop/form")
    assert r.status_code == 200
    assert 'type="checkbox" name="force" value="true"' in r.text
    # Default: unchecked. 'checked' attribute must NOT appear on the force
    # input. (A broader "no 'checked'" assertion would be brittle if a
    # future date/select added checked state elsewhere.)
    force_idx = r.text.find('name="force"')
    assert force_idx > 0
    # Examine the substring from the input's tag-open to the tag-close.
    tag_close = r.text.find(">", force_idx)
    force_tag = r.text[force_idx:tag_close]
    assert "checked" not in force_tag


def test_post_stop_regression_preserves_typed_fields(seeded_db):
    """T7 preservation: on StopRegressionError, typed new_stop, rationale,
    and notes are retained on the re-render. Force checkbox is NOT
    auto-ticked (spec §5)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=890.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={
                "new_stop": "870.00",             # lower than 890 → regression
                "rationale": "manual-trail",
                "notes": "fixing an over-tight initial stop from entry",
                # NOT submitting force=true — default path.
            },
        )
    assert r.status_code == 400
    # Typed values preserved.
    assert 'value="870.00"' in r.text
    assert 'value="manual-trail" selected' in r.text
    assert "fixing an over-tight initial stop from entry" in r.text
    # Force is present as an input, but NOT checked on the re-render.
    force_idx = r.text.find('name="force"')
    assert force_idx > 0
    tag_close = r.text.find(">", force_idx)
    force_tag = r.text[force_idx:tag_close]
    assert "checked" not in force_tag


def test_post_stop_with_force_checkbox_regression_succeeds(seeded_db):
    """T7: ticking the Force checkbox sends `force=true`, the route builds
    StopAdjustRequest(force=True), adjust_stop no longer raises, and the
    stop is lowered. This closes the prior CLI-only workaround."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import get_trade, insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=890.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={
                "new_stop": "870.00",
                "rationale": "manual-trail",
                "notes": "operator override",
                "force": "true",
            },
        )
    assert r.status_code == 200
    conn2 = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn2, trade.id)
    finally:
        conn2.close()
    assert updated.current_stop == 870.0


def test_post_stop_other_without_notes_rejected(seeded_db):
    """T5: rationale=other without notes → 400 with 'notes required' banner."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "910.00", "rationale": "other"},
        )
    assert r.status_code == 400
    assert "notes are required" in r.text.lower()


# ---------------------------------------------------------------------------
# Task 5 (R1 M1): entry_post emits #hypothesis-recommendations OOB on
# origin=hyp-recs success. Closes the production-blocking bug where the
# just-traded ticker stays visible in the hyp-recs panel after a successful
# trade and the broken open-positions row briefly lands inside the hyp-recs
# <tbody>.
#
# Sentinel tickers (reserved for this plan; CLAUDE.md "test fixture
# unambiguity" pattern):
#   - TESTAPLUS — A+ candidate matched by the migration-seeded
#                 "A+ baseline" hypothesis; the just-traded ticker.
#   - TESTPRIOR — already-open position whose candidate row is also in the
#                 latest eval; discriminates "exclude_set built from
#                 request.ticker only" (BUG) vs "post-write list_open_trades"
#                 (CORRECT).
#   - TESTWATCH — watchlist-origin POST sentinel.
#
# These are NEW sentinels (not collision-prone with FOO/BAR/AAPL/NVDA used
# elsewhere in this file).
# ---------------------------------------------------------------------------


def _t5_seed_hyp_recs_aplus_candidate(cfg, *, ticker: str = "TESTAPLUS") -> int:
    """Seed an A+ candidate row in a fresh evaluation_runs row (no
    pipeline_runs row needed — `latest_evaluation_run_id` falls back to the
    most-recent evaluation_runs row when no completed pipeline_run exists,
    which keeps the fixture minimal). Returns the new evaluation_run id.

    Mirrors `_seed_standalone_eval_with_aplus_candidate` from
    tests/web/test_view_models/test_build_hyp_recs_section.py — kept local
    here to avoid cross-package fixture imports.
    """
    from swing.data.db import connect

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T09:00:00", "2026-04-28", "2026-04-29"),
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                (eval_id, ticker),
            )
        return eval_id
    finally:
        conn.close()


def _t5_seed_extra_aplus_candidate(cfg, *, eval_id: int, ticker: str) -> None:
    """Append a second A+ candidate row to an existing evaluation_runs row."""
    from swing.data.db import connect

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                (eval_id, ticker),
            )
    finally:
        conn.close()


def _t5_seed_open_trade(cfg, *, ticker: str) -> None:
    """Seed an existing open trade. Used to test post-write-state exclusion."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=180.0, initial_shares=5, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()


def _t5_patch_pricecache_all(monkeypatch, *, price: float = 180.95):
    """Make PriceCache.get_many return live snapshots for any requested ticker."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=price, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


def test_entry_post_hyp_recs_origin_success_emits_hypothesis_recs_oob_swap(
    seeded_db, monkeypatch,
):
    """Task 5: POST /trades/entry with origin=hyp-recs success → response
    body MUST contain a #hypothesis-recommendations OOB swap section
    rendered through the partial.

    Discriminating: pre-fix the response is just primary-row + status-strip
    OOB + watchlist-top5 OOB; the colocated `id="hypothesis-recommendations"`
    + `hx-swap-oob="true"` marker is absent.
    """
    import re

    cfg, cfg_path = seeded_db
    _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="TESTAPLUS")
    _t5_patch_pricecache_all(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "TESTAPLUS",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
                "origin": "hyp-recs",
            },
        )
    assert r.status_code == 200, (
        f"Expected 200; got {r.status_code}. Body[:500]={r.text[:500]!r}"
    )
    # Pin BOTH the id and the hx-swap-oob attribute on the SAME element
    # via a regex (id and hx-swap-oob can appear in either order, but they
    # must be on the SAME tag — that's the OOB-swap target marker).
    pattern = re.compile(
        r'<section[^>]*\bid="hypothesis-recommendations"[^>]*\bhx-swap-oob="true"'
        r'|<section[^>]*\bhx-swap-oob="true"[^>]*\bid="hypothesis-recommendations"',
        re.IGNORECASE,
    )
    assert pattern.search(r.text), (
        "Response body must contain a <section> tag carrying both "
        "id=\"hypothesis-recommendations\" AND hx-swap-oob=\"true\". "
        f"Body[:1000]={r.text[:1000]!r}"
    )


def test_entry_post_hyp_recs_origin_success_excludes_traded_ticker_from_oob(
    seeded_db, monkeypatch,
):
    """Task 5: the OOB-section's body MUST NOT contain the just-traded
    ticker. The Task 3 `exclude_tickers` kwarg structurally suppresses
    open-position tickers (which now includes TESTAPLUS post-`record_entry`).
    """
    import re

    cfg, cfg_path = seeded_db
    _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="TESTAPLUS")
    _t5_patch_pricecache_all(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "TESTAPLUS",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
                "origin": "hyp-recs",
            },
        )
    assert r.status_code == 200
    # Extract the OOB hyp-recs section block (greedy until next </section>).
    section_match = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"[^>]*>'
        r'(?P<body>.*?)</section>',
        r.text, re.DOTALL | re.IGNORECASE,
    )
    if section_match is None:
        # Try the reverse-attribute order.
        section_match = re.search(
            r'<section[^>]*hx-swap-oob="true"[^>]*id="hypothesis-recommendations"[^>]*>'
            r'(?P<body>.*?)</section>',
            r.text, re.DOTALL | re.IGNORECASE,
        )
    assert section_match is not None, (
        "OOB hyp-recs section not found in response body. "
        f"Body[:1000]={r.text[:1000]!r}"
    )
    section_body = section_match.group("body")
    # The just-traded ticker must NOT appear as a cell value in the OOB
    # rebuild. ">TESTAPLUS<" is the canonical cell-text shape; the row
    # template renders ticker as a plain table cell.
    assert ">TESTAPLUS<" not in section_body, (
        "Just-traded ticker TESTAPLUS leaked into the OOB-section body — "
        "exclude_tickers wiring is broken. "
        f"Section body[:500]={section_body[:500]!r}"
    )


def test_entry_post_hyp_recs_origin_success_exclusion_set_from_post_write_state(
    seeded_db, monkeypatch,
):
    """Codex R1 Major 1 resolution: the exclusion set MUST be sourced from
    POST-WRITE state (i.e., `list_open_trades(conn)` AFTER `record_entry`),
    NOT from `request.ticker` alone.

    Fixture: TESTPRIOR is an existing open position AND a candidate row in
    the latest eval; TESTAPLUS is a candidate row that the operator now
    trades. The OOB chunk MUST exclude BOTH:
      - TESTPRIOR — already-open position (pre-existing).
      - TESTAPLUS — just-traded position (added by `record_entry`).

    Discriminating: a buggy `exclude_tickers={request.ticker}` shortcut
    would let TESTPRIOR leak into the OOB chunk; the correct impl reads
    `list_open_trades(conn)` AFTER `record_entry` so both are filtered.
    """
    import re

    cfg, cfg_path = seeded_db
    eval_id = _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="TESTAPLUS")
    _t5_seed_extra_aplus_candidate(cfg, eval_id=eval_id, ticker="TESTPRIOR")
    _t5_seed_open_trade(cfg, ticker="TESTPRIOR")
    _t5_patch_pricecache_all(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "TESTAPLUS",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
                "origin": "hyp-recs",
            },
        )
    assert r.status_code == 200
    # Extract the OOB section body.
    pattern = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"[^>]*>'
        r'(?P<body>.*?)</section>'
        r'|<section[^>]*hx-swap-oob="true"[^>]*id="hypothesis-recommendations"[^>]*>'
        r'(?P<body2>.*?)</section>',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(r.text)
    assert m is not None, (
        f"OOB hyp-recs section not found. Body[:500]={r.text[:500]!r}"
    )
    section_body = m.group("body") or m.group("body2") or ""
    # Both must be absent — exclusion set sourced from post-write
    # list_open_trades, NOT from request.ticker alone.
    assert ">TESTAPLUS<" not in section_body, (
        "TESTAPLUS (just-traded) leaked into OOB rebuild — "
        "exclude_set should include just-traded ticker via "
        "list_open_trades(conn) AFTER record_entry."
    )
    assert ">TESTPRIOR<" not in section_body, (
        "TESTPRIOR (pre-existing open position) leaked into OOB rebuild — "
        "exclude_set MUST be the full open-positions ticker set (post-write), "
        "not just {request.ticker}. This is the R1 Major 1 discriminator. "
        f"Section body[:1000]={section_body[:1000]!r}"
    )


def test_entry_post_watchlist_origin_success_emits_hyp_recs_oob_swap_for_cross_section_consistency(
    seeded_db, monkeypatch,
):
    """Codex R1 Major 1 (2026-04-29 pure-OOB review): POST origin=watchlist
    success MUST emit the hyp-recs OOB marker pair so the dashboard's
    hyp-recs panel stays consistent with the new open-position state.

    Background. The same ticker can plausibly appear on the watchlist AND
    in the hyp-recs panel simultaneously (both surfaces source from
    candidates + watchlist under the latest eval). Pre-fix, a watchlist-
    origin entry that traded such a ticker updated open-positions +
    watchlist correctly but left the hyp-recs panel STALE — the just-
    traded ticker remained visible in the recommendations table on the
    dashboard until the next interaction. Always-rebuild ensures cross-
    section consistency on every successful entry.

    Discriminator: the OOB chunk uses `oob=True` rendering of the
    hypothesis_recommendations partial, which ALWAYS emits the
    `<section id="hypothesis-recommendations" hx-swap-oob="true">`
    element (populated or hidden+empty per the partial's branches).

    On pages that don't carry the `#hypothesis-recommendations` target
    (e.g., standalone /watchlist), HTMX silently skips the OOB swap —
    emitting the chunk is harmless there. The dashboard is the primary
    consumer; cross-section consistency on the dashboard is the
    invariant under test.
    """
    import re
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="TESTWATCH", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "TESTWATCH",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
                "origin": "watchlist",
            },
        )
    assert r.status_code == 200
    pattern = re.compile(
        r'<section[^>]*\bid="hypothesis-recommendations"[^>]*\bhx-swap-oob="true"'
        r'|<section[^>]*\bhx-swap-oob="true"[^>]*\bid="hypothesis-recommendations"',
        re.IGNORECASE,
    )
    assert pattern.search(r.text) is not None, (
        "Watchlist-origin POST MUST emit the hyp-recs OOB marker pair so "
        "the dashboard's hyp-recs panel rebuilds consistently with the new "
        "open-position state. Without this, watchlist-origin entry of a "
        "ticker that appears in both watchlist AND hyp-recs leaves the "
        "hyp-recs panel STALE on the dashboard. "
        f"Body[:1000]={r.text[:1000]!r}"
    )


def test_entry_post_hyp_recs_origin_error_path_does_not_emit_hyp_recs_oob_swap(
    seeded_db, monkeypatch,
):
    """Task 5 negative: error paths (rationale-validation failure → 400 form
    re-render) MUST NOT carry the OOB marker pair. The OOB swap fires only
    on the success path AFTER `record_entry` persists the new trade.
    """
    import re

    cfg, cfg_path = seeded_db
    _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="TESTAPLUS")
    _t5_patch_pricecache_all(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "TESTAPLUS",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                # Bogus rationale → enum validation fails before record_entry.
                "rationale": "definitely-not-a-real-rationale",
                "origin": "hyp-recs",
            },
        )
    assert r.status_code == 400, (
        f"Expected 400 (rationale enum-validation failure); got "
        f"{r.status_code}. Body[:500]={r.text[:500]!r}"
    )
    pattern = re.compile(
        r'<section[^>]*\bid="hypothesis-recommendations"[^>]*\bhx-swap-oob="true"'
        r'|<section[^>]*\bhx-swap-oob="true"[^>]*\bid="hypothesis-recommendations"',
        re.IGNORECASE,
    )
    assert pattern.search(r.text) is None, (
        "Error-path response must NOT carry the OOB marker pair — the "
        "OOB swap is success-path-only."
    )


# Step 7a: structural-guard pytest (Codex R2 Major 2 + R3 Major 1
# resolution). The hypothesis_recommendations.html.j2 partial is the SOLE
# source of `<section id="hypothesis-recommendations">` markup; entry_post
# must consume it via `templates.get_template(...).render(..., oob=True)`,
# never by hand-duplicating the section element. This guard pins the
# CLAUDE.md "HTMX OOB-swap partial drift" gotcha at the source level.
def test_trades_module_contains_no_literal_hyp_recs_section_markup():
    """Permanent structural guard: swing/web/routes/trades.py source MUST
    NOT contain literal `<section ... id="hypothesis-recommendations"`
    markup. The partial is the SOLE source of that markup — entry_post
    must render it via `templates.get_template(...).render(..., oob=True)`.
    """
    import re
    from pathlib import Path

    import swing.web.routes.trades as trades_module

    source_path = Path(trades_module.__file__)
    source = source_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"',
        re.IGNORECASE,
    )
    matches = pattern.findall(source)
    assert matches == [], (
        f"Found {len(matches)} literal hyp-recs `<section>` tag(s) in "
        f"swing/web/routes/trades.py. The partial is the SOLE source "
        f"of that markup; entry_post must render it via "
        f"`templates.get_template(...).render(..., oob=True)` — never "
        f"hand-duplicate. Matches: {matches!r}"
    )


# ---------------------------------------------------------------------------
# Bug-fix-AB: entry_post response uses pure-OOB architecture (no <tr> primary
# content). Investigation 2026-04-29 confirmed empirically (DevTools capture)
# that a leading <tr id="open-position-..."> in the response triggers HTMX's
# `makeFragment` to wrap the whole response in a synthetic <table><tbody> for
# parsing. HTML5 nested-table parsing rules then DROP the <table>s inside the
# OOB <section id="watchlist-top5"> and <section id="hypothesis-recommendations">
# chunks, leaving the operator with empty section bodies (Bug B). The same
# response architecture also fails to deliver the new row to #open-positions
# (Bug A — primary swap targets `closest tr`, which is in the source tbody,
# not in #open-positions).
#
# Fix: entry_post emits the new open-position row via OOB swap into
# #open-positions (mirroring partials/prices_refresh_container.html.j2's
# pattern), and emits no <tr> at fragment root. Both bugs resolved by one
# architectural change.
# ---------------------------------------------------------------------------


def test_entry_post_response_does_not_lead_with_tr_primary_content(
    seeded_db, monkeypatch,
):
    """Bug A+B fix: response body MUST NOT lead with `<tr id="open-position-`.

    Pre-fix the response leads with `<tr id="open-position-{trade_id}">` as
    primary content; HTMX's `makeFragment` detects the leading <tr> and wraps
    the whole response in a synthetic <table><tbody> for parsing, which
    triggers HTML5 nested-table parse rules that strip <table>s from the OOB
    <section> chunks (DevTools-confirmed mechanism for Bug B).

    Post-fix the response is pure OOB — no <tr> at fragment root.

    Discriminator: the FIRST 80 characters of the response body must NOT
    contain `<tr id="open-position-` (that pattern is the production-bug
    signature that triggers the HTMX fragment-parsing pathology).
    """
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="BUGAB", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "BUGAB",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
                "origin": "watchlist",
            },
        )
    assert r.status_code == 200, (
        f"Got {r.status_code}; body[:500]={r.text[:500]!r}"
    )
    # Body should not start with the bug-signature <tr> primary content.
    # Strip leading whitespace before the check; the response may indent
    # but the first non-whitespace element MUST be an OOB element, never
    # a <tr id="open-position-...">.
    leading = r.text.lstrip()[:80]
    assert "<tr id=\"open-position-" not in leading, (
        "Bug A+B fix regressed: response leads with primary <tr> content. "
        "This triggers HTMX's makeFragment <table>-wrap pathology which "
        "DROPS <table>s from OOB <section> chunks during browser-side "
        "parse (Bug B), AND fails to deliver the new row to #open-positions "
        "(Bug A — primary swap lands in source tbody, not #open-positions). "
        f"Leading body: {leading!r}"
    )


def test_entry_post_response_delivers_new_row_via_open_positions_oob(
    seeded_db, monkeypatch,
):
    """Bug A fix: response MUST contain an OOB swap targeting #open-positions
    that includes the newly-created trade's row. Without this, the new row
    never reaches the open-positions table — only a hard-refresh re-renders
    the dashboard from list_open_trades.

    Discriminator: the response body must contain
    `<div id="open-positions" hx-swap-oob="true">` with the new row's id
    (`open-position-{trade_id}`) inside that div's content.

    Pre-fix the response has NO `id="open-positions"` OOB chunk; the new row
    lives only as primary content (which lands in the source tbody and gets
    nuked by the watchlist/hyp-recs OOB rebuild).

    The OOB target uses the same id (`open-positions`) and template
    (`partials/open_positions.html.j2`) as
    `partials/prices_refresh_container.html.j2` — single source of truth
    per CLAUDE.md "HTMX OOB-swap partial drift" gotcha.
    """
    import re
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="BUGAB", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "BUGAB",
                "entry_date": "2026-04-29",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "aplus-setup",
                "origin": "watchlist",
            },
        )
    assert r.status_code == 200
    # Pin id + hx-swap-oob colocated on the SAME element (either order).
    div_pattern = re.compile(
        r'<div[^>]*\bid="open-positions"[^>]*\bhx-swap-oob="true"'
        r'|<div[^>]*\bhx-swap-oob="true"[^>]*\bid="open-positions"',
        re.IGNORECASE,
    )
    assert div_pattern.search(r.text), (
        "Bug A fix missing: response must contain "
        '`<div id="open-positions" hx-swap-oob="true">` so the new row '
        "actually reaches the open-positions table. Without this OOB "
        "chunk, the new row lives only as primary content which lands in "
        "the source tbody and gets nuked by the watchlist/hyp-recs OOB "
        f"rebuild. Body[:1000]={r.text[:1000]!r}"
    )
    # Extract the OOB div body and verify the new row id is inside it.
    section_match = re.search(
        r'<div[^>]*id="open-positions"[^>]*hx-swap-oob="true"[^>]*>'
        r'(?P<body>.*?)</div>\s*(?:<section|<div|$)',
        r.text, re.DOTALL | re.IGNORECASE,
    )
    if section_match is None:
        section_match = re.search(
            r'<div[^>]*hx-swap-oob="true"[^>]*id="open-positions"[^>]*>'
            r'(?P<body>.*?)</div>\s*(?:<section|<div|$)',
            r.text, re.DOTALL | re.IGNORECASE,
        )
    assert section_match is not None, (
        f"Could not extract #open-positions OOB body. "
        f"Body[:1500]={r.text[:1500]!r}"
    )
    oob_body = section_match.group("body")
    assert "open-position-" in oob_body, (
        "The #open-positions OOB chunk must contain the newly-created "
        "trade's row (`id=\"open-position-{trade_id}\"`). "
        f"OOB body[:500]={oob_body[:500]!r}"
    )
    assert ">BUGAB<" in oob_body, (
        "The #open-positions OOB chunk must contain the new ticker text "
        f"`>BUGAB<`. OOB body[:500]={oob_body[:500]!r}"
    )
