"""Arc 22-B RULING R2-2 (CHARC, FORK R2-2 branch (B)) -- a cohort-read race
during the exit route's post-commit dashboard rebuild is CONTAINED WHERE THE
READ LIVES: ``build_dashboard`` catches ``CohortReadRacedError`` around its
one governed read (``build_recommendation_progress``) and degrades only the
hyp-recs panel (RULING R1-3-SURFACES item 1 (i)). The exit route has NO
handler of its own for it (the one ``9e32503d`` added was unreachable and is
RETIRED by R2-2, not kept as a belt), so the exit returns its ORDINARY success
fragment -- the durable exit is never reported as a failure, never a 500.

The race is planted BY EXECUTION inside the REAL builder (R1-3's technique,
``tests/metrics/test_22b_cohort_read_race.py``): the governed naming read
(``swing.metrics.cohort.list_intent_excluded_for_cohort``) is wrapped so its
FIRST call commits a REAL ``assign(...)`` over a SECOND connection on a
closed H2 trade the journal reader has already COUNTED, then runs the
original read. Nothing on the route is monkeypatched to raise.

The discriminator that the race REACHED the containment on the operator's
path is the builder's own WARNING record ("hyp-recs panel degraded"); no
WARNING means the planted race was not reached, and the test FAILS.

BANKED, pre-existing, not this arc's (unchanged by R2-2): the exit route's
post-commit rebuild is uncontained for ANY OTHER exception (unlike the entry
route's 22-A3 shape) -- the exit-side twin of 22-A3, on CHARC's register.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos import trades as trades_repo
from swing.data.repos.trades import list_open_trades
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests.metrics.test_22b_cohort_exclusion import H2, UNINTENDED, _attest, _seed
from tests.web.test_routes.test_hyp_recs_expand_route import (
    _seed_hyp_recs_fixture,
)

RACED_TID = 50           # a closed H2 trade, NULL intent: COUNTED until the planted assign
DASHBOARD_LOGGER = "swing.web.view_models.dashboard"
DEGRADED_RECORD = "hyp-recs panel degraded"


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=110.0, asof=datetime.now(),
                is_stale=False, source="live",
            )
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_open_trade(cfg, ticker: str = "NVDA") -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trades_repo.insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=10, initial_stop=95.0,
                current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
        return int(trade.id)
    finally:
        conn.close()


def _seed_race_world(cfg) -> int:
    """The exit's open trade (NVDA), the hyp-recs candidates (NVDA, AMD --
    AMD survives the open-ticker filter, so ``build_dashboard`` reaches
    ``build_recommendation_progress``), and the closed H2 trade the planted
    assign moves mid-read (the deployment-leg shape ``_seed`` builds)."""
    trade_id = _seed_open_trade(cfg)
    _seed_hyp_recs_fixture(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        _seed(conn, trade_id=RACED_TID, ticker="CCC", label=H2,
              entry_intent=None)
    finally:
        conn.close()
    return trade_id


class _PlantedAssign:
    """Wraps the governed naming read: its FIRST call commits a REAL
    ``assign(...)`` on ``RACED_TID`` over a SECOND connection, then runs the
    original read."""

    def __init__(self, cfg, original) -> None:
        self.cfg = cfg
        self.original = original
        self.fired = 0

    def __call__(self, *args, **kwargs):
        if not self.fired:
            self.fired += 1
            _attest(self.cfg, RACED_TID)
        return self.original(*args, **kwargs)


def _plant_race_in_the_real_builder(cfg, monkeypatch) -> _PlantedAssign:
    import swing.metrics.cohort as cohort_mod

    planted = _PlantedAssign(cfg, cohort_mod.list_intent_excluded_for_cohort)
    # stats.py / hypothesis.py import the naming read from the module at
    # call time, so the module attribute is the seam.
    monkeypatch.setattr(cohort_mod, "list_intent_excluded_for_cohort", planted)
    return planted


def _post_exit(cfg, cfg_path, trade_id: int, shares: str):
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        return client.post(
            f"/trades/{trade_id}/exit",
            data={
                "exit_date": "2026-05-19", "exit_price": "120.50",
                "shares": shares, "reason": "manual", "notes": "",
            },
            headers={"HX-Request": "true"},
        )


def _assert_race_reached_the_containment(caplog, planted) -> None:
    """No WARNING = the planted race was not reached = FAIL."""
    assert planted.fired == 1, "the planted assign never ran"
    records = [r for r in caplog.records
               if r.name == DASHBOARD_LOGGER and r.levelno == logging.WARNING
               and DEGRADED_RECORD in r.getMessage()]
    assert len(records) == 1, [
        (r.name, r.levelname, r.getMessage()) for r in caplog.records]
    assert str(RACED_TID) in records[0].getMessage()
    # The planted write is real and committed: a FRESH connection sees it.
    c = connect(planted.cfg.paths.db_path)
    try:
        assert c.execute(
            "SELECT t.entry_intent, COUNT(a.attestation_id) FROM trades t "
            "LEFT JOIN entry_intent_attestations a ON a.trade_id = t.id "
            "WHERE t.id = ? GROUP BY t.id", (RACED_TID,)).fetchone() == (
                UNINTENDED, 1)
    finally:
        c.close()


def _trade_row(cfg, trade_id: int) -> tuple:
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT state, current_size FROM trades WHERE id = ?",
            (trade_id,)).fetchone()
    finally:
        conn.close()


def test_full_close_exit_raced_rebuild_returns_the_ordinary_success_b22_237(
        seeded_db, monkeypatch, caplog) -> None:
    """The race planted inside the REAL builder during the post-commit
    rebuild: the trade is CLOSED, the response is the ORDINARY full-close
    fragment at 200 (hidden row stub + status strip + soft-warn), and the
    builder's WARNING proves the race reached its containment."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_race_world(cfg)
    _patch_price_cache(monkeypatch)
    planted = _plant_race_in_the_real_builder(cfg, monkeypatch)
    with caplog.at_level(logging.WARNING, logger=DASHBOARD_LOGGER):
        resp = _post_exit(cfg, cfg_path, trade_id, shares="10")
    assert resp.status_code == 200, resp.text
    _assert_race_reached_the_containment(caplog, planted)
    assert f'<tr id="open-position-{trade_id}" style="display:none"></tr>' in resp.text
    assert 'id="status-strip" hx-swap-oob="true"' in resp.text, resp.text
    assert 'id="trade-close-soft-warn" hx-swap-oob="true"' in resp.text, resp.text
    assert "banner-degraded" not in resp.text, resp.text
    assert "cohort read" not in resp.text, resp.text
    state, _size = _trade_row(cfg, trade_id)
    assert state in ("closed", "reviewed"), state


def test_partial_close_exit_raced_rebuild_returns_the_ordinary_success_b22_237(
        seeded_db, monkeypatch, caplog) -> None:
    """The partial-close shape: the trade is durably PARTIALLY closed, the
    response is the ORDINARY re-rendered row + status strip at 200, and the
    builder's WARNING proves the race reached its containment."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_race_world(cfg)
    _patch_price_cache(monkeypatch)
    planted = _plant_race_in_the_real_builder(cfg, monkeypatch)
    with caplog.at_level(logging.WARNING, logger=DASHBOARD_LOGGER):
        resp = _post_exit(cfg, cfg_path, trade_id, shares="4")
    assert resp.status_code == 200, resp.text
    _assert_race_reached_the_containment(caplog, planted)
    assert f'id="open-position-{trade_id}"' in resp.text, resp.text
    assert 'style="display:none"' not in resp.text, resp.text
    assert 'id="status-strip" hx-swap-oob="true"' in resp.text, resp.text
    assert "banner-degraded" not in resp.text, resp.text
    assert "cohort read" not in resp.text, resp.text
    assert _trade_row(cfg, trade_id) == ("partial_exited", 6)


@pytest.mark.parametrize("shares", ["10", "4"])
def test_the_unraced_twin_logs_no_degraded_record_b22_237(
        seeded_db, monkeypatch, caplog, shares) -> None:
    """Boundary twin: the same world with NO planted race -> the same
    ordinary response and NO degraded WARNING, so the WARNING above is
    pinned to the race and not to the world."""
    cfg, cfg_path = seeded_db
    trade_id = _seed_race_world(cfg)
    _patch_price_cache(monkeypatch)
    with caplog.at_level(logging.WARNING, logger=DASHBOARD_LOGGER):
        resp = _post_exit(cfg, cfg_path, trade_id, shares=shares)
    assert resp.status_code == 200, resp.text
    assert not [r for r in caplog.records
                if DEGRADED_RECORD in r.getMessage()], caplog.text
    assert "banner-degraded" not in resp.text, resp.text
