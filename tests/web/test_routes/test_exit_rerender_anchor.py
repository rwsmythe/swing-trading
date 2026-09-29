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
from datetime import UTC, datetime
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
# The resolver's clock is FROZEN in the `world` fixture, so every fresh
# fetch stamps exactly this; "re-derived" is asserted, not inferred from
# "differs from the submitted stamp" (Codex R1 minor).
_FROZEN_NOW = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
_FRESH_AUDIT_AT = "2026-05-25T12:00:00.000000+00:00"
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

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return _FROZEN_NOW if tz is not None else _FROZEN_NOW.replace(
                tzinfo=None)

    monkeypatch.setattr(f"{m}.datetime", _FrozenDatetime)
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
    assert _hidden(r.text, "auto_fill_audit_at") == _FRESH_AUDIT_AT
    assert _NOTICE not in r.text
    assert _exit_fills(world.cfg) == []


# ================================================= (d) the d2-strict restore
def _refused(tc, tid, **over) -> tuple[dict, object]:
    """GET the form, then submit it as a browser would with ``over`` applied
    and shares=50 (> the 10 remaining), so ``record_exit`` refuses it."""
    fd = _browser_form(tc.get(f"/trades/{tid}/exit/form").text)
    assert fd.get("fill_origin_at_form_render") == "schwab_auto"  # populated
    fd.update({"shares": "50", "reason": "manual",
               "auto_fill_audit_at": _SUBMITTED_AUDIT_AT})
    fd.update(over)
    return fd, _post(tc, tid, fd)


def test_unchanged_list_restores_the_submitted_anchor_triple(world):
    """(d)+(b) World unchanged between GET and the refused POST: the fresh
    re-fetch still RUNS, its ``candidates_map`` equals the submitted one, so
    the SUBMITTED triple is restored -- the envelope byte-for-byte, the
    GET-time ``auto_fill_audit_at``, and the claim STRIPPED -- with kind
    ``populated`` and no refresh notice.

    PRE-FIX: the hidden ``auto_fill_audit_at`` is the fresh fetch's stamp."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd, r = _refused(tc, world.tid,
                         fill_origin_at_form_render="  schwab_auto ")
    assert r.status_code == 400, r.text[:500]
    assert "exceeds" in r.text
    assert len(world.calls) == 2  # GET + the re-render's fetch (d2 keeps it)
    assert _hidden(r.text, "schwab_source_value_json") == (
        fd["schwab_source_value_json"])
    assert _hidden(r.text, "auto_fill_audit_at") == _SUBMITTED_AUDIT_AT
    assert _hidden(r.text, "fill_origin_at_form_render") == "schwab_auto"
    assert "Auto-fill source:" in r.text  # the populated-kind block
    assert _NOTICE not in r.text
    # The fresh list is the one offered: both orders, by hash.
    env = json.loads(fd["schwab_source_value_json"])
    offered = {v for k, v in _browser_form(r.text).items()
               if k.startswith("candidate_signature_hash_")}
    assert offered == set(env["candidates_map"])
    assert _exit_fills(world.cfg) == []


def test_unchanged_list_restores_the_non_default_candidate_pick_by_hash(world):
    """(a) Under the (d) gate the operator's candidate pick is restored BY
    SIGNATURE HASH against the FRESH list: he picked index 0 (o1) where the
    default is the last (o2).

    PRE-FIX: ``checked`` is unconditional on ``loop.last`` -> ['1']."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd, r = _refused(tc, world.tid, candidate_index="0")
    assert r.status_code == 400, r.text[:500]
    assert _hidden(r.text, "auto_fill_audit_at") == _SUBMITTED_AUDIT_AT
    assert _checked_radios(r.text) == ["0"]
    picked = fd["candidate_signature_hash_0"]
    assert _browser_form(r.text)["candidate_signature_hash_0"] == picked


def test_non_default_pick_is_not_carried_when_the_list_changed(world):
    """(a) The pick is restored ONLY under the (d) gate.  When the list
    changed (a third order arrived between GET and POST) the fresh default
    -- the last candidate -- is checked and the notice shows.  CONTROL: the
    picked o1 is STILL in the fresh list, so a port that restored the pick by
    hash outside the gate would check index 0 and fail here.

    PRE-FIX (75de0ac8): FAILS on the notice (the radio is the default either
    way)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        world.box["orders"].append(_order("o3", "2026-05-22", 132.0, 2))
        r = _post(tc, world.tid, dict(fd, shares="50", candidate_index="0",
                                      auto_fill_audit_at=_SUBMITTED_AUDIT_AT))
    assert r.status_code == 400, r.text[:500]
    assert _NOTICE in r.text
    assert _hidden(r.text, "auto_fill_audit_at") == _FRESH_AUDIT_AT
    assert _checked_radios(r.text) == ["2"]


def test_restored_blank_audit_at_stays_blank_not_the_string_none(world):
    """(d) The triple is restored VERBATIM: a submitted blank
    ``auto_fill_audit_at`` re-renders blank.  An ``or None`` restore would
    render the literal ``None`` into the hidden input, and the retry would
    persist the string 'None' as the audit stamp.

    PRE-FIX: the hidden value is the fresh stamp (not blank)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        _fd, r = _refused(tc, world.tid, auto_fill_audit_at="")
    assert r.status_code == 400
    assert _hidden(r.text, "auto_fill_audit_at") == ""


def test_two_tab_record_meanwhile_keeps_the_fresh_anchor_control(world):
    """(d) CONTROL -- E2E-2, two tabs.  Tab 1 records the default order o2.
    Tab 2 replays the SAME rendered form with 9 shares (> the 7 now
    remaining) and is refused.  The fresh list no longer carries o2 (the
    ``existing_fill_order_ids`` exclusion), so the maps differ: the FRESH
    anchor stands, the typed values stay, and the refresh notice shows.
    THIS TEST MUST FAIL a d3 port (restore unconditionally, the literal
    entry precedent): that port re-offers o2 through the restored envelope.

    Asserts only what the RE-RENDER offers; the separate double-record
    defect of an unedited replay is out of scope here.

    PRE-FIX: passes the anchor assertions (the fresh anchor was always
    rendered) and FAILS on the refresh notice."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        fd.update({"reason": "manual",
                   "auto_fill_audit_at": _SUBMITTED_AUDIT_AT})
        r1 = _post(tc, world.tid, fd)
        assert r1.status_code == 200, r1.text[:500]
        r2 = _post(tc, world.tid, dict(fd, shares="9", notes="tab two"))
    assert r2.status_code == 400, r2.text[:500]
    assert "exceeds" in r2.text
    fresh_env = _hidden(r2.text, "schwab_source_value_json")
    assert fresh_env is not None
    assert fresh_env != fd["schwab_source_value_json"]
    fresh = json.loads(fresh_env)
    assert [v["order_id"] for v in fresh["candidates_map"].values()] == ["o1"]
    assert fresh["schwab_order_id"] == "o1"
    submitted_map = json.loads(fd["schwab_source_value_json"])["candidates_map"]
    o2_hash = next(k for k, v in submitted_map.items() if v["order_id"] == "o2")
    assert o2_hash not in r2.text
    assert "o2" not in _hidden(r2.text, "schwab_source_value_json")
    assert _hidden(r2.text, "auto_fill_audit_at") == _FRESH_AUDIT_AT
    assert _NOTICE in r2.text
    assert _input_attr(r2.text, "shares", "value") == "9"
    assert _notes(r2.text) == "tab two"


def test_restore_keeps_the_fresh_possible_duplicate_advisory_control(world):
    """(b) CONTROL -- b2 keeps the FRESH advisory.  An operator-typed exit
    matching o1 is recorded first (no broker id, so it is ANONYMOUS), which
    makes the resolver flag o1 as a POSSIBLE DUPLICATE on every render.
    The refused POST's map equals the fresh one, so the anchor is restored
    AND the possible-duplicate advisory still shows.  THIS TEST MUST FAIL a
    b1 port (clear the advisory on restore, as the entry precedent does).

    PRE-FIX: passes the advisory assertion (the fresh VM always carried it)
    and FAILS on the restored ``auto_fill_audit_at``."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        seed = _post(tc, world.tid, {
            "exit_date": "2026-05-20", "exit_price": "130.00", "shares": "4",
            "reason": "manual", "notes": ""})
        assert seed.status_code == 200, seed.text[:500]
        fd, r = _refused(tc, world.tid)
    assert r.status_code == 400, r.text[:500]
    assert _hidden(r.text, "schwab_source_value_json") == (
        fd["schwab_source_value_json"])
    assert _hidden(r.text, "auto_fill_audit_at") == _SUBMITTED_AUDIT_AT
    assert "Schwab auto-fill:</strong> POSSIBLE DUPLICATE" in r.text
    assert _NOTICE not in r.text


def test_parity_refetch_restores_nothing_and_the_retry_records_operator_typed(
        world):
    """(d) Degraded / parity re-fetch.  The GET was populated; the refused
    POST's re-render fetch raises ``SchwabSchemaParityError`` (kind
    ``error``).  NOTHING is restored -- no hidden anchor at all -- the fresh
    parity advisory shows, the refresh notice shows, the typed values stay,
    and the corrected retry records ``operator_typed`` with NULL audit
    columns.  The asymmetry with entry's A1-e (which restores under parity)
    is deliberate: entry has no already-recorded-order exclusion to protect.

    PRE-FIX: FAILS on the refresh notice."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        world.box["raise"] = SchwabSchemaParityError("<orders: missing 'x'>")
        r = _post(tc, world.tid, dict(
            fd, shares="50", reason="weather", notes="parity note"))
        assert r.status_code == 400, r.text[:500]
        assert "exceeds" in r.text
        assert "SchwabSchemaParityError" in r.text
        assert _hidden(r.text, "schwab_source_value_json") is None
        assert _hidden(r.text, "auto_fill_audit_at") is None
        assert _hidden(r.text, "fill_origin_at_form_render") is None
        assert _NOTICE in r.text
        assert _selected_reasons(r.text) == ["weather"]
        retry = _browser_form(r.text)
        assert "schwab_source_value_json" not in retry
        retry["shares"] = "3"
        r2 = _post(tc, world.tid, retry)
    assert r2.status_code == 200, r2.text[:500]
    [(_fid, action, qty, origin, env, audit_at)] = _exit_fills(world.cfg)
    assert (origin, env, audit_at) == ("operator_typed", None, None)
    assert (action, qty) == ("trim", 3.0)


@pytest.mark.parametrize("claim", ["", "operator_typed"])
def test_unclaimed_anchor_is_never_restored_control(world, claim):
    """(c) CONTROL -- c2.  The submitted envelope parses to a dict and the
    world is unchanged (the maps are EQUAL), but the form made no auto-fill
    claim.  An unclaimed anchor is never restored: the fresh stamp stands and
    no notice shows.  THIS TEST MUST FAIL a restore-unclaimed port (a gate
    that checks only the map equality).

    PRE-FIX: passes (the fresh anchor was always rendered)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        _fd, r = _refused(tc, world.tid, fill_origin_at_form_render=claim)
    assert r.status_code == 400, r.text[:500]
    assert _hidden(r.text, "auto_fill_audit_at") == _FRESH_AUDIT_AT
    assert _hidden(r.text, "fill_origin_at_form_render") == "schwab_auto"
    assert _NOTICE not in r.text


def test_restored_form_round_trips_to_a_schwab_auto_record_with_the_typed_reason(
        world):
    """(d)+(e) The whole round trip, browser-emulated.  GET; a refused POST
    (shares 50, reason ``manual``); the operator corrects ONLY the shares on
    the re-rendered form (to the default candidate's 3) and resubmits
    whatever else the browser sends.  The record is ``schwab_auto`` against
    the RESTORED anchor: the GET-time audit stamp, order o2, the price
    compared at the template's 2 decimals -- and action ``trim`` because the
    reason round-tripped as ``manual``.

    PRE-FIX (75de0ac8): the browser submits the first reason option,
    ``stop-hit``, so the record is ``action='stop'``; and the audit stamp is
    the re-render's.  After ruling (e) alone, only the stamp still fails."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        _fd, r = _refused(tc, world.tid, notes="round trip")
        assert r.status_code == 400, r.text[:500]
        retry = _browser_form(r.text)
        assert retry["exit_price"] == "131.00"  # rendered at 2 decimals
        retry["shares"] = "3"
        r2 = _post(tc, world.tid, retry)
    assert r2.status_code == 200, r2.text[:500]
    [(_fid, action, qty, origin, env, audit_at)] = _exit_fills(world.cfg)
    assert action == "trim"
    assert qty == 3.0
    assert origin == "schwab_auto"
    assert audit_at == _SUBMITTED_AUDIT_AT
    assert json.loads(env)["schwab_order_id"] == "o2"
