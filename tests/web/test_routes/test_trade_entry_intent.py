"""Task 3 (tuition-vs-error): POST /trades/entry server-stamps entry_intent.

The persisted value is ALWAYS the explicit submitted <select> control
(server-stamp; never a derived/trusted hidden input). Three surfaces:
  - selected intent persists AS-IS,
  - empty string ("") persists NULL (the ``... or None`` nullability gotcha),
  - a soft-warn / missing-fields re-render pre-selects the SUBMITTED intent
    (draft_entry_intent), NOT the suggestion, so a force resubmit keeps it.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests.web.conftest import full_phase7_entry_payload


def _price_patch(monkeypatch, ticker: str, price: float) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            ticker: PriceSnapshot(
                ticker=ticker, price=price, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        },
    )


def _read_entry_intent(db_path: Path, ticker: str) -> str | None:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT entry_intent FROM trades WHERE ticker = ? "
            "ORDER BY id DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def test_entry_post_persists_selected_intent(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _price_patch(monkeypatch, "ZZZ", 100.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="ZZZ", entry_date="2026-04-15", entry_price="100.0",
            shares="1", initial_stop="90.0", rationale="vcp-breakout",
            sector="", industry="", origin="watchlist",
            entry_intent="hypothesis_test_by_design",
        ), headers={"HX-Request": "true"})
        assert resp.status_code in (200, 201, 302), resp.text
    assert _read_entry_intent(cfg.paths.db_path, "ZZZ") == (
        "hypothesis_test_by_design"
    )


def test_entry_post_standard_intent_persists(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _price_patch(monkeypatch, "ZZZ", 100.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="ZZZ", entry_date="2026-04-15", entry_price="100.0",
            shares="1", initial_stop="90.0", rationale="vcp-breakout",
            sector="", industry="", origin="watchlist",
            entry_intent="standard",
        ), headers={"HX-Request": "true"})
        assert resp.status_code in (200, 201, 302), resp.text
    assert _read_entry_intent(cfg.paths.db_path, "ZZZ") == "standard"


def test_entry_post_empty_intent_persists_null(seeded_db, monkeypatch):
    """Empty string from an unselected <select> -> NULL, not "" (the
    ``entry_intent or None`` nullability gotcha)."""
    cfg, cfg_path = seeded_db
    _price_patch(monkeypatch, "ZZZ", 100.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="ZZZ", entry_date="2026-04-15", entry_price="100.0",
            shares="1", initial_stop="90.0", rationale="vcp-breakout",
            sector="", industry="", origin="watchlist",
            entry_intent="",
        ), headers={"HX-Request": "true"})
        assert resp.status_code in (200, 201, 302), resp.text
    assert _read_entry_intent(cfg.paths.db_path, "ZZZ") is None


def test_entry_post_omitted_intent_persists_null(seeded_db, monkeypatch):
    """No entry_intent field at all (bare cURL / legacy submit) -> NULL
    via the Form("") default + ``or None``."""
    cfg, cfg_path = seeded_db
    _price_patch(monkeypatch, "ZZZ", 100.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.post("/trades/entry", data=full_phase7_entry_payload(
            ticker="ZZZ", entry_date="2026-04-15", entry_price="100.0",
            shares="1", initial_stop="90.0", rationale="vcp-breakout",
            sector="", industry="", origin="watchlist",
        ), headers={"HX-Request": "true"})
        assert resp.status_code in (200, 201, 302), resp.text
    assert _read_entry_intent(cfg.paths.db_path, "ZZZ") is None


def test_entry_softwarn_roundtrips_intent(seeded_db, monkeypatch):
    """A submission that trips the missing-pre-trade-fields re-render must
    re-render the <select> pre-selected to the SUBMITTED intent
    (draft_entry_intent), NOT the suggestion -- so a force resubmit keeps
    it. The 400 fragment carries the selected option for "standard".
    """
    cfg, cfg_path = seeded_db
    _price_patch(monkeypatch, "ZZZ", 100.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Omit a required pre-trade field (thesis) to trip the
        # MissingPreTradeFieldsException re-render path.
        data = full_phase7_entry_payload(
            ticker="ZZZ", entry_date="2026-04-15", entry_price="100.0",
            shares="1", initial_stop="90.0", rationale="vcp-breakout",
            sector="", industry="", origin="watchlist",
            entry_intent="standard",
        )
        del data["thesis"]
        resp = client.post("/trades/entry", data=data,
                           headers={"HX-Request": "true"})
        assert resp.status_code == 400, resp.text
        assert 'value="standard"' in resp.text and "selected" in resp.text


def test_entry_softwarn_explicit_unclassified_survives(seeded_db, monkeypatch):
    """An explicit Unclassified ("") submission that trips the re-render
    keeps the (unclassified) option selected -- it must NOT silently
    re-suggest (Codex R1-Major-1: NULL != standard). The draft is "",
    which the template treats as a real draft (``is not none``)."""
    cfg, cfg_path = seeded_db
    _price_patch(monkeypatch, "ZZZ", 100.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        data = full_phase7_entry_payload(
            ticker="ZZZ", entry_date="2026-04-15", entry_price="100.0",
            shares="1", initial_stop="90.0", rationale="vcp-breakout",
            sector="", industry="", origin="watchlist",
            entry_intent="",
        )
        del data["thesis"]
        resp = client.post("/trades/entry", data=data,
                           headers={"HX-Request": "true"})
        assert resp.status_code == 400, resp.text
        # The (unclassified) empty option must be selected.
        assert 'value=""' in resp.text and "selected" in resp.text
