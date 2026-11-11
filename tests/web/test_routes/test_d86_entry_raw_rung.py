"""D86 T4.3 in FORM C (RD's FX-1 ruling, 2026-11-11) -- test 4h.

NO RUNG ON THE ENTRY POST. An auto-fill anchor the ONE identity authority
(``canonical_envelope_identity``) refuses REFUSES THE LABEL -- the latch
binding and the cohort keys -- and NEVER THE ENTRY. For each D86 shape:

  (i)   the trade IS written (a 400 fails the test);
  (ii)  the cohort keys land honest-unset: ``manual_off_pipeline``, NULL
        ``hypothesis_label``, NULL ``candidate_id`` (admitting the anchor and
        stamping keys fails the test too);
  (iii) a warning names the malformation;
  (iv)  the rejected anchor string is never replayed on the recovery form.

THE WORLD IS RD'S DISCRIMINATING ONE (2026-09-01): the ticker is ``aplus`` in
TODAY's latest complete run, so the ordinary chain would write
``pipeline_aplus`` + today's candidate + the posted label. With the ticker
rolled out a fall-through and a refusal land on the same row and prove
nothing. The handoff-2 RED is this: an UNCLAIMED refused anchor took the
ordinary chain and was recorded WITH keys.

THE CLAIMED UNDECODABLE anchor is NOT a D86 shape here: it keeps the
pre-existing claim-consistency 400 (``test_entry_post_audit_columns.py::
test_c_malformed_anchor_with_claim_rejects_with_400`` and the ext2 module's
deeply-nested case pin it; the orchestrator's encoding keeps that module
green). It is reported as a deviation for RD.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests._latch_probe_world_22a import BROKER_ORDER_ID, FILL_SESSION, TICKER
from tests.web.test_routes.test_22a_task10_entry_route_ext2 import (
    _build_route_world,
)
from tests.web.test_routes.test_phase13_t2_sb6c_t_a_6c_4 import (
    _pretrade_form_kwargs,
)

_TODAYS_LABEL = "A+ baseline (aplus)"
_REJECTED = "REJECTED-ORDER-777"
_FRESH = "FRESH-ORDER-123"


def _doc(**overrides) -> dict:
    base = {
        "entry_date": FILL_SESSION.isoformat(),
        "entry_date_source": "execution_leg",
        "entry_price": 18.50,
        "shares": 2,
        "schwab_order_id": _REJECTED,
        "schwab_instrument_symbol": TICKER,
    }
    base.update(overrides)
    return base


def _with_duplicate(key: str, first, last) -> str:
    """A decodable document carrying ``key`` TWICE at the root."""
    body = json.dumps({k: v for k, v in _doc().items() if k != key})[1:-1]
    return (f'{{"{key}": {json.dumps(first)}, {body}, '
            f'"{key}": {json.dumps(last)}}}')


# (id, raw anchor, the authority's own words for the malformation)
_SHAPES = [
    pytest.param(_with_duplicate("schwab_order_id", BROKER_ORDER_ID,
                                 _REJECTED),
                 "carries 2 schwab_order_id keys", id="duplicate-order-key"),
    pytest.param(_with_duplicate("schwab_instrument_symbol", TICKER, "XXX"),
                 "carries 2 schwab_instrument_symbol keys",
                 id="duplicate-symbol-key"),
    pytest.param(json.dumps(_doc(schwab_instrument_symbol=7)),
                 "schwab_instrument_symbol is a int", id="non-text-symbol"),
    pytest.param(json.dumps(_doc(schwab_instrument_symbol=f" {TICKER}")),
                 "whitespace-padded or blank", id="padded-symbol"),
    pytest.param(json.dumps(_doc(schwab_order_id=1002937461)),
                 "schwab_order_id is a int", id="non-text-order-id"),
    pytest.param(json.dumps(_doc(schwab_order_id="   ")),
                 "whitespace-padded or blank", id="blank-order-id"),
]
_UNDECODABLE = '{"schwab_order_id": "' + _REJECTED + '", "entry_date": '


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=18.5, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _stub_fresh_fetch(monkeypatch) -> None:
    """The rebuilt VM's fresh Schwab fetch: a DIFFERENT, canonical envelope."""
    from swing.trades import entry_auto_fill
    from swing.trades.entry_auto_fill import EntryAutoFillResult

    def _fake(*, ticker, cfg, conn):  # noqa: ARG001
        return EntryAutoFillResult(
            kind="populated", fill_origin="schwab_auto",
            entry_date=FILL_SESSION.isoformat(), entry_price=18.50, shares=2,
            schwab_source_value_json=json.dumps(
                _doc(schwab_order_id=_FRESH), sort_keys=True),
            auto_fill_audit_at=f"{FILL_SESSION.isoformat()}T09:00:00")

    monkeypatch.setattr(entry_auto_fill, "resolve_entry_auto_fill", _fake)


def _data(raw: str, *, claimed: bool, **over) -> dict:
    data = {
        "ticker": TICKER,
        "entry_date": FILL_SESSION.isoformat(),
        "entry_price": "18.50",
        "shares": "2",
        "initial_stop": "14.00",
        "rationale": "vcp-breakout",
        "origin": "watchlist",
        "hypothesis_label": _TODAYS_LABEL,
        "schwab_source_value_json": raw,
        "auto_fill_audit_at": f"{FILL_SESSION.isoformat()}T09:00:00",
        "fill_origin_at_form_render": "schwab_auto" if claimed else "",
    }
    data.update(_pretrade_form_kwargs())
    data.update(over)
    return data


def _written(cfg) -> list[tuple]:
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT ticker, trade_origin, candidate_id, hypothesis_label "
            "FROM trades WHERE ticker = ? ORDER BY id", (TICKER,)).fetchall()
    finally:
        conn.close()


def _world(cfg, monkeypatch) -> None:
    _build_route_world(cfg, with_link=True, ticker_in_todays_run=True)
    _patch_price_cache(monkeypatch)


def test_the_fixture_shapes_are_refused_by_the_authority():
    """Precondition, measured: every shape is one the ONE authority refuses."""
    from swing.trades.latched_origin import (
        ENVELOPE_REFUSED,
        canonical_envelope_identity,
    )
    for param in _SHAPES:
        raw = param.values[0]
        assert canonical_envelope_identity(raw).state == ENVELOPE_REFUSED, raw
    assert canonical_envelope_identity(_UNDECODABLE).state == ENVELOPE_REFUSED


def _assert_label_refused_entry_written(cfg, resp, caplog, malformation):
    # (i) the trade IS written -- a 400 fails here.
    assert resp.status_code == 200, resp.text
    # (ii) honest-unset keys -- admit-with-keys fails here.
    assert _written(cfg) == [(TICKER, "manual_off_pipeline", None, None)], (
        "the anchor was admitted and the ordinary chain stamped keys")
    # (iii) a warning names the malformation, and one names the disposition.
    warnings = [r.getMessage() for r in caplog.records
                if r.levelno >= logging.WARNING]
    assert any(malformation in m for m in warnings), warnings
    assert any("refuses the LABEL, not the ENTRY" in m for m in warnings), (
        warnings)


@pytest.mark.parametrize("claimed", [True, False], ids=["claimed", "unclaimed"])
@pytest.mark.parametrize(("raw", "malformation"), _SHAPES)
def test_4h_a_refused_anchor_refuses_the_label_never_the_entry(
        seeded_db, monkeypatch, caplog, raw, malformation, claimed):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with caplog.at_level(logging.WARNING):
        with TestClient(create_app(cfg, cfg_path)) as client:
            resp = client.post("/trades/entry",
                               data=_data(raw, claimed=claimed),
                               headers={"HX-Request": "true"})
    _assert_label_refused_entry_written(cfg, resp, caplog, malformation)


def test_4h_an_unclaimed_undecodable_anchor_refuses_the_label(
        seeded_db, monkeypatch, caplog):
    """The bare-cURL fallback still records the entry as ``operator_typed``
    (``test_c_malformed_anchor_without_claim_falls_back``), and now with
    honest-unset keys."""
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with caplog.at_level(logging.WARNING):
        with TestClient(create_app(cfg, cfg_path)) as client:
            resp = client.post("/trades/entry",
                               data=_data(_UNDECODABLE, claimed=False),
                               headers={"HX-Request": "true"})
    _assert_label_refused_entry_written(
        cfg, resp, caplog, "could not be DECODED")
    conn = connect(cfg.paths.db_path)
    try:
        assert conn.execute(
            "SELECT fill_origin FROM fills WHERE action = 'entry'"
        ).fetchone()[0] == "operator_typed"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# (iv) the rejected anchor is NEVER REPLAYED on a recovery form. Two recovery
# forms reach a refused anchor: an early validation re-render (before the
# service) and the service's missing-field re-render. "Never replayed" is the
# R3-01 meaning: the fresh fetch may legitimately repopulate the input.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("claimed", [True, False], ids=["claimed", "unclaimed"])
@pytest.mark.parametrize("recovery", ["early-validation", "missing-field"])
def test_4h_the_refused_anchor_is_never_replayed_on_the_recovery_form(
        seeded_db, monkeypatch, recovery, claimed):
    import html

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _stub_fresh_fetch(monkeypatch)
    raw = _SHAPES[0].values[0]
    data = _data(raw, claimed=claimed)
    if recovery == "early-validation":
        data["rationale"] = "not-a-rationale"
    else:
        data.pop("thesis")
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.post("/trades/entry", data=data,
                           headers={"HX-Request": "true"})
    assert resp.status_code == 400, resp.text
    assert _written(cfg) == []
    assert _REJECTED not in resp.text
    assert html.escape(raw) not in resp.text
    assert _FRESH in resp.text, "the fresh fetch's anchor should be rendered"


def test_4h_the_soft_warn_resubmit_still_refuses_the_label(
        seeded_db, monkeypatch):
    """The soft-warn confirm is the SAME submission's confirmation, not a
    recovery form: the anchor round-trips through ``form_values`` (the
    hidden-anchor round-trip gotcha), so the force resubmit is refused the
    label exactly as the first submit would have been. Dropping it there
    would hand the resubmit to the ordinary chain and stamp keys -- the
    defect D86 exists to close."""
    import html
    import re

    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for t in ["MSFT", "NVDA", "AMD", "TSLA", "META"][
                    :cfg.position_limits.soft_warn_open]:
                insert_trade_with_event(
                    conn, Trade(
                        id=None, ticker=t, entry_date="2026-07-20",
                        entry_price=100.0, initial_shares=1,
                        initial_stop=90.0, current_stop=90.0,
                        state="entered", watchlist_entry_target=None,
                        watchlist_initial_stop=None, notes=None),
                    event_ts="2026-07-20T09:30:00")
    finally:
        conn.close()
    raw = _SHAPES[0].values[0]
    with TestClient(create_app(cfg, cfg_path)) as client:
        first = client.post("/trades/entry", data=_data(raw, claimed=False),
                            headers={"HX-Request": "true"})
        assert first.status_code == 200, first.text
        assert _written(cfg) == []
        fragment = {k: html.unescape(v) for k, v in re.findall(
            r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
            first.text)}
        fragment["force"] = "true"
        second = client.post("/trades/entry", data=fragment,
                             headers={"HX-Request": "true"})
    assert second.status_code == 200, second.text
    assert _written(cfg) == [(TICKER, "manual_off_pipeline", None, None)]
