"""Exit POST refusal re-render: the submitted anchor + the typed values.

RD 1(iii) / 22-F AL-6.  Round 0 and the orchestrator's rulings are in
``docs/superpowers/plans/2026-09-28-exit-rerender-anchor.ledger.md``.

Every exit-POST refusal that re-renders the form (the ``record_exit``
``ValueError`` branch and the ``_reject_anchor`` rejection ladder) used to
rebuild the form VM FRESH: a new Schwab fetch, a new anchor, and every value
the operator typed reset.  The reason ``<select>`` never emitted ``selected``,
so a corrected resubmit went out as ``stop-hit`` -- recorded as
``action='stop'``.

The rulings these tests pin:

* (d) d2-strict.  The re-render still FETCHES.  It restores the SUBMITTED
  anchor triple (``schwab_source_value_json``, ``auto_fill_audit_at``,
  ``fill_origin_at_form_render``) ONLY when the fresh result is ``populated``
  AND the fresh ``candidates_map`` equals the submitted one as parsed JSON.
  Otherwise the FRESH anchor stands, the typed values stay, and ONE banner
  notice says the selection was refreshed.  Under a degraded or parity
  re-fetch nothing is restored and the retry records ``operator_typed``.
* (a) the operator's candidate pick is restored BY SIGNATURE HASH against
  the fresh list, under the (d) gate only.
* (b) b2: kind ``populated``, the claim stripped, the FRESH advisory kept.
* (c) c2: only a CLAIMED anchor that parsed to a dict is ever restored;
  ``_reject_anchor`` keeps clearing the anchor.
* (e) the typed values (date, price, shares, notes, reason ``selected``)
  survive BOTH re-render paths.

The world is the REAL resolver (``resolve_exit_auto_fill``) over a stubbed
``trader.get_account_orders``, so the anchor, the candidate hashes and the
already-recorded-order exclusion are the production ones.
"""
from __future__ import annotations

import dataclasses
import html
import json
import re
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos import trades as trades_repo
from swing.data.repos.trades import list_open_trades
from swing.integrations.schwab.client import SchwabSchemaParityError
from swing.integrations.schwab.models import SchwabExecutionLeg, SchwabOrderResponse
from swing.web.app import create_app
from swing.web.price_cache import PriceCache

_HX = {"HX-Request": "true"}
# A GET-time stamp distinct from any stamp a fresh fetch can produce, so
# "restored" and "re-derived" are told apart deterministically.
_SUBMITTED_AUDIT_AT = "2026-05-22T14:30:00.000000+00:00"
# The (d) notice, matched on a fragment so its wording can be tuned without
# every test moving.
_NOTICE = "auto-fill selection was refreshed"


# ---------------------------------------------------------------- the world
def _order(oid: str, day: str, price: float, qty: int) -> SchwabOrderResponse:
    t = f"{day}T14:30:00.000Z"
    return SchwabOrderResponse(
        order_id=oid, status="FILLED", enter_time=t, instrument_symbol="NVDA",
        instruction="SELL", quantity=qty, order_type="LIMIT", price=price,
        executions=[SchwabExecutionLeg(
            leg_id=1, price=price, quantity=qty, mismarked_quantity=None,
            instrument_id=1, time=t)])


def _seed_trade(cfg) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Via the module reference so the autouse entry-fill monkeypatch
            # is honoured (current_size = 10).
            trades_repo.insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=95.0,
                current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        return int(list_open_trades(conn)[0].id)
    finally:
        conn.close()


@pytest.fixture
def world(seeded_db, monkeypatch):
    """Production Schwab config; two FILLED SELL orders, o1 then o2 (so the
    resolver's default -- the most recent -- is o2).  ``box['raise']`` makes
    the NEXT fetch fail."""
    cfg, cfg_path = seeded_db
    schwab = dataclasses.replace(
        cfg.integrations.schwab, environment="production",
        account_hash="deadbeef", marketdata_ladder_enabled=False)
    cfg = dataclasses.replace(
        cfg, integrations=dataclasses.replace(cfg.integrations, schwab=schwab))
    m = "swing.trades.exit_auto_fill"
    monkeypatch.setattr(f"{m}._compute_degraded_state",
                        lambda conn, *, env, tokens_path, now: ("LIVE", None))
    monkeypatch.setattr(f"{m}.resolve_credentials_env_or_prompt",
                        lambda cfg, env, **kw: ("id", "sec"))
    monkeypatch.setattr(f"{m}.construct_authenticated_client",
                        lambda cfg, env, a, b: object())
    box: dict = {
        "orders": [_order("o1", "2026-05-20", 130.0, 4),
                   _order("o2", "2026-05-21", 131.0, 3)],
        "raise": None,
    }
    calls: list[int] = []

    def fake_get(client, conn, account_hash, from_dt, to_dt, **kw):
        calls.append(1)
        if box["raise"] is not None:
            raise box["raise"]
        return list(box["orders"])

    monkeypatch.setattr(f"{m}.trader.get_account_orders", fake_get)
    monkeypatch.setattr(PriceCache, "get_many",
                        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    return SimpleNamespace(cfg=cfg, cfg_path=cfg_path, box=box, calls=calls,
                           tid=_seed_trade(cfg))


# ------------------------------------------------------------- HTML helpers
def _hidden(body: str, name: str) -> str | None:
    m = re.search(r'<input[^>]*name="' + re.escape(name) + r'"[^>]*>', body)
    if m is None:
        return None
    v = re.search(r'value="([^"]*)"', m.group(0))
    return html.unescape(v.group(1)) if v else ""


def _input_attr(body: str, name: str, attr: str) -> str | None:
    m = re.search(r'<input[^>]*name="' + re.escape(name) + r'"[^>]*>', body, re.S)
    if m is None:
        return None
    v = re.search(attr + r'="([^"]*)"', m.group(0))
    return html.unescape(v.group(1)) if v else None


def _checked_radios(body: str) -> list[str]:
    return re.findall(
        r'name="candidate_index" value="(\d+)"\s*checked', body)


def _selected_reasons(body: str) -> list[str]:
    select = re.search(r'<select name="reason"[^>]*>(.*?)</select>', body, re.S)
    assert select is not None
    return re.findall(r'<option value="([^"]*)"\s*selected', select.group(1))


def _notes(body: str) -> str | None:
    m = re.search(r'<textarea name="notes">(.*?)</textarea>', body, re.S)
    return html.unescape(m.group(1)) if m else None


def _browser_form(body: str) -> dict[str, str]:
    """What a browser submits for the rendered exit form: every named
    ``<input>`` (a radio only when ``checked``), the reason ``<select>``'s
    ``selected`` option or else its FIRST option (the browser default), and
    the notes ``<textarea>``'s content."""
    form = re.search(r'<form hx-post="[^"]*/exit".*?</form>', body, re.S)
    assert form is not None, body[:500]
    text = form.group(0)
    data: dict[str, str] = {}
    for m in re.finditer(r'<input([^>]*)>', text, re.S):
        attrs = m.group(1)
        n = re.search(r'name="([^"]*)"', attrs)
        if n is None:
            continue
        v = re.search(r'value="([^"]*)"', attrs)
        value = html.unescape(v.group(1)) if v else ""
        if 'type="radio"' in attrs:
            if re.search(r'\bchecked\b', attrs):
                data[n.group(1)] = value
            continue
        data[n.group(1)] = value
    select = re.search(r'<select name="reason"[^>]*>(.*?)</select>', text, re.S)
    options = re.findall(r'<option value="([^"]*)"([^>]*)>', select.group(1))
    chosen = [v for v, rest in options if "selected" in rest]
    data["reason"] = html.unescape(chosen[0] if chosen else options[0][0])
    data["notes"] = _notes(text) or ""
    return data


def _exit_fills(cfg) -> list[tuple]:
    c = sqlite3.connect(str(cfg.paths.db_path))
    try:
        return c.execute(
            "SELECT fill_id, action, quantity, fill_origin, "
            "schwab_source_value_json, auto_fill_audit_at FROM fills "
            "WHERE action != 'entry' ORDER BY fill_id").fetchall()
    finally:
        c.close()


def _post(tc, tid, data):
    return tc.post(f"/trades/{tid}/exit", headers=_HX, data=data)


# ============================================================ (e) typed values
def test_valueerror_rerender_preserves_every_typed_value(world):
    """(e) The ``record_exit`` ``ValueError`` re-render keeps date, price,
    shares, notes and the reason (``selected``).  The form carried NO anchor
    (an operator-typed submission), so nothing is restored and no notice is
    shown; the fresh populated anchor stands.  Typed shares are KEPT even
    though they exceed the remaining size -- the DB ``max=`` still renders,
    so the browser blocks the resubmit until they are corrected.

    PRE-FIX: date/price/shares are the fresh auto-fill values
    (2026-05-21 / 131.00 / 3), notes are empty, and no option is
    ``selected`` (the browser falls back to ``stop-hit``)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r = _post(tc, world.tid, {
            "exit_date": "2026-05-12", "exit_price": "117.25", "shares": "50",
            "reason": "time-stop", "notes": 'typed <note> & "more"',
        })
    assert r.status_code == 400, r.text[:500]
    assert "exceeds" in r.text
    assert _input_attr(r.text, "exit_date", "value") == "2026-05-12"
    assert _input_attr(r.text, "exit_price", "value") == "117.25"
    assert _input_attr(r.text, "shares", "value") == "50"
    assert _input_attr(r.text, "shares", "max") == "10"
    assert _selected_reasons(r.text) == ["time-stop"]
    assert _notes(r.text) == 'typed <note> & "more"'
    assert "typed <note>" not in r.text  # autoescaped, never raw markup
    assert _NOTICE not in r.text
    assert _exit_fills(world.cfg) == []


@pytest.mark.parametrize("bad", ["malformed", "bad_index"])
def test_reject_anchor_preserves_typed_values_and_still_clears_the_anchor(
        world, bad):
    """(c)+(e) ``_reject_anchor`` keeps CLEARING the submitted anchor -- the
    ``test_e_*`` discipline -- and now keeps the typed values.  Two rungs:
    a malformed envelope, and a VALID dict envelope whose ``candidate_index``
    is not an integer.  The second is the restore-in-reject control: the
    world is unchanged, so a port that restored inside ``_reject_anchor``
    would echo the submitted ``auto_fill_audit_at``.

    PRE-FIX: the typed values are lost (fails on the date)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        fd.update({
            "exit_date": "2026-05-13", "exit_price": "118.40", "shares": "2",
            "reason": "target", "notes": "reject path note",
            "auto_fill_audit_at": _SUBMITTED_AUDIT_AT,
        })
        if bad == "malformed":
            fd["schwab_source_value_json"] = "not a json envelope"
        else:
            fd["candidate_index"] = "abc"
        r = _post(tc, world.tid, fd)
    assert r.status_code == 400, r.text[:500]
    assert "Trade exit rejected" in r.text
    assert _input_attr(r.text, "exit_date", "value") == "2026-05-13"
    assert _input_attr(r.text, "exit_price", "value") == "118.40"
    assert _input_attr(r.text, "shares", "value") == "2"
    assert _selected_reasons(r.text) == ["target"]
    assert _notes(r.text) == "reject path note"
    # The anchor is the FRESH one, never the submitted one.
    assert "not a json envelope" not in r.text
    assert _hidden(r.text, "auto_fill_audit_at") != _SUBMITTED_AUDIT_AT
    assert _hidden(r.text, "auto_fill_audit_at") is not None
    assert _NOTICE not in r.text
    assert _exit_fills(world.cfg) == []
