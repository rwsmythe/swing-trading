"""Trade routes: GET /trades/entry/sizing-hint (tolerant contract) for now."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests.web.conftest import full_phase7_entry_payload


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
            data=full_phase7_entry_payload(
                ticker="AAPL",
                entry_date="2026-04-18",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
            ),
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
                    current_stop=90.0, state="entered",
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
    form_data = full_phase7_entry_payload(
        ticker="AAPL", entry_date="2026-04-18",
        entry_price="180.95", shares="1", initial_stop="170.00",
        rationale="aplus-setup",
    )
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


def _seed_soft_warn_trades_and_watchlist(cfg) -> None:
    """Seed 4 unrelated open trades (= soft_warn_open default) + AAPL
    watchlist row so the (5th) AAPL entry trips the soft-warn cap."""
    from swing.data.db import connect
    from swing.data.models import Trade, WatchlistEntry
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.repos.watchlist import upsert_watchlist_entry
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, t in enumerate(("MSFT", "NVDA", "GOOG", "META")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=t, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, state="entered",
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


def test_post_entry_soft_warn_confirm_round_trips_18_pre_trade_fields(
    seeded_db, monkeypatch,
):
    """Phase 7 Sub-C C.4 follow-up regression. Discriminating: under
    buggy soft-warn confirm (form_values missing the 13+ pre-trade
    fields), the confirm fragment emits no hidden inputs for thesis /
    why_now / etc., a fragment-faithful second POST loses those values,
    and record_entry's MissingPreTradeFieldsException fires (400). Under
    the fix, the confirm fragment carries every operator-typed
    pre-trade field; the second POST persists them and the trade row
    is created (state='entered')."""
    import re
    from datetime import datetime
    from swing.data.db import connect
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    _seed_soft_warn_trades_and_watchlist(cfg)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    form_data = full_phase7_entry_payload(
        ticker="AAPL", entry_date="2026-04-18",
        entry_price="180.95", shares="1", initial_stop="170.00",
        rationale="aplus-setup",
        thesis="round-trip-thesis-marker",
        why_now="round-trip-why-now-marker",
    )
    with TestClient(app) as client:
        # First POST → soft-warn confirm fragment.
        r1 = client.post(
            "/trades/entry", headers={"HX-Request": "true"}, data=form_data,
        )
        assert r1.status_code == 200, r1.text
        assert "Soft cap reached" in r1.text

        # Confirm fragment must emit a hidden input for every pre-trade
        # field. Pin specific markers (thesis, why_now) so the test fails
        # discriminatingly under the bug — pre-fix, those keys would be
        # absent from form_values entirely.
        for name, value in (
            ("thesis", "round-trip-thesis-marker"),
            ("why_now", "round-trip-why-now-marker"),
            ("invalidation_condition", "stop-hit"),
            ("expected_scenario", "win"),
            ("premortem_technical", "tech-risk"),
            ("premortem_market_sector", "market-risk"),
            ("premortem_execution", "execution-risk"),
            ("event_risk_present", "0"),
            ("gap_risk_present", "0"),
            ("manual_entry_confidence", "normal"),
            ("market_regime", "Bullish"),
            ("catalyst", "technical_only"),
        ):
            assert (
                f'name="{name}" value="{value}"' in r1.text
            ), (
                f"soft-warn confirm fragment missing hidden input "
                f'name="{name}" value="{value}"; pre-trade field would '
                f"be lost on the force=true resubmit"
            )

        # Fragment-faithful resubmit: parse server-emitted hidden inputs
        # and POST those (mimicking what a real browser submits when the
        # operator clicks "Submit anyway"). This is the only way to
        # exercise the bug — hand-curating the second POST's payload from
        # the original form_data masks form_values omissions.
        fragment_inputs = re.findall(
            r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
            r1.text,
        )
        # Multi-value list fields (emotional_state_pre_trade) MAY emit
        # multiple inputs; collect as list-of-pairs to preserve repeats.
        second_post_data: dict[str, object] = {}
        for k, v in fragment_inputs:
            if k in second_post_data:
                existing = second_post_data[k]
                if isinstance(existing, list):
                    existing.append(v)
                else:
                    second_post_data[k] = [existing, v]
            else:
                second_post_data[k] = v
        r2 = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data=second_post_data,
        )
        assert r2.status_code == 200, r2.text
        # Success path emits an `open-position-<id>` table row.
        assert "open-position-" in r2.text, (
            "force=true resubmit must succeed (state='entered'); "
            "if 400, MissingPreTradeFieldsException fired → fields lost"
        )

    # Verify pre-trade values persisted correctly.
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT thesis, why_now, market_regime, catalyst "
            "FROM trades WHERE ticker = 'AAPL' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "AAPL trade row must exist after force=true resubmit"
    assert row[0] == "round-trip-thesis-marker", (
        f"thesis must round-trip; got {row[0]!r}"
    )
    assert row[1] == "round-trip-why-now-marker", (
        f"why_now must round-trip; got {row[1]!r}"
    )
    assert row[2] == "Bullish", f"market_regime; got {row[2]!r}"
    assert row[3] == "technical_only", f"catalyst; got {row[3]!r}"


def test_post_entry_soft_warn_confirm_emotional_state_multi_value_round_trips(
    seeded_db, monkeypatch,
):
    """Phase 7 Sub-C C.4 follow-up regression. Discriminating multi-
    select round-trip: emotional_state_pre_trade is a multi-select that
    arrives as a list[str]. If form_values rendered it via plain
    {{ value }} (single hidden input), the second POST would receive
    "['calm', 'focused']" as a single string value → JSON-encoded
    differently than ["calm", "focused"]. The template's list-special-
    case must emit ONE hidden input per element so the fragment-faithful
    resubmit reconstructs the list."""
    import json
    import re
    from datetime import datetime
    from swing.data.db import connect
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    _seed_soft_warn_trades_and_watchlist(cfg)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    form_data = full_phase7_entry_payload(
        ticker="AAPL", entry_date="2026-04-18",
        entry_price="180.95", shares="1", initial_stop="170.00",
        rationale="aplus-setup",
    )
    # Multi-select values: TestClient encodes a list as repeat form keys
    # (matches the HTML `<select multiple>` submission shape).
    form_data["emotional_state_pre_trade"] = ["calm", "focused"]
    with TestClient(app) as client:
        r1 = client.post(
            "/trades/entry", headers={"HX-Request": "true"}, data=form_data,
        )
        assert r1.status_code == 200, r1.text
        assert "Soft cap reached" in r1.text
        # Both vocabulary values must appear as separate hidden inputs.
        assert (
            'name="emotional_state_pre_trade" value="calm"' in r1.text
        ), "first emotional_state value missing from confirm fragment"
        assert (
            'name="emotional_state_pre_trade" value="focused"' in r1.text
        ), "second emotional_state value missing from confirm fragment"
        # Critically, the bug-form rendering ("['calm', 'focused']" as a
        # single value) MUST NOT be present — that would round-trip a
        # malformed single-string token.
        assert (
            "value=\"['calm', 'focused']\"" not in r1.text
            and 'value="[&#39;calm&#39;, &#39;focused&#39;]"' not in r1.text
        ), "list-typed value must NOT render as Python repr"

        # Fragment-faithful resubmit (multi-value preserved).
        pairs = re.findall(
            r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
            r1.text,
        )
        second_post_data: dict[str, object] = {}
        for k, v in pairs:
            if k in second_post_data:
                existing = second_post_data[k]
                if isinstance(existing, list):
                    existing.append(v)
                else:
                    second_post_data[k] = [existing, v]
            else:
                second_post_data[k] = v
        # Defensive: emotional_state_pre_trade should be a 2-element list.
        emo = second_post_data.get("emotional_state_pre_trade")
        assert emo == ["calm", "focused"], (
            f"fragment parsing must yield 2-element list; got {emo!r}"
        )
        r2 = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data=second_post_data,
        )
        assert r2.status_code == 200, r2.text
        assert "open-position-" in r2.text

    # Verify persisted JSON list.
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT emotional_state_pre_trade FROM trades "
            "WHERE ticker = 'AAPL' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    persisted = json.loads(row[0])
    assert persisted == ["calm", "focused"], (
        f"persisted emotional_state must be 2-element JSON list; got {persisted!r}"
    )


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
                    current_stop=90.0, state="entered",
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
            data=full_phase7_entry_payload(
                ticker="AAPL", entry_date="2026-04-18",
                entry_price="180.0", shares="1",
                initial_stop="170.0", rationale="aplus-setup",
                force="true",   # bypass soft-warn; but hard cap still blocks
            ),
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
                current_stop=170.0, state="entered",
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
            data=full_phase7_entry_payload(
                ticker="AAPL", entry_date="2026-04-18",
                entry_price="182.0", shares="3",
                initial_stop="175.0", rationale="aplus-setup",
            ),
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
    # Remaining shares: 10 - 3 = 7. Phase 7 fills.quantity is REAL, so
    # the displayed value is "7.0 / 10".
    assert "7 / 10" in r.text or "7.0 / 10" in r.text or ">7<" in r.text


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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=900.0, state="entered",  # someone already trailed to BE
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=900.0, state="entered",
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
                current_stop=170.0, state="entered",
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
            data=full_phase7_entry_payload(
                ticker="AAPL", entry_date="2026-04-18",
                entry_price="182.0", shares="3",
                initial_stop="175.0", rationale="aplus-setup",
            ),
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
            data=full_phase7_entry_payload(
                ticker="AAPL",
                entry_date="2026-04-18",
                entry_price="170.00",
                shares="5",
                initial_stop="170.00",  # stop == entry → ValueError pre-fix
                rationale="aplus-setup",
            ),
        )
    # Pre-fix this is 500; post-fix it must be 400 (validation failure shape
    # mirroring DuplicateOpenPositionError).
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
            data=full_phase7_entry_payload(
                ticker="AAPL",
                entry_date="2026-04-18",
                entry_price="170.00",
                shares="5",
                initial_stop="175.00",  # stop > entry
                rationale="aplus-setup",
            ),
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
            data=full_phase7_entry_payload(
                ticker="AAPL",
                entry_date="2026-04-18",
                entry_price="180.00",
                shares="5",
                initial_stop="170.00",   # valid (entry > stop) — passes pre-check
                rationale="aplus-setup",
            ),
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
                current_stop=170.0, state="entered",
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
            data=full_phase7_entry_payload(ticker="AAPL", entry_date="2026-04-18",
                  entry_price="182.00", shares="9999",
                  initial_stop="175.00", rationale="aplus-setup"),
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
                current_stop=860.0, state="entered",
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
            data=full_phase7_entry_payload(ticker="AAPL", entry_date="2026-04-18",
                  entry_price="180.0", shares="1",
                  initial_stop="170.0", rationale="aplus-setup"),
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
                current_stop=860.0, state="entered",
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
            data=full_phase7_entry_payload(
                ticker="AAPL", entry_date="2026-04-18",
                entry_price="180.95", shares="5",
                initial_stop="170.00",
                rationale="VCP entry",       # pre-T4 free-text phrasing
                notes="Keep this on re-render",
            ),
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
    payload = full_phase7_entry_payload(
        ticker="AAPL", entry_date="2026-04-18",
        entry_price="180.95", shares="5",
        initial_stop="170.00",
        rationale="other",
    )
    # Test discriminates the "rationale=other ⇒ notes required" guard;
    # remove the helper's default notes value to trigger it.
    del payload["notes"]
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data=payload,
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
            data=full_phase7_entry_payload(
                ticker="AAPL", entry_date="2026-04-18",
                entry_price="180.95", shares="5",
                initial_stop="170.00",
                rationale="other",
                notes="post-earnings gap with high ADR",
            ),
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=890.0, state="entered",
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
                current_stop=890.0, state="entered",
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
                current_stop=860.0, state="entered",
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
                current_stop=170.0, state="entered",
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
            data=full_phase7_entry_payload(
                ticker="TESTAPLUS",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
                origin="hyp-recs",
            ),
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
            data=full_phase7_entry_payload(
                ticker="TESTAPLUS",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
                origin="hyp-recs",
            ),
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
            data=full_phase7_entry_payload(
                ticker="TESTAPLUS",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
                origin="hyp-recs",
            ),
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

    Codex R2 Minor 1 (2026-04-29): the marker-presence assertion alone is
    insufficient — a regression could emit an OOB hyp-recs section while
    leaving the just-traded ticker stale inside it. Strengthened by
    seeding the just-traded ticker AS BOTH a watchlist row AND an A+
    candidate (so it would naturally surface in hyp-recs); plus a
    witness candidate (`TESTWITNESS`) that's NOT being traded. The OOB
    section body must contain `>TESTWITNESS<` (witness) and must NOT
    contain `>TESTWATCH<` (just-traded ticker excluded post-write).

    Background. The same ticker can plausibly appear on the watchlist AND
    in the hyp-recs panel simultaneously (both surfaces source from
    candidates + watchlist under the latest eval). Pre-fix, a watchlist-
    origin entry that traded such a ticker updated open-positions +
    watchlist correctly but left the hyp-recs panel STALE — the just-
    traded ticker remained visible in the recommendations table on the
    dashboard until the next interaction. Always-rebuild ensures cross-
    section consistency on every successful entry.

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
    # Seed the watchlist row + the same ticker AND a witness as A+
    # candidates so the matcher would surface BOTH in hyp-recs absent
    # exclusion. Post-write, the just-traded ticker must be excluded;
    # the witness must remain.
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
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 2, 2, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T09:00:00", "2026-04-28", "2026-04-29"),
            )
            eval_id = int(cur.lastrowid)
            for ticker in ("TESTWATCH", "TESTWITNESS"):
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, rs_method)
                       VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                    (eval_id, ticker),
                )
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
            data=full_phase7_entry_payload(
                ticker="TESTWATCH",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
                origin="watchlist",
            ),
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
        "open-position state. "
        f"Body[:1000]={r.text[:1000]!r}"
    )
    # Extract the OOB section body and assert the semantic invariant:
    # witness present, just-traded ticker absent.
    section_match = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"[^>]*>'
        r'(?P<body>.*?)</section>',
        r.text, re.DOTALL | re.IGNORECASE,
    )
    if section_match is None:
        section_match = re.search(
            r'<section[^>]*hx-swap-oob="true"[^>]*id="hypothesis-recommendations"[^>]*>'
            r'(?P<body>.*?)</section>',
            r.text, re.DOTALL | re.IGNORECASE,
        )
    assert section_match is not None, (
        f"OOB hyp-recs section not found. Body[:1500]={r.text[:1500]!r}"
    )
    section_body = section_match.group("body")
    assert ">TESTWITNESS<" in section_body, (
        "TESTWITNESS (untraded A+ candidate) must appear in the OOB "
        "rebuild — without it, the test is vacuous (an empty hyp-recs "
        "section would trivially satisfy the just-traded-absence "
        f"assertion). Section body[:500]={section_body[:500]!r}"
    )
    assert ">TESTWATCH<" not in section_body, (
        "TESTWATCH (just-traded) must NOT leak into the OOB rebuild on "
        "watchlist-origin entry. The exclusion set on the watchlist-"
        "origin success path must include the just-traded ticker even "
        "though origin != 'hyp-recs'. "
        f"Section body[:500]={section_body[:500]!r}"
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
            data=full_phase7_entry_payload(
                ticker="TESTAPLUS",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                # Bogus rationale → enum validation fails before record_entry.
                rationale="definitely-not-a-real-rationale",
                origin="hyp-recs",
            ),
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
            data=full_phase7_entry_payload(
                ticker="BUGAB",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
                origin="watchlist",
            ),
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
            data=full_phase7_entry_payload(
                ticker="BUGAB",
                entry_date="2026-04-29",
                entry_price="180.95",
                shares="5",
                initial_stop="170.00",
                rationale="aplus-setup",
                origin="watchlist",
            ),
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
    # Phase 7: ticker cell now contains a trailing state-badge span, so
    # the cell renders as `<td>BUGAB <span class="state-badge...">...`.
    # Assert the ticker appears in the cell — the state-badge introduction
    # broke the literal `>BUGAB<` match without changing intent.
    assert ">BUGAB" in oob_body, (
        "The #open-positions OOB chunk must contain the new ticker text "
        f"`>BUGAB`. OOB body[:500]={oob_body[:500]!r}"
    )


# Phase 4.5 — hypothesis_label template render tests.

def _seed_aplus_pipeline_for_route_test(db_path, ticker: str) -> None:
    """Same seed pattern as tests/web/test_view_models/test_trade_entry_form_hypothesis.py."""
    from swing.data.db import connect
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def test_entry_form_renders_exact_hypothesis_label_in_hidden_input(
    seeded_db, monkeypatch,
):
    """Discriminating (per Codex R1 Major 3): GET /trades/entry/form?ticker=AAPL
    renders the hypothesis_label hidden input with EXACTLY the matcher's
    canonical output `"A+ baseline (aplus)"` — full label string, not
    a prefix.

    Sanity: if the template row is missing entirely, the hidden-input
    substring assertion fails. If the template emits the wrong field
    (e.g. `vm.hypothesis_label_short` if such a field were ever added),
    the exact-value substring fails.
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline_for_route_test(cfg.paths.db_path, ticker="AAPL")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    assert r.status_code == 200
    assert 'name="hypothesis_label"' in r.text, (
        "template must render the hypothesis_label hidden input"
    )
    # Exact-value substring assertion. The matcher emits
    # "A+ baseline (aplus)" verbatim for the seed fixture; the template
    # must emit it verbatim into the hidden-input value attribute.
    assert 'name="hypothesis_label" value="A+ baseline (aplus)"' in r.text, (
        "hidden input must carry exact matcher label "
        f'"A+ baseline (aplus)"; response excerpt: {r.text[:500]!r}'
    )
    # Visible read-only display row also carries the exact label.
    assert ">A+ baseline (aplus)<" in r.text, (
        "visible display row must show the exact matcher label "
        "(in a span between > and <)"
    )


def test_entry_form_renders_none_display_when_label_unresolved(
    seeded_db, monkeypatch,
):
    """Degenerate: GET form for a ticker with no candidate row renders
    `(none)` in the read-only display + an empty value="" hidden input.

    Sanity: if the template uses `vm.hypothesis_label` directly without
    the `or "(none)"` filter, this assertion would fail (Jinja would
    emit `None`-as-empty-string, not the literal `(none)` token).
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    # No candidate seeded for ZZZ — vm.hypothesis_label resolves to None.
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=ZZZ")
    assert r.status_code == 200
    assert 'name="hypothesis_label"' in r.text
    # Empty hidden-input value when label is None.
    assert 'name="hypothesis_label" value=""' in r.text, (
        "unresolved label must produce empty hidden-input value"
    )
    # Visible read-only display falls back to "(none)".
    assert "(none)" in r.text, (
        "template must render (none) display when vm.hypothesis_label is None"
    )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.3 — entry route handles 18 pre-trade fields + gate rejection.
#
# Plan §6 C.3. The route accepts 18 new Form() parameters covering the spec
# §1 / §3.5.1 pre-trade required fields. POSTs supplying all 18 succeed via
# the existing OOB-swap pattern; POSTs missing any required field raise
# MissingPreTradeFieldsException at the service layer and the catch path
# re-renders a 400 row-shaped error fragment naming the missing fields
# (instead of escaping as a generic 500). Nullable+CHECK columns persist
# NULL (not "") via `... or None` per CLAUDE.md gotcha 2026-05-04.
# ---------------------------------------------------------------------------


def _c3_seed_watchlist(cfg, *, ticker: str) -> None:
    """Helper: seed an active watchlist row so build_entry_form_vm + the
    record_entry watchlist-archive branch both have something to read."""
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=ticker, added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()


def _c3_all_18_fields(*, ticker: str) -> dict:
    """Return a POST data dict for /trades/entry that satisfies all 18 Phase
    7 pre-trade required fields. Tests parameterize off this via dict
    update/pop to construct discriminating payloads.

    event_risk_present=0 / gap_risk_present=0 keep the conditional rules
    inert (no event_handling/event_type/event_date/gap_risk_handling
    required); catalyst='technical_only' keeps the catalyst-other gate inert.
    """
    return {
        "ticker": ticker,
        "entry_date": "2026-04-29",
        "entry_price": "180.95",
        "shares": "5",
        "initial_stop": "170.00",
        "rationale": "aplus-setup",
        # 18 pre-trade fields:
        "thesis": "Trend continuation post-VCP base.",
        "why_now": "Volume contraction tightening; pivot just cleared.",
        "invalidation_condition": "Close below initial stop ends thesis.",
        "expected_scenario": "+15% target over 4-6 weeks.",
        "premortem_technical": "False breakout / shakeout below pivot.",
        "premortem_market_sector": "Sector rotation away from tech.",
        "premortem_execution": "Slippage on thin pre-market fill.",
        "premortem_additional": "",  # optional
        "event_risk_present": "0",
        "gap_risk_present": "0",
        "emotional_state_pre_trade": "calm",
        "manual_entry_confidence": "normal",
        "market_regime": "Bullish",
        "catalyst": "technical_only",
    }


def _c3_patch_pricecache(monkeypatch, *, price: float = 180.95) -> None:
    """Monkeypatch PriceCache so tests don't hit yfinance."""
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


def test_entry_post_with_all_18_pre_trade_fields_creates_trade(
    seeded_db, monkeypatch,
):
    """C.3: POST with all 18 pre-trade fields populated → success.

    Discriminating: pre-C.3 the route did not pass the 18 fields to
    EntryRequest, so record_entry's MissingPreTradeFieldsException would
    fire even when the form supplied them — silent field drop. Post-fix
    the trade row persists with state='entered' AND the pre-trade columns
    populated AS-IS.
    """
    from swing.data.db import connect

    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3OK")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=_c3_all_18_fields(ticker="C3OK"),
        )
    assert r.status_code == 200, (
        f"happy path must succeed (200 OOB-swap response). Got "
        f"{r.status_code}: {r.text[:300]!r}"
    )
    # Trade row created with state='entered' (not legacy 'managing').
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT state, thesis, market_regime, catalyst, "
            "       event_risk_present, gap_risk_present "
            "FROM trades WHERE ticker = ?",
            ("C3OK",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "trade row must exist after successful POST"
    assert row[0] == "entered", (
        f"freshly recorded Phase 7 trade must persist state='entered'; "
        f"got {row[0]!r}. Sub-A's legacy-data shim defaults legacy "
        f"unmigrated rows to 'managing' — but record_entry's atomic "
        f"INSERT path must persist 'entered'."
    )
    # Pre-trade fields persisted AS-IS (not silently dropped).
    assert row[1] == "Trend continuation post-VCP base."
    assert row[2] == "Bullish"
    assert row[3] == "technical_only"
    assert row[4] == 0
    assert row[5] == 0


def test_entry_post_missing_thesis_returns_400_with_field_name(
    seeded_db, monkeypatch,
):
    """C.3 gate-rejection: POST missing thesis → 400 + error names 'thesis'.

    Discriminating: under buggy code (no MissingPreTradeFieldsException
    catch), the exception escapes to the global 500 handler — status_code
    would be 500, not 400. Post-fix: 400 + the missing-field name appears
    in the rendered banner.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3MISS")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C3MISS")
    data.pop("thesis")  # deliberately omit a required field

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 400, (
        f"missing required field must yield 400 (not 500 from uncaught "
        f"exception). Got {r.status_code}: {r.text[:300]!r}"
    )
    assert "thesis" in r.text, (
        "error banner must name the missing field 'thesis' so the "
        "operator knows what to fix"
    )
    assert "missing required pre-trade fields" in r.text.lower(), (
        "banner must use the canonical missing-fields message format"
    )


def test_entry_post_event_handling_empty_string_persists_null(
    seeded_db, monkeypatch,
):
    """C.3 `... or None` discriminating test for nullable+CHECK columns.

    CLAUDE.md gotcha 2026-05-04: form-input fallback for a nullable
    column with a CHECK enum constraint must use `... or None`, NOT
    `... or ""` — empty string is rejected by the CHECK at INSERT time
    (sqlite3.IntegrityError → 500); NULL is accepted.

    Setup: event_risk_present=0 (no event present), so the conditional
    rule does NOT require event_handling. The form posts an empty
    'event_handling' input (typical browser behavior for an unfilled
    nullable text input). Buggy code (`event_handling or ""`) would
    INSERT '' which trips the CHECK enum and 500s. Correct code
    (`event_handling or None`) persists NULL.

    Post-fix expectation: 200 + persisted column IS NULL.
    """
    from swing.data.db import connect

    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3NULL")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C3NULL")
    data["event_handling"] = ""  # empty form input on a nullable+CHECK col
    data["event_type"] = ""
    data["event_date"] = ""
    data["gap_risk_handling"] = ""

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 200, (
        f"empty nullable+CHECK form input must persist NULL (not '') so "
        f"the CHECK enum doesn't fail. Got {r.status_code}: "
        f"{r.text[:300]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT event_handling, event_type, event_date, gap_risk_handling "
            "FROM trades WHERE ticker = ?",
            ("C3NULL",),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None, f"event_handling must persist NULL, got {row[0]!r}"
    assert row[1] is None, f"event_type must persist NULL, got {row[1]!r}"
    assert row[2] is None, f"event_date must persist NULL, got {row[2]!r}"
    assert row[3] is None, (
        f"gap_risk_handling must persist NULL, got {row[3]!r}"
    )


def test_entry_post_catalyst_other_description_empty_persists_null(
    seeded_db, monkeypatch,
):
    """C.3 sibling discriminating test: free-text companion field also
    persists NULL (not '') from an empty form input.

    catalyst_other_description has no CHECK enum (free text), but the
    persistence-shape contract is the same: empty input → NULL row, not
    empty-string row. Otherwise the conditional rule
    `catalyst='other' → catalyst_other_description required` would
    silently accept '' as 'present' on a future tightening.
    """
    from swing.data.db import connect

    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3CDN")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C3CDN")
    # catalyst != 'other' so no requirement; form input still posts as ''.
    data["catalyst_other_description"] = ""

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 200, (
        f"happy path with empty free-text field must succeed; got "
        f"{r.status_code}: {r.text[:300]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT catalyst_other_description FROM trades WHERE ticker = ?",
            ("C3CDN",),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None, (
        f"catalyst_other_description must persist NULL (not ''), got "
        f"{row[0]!r}"
    )


def test_entry_post_missing_multiple_fields_lists_all_in_banner(
    seeded_db, monkeypatch,
):
    """C.3: when multiple fields are missing, the error banner names ALL
    of them (not just the first). Discriminating: a buggy implementation
    that returned only `exc.missing_fields[0]` would pass thesis-only
    tests but fail this one.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3MULTI")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C3MULTI")
    data.pop("thesis")
    data.pop("why_now")
    data.pop("market_regime")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 400
    body_lower = r.text.lower()
    for field in ("thesis", "why_now", "market_regime"):
        assert field in body_lower, (
            f"banner must name missing field {field!r}; got {r.text[:500]!r}"
        )


def test_entry_post_event_risk_present_1_requires_event_handling(
    seeded_db, monkeypatch,
):
    """C.3 conditional rule: event_risk_present=1 promotes event_handling,
    event_type, event_date to required. Submitting event_risk_present=1
    with empty event_* fields → 400 listing the conditionally-required
    deps (validator's _CONDITIONAL_FIELD_RULES).

    Discriminating: a buggy route that swallowed the conditional gate
    (only checked the always-required set) would 200 here while
    persisting state='entered' with NULL event_handling — silently
    accepting an event-present trade with no event-handling plan.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3EVT")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C3EVT")
    data["event_risk_present"] = "1"
    # Leave event_handling / event_type / event_date as ''.
    data["event_handling"] = ""
    data["event_type"] = ""
    data["event_date"] = ""

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 400, (
        f"event_risk_present=1 with missing event_* fields must be "
        f"rejected. Got {r.status_code}: {r.text[:300]!r}"
    )
    body_lower = r.text.lower()
    assert "event_handling" in body_lower
    assert "event_type" in body_lower
    assert "event_date" in body_lower


def test_entry_post_emotional_state_multi_select_persists_json_list(
    seeded_db, monkeypatch,
):
    """C.3: emotional_state_pre_trade is a multi-select (HTML
    `<select multiple>`); the route receives it as a list and JSON-
    encodes for persistence. Matches the CLI shape (swing/cli.py uses
    `_json.dumps(list(emotional_state))`).

    Discriminating: a buggy route that posted only the first value (or
    just the comma-joined string) would persist
    '"calm"' or '"calm,confident"' instead of '["calm","confident"]'.
    """
    import json
    from swing.data.db import connect

    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C3EMO")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C3EMO")
    # Replace the single-value default with a list; httpx serializes
    # list values as repeated form keys, which FastAPI binds to
    # `list[str] | None = Form(None)`.
    data["emotional_state_pre_trade"] = ["calm", "confident"]

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 200, (
        f"multi-select happy path must succeed; got {r.status_code}: "
        f"{r.text[:300]!r}"
    )
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT emotional_state_pre_trade FROM trades WHERE ticker = ?",
            ("C3EMO",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    persisted = json.loads(row[0])
    assert persisted == ["calm", "confident"], (
        f"multi-select values must persist as JSON list, got {row[0]!r}"
    )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.4 — entry form 7 sectioned <fieldset> blocks + per-field
# error markers + draft preservation. Spec §11.1.
#
# Discriminating-test discipline: each test must FAIL on the pre-C.4
# template (single un-sectioned form, no per-field error class plumbing,
# no `draft_*` preservation for the 18 pre-trade fields). PASS on the
# post-C.4 template.
# ---------------------------------------------------------------------------


def test_c4_entry_form_renders_7_fieldset_legends(seeded_db, monkeypatch):
    """All 7 spec §11.1 section legends must appear in the rendered form."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4LG")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4LG")
    assert r.status_code == 200
    text = r.text
    for legend in (
        "Position basics",
        "Setup attribution",
        "Pre-trade thesis",
        "Premortem",
        "Risk acknowledgments",
        "Operator state",
        "Notes",
    ):
        assert legend in text, (
            f"Missing fieldset legend {legend!r} in rendered entry form. "
            f"Spec §11.1 requires 7 sectioned blocks."
        )


def test_c4_entry_form_thesis_textarea_in_section_3(seeded_db, monkeypatch):
    """`name='thesis'` textarea must appear AFTER 'Pre-trade thesis' legend
    AND BEFORE 'Premortem' legend (i.e., located in section §3)."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4SEC")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4SEC")
    text = r.text
    legend_pos = text.find("Pre-trade thesis")
    thesis_pos = text.find('name="thesis"')
    premortem_pos = text.find("Premortem")
    assert legend_pos != -1
    assert thesis_pos != -1
    assert premortem_pos != -1
    assert legend_pos < thesis_pos < premortem_pos, (
        f"`name='thesis'` must render inside section §3 (after 'Pre-trade "
        f"thesis' legend, before 'Premortem' legend). Got positions: "
        f"legend={legend_pos}, thesis={thesis_pos}, premortem={premortem_pos}"
    )


def test_c4_entry_form_premortem_renders_all_4_textareas(
    seeded_db, monkeypatch,
):
    """§4 Premortem fieldset renders all 4 textareas (3 required + 1 optional)."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4PM")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4PM")
    text = r.text
    for name in (
        "premortem_technical", "premortem_market_sector",
        "premortem_execution", "premortem_additional",
    ):
        assert f'name="{name}"' in text, (
            f"§4 Premortem section must render `name={name!r}` textarea"
        )


def test_c4_entry_form_event_risk_radios_and_handling_select(
    seeded_db, monkeypatch,
):
    """§5 Risk acknowledgments: event_risk_present No/Yes radios +
    event_handling/event_type/event_date inputs render."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4RSK")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4RSK")
    text = r.text
    # event_risk_present rendered as radio with value="0" and value="1":
    assert text.count('name="event_risk_present"') == 2, (
        "event_risk_present must be rendered as a No/Yes radio pair "
        "(2 inputs); bare-checkbox semantics collide with the "
        "validator's required-field check."
    )
    assert 'name="event_risk_present" value="0"' in text
    assert 'name="event_risk_present" value="1"' in text
    # gap_risk_present same shape:
    assert text.count('name="gap_risk_present"') == 2
    assert 'name="event_handling"' in text
    assert 'name="event_type"' in text
    assert 'name="event_date"' in text
    assert 'name="gap_risk_handling"' in text


def test_c4_entry_form_emotional_state_8_checkboxes(seeded_db, monkeypatch):
    """§6 Operator state — emotional_state_pre_trade vocabulary has 8
    values per spec §1.2 (calm/confident/anxious/fomo/revenge/hopeful/
    doubtful/distracted)."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4EMO")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4EMO")
    text = r.text
    assert text.count('name="emotional_state_pre_trade"') == 8, (
        f"emotional_state_pre_trade must render 8 checkboxes (one per "
        f"vocabulary value). Got {text.count('name=\"emotional_state_pre_trade\"')}."
    )
    for value in (
        "calm", "confident", "anxious", "fomo",
        "revenge", "hopeful", "doubtful", "distracted",
    ):
        assert f'value="{value}"' in text, (
            f"emotional_state vocabulary value {value!r} missing from form"
        )


def test_c4_entry_form_manual_entry_confidence_3_radios(
    seeded_db, monkeypatch,
):
    """§6 Operator state — manual_entry_confidence is 3-radio (high/normal/low)."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4MEC")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4MEC")
    text = r.text
    assert text.count('name="manual_entry_confidence"') == 3
    for value in ("high", "normal", "low"):
        # Radio rendered with type=radio + value="high"/"normal"/"low":
        assert (
            f'name="manual_entry_confidence" value="{value}"' in text
        ), f"manual_entry_confidence radio for {value!r} missing"


def test_c4_entry_form_market_regime_3_radios(seeded_db, monkeypatch):
    """§6 Operator state — market_regime 3 radios (Bullish/Caution/Bearish)."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4MR")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4MR")
    text = r.text
    assert text.count('name="market_regime"') == 3
    for value in ("Bullish", "Caution", "Bearish"):
        assert (
            f'name="market_regime" value="{value}"' in text
        ), f"market_regime radio for {value!r} missing"


def test_c4_entry_form_catalyst_select_9_options(seeded_db, monkeypatch):
    """§6 Operator state — catalyst <select> has 9 vocabulary options
    matching the migration 0014 CHECK enum."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4CAT")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4CAT")
    text = r.text
    # Vocabulary per migration 0014:
    for value in (
        "earnings_driven", "guidance_change", "corporate_action",
        "sector_rotation", "macro_event", "sympathy_move",
        "product_news", "technical_only", "other",
    ):
        assert f'value="{value}"' in text, (
            f"catalyst vocabulary value {value!r} missing from <select>. "
            f"Vocabulary must match migration 0014 CHECK enum."
        )


def test_c4_entry_form_includes_hx_headers_attribute(seeded_db, monkeypatch):
    """CLAUDE.md gotcha 2026-05-02: HTMX form inside fragment MUST emit
    `hx-headers='{"HX-Request": "true"}'` so OriginGuard strict-mode
    accepts the form's POST. TestClient cannot detect a regression here
    because tests pass HX-Request explicitly; this assertion guards the
    operator-witnessed browser path."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4HXH")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C4HXH")
    text = r.text
    assert "hx-headers=" in text, (
        "form must emit hx-headers attribute (CLAUDE.md gotcha 2026-05-02)"
    )
    assert '"HX-Request"' in text
    assert '"true"' in text


def test_c4_entry_form_post_missing_thesis_marks_field_with_error_class(
    seeded_db, monkeypatch,
):
    """Discriminating: pre-C.4 the MissingPreTradeFieldsException catch
    rendered `partials/trade_form_error.html.j2` (banner-only); the form
    didn't re-render at all so no per-field error class could exist.
    Post-C.4 the catch path re-renders the full form template with
    `vm.missing_fields` populated; the thesis textarea carries
    `class="field-error"`.
    """
    import re
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4ERR")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C4ERR")
    data.pop("thesis")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 400
    text = r.text
    # Locate the thesis textarea opening tag:
    m = re.search(r'<textarea[^>]*name="thesis"[^>]*>', text)
    assert m is not None, (
        f"thesis textarea not found in re-rendered form. Got: {text[:600]!r}"
    )
    tag = m.group(0)
    assert 'class="field-error"' in tag, (
        f"Missing-thesis re-render must mark the thesis textarea with "
        f"class='field-error'; got opening tag {tag!r}. Pre-C.4 the catch "
        f"path returned a banner-only fragment with no form to mark — this "
        f"test fails on that pre-state."
    )


def test_c4_entry_form_post_missing_thesis_preserves_typed_why_now(
    seeded_db, monkeypatch,
):
    """Discriminating: pre-C.4 the catch path returned the banner-only
    fragment, losing every typed field. Post-C.4 the operator's typed
    why_now value round-trips back into the textarea body via
    `vm.draft_why_now`."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4DRFT")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C4DRFT")
    data.pop("thesis")
    sentinel = "OPERATOR_TYPED_WHY_NOW_REASON_C4"
    data["why_now"] = sentinel

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 400
    assert sentinel in r.text, (
        f"why_now value {sentinel!r} must round-trip back into the "
        f"re-rendered form via draft_why_now preservation; got "
        f"text not containing sentinel"
    )


def test_c4_entry_form_post_missing_thesis_preserves_catalyst_select(
    seeded_db, monkeypatch,
):
    """Draft preservation for `<select name='catalyst'>` — selected option
    must round-trip via the `selected` attribute. Discriminating: a buggy
    implementation that only preserved textarea bodies would lose the
    catalyst selection (the operator would have to re-pick).
    """
    import re
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C4CATD")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C4CATD")
    data["catalyst"] = "earnings_driven"  # operator picked something specific
    data.pop("thesis")  # trip the gate

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data=data,
        )
    assert r.status_code == 400
    text = r.text
    # Match the <option value="earnings_driven" selected>...</option>:
    m = re.search(
        r'<option\s+value="earnings_driven"[^>]*\bselected\b',
        text,
    )
    assert m is not None, (
        f"catalyst='earnings_driven' must round-trip as <option ... selected> "
        f"on re-render; not found. Pre-C.4 (banner-only re-render) had no "
        f"<select> at all — test discriminates."
    )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.5 — GET /trades/{trade_id} canonical trade-detail page.
# ---------------------------------------------------------------------------


def _c5_seed_phase7_trade(
    cfg, *, ticker: str, state: str = "entered",
    premortem_technical: str | None = "False breakout below pivot.",
    thesis: str = "Trend continuation post-VCP base.",
    market_regime: str = "Bullish",
    catalyst: str = "technical_only",
    trade_origin: str = "pipeline_watch_manual",
    pre_trade_locked_at: str = "2026-04-15T16:00:00",
) -> int:
    """Seed a Phase 7 trade with the 18 pre-trade fields populated.

    Bypasses ``record_entry`` because that path requires PriceCache and a
    watchlist row; tests just need a row in the ``trades`` table for the
    GET route to render. Returns the new trade_id.
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=90.0,
                current_stop=90.0, state=state,
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin=trade_origin,
                pre_trade_locked_at=pre_trade_locked_at,
                current_size=10.0,
                thesis=thesis,
                why_now="Volume contraction tightening.",
                invalidation_condition="Close below initial stop ends thesis.",
                expected_scenario="+15% target over 4-6 weeks.",
                premortem_technical=premortem_technical,
                premortem_market_sector="Sector rotation.",
                premortem_execution="Slippage on thin pre-market fill.",
                event_risk_present=0,
                gap_risk_present=0,
                emotional_state_pre_trade='["calm"]',
                market_regime=market_regime,
                catalyst=catalyst,
            ), event_ts="2026-04-15T16:00:00")
    finally:
        conn.close()
    return tid


def _c5_seed_legacy_trade(
    cfg, *, ticker: str, state: str = "entered",
) -> int:
    """Seed a legacy (pre-Phase-7) trade where the 18 pre-trade fields are
    NULL. Discriminating: spec §11.4 requires the Pre-Trade Decision section
    to be HIDDEN on legacy rows.
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

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
                # All 18 pre-trade fields default to None on the dataclass —
                # leaving them unset persists NULL in the trades row.
            ), event_ts="2026-04-15T16:00:00")
    finally:
        conn.close()
    return tid


def test_c5_trade_detail_route_renders_for_existing_trade(seeded_db):
    """GET /trades/{id} → 200 + ticker shown."""
    cfg, cfg_path = seeded_db
    tid = _c5_seed_phase7_trade(cfg, ticker="C5OK")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    assert r.status_code == 200, (
        f"GET /trades/{tid} must return 200; got {r.status_code}: "
        f"{r.text[:300]!r}"
    )
    assert "C5OK" in r.text
    # Trade #N header must appear:
    assert f"#{tid}" in r.text


def test_c5_trade_detail_route_404_for_nonexistent(seeded_db):
    """Unknown trade_id → 404 (not 500)."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/99999")
    assert r.status_code == 404


def test_c5_trade_detail_shows_pre_trade_section_for_phase7_trade(seeded_db):
    """premortem_technical IS NOT NULL → Pre-Trade Decision section RENDERED.

    Discriminating: pre-C.5 the route + template don't exist; even if a
    bare summary page were stubbed without the {% if has_pre_trade_data %}
    guard for an empty section, this test would still fail because the
    template must echo the operator's typed thesis and lock indicator.
    """
    cfg, cfg_path = seeded_db
    tid = _c5_seed_phase7_trade(
        cfg, ticker="C5PT",
        thesis="my-thesis-text-C5",
        premortem_technical="risk-A",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    assert r.status_code == 200
    text = r.text
    assert "Pre-Trade Decision" in text
    assert "my-thesis-text-C5" in text
    # Lock indicator (icon entity OR text):
    assert "&#128274;" in text or "Locked at" in text


def test_c5_trade_detail_hides_pre_trade_section_for_legacy_null(seeded_db):
    """Spec §11.4: premortem_technical IS NULL → section HIDDEN entirely.

    Discriminating: legacy trades pre-Phase-7 have NULL premortem_technical
    and the operator should NOT see an empty/placeholder section. Under a
    buggy template (no {% if vm.has_pre_trade_data %} guard), the section
    would render with empty <dd> elements and "Pre-Trade Decision" would
    appear in the response.
    """
    cfg, cfg_path = seeded_db
    tid = _c5_seed_legacy_trade(cfg, ticker="C5LEG")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    assert r.status_code == 200
    text = r.text
    assert "Pre-Trade Decision" not in text, (
        "Legacy trade (premortem_technical IS NULL) must HIDE the "
        "Pre-Trade Decision section entirely (spec §11.4). Found the "
        "section heading in response — has_pre_trade_data guard missing "
        "or bypassed."
    )


def test_c5_trade_detail_renders_audit_log_empty_state(seeded_db):
    """V1 has no edit-after-lock UI → audit_entries is empty → empty-state
    message rendered (not omitted)."""
    cfg, cfg_path = seeded_db
    tid = _c5_seed_phase7_trade(cfg, ticker="C5AUD")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    assert r.status_code == 200
    text = r.text
    # Audit-log section header rendered (gated on has_pre_trade_data, which
    # is True for this seeded row).
    assert "Audit log" in text, (
        "Audit-log header must render even when no edits exist (spec §11.4)"
    )
    # Empty-state message present:
    assert "No edits since lock." in text


def test_c5_trade_detail_state_badge_rendered(seeded_db):
    """Phase 7 state badge visible at top of detail page."""
    cfg, cfg_path = seeded_db
    tid = _c5_seed_phase7_trade(cfg, ticker="C5BDG", state="managing")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    assert r.status_code == 200
    text = r.text
    # Either the CSS class with the state, or the human label, or both:
    assert 'class="state-badge state-managing"' in text or "Managing" in text


def test_c5_trade_detail_route_does_not_shadow_existing_subroutes(
    seeded_db, monkeypatch,
):
    """Discriminating: registering /trades/{trade_id} after the more-specific
    routes (entry/form, exit/form, stop/form, expand, review) prevents URL-
    pattern shadowing. Pre-fix order check: if /trades/{trade_id} were
    registered FIRST, FastAPI would match /trades/entry/form to trade_detail
    with trade_id="entry" → 422 (int conversion fails) or wrong route →
    test fails.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C5SDW")
    _c3_patch_pricecache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=C5SDW")
    assert r.status_code == 200, (
        f"GET /trades/entry/form must STILL resolve to entry_form (not "
        f"shadowed by /trades/{{trade_id}}); got status {r.status_code}, "
        f"text {r.text[:300]!r}"
    )
    # Form fieldsets render — proves /trades/entry/form did NOT route to
    # the trade-detail handler (which would render an entirely different
    # page without the form ticker):
    assert "C5SDW" in r.text
    assert 'name="thesis"' in r.text  # form-only field, not in detail page


def test_c5_trade_detail_renders_all_5_base_layout_safe_defaults(seeded_db):
    """Defensive: TradeDetailVM must carry the 5 base-layout safe defaults
    (CLAUDE.md base-layout VM rule — session_date, stale_banner,
    price_source_degraded, price_source_degraded_until, ohlcv_source_degraded).
    Without them, base.html.j2's {% if vm.foo %} dereferences raise
    UndefinedError → 500. This test discriminates by hitting a route whose
    template extends base.html.j2; a successful 200 means the base layout
    rendered without UndefinedError on any of the 5 fields.
    """
    cfg, cfg_path = seeded_db
    tid = _c5_seed_phase7_trade(cfg, ticker="C5BSE")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}")
    # If any of the 5 safe defaults were missing, Jinja would raise
    # UndefinedError at render time and the response would be 500.
    assert r.status_code == 200, (
        f"GET /trades/{tid} must return 200; a 500 here means a base-layout "
        f"VM field is missing on TradeDetailVM (CLAUDE.md base-layout rule). "
        f"Got: {r.text[:300]!r}"
    )
    # Also check the topbar nav links rendered (proves base.html.j2 ran to
    # completion, not just the {% block content %} body):
    assert "Dashboard" in r.text
    assert "Watchlist" in r.text


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.7 — route state-aware predicate rewrites + base-layout VM
# no-regression check.
# ---------------------------------------------------------------------------


def _c7_seed_trade(
    cfg, *, ticker: str, state: str = "entered",
    reviewed_at: str | None = None,
) -> int:
    """Seed a single trade row with a chosen lifecycle state.

    Bypasses ``record_entry`` because tests just need a row in the trades
    table for route-precondition checks. Returns the new trade_id.

    For state='reviewed' the row is seeded with reviewed_at populated (the
    Phase 7 schema permits it without a CHECK enforcing the cross-field tie,
    but we set it for realism + so the predicate-discriminator test is
    unambiguous).
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

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
                reviewed_at=reviewed_at,
            ), event_ts="2026-04-15T16:00:00")
    finally:
        conn.close()
    return tid


# --- Line ~989: trade_cancel GET /trades/{id}/cancel (active-trade) ---


def test_c7_cancel_route_managing_state_accepted(seeded_db, monkeypatch):
    """state='managing' is active — GET /cancel proceeds (200, normal row)."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7CMG", state="managing")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "C7CMG": PriceSnapshot(
                ticker="C7CMG", price=105.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/cancel",
                       headers={"HX-Request": "true"})
    # Pre-fix (status != 'open'): trade.status no longer exists on Phase 7
    # rows → AttributeError or always-True predicate → 404 or 500. Post-fix:
    # state in _ACTIVE_STATES → 200.
    assert r.status_code == 200, (
        f"managing IS active — cancel route must accept; got {r.status_code} "
        f"text={r.text[:200]!r}"
    )


def test_c7_cancel_route_partial_exited_state_accepted(
    seeded_db, monkeypatch,
):
    """state='partial_exited' is active — cancel proceeds."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7CPE", state="partial_exited")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "C7CPE": PriceSnapshot(
                ticker="C7CPE", price=105.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/cancel",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200


def test_c7_cancel_route_closed_state_rejected(seeded_db):
    """state='closed' is NOT active — cancel must 404."""
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7CCL", state="closed")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{tid}/cancel",
                       headers={"HX-Request": "true"})
    assert r.status_code == 404


# --- Line ~1046: stop_post inner trade_check guard (active-trade) ---


def test_c7_stop_post_partial_exited_state_accepted(seeded_db):
    """state='partial_exited' is active — stop POST passes the precondition.

    Discriminating: pre-fix the predicate was ``trade_check.status != 'open'``
    which would AttributeError on a Phase 7 row (no status column). Post-fix
    it's ``state not in _ACTIVE_STATES`` and partial_exited IS in the set →
    guard does NOT fire. The downstream service-layer check accepts a
    partial_exited trade for stop adjusts; expect 200/400 (not 404).
    """
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7SPE", state="partial_exited")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{tid}/stop",
            headers={"HX-Request": "true",
                     "HX-Target": f"open-position-{tid}"},
            data={"new_stop": "95.00", "rationale": "manual-trail"},
        )
    # Precondition guard must NOT 404 a partial_exited trade.
    assert r.status_code != 404, (
        f"partial_exited IS active — stop POST precondition must NOT 404; "
        f"got {r.status_code} text={r.text[:200]!r}"
    )


def test_c7_stop_post_closed_state_rejected(seeded_db):
    """state='closed' is NOT active — stop POST returns 404."""
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7SCL", state="closed")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{tid}/stop",
            headers={"HX-Request": "true",
                     "HX-Target": f"open-position-{tid}"},
            data={"new_stop": "95.00", "rationale": "manual-trail"},
        )
    assert r.status_code == 404


# --- Line ~1227: review_post precondition (closed-but-not-reviewed) ---


def test_c7_review_post_closed_state_accepted(seeded_db):
    """state='closed' (not yet reviewed) — review POST proceeds past 404 guard.

    The handler may still 400 on missing/invalid form fields, or 204 on
    success, but it must NOT 404 the precondition. Discriminating: pre-fix
    `trade.status != 'closed'` would AttributeError on Phase 7 rows; post-fix
    `trade.state != 'closed'` evaluates False (predicate doesn't fire) and
    the handler proceeds to review-business-logic.
    """
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7RCL", state="closed")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{tid}/review",
            headers={"HX-Request": "true"},
            data={
                "entry_grade": "A", "management_grade": "A",
                "exit_grade": "A", "lesson_learned": "Solid entry.",
                "mistake_tags": "none_observed",
            },
        )
    assert r.status_code != 404, (
        f"closed-and-unreviewed must pass the 404 precondition guard; "
        f"got {r.status_code} text={r.text[:200]!r}"
    )


def test_c7_review_post_reviewed_state_rejected(seeded_db):
    """state='reviewed' MUST 404 the precondition.

    Discriminating: under buggy `state not in ('closed','reviewed')`,
    'reviewed' IS in the set → predicate False → guard does NOT fire →
    handler proceeds against an already-reviewed trade. Under correct
    `state != 'closed'`: 'reviewed' != 'closed' is True → guard fires → 404.

    (Note: even if the precondition were broadened, the handler's later
    `reviewed_at is not None` check would catch this with a 409 — but that
    is a defense-in-depth fallback. The PRECONDITION must reject 'reviewed'
    at the gate to keep the spec contract clean.)
    """
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(
        cfg, ticker="C7RRV", state="reviewed",
        reviewed_at="2026-04-30T16:00:00",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{tid}/review",
            headers={"HX-Request": "true"},
            data={
                "entry_grade": "A", "management_grade": "A",
                "exit_grade": "A", "lesson_learned": "n/a",
                "mistake_tags": "none_observed",
            },
        )
    assert r.status_code == 404, (
        f"reviewed state must be rejected by precondition; got "
        f"{r.status_code} text={r.text[:200]!r}"
    )


def test_c7_review_post_managing_state_rejected(seeded_db):
    """state='managing' is NOT closed — review POST must 404.

    Sanity case for the closed-but-not-reviewed predicate.
    """
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7RMG", state="managing")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{tid}/review",
            headers={"HX-Request": "true"},
            data={
                "entry_grade": "A", "management_grade": "A",
                "exit_grade": "A", "lesson_learned": "n/a",
                "mistake_tags": "none_observed",
            },
        )
    assert r.status_code == 404


# --- Line ~1343: open_position_row GET /trades/open/{id}/row (active) ---


def test_c7_open_position_row_managing_accepted(seeded_db, monkeypatch):
    """state='managing' is active — open-positions row partial returns 200."""
    from datetime import datetime
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7ORM", state="managing")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "C7ORM": PriceSnapshot(
                ticker="C7ORM", price=105.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/open/{tid}/row",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200


def test_c7_open_position_row_closed_rejected(seeded_db):
    """state='closed' is NOT active — open-position row endpoint 404s."""
    cfg, cfg_path = seeded_db
    tid = _c7_seed_trade(cfg, ticker="C7ORC", state="closed")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/open/{tid}/row",
                       headers={"HX-Request": "true"})
    assert r.status_code == 404


# --- Base-layout VM no-regression check (spec §11.5 + plan §6 C.7 step 3) ---


def test_c7_base_layout_does_not_dereference_phase7_specific_fields():
    """Spec §11.5 verification: Phase 7 does NOT add base-layout-dereferenced
    fields. If a future change starts dereferencing `vm.state` or
    `vm.has_pre_trade_data` etc. from base.html.j2, EVERY base-layout VM
    must gain that field — caught by this test failing.
    """
    from pathlib import Path
    base_layout = Path(
        "swing/web/templates/base.html.j2"
    ).read_text(encoding="utf-8")
    for forbidden_attr in (
        "vm.state",
        "vm.has_pre_trade_data",
        "vm.trade_origin",
        "vm.thesis",
        "vm.state_badge_label",
    ):
        assert forbidden_attr not in base_layout, (
            f"base.html.j2 dereferences {forbidden_attr!r} — every "
            f"base-layout VM (DashboardVM, PipelineVM, JournalVM, "
            f"WatchlistVM, PageErrorVM, ReviewVM, CadenceCompleteVM, "
            f"ReviewsPendingVM, TradeDetailVM) must gain that field with "
            f"a safe default."
        )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.8 — pre-trade gate failure rendering consistency across
# the 3 entry surfaces (web watchlist origin, web hyp-recs origin, CLI).
#
# Architecture finding (recorded in commit body): the plan's implementation
# sketch said "Hyp-recs route (existing route handler in
# swing/web/routes/recommendations.py — adjust path; this Phase 7 task
# expands the existing handler)." THIS WAS STALE. There is no POST handler
# for hyp-recs trade entry in `swing/web/routes/recommendations.py`; the
# hyp-recs "Take this trade" link navigates to GET
# `/trades/entry/form?ticker=X&origin=hyp-recs` and the submit POSTs to the
# SAME `/trades/entry` handler that watchlist origin uses. The `origin`
# discriminator threads through `_coerce_origin` + `build_entry_form_vm` +
# `_rerender_entry_form_with_error` (added in Task 8 / R4-Major-1). So the
# cross-surface "consistency" is structural — both origins go through the
# same MissingPreTradeFieldsException catch path.
#
# C.8's job is therefore to PIN that consistency with discriminating tests.
# CLI parity is already covered by Sub-B B.8's
# `test_cli_trade_entry_rejects_missing_thesis`; we add a smoke-pin here
# that confirms the catalog is complete.
# ---------------------------------------------------------------------------


def test_c8_hyp_recs_origin_missing_thesis_returns_400_same_as_watchlist(
    seeded_db, monkeypatch,
):
    """Cross-surface consistency: hyp-recs origin and watchlist origin
    must both produce 400 + same canonical missing-fields banner format
    when MissingPreTradeFieldsException fires.

    Discriminating: under buggy code that diverged on ``origin=hyp-recs``
    (e.g., dropped the gate, returned 500, or used a different banner
    template), this test would fail because one of the responses would
    not match. Because both paths share the SAME
    `_rerender_entry_form_with_error` helper + 400 status under the
    current architecture, the test passes.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C8X")
    _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="C8X")
    _c3_patch_pricecache(monkeypatch)

    data_watchlist = _c3_all_18_fields(ticker="C8X")
    data_watchlist.pop("thesis")
    data_watchlist["origin"] = "watchlist"

    data_hyp_recs = _c3_all_18_fields(ticker="C8X")
    data_hyp_recs.pop("thesis")
    data_hyp_recs["origin"] = "hyp-recs"

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_w = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"}, data=data_watchlist,
        )
        r_h = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"}, data=data_hyp_recs,
        )

    # Both surfaces yield 400 (not 500 / 422 / 200):
    assert r_w.status_code == 400, (
        f"watchlist-origin missing-thesis must return 400; got "
        f"{r_w.status_code}: {r_w.text[:300]!r}"
    )
    assert r_h.status_code == 400, (
        f"hyp-recs-origin missing-thesis must return 400; got "
        f"{r_h.status_code}: {r_h.text[:300]!r}"
    )
    # Both surfaces use the canonical banner format (same wording):
    canonical = "missing required pre-trade fields"
    assert canonical in r_w.text.lower(), (
        f"watchlist banner missing canonical phrase {canonical!r}: "
        f"{r_w.text[:300]!r}"
    )
    assert canonical in r_h.text.lower(), (
        f"hyp-recs banner missing canonical phrase {canonical!r}: "
        f"{r_h.text[:300]!r}"
    )
    # Both surfaces name the missing field by name in the banner:
    assert "thesis" in r_w.text.lower()
    assert "thesis" in r_h.text.lower()


def test_c8_hyp_recs_origin_missing_thesis_marks_field_with_error_class(
    seeded_db, monkeypatch,
):
    """Cross-surface consistency: hyp-recs origin re-renders the FULL
    form with the per-field error class on the missing input — same
    contract as watchlist origin (verified by C.4's
    test_c4_entry_form_post_missing_thesis_marks_field_with_error_class).

    Discriminating: a regression that branched on origin in the catch path
    (e.g., banner-only fragment for hyp-recs but full re-render for
    watchlist) would fail this test. The shared
    `_rerender_entry_form_with_error` + `build_entry_form_vm(origin=...)`
    plumbing means both origins traverse the same template.
    """
    import re
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C8FE")
    _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="C8FE")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C8FE")
    data.pop("thesis")
    data["origin"] = "hyp-recs"

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"}, data=data,
        )
    assert r.status_code == 400
    m = re.search(r'<textarea[^>]*name="thesis"[^>]*>', r.text)
    assert m is not None, (
        f"hyp-recs re-render must contain the thesis textarea (full form "
        f"re-render, not banner-only). Body[:600]={r.text[:600]!r}"
    )
    assert 'class="field-error"' in m.group(0), (
        f"hyp-recs re-render must mark the thesis textarea with "
        f"class='field-error' identical to watchlist origin "
        f"(C.4 contract). Got tag {m.group(0)!r}."
    )


def test_c8_hyp_recs_origin_missing_thesis_preserves_typed_why_now(
    seeded_db, monkeypatch,
):
    """Cross-surface consistency: hyp-recs origin draft preservation
    (operator's typed why_now round-trips back into the textarea body
    via `vm.draft_why_now`) — same contract as watchlist origin
    (C.4 test_c4_entry_form_post_missing_thesis_preserves_typed_why_now).

    Discriminating: a regression that bypassed the dataclass-replace
    draft-preservation block on the hyp-recs branch would clear typed
    fields. Architecture today shares the same code path so the
    operator's typing survives the gate-fail re-render.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C8DR")
    _t5_seed_hyp_recs_aplus_candidate(cfg, ticker="C8DR")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C8DR")
    data.pop("thesis")
    sentinel = "OPERATOR_TYPED_WHY_NOW_HYP_RECS_C8"
    data["why_now"] = sentinel
    data["origin"] = "hyp-recs"

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"}, data=data,
        )
    assert r.status_code == 400
    assert sentinel in r.text, (
        f"hyp-recs origin draft-preservation regression: typed why_now "
        f"value {sentinel!r} did not round-trip back into re-rendered "
        f"form. Body[:600]={r.text[:600]!r}"
    )


def test_c8_missing_multiple_fields_banner_lists_all_missing(
    seeded_db, monkeypatch,
):
    """Discriminating: under buggy code that reported only the first
    missing field (e.g., early-return on first `not value` check), only
    'thesis' would appear in the banner. Correct code enumerates ALL
    missing fields in the message body; multiple field names appear.

    Pins the consistency principle that the gate's exception payload
    drives the banner enumeration — important for both surfaces because
    the operator should fix all missing fields in one round trip rather
    than discovering them sequentially.
    """
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="C8MM")
    _c3_patch_pricecache(monkeypatch)

    data = _c3_all_18_fields(ticker="C8MM")
    # Drop 3 distinct fields to discriminate first-only enumeration:
    data.pop("thesis")
    data.pop("why_now")
    data.pop("invalidation_condition")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"}, data=data,
        )
    assert r.status_code == 400
    text = r.text.lower()
    # All three missing field names must appear in the response body
    # (banner OR per-field error markers; both are acceptable since the
    # full form re-renders with the missing-fields set populated):
    assert "thesis" in text, (
        f"missing field 'thesis' must surface; body[:600]={text[:600]!r}"
    )
    assert "why_now" in text, (
        f"missing field 'why_now' must surface (NOT just the first-listed "
        f"field). Discriminating against early-return-after-first bug. "
        f"body[:600]={text[:600]!r}"
    )
    assert "invalidation_condition" in text, (
        f"missing field 'invalidation_condition' must surface. "
        f"body[:600]={text[:600]!r}"
    )


def test_c8_recommendations_route_exposes_no_post_entry_handler():
    """Architecture pin: hyp-recs trade entry MUST flow through the shared
    `/trades/entry` POST handler — there must be NO competing POST handler
    in `swing/web/routes/recommendations.py` that would diverge from the
    watchlist-origin gate path.

    Discriminating: if a future refactor splits the hyp-recs surface into
    its own POST handler, the cross-surface consistency contract this
    task pins becomes load-bearing on TWO handlers staying in sync. This
    test catches that split at architecture level so the next maintainer
    is forced to update the consistency tests above (or rejoin the
    surfaces).
    """
    from pathlib import Path
    src = Path("swing/web/routes/recommendations.py").read_text(encoding="utf-8")
    # No @router.post decorator targeting an entry path:
    assert "@router.post" not in src or "/entry" not in src, (
        "recommendations.py must not register a POST handler for trade "
        "entry; the shared /trades/entry handler in trades.py owns both "
        "watchlist and hyp-recs origins. Found POST handler — re-evaluate "
        "C.8's consistency tests."
    )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.10 — sizing-hint route migrates the C.1-deferred
# list_all_exits site onto _list_all_exitshape_via_fills (imported from
# the view-models layer). Discriminating: with realized PnL seeded via
# non-entry fills, the sizing hint reflects the larger equity.
# ---------------------------------------------------------------------------


def test_c10_sizing_hint_consumes_fills_for_equity(seeded_db):
    """C.10: GET /trades/entry/sizing-hint computes equity through the
    C.10 view_models/trades._list_all_exitshape_via_fills helper.
    Discriminating against (a) helper not threaded through (would still
    see baseline equity from cfg.account.starting_equity and the floor)
    and (b) helper returning empty (equity = starting_equity, smaller
    suggested shares).

    Uses entry=10, stop=9 so rps=$1 → shares = floor(equity*risk_pct/$1).
    With test config (starting=$1200, max_risk_pct=0.005), baseline equity
    yields ~6 shares. After seeding $20k of realized PnL via a non-entry
    fill, equity grows to ~$21,200; max_risk_dollars = ~$106; shares =
    ~106. So the post-fill response should mention significantly more
    shares than the baseline.
    """
    from swing.data.db import connect
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    cfg, cfg_path = seeded_db

    # Baseline call — no realized PnL.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        baseline = client.get(
            "/trades/entry/sizing-hint?entry_price=10.0&initial_stop=9.0"
        )
    assert baseline.status_code == 200
    baseline_text = baseline.text

    # Seed a closed trade with $20k realized PnL via non-entry fill.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="ZZZ", entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=200,
                    initial_stop=90.0, current_stop=90.0,
                    state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None, notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=trade_id,
                    fill_datetime="2026-04-29T16:00:00",
                    action="exit", quantity=200, price=200.0,
                    reason="target",
                ),
                event_ts="2026-04-29T16:00:00",
            )
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?",
                (trade_id,),
            )
    finally:
        conn.close()

    # Post-PnL call.
    app2 = create_app(cfg, cfg_path)
    with TestClient(app2) as client:
        after = client.get(
            "/trades/entry/sizing-hint?entry_price=10.0&initial_stop=9.0"
        )
    assert after.status_code == 200
    # The response shape includes the suggested shares; assert it grew.
    # Both responses are 200 with a numbers fragment; the cheap discriminator
    # is "the response text changed" (different shares produces different
    # output).
    assert after.text != baseline_text, (
        "C.10 sizing-hint route equity computation should reflect a "
        "$20k realized-PnL exit fill. Baseline and post-fill response "
        "are identical, suggesting the route did not see the new fill — "
        "the migration helper may have returned empty. Baseline text:\n"
        f"{baseline_text!r}\nAfter:\n{after.text!r}"
    )


# ---------------------------------------------------------------------------
# 3e.7 Task B.1 — Example asides on entry-form textareas. One <aside> per
# each of the 5 brief-locked textareas (thesis + 4 premortem). Brief §0.3
# #5 + #6 (locked content). Verify each aside's hint-bullet content is
# rendered verbatim and the structural wrapper class is present.
# ---------------------------------------------------------------------------
def test_b1_entry_form_renders_thesis_aside(seeded_db, monkeypatch):
    """B.AC.1+B.AC.2 — Pre-trade thesis aside renders with locked content."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="B1TH")
    _c3_patch_pricecache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=B1TH")
    assert r.status_code == 200
    text = r.text
    # Anchor on unique substring from each of the 3 locked thesis hints.
    assert "Setup type + base structure" in text
    assert "Setup grade + binding criteria passed" in text
    assert "Catalyst + RS context" in text


def test_b1_entry_form_renders_premortem_technical_aside(
    seeded_db, monkeypatch,
):
    """B.AC.1+B.AC.2 — Premortem: technical aside renders with locked content."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="B1PT")
    _c3_patch_pricecache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=B1PT")
    assert r.status_code == 200
    text = r.text
    assert "What invalidates the setup" in text
    assert "Where the framework would call you wrong" in text
    assert "Failure modes for the specific pattern" in text


def test_b1_entry_form_renders_premortem_market_sector_aside(
    seeded_db, monkeypatch,
):
    """B.AC.1+B.AC.2 — Premortem: market/sector aside renders with locked content."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="B1PM")
    _c3_patch_pricecache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=B1PM")
    assert r.status_code == 200
    text = r.text
    assert "Market weather state + your sizing response" in text
    assert "Sector strength vs market" in text
    assert "Macro/news risk specific to the trade window" in text


def test_b1_entry_form_renders_premortem_execution_aside(
    seeded_db, monkeypatch,
):
    """B.AC.1+B.AC.2 — Premortem: execution aside renders with locked content."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="B1PX")
    _c3_patch_pricecache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=B1PX")
    assert r.status_code == 200
    text = r.text
    assert "Personal entry biases" in text
    assert "Stop discipline" in text
    assert "Position management" in text


def test_b1_entry_form_renders_premortem_additional_aside(
    seeded_db, monkeypatch,
):
    """B.AC.1+B.AC.2 — Premortem: additional aside renders with locked content."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="B1PA")
    _c3_patch_pricecache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=B1PA")
    assert r.status_code == 200
    text = r.text
    assert "Earnings proximity + hold-through policy" in text
    assert "Personal availability" in text
    assert "Catch-all for pattern-specific or ticker-specific risks" in text


def test_b1_entry_form_aside_layout_class_present(seeded_db, monkeypatch):
    """B.AC.3 — structural wrapper `entry-textarea-row` class present so
    the CSS flex layout (Task B.2) targets the textarea-aside pairs.
    Discriminating: regression that drops the wrapper would fail here."""
    cfg, cfg_path = seeded_db
    _c3_seed_watchlist(cfg, ticker="B1LC")
    _c3_patch_pricecache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=B1LC")
    assert r.status_code == 200
    text = r.text
    # 5 wrappers expected (one per textarea getting an aside).
    assert text.count("entry-textarea-row") >= 5, (
        f"expected at least 5 `entry-textarea-row` wrapper occurrences "
        f"(one per thesis + 4 premortem textareas); got {text.count('entry-textarea-row')}"
    )
    # 5 asides expected.
    assert text.count("entry-example-aside") >= 5, (
        f"expected at least 5 `entry-example-aside` elements; "
        f"got {text.count('entry-example-aside')}"
    )
