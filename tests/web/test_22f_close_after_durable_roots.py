"""22-F T-G2 -- F4 close-after-durable on the web operator-record POST roots
(plan section 8; S-CONTAIN via `swing/web/routes/__init__.py::
close_after_commit`, with `append_close_notice` carrying the notice on a
body-bearing HTML response).

Per root, over the ROOT TABLE below (each row carries its opener `target`,
the name the route resolves AT CALL TIME, read from its source, and `nth`,
the 1-based index of the connection opened through that target whose close
the case fails -- a route that opens a READ connection first names its WRITE
connection):

* G2-a -- the route's SUCCESS path with that connection's `close()` failing
  (`FailingVerbsConn(fail_close=True)`: the real close runs, then the error).
  PRE-FIX: 500 over a durable write.  POST-FIX: the route's own success
  status, a FRESH read shows the write, exactly ONE contained ERROR record
  from the helper, and a body-bearing HTML response carries the notice.
* G2-b -- CONTROL: the route's own 4xx path with that connection open and
  nothing written, the close failing.  BOTH TREES: 500 (nothing durable; the
  bare close is byte-unchanged and the app handler is correct), and nothing
  written.

Did-it-fire (R3-01): every case asserts the failing proxy recorded >= 1
`close()`.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app
from tests._22f_proxies import FailingVerbsConn, patch_conn_opener

_HX = {"HX-Request": "true"}
_NOTICE = ("IS recorded; the database connection could not be closed "
           "cleanly (see the log).")
_HELPER_RECORD = "IS recorded and CLOSING the database connection"


def _scalar(db: Path, sql: str, *params: Any) -> Any:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(sql, params).fetchone()[0]
    finally:
        c.close()


@dataclass
class WebRoot:
    id: str
    target: str
    # seeds the world before the app starts; returns the case's `extra`
    world: Callable[[Config, Any], dict]
    # the success request
    call: Callable[[TestClient, dict], Any]
    success_status: int
    # a FRESH read that changes when the route's write lands
    probe: Callable[[Config, dict], Any]
    body_notice: bool
    nth: int = 1
    # the route's own 4xx path with the connection open (None: declared not
    # constructible, the reason in the row)
    control: Callable[[TestClient, dict], Any] | None = None
    control_nth: int | None = None
    # seeds run with the client open (a world step that is itself a request)
    live_world: Callable[[TestClient, dict], None] | None = None


# ---------------------------------------------------------------- worlds ---

def _no_world(cfg: Config, mp: Any) -> dict:
    return {"db": cfg.paths.db_path}


def _home_world(cfg: Config, mp: Any) -> dict:
    """The config routes WRITE user-config: USERPROFILE and HOME point at the
    test's home (the `_minimal_config` layout: db under home/swing-data)."""
    home = Path(cfg.paths.db_path).parent.parent
    mp.setenv("USERPROFILE", str(home))
    mp.setenv("HOME", str(home))
    return {"db": cfg.paths.db_path}


def _config_payload(floor: str) -> dict:
    return {"account.risk_equity_floor": floor, "web.chase_factor": "0.01",
            "pipeline.chart_top_n_watch": "1", "force": "true"}


def _set_floor_first(tc: TestClient, extra: dict) -> None:
    r = tc.post("/config", data=_config_payload("8500.0"), headers=_HX)
    assert r.status_code in (204, 303), r.text[:300]


def _policy_rows(cfg: Config, extra: dict) -> int:
    return _scalar(extra["db"], "SELECT COUNT(*) FROM risk_policy")


def _snapshots(cfg: Config, extra: dict) -> int:
    return _scalar(extra["db"], "SELECT COUNT(*) FROM account_equity_snapshots")


def _latch_world(cfg: Config, mp: Any) -> dict:
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    from tests.web.test_routes.test_latches_intent_route import (
        NOW,
        _anchor_form,
        _seed,
    )
    mp.setattr(vm_mod, "_now", lambda: NOW)
    mp.setattr(route_mod, "_now", lambda: NOW)
    cid = _seed(cfg)
    return {"db": cfg.paths.db_path,
            "form": _anchor_form(cfg, cid) | {"intent_kind": "place"}}


def _intents(cfg: Config, extra: dict) -> int:
    return _scalar(extra["db"], "SELECT COUNT(*) FROM latch_order_intents")


def _exemplar_world(cfg: Config, mp: Any) -> dict:
    from swing.data.db import connect
    from swing.data.repos import pattern_exemplars as exemplars_repo
    from tests.web.test_routes.test_patterns_exemplars import _make_silver
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eid = exemplars_repo.insert_exemplar(conn, _make_silver("ABC"))
    finally:
        conn.close()
    return {"db": cfg.paths.db_path, "eid": eid}


def _exemplar_decision(cfg: Config, extra: dict) -> str:
    return _scalar(extra["db"], "SELECT final_decision FROM pattern_exemplars "
                   "WHERE id = ?", extra["eid"])


def _evaluation_world(cfg: Config, mp: Any) -> dict:
    from swing.data.db import connect
    from swing.data.repos import pattern_evaluations as evals_repo
    from tests.web.test_routes.test_patterns_review import (
        _make_evaluation,
        _seed_pipeline_run,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_pipeline_run(conn)
            eval_id = evals_repo.insert_evaluation(conn, _make_evaluation(
                pipeline_run_id=run_id, ticker="ABC", pattern_class="vcp"))
    finally:
        conn.close()
    return {"db": cfg.paths.db_path, "eval_id": eval_id}


def _exemplars(cfg: Config, extra: dict) -> int:
    return _scalar(extra["db"], "SELECT COUNT(*) FROM pattern_exemplars")


def _run_row(db: Path, heartbeat: str) -> int:
    c = sqlite3.connect(str(db))
    try:
        cur = c.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token, lease_heartbeat_ts, "
            "last_step_progress_ts, current_step) VALUES "
            "('2026-01-02T09:00:00', 'manual', '2026-01-01', '2026-01-02', "
            "'running', 't-x', ?, ?, 'evaluate')", (heartbeat, heartbeat))
        c.commit()
        return int(cur.lastrowid)
    finally:
        c.close()


def _stale_run_world(cfg: Config, mp: Any) -> dict:
    """A literal timestamp, no clock read: 2026-01-02 is stale against any
    `now` the suite runs at. (The 404 control names an absent run: a
    second `running` row is refused by the one-running-run index.)"""
    return {"db": cfg.paths.db_path,
            "run": _run_row(cfg.paths.db_path, "2026-01-02T09:00:00")}


def _run_state(cfg: Config, extra: dict) -> str:
    return _scalar(extra["db"], "SELECT state FROM pipeline_runs WHERE id = ?",
                   extra["run"])


def _orphan_world(cfg: Config, mp: Any) -> dict:
    from tests.web.test_reconcile_resolve_orphan_route import _seed_orphan
    return {"db": cfg.paths.db_path,
            "did": _seed_orphan(cfg.paths.db_path),
            "resolved_did": _seed_orphan(
                cfg.paths.db_path, resolution="acknowledged_immaterial",
                ticker="ZZZZ")}


def _orphan_resolution(cfg: Config, extra: dict) -> str:
    return _scalar(extra["db"], "SELECT resolution FROM "
                   "reconciliation_discrepancies WHERE discrepancy_id = ?",
                   extra["did"])


def _quiet_prices(mp: Any) -> None:
    from swing.web.price_cache import PriceCache
    mp.setattr(PriceCache, "get_many",
               lambda self, tickers, deadline_seconds, *, executor=None: {})
    mp.setattr(PriceCache, "is_degraded", lambda self: False)


def _open_trade_world(cfg: Config, mp: Any) -> dict:
    from swing.data.db import connect
    from tests.trades.test_exit import _seed_active_trade
    _quiet_prices(mp)
    conn = connect(cfg.paths.db_path)
    try:
        tid = int(_seed_active_trade(conn, ticker="AAPL", current_size=100.0))
    finally:
        conn.close()
    return {"db": cfg.paths.db_path, "tid": tid}


def _current_stop(cfg: Config, extra: dict) -> float:
    return _scalar(extra["db"], "SELECT current_stop FROM trades WHERE id = ?",
                   extra["tid"])


def _closed_trade_world(cfg: Config, mp: Any) -> dict:
    from swing.data.db import connect
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00",
            ), event_ts="2026-04-20T09:30:00")
            for when, action, price in (("2026-04-20T09:30:00", "entry", 10.0),
                                        ("2026-04-25T09:30:00", "exit", 11.5)):
                insert_fill_with_event(conn, Fill(
                    fill_id=None, trade_id=tid, fill_datetime=when,
                    action=action, quantity=10.0, price=price,
                    reason="manual" if action == "exit" else None,
                ), event_ts=when)
            conn.execute("UPDATE trades SET state='closed' WHERE id=?", (tid,))
    finally:
        conn.close()
    return {"db": cfg.paths.db_path, "tid": tid}


def _reviewed_at(cfg: Config, extra: dict) -> Any:
    return _scalar(extra["db"], "SELECT reviewed_at FROM trades WHERE id = ?",
                   extra["tid"])


_REVIEW_FORM = {
    "entry_grade": "C", "management_grade": "B", "exit_grade": "B",
    "disqualifying_process_violation": "false", "mistake_tags": ["CHASED"],
    "realized_R_if_plan_followed": "2.0", "mistake_cost_confidence": "medium",
    "lesson_learned": "Wait for the breakout.",
}


def _managing_trade_world(cfg: Config, mp: Any) -> dict:
    from swing.data.db import connect
    from tests.web.test_daily_management_event_route import _seed_trade
    conn = connect(cfg.paths.db_path)
    try:
        _seed_trade(conn, trade_id=1)
    finally:
        conn.close()
    return {"db": cfg.paths.db_path}


def _event_form(**over: Any) -> dict:
    data = {"stop_changed": "0", "action_taken": "hold",
            "rule_violation_suspected": "0", "emotional_state": ["calm"],
            "created_at": "2026-05-07T18:00:00", "review_date": "2026-05-07",
            "data_asof_session": "2026-05-07",
            "mfe_mae_precision_level": "daily_approximate"}
    data.update(over)
    return data


def _event_logs(cfg: Config, extra: dict) -> int:
    return _scalar(extra["db"], "SELECT COUNT(*) FROM daily_management_records "
                   "WHERE trade_id = 1 AND record_type = 'event_log'")


def _watchlist_world(cfg: Config, mp: Any) -> dict:
    from tests.web.test_routes.test_watchlist_pin_route import _seed_entry
    _seed_entry(cfg, "AAAA")
    _quiet_prices(mp)
    return {"db": cfg.paths.db_path}


def _pin_note(cfg: Config, extra: dict) -> Any:
    return _scalar(extra["db"], "SELECT pin_note FROM watchlist "
                   "WHERE ticker = 'AAAA'")


# ------------------------------------------------------------ root table ---

ROOTS: list[WebRoot] = [
    WebRoot(
        id="account-snapshot", target="swing.web.routes.account.open_connection",
        world=_no_world,
        call=lambda tc, x: tc.post("/account/snapshot", headers=_HX,
                                   data={"equity_dollars": "1300"}),
        success_status=204, probe=_snapshots, body_notice=False,
        # the route's FIRST connection is a banner-count READ; the write is #2
        nth=2,
        control=lambda tc, x: tc.post("/account/snapshot", headers=_HX,
                                      data={"equity_dollars": "0"}),
    ),
    WebRoot(
        id="config-save", target="swing.web.routes.config.open_connection",
        world=_home_world,
        call=lambda tc, x: tc.post("/config", headers=_HX,
                                   data=_config_payload("8500.0")),
        success_status=204, probe=_policy_rows, body_notice=False,
        # No G2-b: the override is written BEFORE the cascade connection
        # opens (every 4xx returns before it), so that connection never lives
        # with nothing durable.
    ),
    WebRoot(
        id="config-reset", target="swing.web.routes.config.open_connection",
        world=_home_world, live_world=_set_floor_first,
        call=lambda tc, x: tc.post("/config/reset/account.risk_equity_floor",
                                   headers=_HX),
        success_status=204, probe=_policy_rows, body_notice=False,
        # No G2-b: as `/config` (the override is deleted first).
    ),
    WebRoot(
        id="latches-intent", target="swing.web.routes.latches.connect",
        world=_latch_world,
        call=lambda tc, x: tc.post("/latches/intent", headers=_HX,
                                   data=x["form"]),
        success_status=200, probe=_intents, body_notice=True,
        control=lambda tc, x: tc.post(
            "/latches/intent", headers=_HX,
            data=x["form"] | {"framework_limit_price": "17.00"}),
    ),
    WebRoot(
        id="patterns-exemplar-action",
        target="swing.web.routes.patterns.connect", world=_exemplar_world,
        call=lambda tc, x: tc.post(f"/patterns/exemplars/{x['eid']}/action",
                                   headers=_HX, data={"action": "reject"}),
        success_status=204, probe=_exemplar_decision, body_notice=False,
        control=lambda tc, x: tc.post("/patterns/exemplars/99999/action",
                                      headers=_HX, data={"action": "reject"}),
    ),
    WebRoot(
        id="patterns-review", target="swing.web.routes.patterns.connect",
        world=_evaluation_world,
        call=lambda tc, x: tc.post(f"/patterns/{x['eval_id']}/review",
                                   headers=_HX, data={"decision": "watch"}),
        success_status=204, probe=_exemplars, body_notice=False,
        control=lambda tc, x: tc.post("/patterns/99999/review", headers=_HX,
                                      data={"decision": "watch"}),
    ),
    WebRoot(
        id="pipeline-force-clear", target="swing.web.routes.pipeline.connect",
        world=_stale_run_world,
        call=lambda tc, x: tc.post(f"/pipeline/force-clear/{x['run']}",
                                   headers=_HX),
        success_status=200, probe=_run_state, body_notice=True,
        control=lambda tc, x: tc.post("/pipeline/force-clear/99999",
                                      headers=_HX),
    ),
    WebRoot(
        id="reconcile-resolve",
        target="swing.web.routes.reconcile.open_connection",
        world=_orphan_world,
        call=lambda tc, x: tc.post(
            f"/reconcile/discrepancy/{x['did']}/resolve", headers=_HX,
            data={"resolution_reason": "Journaled SPCX IPO shares."}),
        success_status=204, probe=_orphan_resolution, body_notice=False,
        control=lambda tc, x: tc.post(
            f"/reconcile/discrepancy/{x['resolved_did']}/resolve",
            headers=_HX, data={"resolution_reason": "again"}),
    ),
    WebRoot(
        id="trades-stop", target="swing.web.routes.trades.connect",
        world=_open_trade_world,
        call=lambda tc, x: tc.post(f"/trades/{x['tid']}/stop", headers=_HX,
                                   data={"new_stop": "9.50",
                                         "rationale": "trail-10ma"}),
        success_status=200, probe=_current_stop, body_notice=True,
        control=lambda tc, x: tc.post("/trades/99999/stop", headers=_HX,
                                      data={"new_stop": "9.50",
                                            "rationale": "trail-10ma"}),
    ),
    WebRoot(
        id="trades-review", target="swing.data.db.connect",
        world=_closed_trade_world,
        call=lambda tc, x: tc.post(f"/trades/{x['tid']}/review", headers=_HX,
                                   data=_REVIEW_FORM, follow_redirects=False),
        success_status=204, probe=_reviewed_at, body_notice=False,
        control=lambda tc, x: tc.post("/trades/99999/review", headers=_HX,
                                      data=_REVIEW_FORM,
                                      follow_redirects=False),
    ),
    WebRoot(
        id="trades-daily-management-event",
        target="swing.web.routes.trades.connect", world=_managing_trade_world,
        call=lambda tc, x: tc.post("/trades/1/daily-management/event",
                                   headers=_HX, data=_event_form()),
        success_status=204, probe=_event_logs, body_notice=False,
        control=lambda tc, x: tc.post(
            "/trades/1/daily-management/event", headers=_HX,
            data=_event_form(stop_changed="1", action_taken="move_stop",
                             action_reason="breakout_confirmed")),
    ),
    WebRoot(
        id="watchlist-pin", target="swing.web.routes.watchlist.open_connection",
        world=_watchlist_world,
        call=lambda tc, x: tc.post("/watchlist/AAAA/pin", headers=_HX,
                                   data={"pinned": "on",
                                         "pin_note": "future breakout"}),
        success_status=200, probe=_pin_note, body_notice=True,
        control=lambda tc, x: tc.post("/watchlist/ZZZZ/pin", headers=_HX,
                                      data={"pinned": "on"}),
    ),
]

_CONTROLLED = [r for r in ROOTS if r.control is not None]


def _fail_nth_close(monkeypatch, target: str, nth: int) -> list:
    count = {"n": 0}

    def _factory(real):
        count["n"] += 1
        return FailingVerbsConn(real, fail_close=(count["n"] == nth))
    return patch_conn_opener(monkeypatch, target, _factory)


def _helper_records(caplog) -> list:
    return [r for r in caplog.records if r.levelno == logging.ERROR
            and _HELPER_RECORD in r.getMessage()]


@pytest.mark.parametrize("root", ROOTS, ids=[r.id for r in ROOTS])
def test_G2a_success_with_close_failure_is_the_routes_own_success(
        root: WebRoot, seeded_db: tuple[Config, Path], monkeypatch, caplog):
    cfg, cfg_path = seeded_db
    extra = root.world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        if root.live_world is not None:
            root.live_world(tc, extra)
        before = root.probe(cfg, extra)
        built = _fail_nth_close(monkeypatch, root.target, root.nth)
        with caplog.at_level(logging.ERROR):
            resp = root.call(tc, extra)
    assert len(built) >= root.nth
    assert built[root.nth - 1].calls["close"] >= 1  # did-it-fire
    assert resp.status_code == root.success_status, (
        resp.status_code, resp.text[:600])
    assert root.probe(cfg, extra) != before  # durable (fresh read)
    assert len(_helper_records(caplog)) == 1
    if root.body_notice:
        assert _NOTICE in resp.text


@pytest.mark.parametrize("root", _CONTROLLED, ids=[r.id for r in _CONTROLLED])
def test_G2b_control_4xx_with_close_failure_stays_a_500(
        root: WebRoot, seeded_db: tuple[Config, Path], monkeypatch, caplog):
    cfg, cfg_path = seeded_db
    extra = root.world(cfg, monkeypatch)
    nth = root.control_nth or root.nth
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        if root.live_world is not None:
            root.live_world(tc, extra)
        before = root.probe(cfg, extra)
        built = _fail_nth_close(monkeypatch, root.target, nth)
        with caplog.at_level(logging.ERROR):
            resp = root.control(tc, extra)
    assert len(built) >= nth
    assert built[nth - 1].calls["close"] >= 1  # did-it-fire
    assert resp.status_code == 500, (resp.status_code, resp.text[:600])
    assert root.probe(cfg, extra) == before
    assert _helper_records(caplog) == []


def test_append_close_notice_escapes_and_keeps_the_status():
    """The notice carrier: `None` is the identity; a notice is HTML-escaped
    and appended, and the status survives."""
    from fastapi.responses import HTMLResponse

    from swing.web.routes import append_close_notice
    resp = HTMLResponse("<p>row</p>", status_code=200)
    assert append_close_notice(resp, None) is resp
    out = append_close_notice(HTMLResponse("<p>row</p>", status_code=409),
                              "The <x> IS recorded")
    assert out.status_code == 409
    assert out.body.decode("utf-8") == (
        '<p>row</p><div class="close-notice" role="alert">'
        'The &lt;x&gt; IS recorded</div>')



def test_stop6_interrupt_at_the_close_is_not_answered_with_the_success_body(
        seeded_db: tuple[Config, Path], monkeypatch, caplog):
    """STOP-6 (CHARC): an INTERRUPT at the close after the pin committed is
    the operator's stop signal -- re-raised BARE out of the route, so the
    route's success body is NOT built or returned (the renderer after the
    close is a counting wrapper: zero calls); the helper's record names the
    interrupt; the write is durable (fresh read).

    The route function is called DIRECTLY, not through `TestClient`: an
    interrupt escaping into the client's event-loop portal kills the portal
    thread's loop and hangs the client's shutdown (measured), which is the
    TEST HARNESS's limit, not the route's -- the server's own interrupt
    handling owns a propagated interrupt in production."""
    from types import SimpleNamespace

    from fastapi.responses import HTMLResponse

    import swing.web.routes.watchlist as watchlist_routes
    from tests._22f_proxies import CountingWrapper

    root = next(r for r in ROOTS if r.id == "watchlist-pin")
    cfg, _cfg_path = seeded_db
    extra = root.world(cfg, monkeypatch)
    before = root.probe(cfg, extra)

    class _InterruptOnClose(FailingVerbsConn):
        def close(self) -> None:
            self.calls["close"] += 1
            self._real.close()
            raise KeyboardInterrupt("planted interrupt on close")

    built = patch_conn_opener(monkeypatch, root.target, _InterruptOnClose)
    render = CountingWrapper(lambda *_a, **_k: HTMLResponse("success body"))
    monkeypatch.setattr(watchlist_routes, "_render_expanded_row", render)
    request = SimpleNamespace(app=SimpleNamespace(
        state=SimpleNamespace(cfg=cfg)))
    returned: list = []
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KeyboardInterrupt,
                           match="planted interrupt on close"):
            returned.append(watchlist_routes.watchlist_pin(
                request, "AAAA", pinned="on", pin_note="future breakout"))
    assert len(built) == 1 and built[0].calls["close"] == 1  # did-it-fire
    assert render.calls == 0  # nothing after the close ran
    assert returned == []  # no success body was returned
    records = _helper_records(caplog)
    assert len(records) == 1
    assert "KeyboardInterrupt" in records[0].getMessage()
    assert root.probe(cfg, extra) != before  # durable (fresh read)
