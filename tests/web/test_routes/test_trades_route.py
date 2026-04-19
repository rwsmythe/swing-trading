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
                "rationale": "A+ entry",
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
        "rationale": "5th trade past soft cap",
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
                "initial_stop": "170.0", "rationale": "test",
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
                "initial_stop": "175.0", "rationale": "add-on",
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

    Path-aware handler (R2 Major 1): /trades/* routes use <tr> swap targets,
    so 404s from these paths render trade_form_error.html.j2 (<tr>), not
    http_error_fragment.html.j2 (<div>).
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/99999/exit/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 404
    # Not JSON — HTMX-aware fragment.
    assert "banner" in r.text
    assert "not found" in r.text.lower() or "not open" in r.text.lower()
    # Path-aware handler: /trades/* → <tr>-shaped fragment.
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
                  "shares": "5", "reason": "manual", "rationale": "full close"},
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
                  "shares": "3", "reason": "partial", "rationale": "lock in partial gain"},
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
                  "shares": "10", "reason": "manual",  # over-exit
                  "rationale": "too many"},
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
            data={"new_stop": "912.00", "rationale": "trail to 10MA"},
        )
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    assert "912.00" in r.text
    # Stop-adjust emits NO OOB.
    assert 'id="status-strip"' not in r.text


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
            data={"new_stop": "880.00", "rationale": "attempt lower"},
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
                  "shares": "10", "reason": "manual",
                  "rationale": "too many"},
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
            data={"new_stop": "880.00", "rationale": "attempt lower"},
        )
    assert r.status_code == 400
    # Error message names the actual current_stop.
    assert "900" in r.text
    # Form re-rendered inside the error fragment.
    assert 'name="new_stop"' in r.text
    # Authoritative current_stop prefilled (not the user's regressed 880).
    assert 'value="900.00"' in r.text


def test_post_stop_for_closed_trade_returns_404_fragment(seeded_db):
    """POST /trades/{id}/stop for a missing trade → 404 HTMX <tr> fragment (Major 2).

    adjust_stop raises ValueError when the trade_id is not found; the route
    must catch that and re-raise as HTTPException(404) so the HTMX-aware
    path-aware handler renders trade_form_error.html.j2 (a <tr>) rather than
    http_error_fragment.html.j2 (a <div>), since /trades/* uses <tr> targets.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/99999/stop", headers={"HX-Request": "true"},
            data={"new_stop": "880.00", "rationale": "stale stop"},
        )
    assert r.status_code == 404
    assert "banner" in r.text
    assert "not" in r.text.lower()
    # Path-aware handler (R2 Major 1): /trades/* → <tr>-shaped fragment, not <div>.
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
                "initial_stop": "175.0", "rationale": "add-on attempt",
            },
        )
    assert r.status_code == 400
    # Banner mentions the duplicate.
    assert "already" in r.text.lower() or "open trade" in r.text.lower()
    # Form is re-rendered inside the error fragment.
    assert 'name="ticker"' in r.text
    # Submitted values preserved (R2 Major 2 fix: dataclasses.replace).
    assert "add-on attempt" in r.text          # rationale textarea content
    assert 'value="175.00"' in r.text          # initial_stop echoed back
    assert 'value="182.00"' in r.text          # entry_price echoed back
    # R5 fix: input value reflects user's submitted shares (shares=3 was submitted).
    assert 'name="shares"' in r.text
    assert 'value="3"' in r.text


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
                  "initial_stop": "175.00", "rationale": "drift"},
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
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "900.00", "rationale": "attempt after close"},
        )
    assert r.status_code == 404
    # Path-aware handler (R2 Major 1): /trades/* → <tr>-shaped fragment.
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
                  "initial_stop": "170.0", "rationale": "test"},
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
                  "shares": "10", "reason": "manual",
                  "rationale": "over-exit"},
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
