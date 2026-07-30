"""The VALIDITY PROMPT UI -- `POST /latches/orders` (Arc 21-B, plan section F.3).

THIS IS THE ONLY SURFACE THAT CAN COLLECT THE MEASUREMENT. Every other piece of
the validity path -- the schema, the model, the handler, the resolver, the
report -- shipped and was green while the operator had no way to REACH it: the
whole branch was exercised only by hand-built HTTP in the tests, so
`intent_kind='validity'` was unreachable in a browser and the agreement rate,
this arc's headline deliverable, had a permanently empty denominator.

So these tests are deliberately END-TO-END through the RENDERED FRAGMENT: they
parse the emitted form, post exactly what it emits, and assert the ledger row.
A test that constructs its own POST would re-create the exact blind spot.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.latches.constants import (
    LATCH_BROKER_SNAPSHOT_KEYS,
    LATCH_VALIDITY_OUTCOMES,
)
from swing.web.app import create_app

# The PLACE is logged in session 2026-07-27; the prompt is rendered in the NEXT
# session, 2026-07-29. The gap is load-bearing for the ABSENCE branch: a prompt
# fired the same evening he logged the order would be asking him about something
# he has not had a session to do yet.
PLACE_NOW = datetime(2026, 7, 25, 12, 0)      # -> action session 2026-07-27
PLACE_ANCHOR = "2026-07-27"
PROMPT_NOW = datetime(2026, 7, 28, 12, 0)     # -> action session 2026-07-29
PROMPT_ANCHOR = "2026-07-29"
DERIVATION_SESSION = "2026-07-24"
_HX = {"HX-Request": "true"}


def _seed(cfg):
    """FTRE's real geometry: pivot 18.34, stop 14.88, cap 18.8902 -> limit 18.89
    with a pullback-regime close, which is the 9-share prepared order."""
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
            (f"{DERIVATION_SESSION}T17:30:05", DERIVATION_SESSION, PLACE_ANCHOR))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(900, 'FTRE', 'watch', 19.20, 18.34, 14.88, 'universe')")
    conn.close()
    return cid


class _Holder:
    """Stands in for the app's SchwabClientHolder (the 18-H.4 borrow seam)."""

    def __init__(self, client):
        self._client = client

    def borrow(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield self._client

        return _cm()


def _order(**over):
    """FTRE's REAL divergent geometry by default: the framework prepared
    LIMIT 18.89 / 9 sh and the order actually resting is LIMIT 18.89 / 10 sh."""
    base = dict(order_id="1001", status="WORKING",
                enter_time="2026-07-27T13:30:00Z", instrument_symbol="FTRE",
                instruction="BUY", quantity=10.0, order_type="LIMIT",
                price=18.89, stop_price=None, duration="GOOD_TILL_CANCEL")
    base.update(over)
    return SchwabOrderResponse(**base)


@pytest.fixture
def clocks(monkeypatch):
    """Both clocks, movable. The fragment requires the posted anchor to BE the
    current action session, so the route clock must move with the VM clock."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod

    class _Clock:
        now = PLACE_NOW

        def set(self, value):
            _Clock.now = value

    clock = _Clock()
    monkeypatch.setattr(vm_mod, "_now", lambda: _Clock.now)
    monkeypatch.setattr(route_mod, "_now", lambda: _Clock.now)
    return clock


def _app(cfg, cfg_path, monkeypatch, *, orders=(), environment="production"):
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(
        vm_mod, "_resolve_schwab_environment", lambda _cfg: environment)
    monkeypatch.setattr(vm_mod, "_resolve_account_hash", lambda _cfg: "HASH")
    monkeypatch.setattr(
        vm_mod, "_fetch_account_orders",
        lambda *a, **k: list(orders))
    app = create_app(cfg, cfg_path)
    app.state.schwab_client_holder = _Holder(object())
    return app


def _anchor_form(cfg, cid, *, now):
    from swing.web.view_models.latches import build_latch_panel_vm
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg, now=now)
    finally:
        conn.close()
    row = next(r for r in vm.rows if r.candidate_id == cid)
    assert row.prepared_order.offered, "the fixture must reach the OFFERED form"
    return dict(row.prepared_order.anchor_fields)


def _log_place(client, cfg, cid):
    form = _anchor_form(cfg, cid, now=PLACE_NOW) | {"intent_kind": "place"}
    r = client.post("/latches/intent", headers=_HX, data=form)
    assert r.status_code == 200, r.text
    return _rows(cfg)[0][0]


def _rows(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT intent_id, intent_kind, validity_outcome, actual_quantity, "
            "actual_limit_price, actual_broker_order_id, "
            "validated_place_intent_id, validity_detail, action_session_date "
            "FROM latch_order_intents ORDER BY intent_id").fetchall()
    finally:
        conn.close()


_INPUT = re.compile(
    r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"[^>]*>")

def _prompt_html(text: str) -> str:
    """The validity-prompt SECTION only, so an assertion cannot pass off the
    rest of the fragment as the prompt."""
    start = text.index('<section class="latch-validity-prompt')
    return text[start:text.index("</section>", start)]


def _form_fields(prompt_html: str) -> dict:
    """Every hidden input the rendered form emits, exactly as a browser would
    submit it.

    `html.unescape` is what the BROWSER does: Jinja autoescapes the quotes
    inside `broker_snapshot_json` to `&#34;` in the attribute, and the browser
    decodes them back before submitting. A test that posted the raw attribute
    text would be testing an escape artefact, not the form.
    """
    fields = {}
    for name, value in _INPUT.findall(prompt_html):
        if name == "validity_outcome":
            continue
        fields[name] = unescape(value)
    return fields


def _radio_values(prompt_html: str) -> set:
    return set(re.findall(
        r'<input type="radio" name="validity_outcome" value="([^"]+)"',
        prompt_html))


def _fragment(client, anchor):
    return client.post("/latches/orders", headers=_HX,
                       data={"view_session_date": anchor})


# ---------------------------------------------------------------------------
# The PRESENCE branch -- and the arc's own worked example
# ---------------------------------------------------------------------------
def test_the_presence_prompt_renders_a_REAL_FORM_a_browser_can_submit(
        seeded_db, monkeypatch, clocks):
    """THE FINDING THIS TASK EXISTS TO CLOSE. The arc shipped the DISPLAY for a
    measurement it could not COLLECT: `latch_orders.html.j2` carried zero
    occurrences of `validity`, `broker_snapshot_json`,
    `validated_place_intent_id` or `intent_kind`, so no operator could ever
    produce a validity row and the agreement denominator was empty forever.

    An `hx-post` FORM is the deliverable -- not a rendered outcome.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    prompt = _prompt_html(html)
    assert 'hx-post="/latches/intent"' in prompt
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in prompt, (
        "without it OriginGuard strict mode 403s the submit -- browser-only")
    assert 'hx-target="this"' in prompt, (
        "hx-target INHERITS from ancestors; without this the swap lands "
        "somewhere unrelated -- browser-only")
    assert not prompt.lstrip().startswith("<tr"), (
        "a fragment leading with <tr> triggers makeFragment's synthetic table "
        "wrap -- browser-only")
    fields = _form_fields(prompt)
    assert fields["intent_kind"] == "validity"
    assert fields["candidate_id"] == str(cid)
    assert fields["view_session_date"] == PROMPT_ANCHOR


def test_the_DIVERGENCE_path_records_BOTH_sides_and_the_delta_comes_from_the_ledger(
        seeded_db, monkeypatch, clocks):
    """THE ARC'S OWN WORKED EXAMPLE, end to end through the RENDERED form
    (R17 CRITICAL). Framework LIMIT 18.89 / 9 sh; actually resting
    LIMIT 18.89 / 10 sh. An exact-match gate renders NOTHING here and the +1
    quantity delta could never reach the ledger.

    The row carries `accepted_by_broker` -- a resting broker order is positive
    acceptance evidence whether or not its quantity matches -- so it ENTERS the
    agreement denominator while FAILING the numerator (R19 MAJOR 7).
    """
    from swing.latches.order_intent import compute_order_delta

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        place_id = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
        assert "quantity 10 vs 9" in prompt, (
            "the prompt must NAME the difference; confirming an order described "
            "only as non-matching is not the same act")
        fields = _form_fields(prompt)
        assert fields["validated_place_intent_id"] == str(place_id)
        r = client.post("/latches/intent", headers=_HX,
                        data=fields | {"validity_outcome": "accepted_by_broker"})
    assert r.status_code == 200, r.text
    rows = _rows(cfg)
    assert len(rows) == 2
    validity = rows[1]
    assert validity[1] == "validity"
    assert validity[2] == "accepted_by_broker"
    assert validity[3] == 10 and validity[4] == 18.89
    assert validity[5] == "1001"
    assert validity[6] == place_id
    # The parent's mandate session, SERVER-COPIED -- never the render anchor.
    assert validity[8] == PLACE_ANCHOR
    # THE DELTA IS COMPUTED FROM THE LEDGER, not from a fixture.
    conn = connect(cfg.paths.db_path)
    try:
        place, actual = conn.execute(
            "SELECT (SELECT framework_quantity FROM latch_order_intents "
            "        WHERE intent_id = ?), actual_quantity "
            "FROM latch_order_intents WHERE intent_id = ?",
            (place_id, validity[0])).fetchone()
    finally:
        conn.close()
    delta = compute_order_delta(
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": place},
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": actual})
    assert delta.quantity_delta == 1
    assert delta.any_difference is True


def test_the_presence_branch_PRESELECTS_accepted_and_offers_the_full_enum(
        seeded_db, monkeypatch, clocks):
    """Presence is DIRECT POSITIVE EVIDENCE, so the framework may pre-select the
    answer. It is a convenience, not an assertion -- no row is written without
    his click, which the no-POST test pins."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    assert _radio_values(prompt) == set(LATCH_VALIDITY_OUTCOMES)
    assert 'value="accepted_by_broker"' in prompt
    checked = re.search(
        r'value="([^"]+)"\s*\n?\s*checked', prompt)
    assert checked is not None and checked.group(1) == "accepted_by_broker"


def test_an_INCOMPLETE_observed_order_may_not_be_logged_as_accepted(
        seeded_db, monkeypatch, clocks):
    """The migration REQUIRES a complete observed side on an accepted row (known
    type, known duration, a limit, a quantity and the broker order id). Offering
    `accepted_by_broker` over an order we could not fully read hands the operator
    a click the ledger then REFUSES -- a dead end rather than a measurement. So
    the option is withheld and the reduction is LABELLED."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration=None)])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    assert _radio_values(prompt) == set(LATCH_VALIDITY_OUTCOMES) - {
        "accepted_by_broker"}
    assert "could not be read completely" in prompt
    assert "checked" not in prompt


# ---------------------------------------------------------------------------
# The ABSENCE branch
# ---------------------------------------------------------------------------
def test_the_absence_prompt_offers_the_enum_MINUS_accepted_with_NOTHING_selected(
        seeded_db, monkeypatch, clocks):
    """ABSENCE is equally consistent with a rejection, a cancel and a
    never-submitted order, so the framework may raise the QUESTION and may NOT
    pre-select an ANSWER.

    "Filled" is deliberately NOT an option (R7 MAJOR 2): it is not in
    `LATCH_VALIDITY_OUTCOMES`, so offering it would force the handler to
    mislabel or discard the answer -- and the fill short-circuit already covers
    that case from data the framework owns.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    assert _radio_values(prompt) == set(LATCH_VALIDITY_OUTCOMES) - {
        "accepted_by_broker"}
    assert "checked" not in prompt
    assert "filled" not in prompt.lower()
    assert "actual_broker_order_id" not in prompt, (
        "the absence branch observed NO order, so it carries no observed side")


def test_an_absence_answer_writes_ONE_row_carrying_the_snapshot_envelope(
        seeded_db, monkeypatch, clocks):
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        place_id = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        fields = _form_fields(_prompt_html(_fragment(client, PROMPT_ANCHOR).text))
        r = client.post("/latches/intent", headers=_HX,
                        data=fields | {"validity_outcome": "rejected_by_broker"})
    assert r.status_code == 200, r.text
    rows = _rows(cfg)
    assert len(rows) == 2
    assert rows[1][2] == "rejected_by_broker"
    assert rows[1][6] == place_id
    envelope = json.loads(rows[1][7])
    assert set(envelope) == set(LATCH_BROKER_SNAPSHOT_KEYS)
    assert envelope["broker_snapshot_branch"] == "absence"
    assert envelope["attributable_order_count"] == 0
    assert envelope["broker_snapshot_session"] == PROMPT_ANCHOR


def test_the_prompt_does_not_fire_in_the_session_the_place_was_logged(
        seeded_db, monkeypatch, clocks):
    """He has not had a session to place it in yet. The ABSENCE branch only."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        html = _fragment(client, PLACE_ANCHOR).text
    assert "latch-validity-prompt" not in html


# ---------------------------------------------------------------------------
# Where the prompt must NOT fire
# ---------------------------------------------------------------------------
def test_an_unavailable_order_book_renders_NO_prompt_in_EITHER_direction(
        seeded_db, monkeypatch, clocks):
    """R8 MAJOR 1. Neither presence nor absence is knowable, and a prompt built
    on an unknown book would invite an answer the operator would reasonably
    infer from the panel's own silence."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[], environment="sandbox")
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "Broker order book UNKNOWN" in html


def test_a_latch_with_NO_place_intent_gets_no_prompt(
        seeded_db, monkeypatch, clocks):
    """There is nothing to validate: the question is about an order he LOGGED."""
    cfg, cfg_path = seeded_db
    _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html


def test_an_already_answered_place_intent_gets_no_second_prompt(
        seeded_db, monkeypatch, clocks):
    """`resolve_execution_outcome_for` has moved off `unknown`, so the question
    is CLOSED. Re-asking it is how an instrument trains its subject to dismiss
    it."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        fields = _form_fields(_prompt_html(_fragment(client, PROMPT_ANCHOR).text))
        client.post("/latches/intent", headers=_HX,
                    data=fields | {"validity_outcome": "not_submitted"})
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html


def test_a_FILL_CLEARED_latch_renders_no_prompt_and_derives_acceptance(
        seeded_db, monkeypatch, clocks):
    """The FILL SHORT-CIRCUIT, and it is structural rather than a second rule:
    the outcome resolves `accepted_by_broker` from the trades ledger, so the
    latch never reaches a prompt. This is the ONE place the framework may answer
    for itself, because the evidence is a real position rather than an absence.
    """
    from swing.latches.classification import (
        governing_intent,
        resolve_execution_outcome_for,
    )
    from swing.latches.models import Latch

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        assert "latch-validity-prompt" in _fragment(client, PROMPT_ANCHOR).text

    # The same latch, cleared by FILL: the resolver stops returning `unknown`,
    # which is the ONLY gate the prompt consults.
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.reader import build_latch_derivation
    conn = connect(cfg.paths.db_path)
    try:
        derivation = build_latch_derivation(conn, cfg, now=PROMPT_NOW)
        latch = next(x for x in derivation.latches
                     if x.identity.candidate_id == cid)
        intents = list_intents_for_latch(conn, candidate_id=cid)
    finally:
        conn.close()
    filled = Latch(**{
        **{f.name: getattr(latch, f.name)
           for f in latch.__dataclass_fields__.values()},
        "state": "filled", "clear_reason": "fill",
        "clear_session": __import__("datetime").date(2026, 7, 28),
        "clear_trade_id": 7, "fill_link_basis": "candidate_id",
    })
    place = governing_intent(intents, "place")
    assert resolve_execution_outcome_for(filled, place, intents) == (
        "accepted_by_broker")


def test_a_MULTIPLICITY_of_attributable_orders_renders_no_prompt(
        seeded_db, monkeypatch, clocks):
    """With two attributable orders there is no unique `order_id`, so the one
    carried into `actual_broker_order_id` would be arbitrary. The fragment
    renders its multiplicity note instead."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(), _order(order_id="1002", quantity=4.0)])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "MULTIPLE ORDERS MATCH THIS MANDATE" in html


def test_an_INDETERMINATE_broker_status_renders_no_prompt(
        seeded_db, monkeypatch, clocks):
    """The broker's own answer is unknown, so the framework may not ask the
    operator to answer for it."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(status="PENDING_CANCEL")])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "ORDER STATUS INDETERMINATE" in html


def test_NO_validity_row_is_ever_written_without_a_POST(
        seeded_db, monkeypatch, clocks):
    """Rendering the prompt is not answering it. Pre-selection is a convenience,
    never an assertion."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _fragment(client, PROMPT_ANCHOR)
        _fragment(client, PROMPT_ANCHOR)
    assert [r[1] for r in _rows(cfg)] == ["place"]


# ---------------------------------------------------------------------------
# The envelope + the digest
# ---------------------------------------------------------------------------
def test_the_emitted_envelope_key_set_EQUALS_what_validity_detail_requires(
        seeded_db, monkeypatch, clocks):
    """Drift between the fragment's emitted set and the row's required set makes
    the audit row UNWRITABLE. Neither site states a count."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        fields = _form_fields(_prompt_html(_fragment(client, PROMPT_ANCHOR).text))
    envelope = json.loads(fields["broker_snapshot_json"])
    assert set(envelope) == set(LATCH_BROKER_SNAPSHOT_KEYS)
    assert envelope["broker_snapshot_branch"] == "presence"
    assert envelope["attributable_order_count"] == 1
    assert envelope["exact_framework_match_count"] == 0, (
        "the resting order is 10 sh against a 9 sh framework order")
    assert envelope["indeterminate"] is False
    assert len(envelope["broker_snapshot_digest"]) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", envelope["broker_snapshot_digest"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                        envelope["broker_snapshot_ts"])


def test_the_digest_CHANGES_when_a_non_matching_order_appears_at_count_zero(
        seeded_db, monkeypatch, clocks):
    """A COUNTS-ONLY digest is IDENTICAL across these two books, so it could not
    tell an answer about one from an answer about the other. And it is UNCHANGED
    across a reload of the same book, or a plain refresh would duplicate the
    ledger row."""
    from swing.latches.orders import to_resting_orders
    from swing.web.view_models.latches import _broker_book_digest

    # The PRODUCTION shape: the fragment digests `to_resting_orders(raw)`, not
    # the raw Schwab payload, so the test feeds it through the same mapper.
    stray = to_resting_orders([_order(order_id="7777", price=12.00,
                                      quantity=1.0)])
    empty = _broker_book_digest([])
    with_stray = _broker_book_digest(stray)
    assert empty != with_stray, (
        "both books have attributable_order_count 0 for the FTRE latch, so a "
        "counts-only digest cannot tell them apart")
    assert _broker_book_digest(stray) == with_stray, "stable across a reload"
    assert _broker_book_digest(to_resting_orders([
        _order(order_id="7777", price=12.50, quantity=1.0)])) != with_stray


def test_a_replayed_identical_answer_writes_ONE_row(
        seeded_db, monkeypatch, clocks):
    """A double-click on the rendered prompt is ONE answer."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        fields = _form_fields(_prompt_html(_fragment(client, PROMPT_ANCHOR).text))
        payload = fields | {"validity_outcome": "not_submitted"}
        first = client.post("/latches/intent", headers=_HX, data=payload)
        second = client.post("/latches/intent", headers=_HX, data=payload)
    assert first.status_code == second.status_code == 200
    assert len([r for r in _rows(cfg) if r[1] == "validity"]) == 1
