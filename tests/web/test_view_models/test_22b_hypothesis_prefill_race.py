"""Arc 22-B RULING R1-3-SURFACES item 2 -- the web entry-form GET prefill
DEGRADES on a raced governed read: the suggestion is skipped and the form
renders WITHOUT it and WITH the ruled ASCII line visible beside the field
(never a refusal -- a bookkeeping transient must not block a real trade,
R1-1's asymmetry). The SAME text the CLI prefill prints
(``swing.recommendations.hypothesis_prefill.PREFILL_UNAVAILABLE_TEXT``).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from swing.recommendations.hypothesis_prefill import PREFILL_UNAVAILABLE_TEXT
from swing.web.app import create_app
from tests.web.test_view_models.test_trade_entry_form_hypothesis import (
    _seed_aplus_pipeline,
)


def _plant_prefill_race(monkeypatch) -> None:
    import swing.recommendations.hypothesis_prefill as prefill_mod

    def raced(conn, *, ticker, starting_equity, budget_seconds=None):
        from swing.metrics.cohort import CohortReadRacedError
        raise CohortReadRacedError((3,))

    monkeypatch.setattr(prefill_mod, "lookup_active_recommendation_label", raced)


def test_build_entry_form_vm_degrades_the_suggestion_b22_239(
        seeded_db, monkeypatch) -> None:
    from swing.web.view_models.trades import build_entry_form_vm

    cfg, _ = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")
    _plant_prefill_race(monkeypatch)

    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )
    assert vm.hypothesis_label is None
    assert vm.hypothesis_suggestion_unavailable_text == PREFILL_UNAVAILABLE_TEXT


def test_entry_form_route_renders_without_suggestion_and_with_the_line_b22_239(
        seeded_db, monkeypatch) -> None:
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")
    _plant_prefill_race(monkeypatch)

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get(
            "/trades/entry/form?ticker=AAPL",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    assert PREFILL_UNAVAILABLE_TEXT in resp.text, resp.text
    # The form still renders (the entry PROCEEDS -- this is not a refusal).
    assert 'name="ticker"' in resp.text, resp.text
    # No suggestion is displayed.
    assert "(none)" in resp.text, resp.text
