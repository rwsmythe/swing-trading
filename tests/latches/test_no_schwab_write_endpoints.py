"""Arc 21-B: ZERO Schwab WRITE calls, pinned BEHAVIOURALLY (Task 10).

This arc logs intent only. The write path is 21-C, behind an operator-signed L2
endpoint diff.

THE PIN IS PLACED WHERE NAMES CANNOT MATTER. A name-matched mutator list is not
exhaustive -- `submit_order`, or any future write API whose name misses the verb
heuristic, sails straight through while the test passes green (the D21 decay
class). So the PRIMARY enforcement is at the HTTP TRANSPORT, deny-by-default:
ANY non-GET request to the Schwab Trader API host fails, regardless of the
method name that issued it. The remaining layers are nets, and the grep is
explicitly NOT the enforcement.
"""
from __future__ import annotations

import pathlib
import threading
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)
ANCHOR = "2026-07-27"
DERIVATION_SESSION = "2026-07-24"
_HX = {"HX-Request": "true"}
_REPO = pathlib.Path(__file__).resolve().parents[2]

# The EXPLICIT read-only allowlist for the installed `schwabdev.Client`.
#
# DENY-BY-DEFAULT: everything NOT named here is monkeypatched to RAISE, so a
# schwabdev upgrade that adds a write API is covered THE DAY IT LANDS and
# widening the allowlist is a deliberate act with a reviewer. An allowlist of
# WRITES would have the opposite property -- silence would mean permission.
_READ_ONLY_ALLOWLIST = frozenset({
    "account_details", "account_details_all", "account_orders",
    "account_orders_all", "order_details", "transaction_details",
    "transactions", "linked_accounts", "preferences",
    "quote", "quotes", "option_chains", "option_expiration_chain",
    "price_history", "movers", "market_hour", "market_hours",
    "instruments", "instrument_cusip",
    # Not an API call: lifecycle only.
    "close", "update_tokens",
})


class _WriteAttempted(AssertionError):
    """Raised the instant ANYTHING issues a mutating Trader-API request."""


class _DenyByDefaultSession:
    """The transport stub. FAILS ON ANY NON-GET to the Trader API host.

    THE CARVE-OUT IS HOST-SCOPED, NOT VERB-SCOPED, and that distinction is the
    point: an OAuth token refresh is a legitimate POST to the AUTH endpoint, so
    scoping by host lets it through while every Trader-API write still fails. A
    verb-scoped carve-out would have allowed POSTs everywhere.
    """

    trader_host_marker = "/trader/"

    def __init__(self):
        self.attempts: list[tuple[str, str]] = []
        self.headers: dict = {}

    def request(self, method, url, *args, **kwargs):
        self.attempts.append((str(method).upper(), str(url)))
        if (str(method).upper() != "GET"
                and self.trader_host_marker in str(url)):
            raise _WriteAttempted(
                f"a MUTATING Trader-API request escaped 21-B: {method} {url}")

        class _Resp:
            ok = True
            status_code = 200

            @staticmethod
            def json():
                return []

        return _Resp()

    def close(self):
        pass


def _client_with_denying_transport():
    """A REAL `schwabdev.Client` whose transport is the deny-by-default stub.

    Built WITHOUT `__init__` on purpose: schwabdev 3.x's constructor calls
    `update_tokens()` and, on a missing or stale row, enters an INTERACTIVE
    `input()`/browser auth flow -- a headless-process hang. The methods under
    test are the REAL ones, so a renamed or newly-added mutator still routes
    through `_request` -> `_session.request` and is caught there.
    """
    import schwabdev
    client = object.__new__(schwabdev.Client)
    session = _DenyByDefaultSession()
    client._session = session
    client._session_lock = threading.RLock()
    client._base_api_url = "https://api.schwabapi.com"
    client.timeout = 5

    class _Tokens:
        access_token = "stub"

        def update_tokens(self, *_a, **_k):
            # schwabdev's `Client._request` calls this on EVERY request with two
            # positional flags. Accepting them keeps the real request path
            # intact -- a narrower signature would abort BEFORE the transport
            # and turn the write test green for the wrong reason.
            return False

    client.tokens = _Tokens()
    return client, session


class _Holder:
    def __init__(self, client, record):
        self._client = client
        self._record = record

    def borrow(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            self._record.append("borrowed")
            yield self._client

        return _cm()


@pytest.fixture
def frozen_clocks(monkeypatch):
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)


@pytest.fixture
def seeded_db(tmp_path):
    from swing.config import load
    from swing.data.db import ensure_schema
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed(cfg):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, "
            "0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')")
        cid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(900, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
            (f"{DERIVATION_SESSION}T17:30:05", DERIVATION_SESSION, ANCHOR))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(900, 'FTRE', 'watch', 19.20, 18.34, 14.88, 'universe')")
    conn.close()
    # A run stamp is an UPPER BOUND on a close's date, not a proof of it (#30),
    # so the derivation-session bar is what lets the panel offer the form at all.
    import pandas as pd
    cache = pathlib.Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "asof_date": DERIVATION_SESSION, "open": 19.20, "high": 19.20,
        "low": 19.20, "close": 19.20, "volume": 100.0,
    }]).to_parquet(cache / "FTRE.yfinance.parquet")
    return cid


def _anchor_form(cfg, cid):
    from swing.web.view_models.latches import build_latch_panel_vm
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg, now=NOW)
    finally:
        conn.close()
    row = next(r for r in vm.rows if r.candidate_id == cid)
    assert row.prepared_order.offered
    return dict(row.prepared_order.anchor_fields)


def _app(cfg, cfg_path, monkeypatch, client, record):
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(
        vm_mod, "_resolve_schwab_environment", lambda _cfg: "production")
    monkeypatch.setattr(vm_mod, "_resolve_account_hash", lambda _cfg: "HASH")
    app = create_app(cfg, cfg_path)
    app.state.schwab_client_holder = _Holder(client, record)
    return app


def _drive_every_surface(client_http, cfg, cid):
    """GET /latches, POST /latches/orders and EVERY branch of the intent POST."""
    client_http.get("/latches")
    client_http.post("/latches/orders", headers=_HX,
                     data={"view_session_date": ANCHOR})
    base = _anchor_form(cfg, cid)
    branches = [
        base | {"intent_kind": "place"},
        base | {"intent_kind": "decline", "decline_reason": "too extended"},
        {"view_session_date": ANCHOR, "candidate_id": str(cid),
         "intent_kind": "cancel", "actual_broker_order_id": "1001"},
        {"view_session_date": ANCHOR, "candidate_id": str(cid),
         "intent_kind": "attest", "attested_disposition": "chose_not_to_act"},
    ]
    for form in branches:
        client_http.post("/latches/intent", headers=_HX, data=form)
    # ...and the validity branch, which needs the place row to exist first.
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT intent_id FROM latch_order_intents WHERE intent_kind='place'"
        ).fetchone()
    finally:
        conn.close()
    if row is not None:
        import json
        client_http.post("/latches/intent", headers=_HX, data={
            "view_session_date": ANCHOR, "candidate_id": str(cid),
            "intent_kind": "validity",
            "validated_place_intent_id": str(row[0]),
            "validity_outcome": "not_submitted",
            "broker_snapshot_json": json.dumps({
                "broker_snapshot_ts": "2026-07-25T11:58:00",
                "broker_snapshot_branch": "absence",
                "broker_snapshot_digest": "a" * 64,
                "broker_snapshot_session": ANCHOR,
                "attributable_order_count": 0,
                "exact_framework_match_count": 0,
                "indeterminate": False,
            }, sort_keys=True)})


# --- (i) TRANSPORT-LEVEL, DENY-BY-DEFAULT -- the PRIMARY enforcement ------
def test_no_mutating_trader_request_escapes_any_21B_surface(
        seeded_db, monkeypatch, frozen_clocks):
    """THE PRIMARY PIN. Names cannot matter here: the stub fails on ANY non-GET
    to the Trader API host, so a renamed or newly-added mutator is caught
    REGARDLESS OF WHAT IT IS CALLED."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    client, session = _client_with_denying_transport()
    app = _app(cfg, cfg_path, monkeypatch, client, [])
    with TestClient(app) as http:
        _drive_every_surface(http, cfg, cid)
    mutating = [
        (m, u) for m, u in session.attempts
        if m != "GET" and "/trader/" in u
    ]
    assert mutating == []
    # ...AND THE TRANSPORT WAS ACTUALLY REACHED. Without this the assertion
    # above is satisfied by a run in which no Schwab request happened at all --
    # a green pin over a path the test never exercised, which is the vacuity
    # class this arc's own acceptance test fell into.
    assert any("/trader/" in u for _, u in session.attempts), session.attempts


def test_the_transport_stub_actually_TRIPS_on_a_write(seeded_db):
    """THE PAIRED DISCRIMINATOR, and it is not optional: without it the test
    above is satisfied by a stub that never fails at all -- a green pin over a
    dead net. `place_order` is the REAL schwabdev method, so this also proves
    the real write path routes through the transport we are watching."""
    client, session = _client_with_denying_transport()
    with pytest.raises(_WriteAttempted):
        client.place_order("HASH", {"orderType": "LIMIT"})
    assert any(m != "GET" for m, _ in session.attempts)


def test_the_carve_out_is_HOST_scoped_and_not_VERB_scoped(seeded_db):
    """An OAuth token refresh is a legitimate POST -- to the AUTH endpoint, not
    the Trader API. Scoping the carve-out by HOST lets it through while every
    Trader write still fails; scoping it by VERB would have allowed POSTs
    everywhere, which is the hole this test exists to keep closed."""
    _, session = _client_with_denying_transport()
    session.request("POST", "https://api.schwabapi.com/v1/oauth/token")
    with pytest.raises(_WriteAttempted):
        session.request("POST", "https://api.schwabapi.com/trader/v1/accounts")


# --- (i-b) METHOD-LEVEL, deny-by-default -- the SECONDARY net -------------
def test_every_non_allowlisted_schwabdev_callable_is_denied(
        seeded_db, monkeypatch, frozen_clocks):
    """DENY-BY-DEFAULT over the INSTALLED client's public surface. An allowlist
    of WRITES would make silence mean permission; an allowlist of READS means a
    schwabdev upgrade that adds a write API is covered the day it lands."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    client, _ = _client_with_denying_transport()
    denied: list[str] = []
    for name in dir(type(client)):
        if name.startswith("_") or name in _READ_ONLY_ALLOWLIST:
            continue
        if not callable(getattr(type(client), name, None)):
            continue
        denied.append(name)

        def _boom(*_a, _n=name, **_k):
            raise _WriteAttempted(f"21-B called the denied schwabdev API {_n}")

        monkeypatch.setattr(client, name, _boom, raising=False)
    # The allowlist must not have swallowed the whole surface -- otherwise this
    # net is vacuous.
    assert {"place_order", "cancel_order", "replace_order",
            "preview_order"} <= set(denied)
    app = _app(cfg, cfg_path, monkeypatch, client, [])
    with TestClient(app) as http:
        _drive_every_surface(http, cfg, cid)


# --- (ii) SEAM: the intent path never borrows the client -----------------
def test_the_intent_path_makes_ZERO_borrow_calls(
        seeded_db, monkeypatch, frozen_clocks):
    """There is no path from the intent flow to a broker write even in
    principle: the client is never borrowed at all."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    client, _ = _client_with_denying_transport()
    record: list[str] = []
    app = _app(cfg, cfg_path, monkeypatch, client, record)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    with TestClient(app) as http:
        assert http.post(
            "/latches/intent", headers=_HX, data=form).status_code == 200
    assert record == []


# --- (iii) LEDGER: the audit row count is unchanged ----------------------
def test_the_schwab_api_calls_row_count_is_unchanged_across_the_intent_post(
        seeded_db, monkeypatch, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    client, _ = _client_with_denying_transport()
    app = _app(cfg, cfg_path, monkeypatch, client, [])
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}

    def _count():
        conn = connect(cfg.paths.db_path)
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0]
        finally:
            conn.close()

    with TestClient(app) as http:
        before = _count()
        assert http.post(
            "/latches/intent", headers=_HX, data=form).status_code == 200
        assert _count() == before


# --- (iv) the TEXTUAL belt -- explicitly NOT the enforcement -------------
_ARC_FILES = (
    "swing/latches/order_intent.py",
    "swing/latches/classification.py",
    "swing/web/routes/latches.py",
    "swing/web/view_models/latches.py",
    "swing/cli_latches.py",
)
_MUTATORS = ("place_order", "cancel_order", "replace_order", "preview_order")


@pytest.mark.parametrize("name", _MUTATORS)
def test_no_arc_file_names_a_schwab_mutator(name):
    """A CHEAP BELT ONLY. It passes while a RENAMED mutator sails through, which
    is exactly why (i)-(iii) exist and why this is not called the pin."""
    for rel in _ARC_FILES:
        text = (_REPO / rel).read_text(encoding="utf-8")
        assert name not in text, f"{rel} names the Schwab mutator {name}"


# --- (v) the two counters must never be conflated ------------------------
def test_the_bare_name_matched_order_count_appears_nowhere_in_21B(seeded_db):
    """TWO DISTINCT COUNTERS, NAMED APART. `attributable_order_count` drives the
    prompt branch and the multiplicity gate; `exact_framework_match_count`
    drives the agreement wording. Reusing 21-A's single `matched_order_count`
    for both hands an implementer two incompatible meanings -- and routes FTRE's
    real LIMIT 18.89 / 10 sh down the ABSENCE path instead of the divergence
    path. 21-A's `LatchOrderJoin` field keeps its name; every 21-B consumer must
    name WHICH QUESTION it is asking."""
    for rel in ("swing/latches/order_intent.py",
                "swing/latches/classification.py",
                "swing/cli_latches.py",
                "tests/latches/test_order_intent.py",
                "tests/latches/test_classification.py",
                "tests/latches/test_execution_parity.py",
                "tests/web/test_routes/test_latches_intent_route.py",
                "tests/web/test_view_models/test_latch_prepared_order_vm.py"):
        text = (_REPO / rel).read_text(encoding="utf-8")
        assert "matched_order_count" not in text, rel
