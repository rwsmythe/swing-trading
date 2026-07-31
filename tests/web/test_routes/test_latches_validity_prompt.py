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


def _write_archive_bars(cfg, rows, ticker="FTRE"):
    """Shape-A OHLCV archive bars for `ticker`, as `(iso_session, close)`.

    THE ARCHIVE IS THE ONLY READ-SIDE SOURCE THAT DATES A CLOSE PER ROW, and
    only a close it dates to the derivation session may pick the mandate form --
    a run stamp is an upper bound, not a proof (#30). Without the bar the form
    is correctly WITHHELD and there is no prepared order to validate.
    """
    from pathlib import Path

    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ]).to_parquet(cache / f"{ticker.upper()}.yfinance.parquet")


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
    _write_archive_bars(cfg, [(DERIVATION_SESSION, 19.20)])
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
    for tag in re.findall(r"<input[^>]*>", prompt_html):
        if 'type="radio"' in tag:
            # A radio is an OPTION, not a submitted default: an unchecked group
            # sends nothing, so folding one in here would fabricate an answer
            # the browser would not have sent.
            continue
        found = _INPUT.findall(tag)
        if not found:
            continue
        name, value = found[0]
        fields[name] = unescape(value)
    return fields


def _clone_place(cfg, place_id: int) -> int:
    """A SECOND `place` row for the same latch, copied off the first.

    Raw SQL rather than a second form POST: the prepared-order form is
    legitimately WITHHELD in the prompt session, and a test that needed the form
    to be offered would be testing the fixture rather than the displacement.
    """
    conn = connect(cfg.paths.db_path)
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(latch_order_intents)").fetchall()
            if r[1] != "intent_id"]
        row = dict(zip(cols, conn.execute(
            f"SELECT {', '.join(cols)} FROM latch_order_intents "
            "WHERE intent_id = ?", (place_id,)).fetchone(), strict=True))
        row["idempotency_key"] = "cloned-place"
        row["recorded_ts"] = "2026-07-29T23:59:59"
        with conn:
            cur = conn.execute(
                f"INSERT INTO latch_order_intents ({', '.join(cols)}) VALUES "
                f"({', '.join('?' * len(cols))})",
                tuple(row[c] for c in cols))
        return int(cur.lastrowid)
    finally:
        conn.close()


def _form_html(prompt_html: str, css_class: str) -> str:
    """ONE named form out of the prompt, so an assertion about the confirm form
    cannot be satisfied by the other one."""
    start = prompt_html.index(css_class)
    return prompt_html[prompt_html.rindex("<form", 0, start):
                       prompt_html.index("</form>", start)]


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


def test_the_presence_branch_offers_TWO_WRITABLE_FORMS_not_one_unwritable_one(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R6 MAJOR -- this dispatch's own signature defect reappearing
    inside the fix for it.

    The model and the migration BOTH require that a NON-accepted validity row
    carry no observed order at all ("an outcome and its evidence must not be able
    to disagree"). A single radio group emitting the observed side alongside all
    four outcomes was therefore UNWRITABLE for three of them: every
    `rejected_by_broker` / `not_submitted` / `unknown` click 400d against the
    ledger contract, and the incomplete-observation branch -- which offers ONLY
    those three -- was unwritable for every click it had.

    So the observed side rides on its OWN confirm form and the three
    non-accepted answers ride on a second form carrying none of it. PRESENCE is
    still direct positive evidence, so the framework still offers a one-click
    CONFIRM; it still asserts nothing, because nothing is written without a POST.

    THE END-TO-END POST IS THE LOAD-BEARING HALF: a rendering assertion alone is
    exactly what let the unwritable form ship.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
        confirm = _form_html(prompt, "latch-validity-confirm")
        other = _form_html(prompt, "latch-validity-other")
        assert _form_fields(confirm)["validity_outcome"] == "accepted_by_broker"
        assert _form_fields(confirm)["actual_broker_order_id"] == "1001"
        assert _radio_values(other) == set(LATCH_VALIDITY_OUTCOMES) - {
            "accepted_by_broker"}
        assert "actual_broker_order_id" not in other, (
            "a non-accepted validity row may carry NO observed order")
        r = client.post("/latches/intent", headers=_HX,
                        data=_form_fields(other) | {
                            "validity_outcome": "not_submitted"})
        assert r.status_code == 200, r.text
    rows = [row for row in _rows(cfg) if row[1] == "validity"]
    assert [row[2] for row in rows] == ["not_submitted"]
    assert rows[0][5] is None, "no observed side on a non-accepted answer"


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


def test_an_ANSWERED_prompt_becomes_a_CORRECTION_control_and_the_LATEST_governs(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R6 MAJOR. Suppressing the form the moment ANY outcome was
    recorded left an erroneous answer uncorrectable through the browser, so the
    flattering one stayed governing -- and the append-only correction path the
    resolver explicitly supports became a handler capability the operator could
    never use. RD's ruling 3: the governing answer is his LAST.

    It renders as a CORRECTION, not as the question asked again -- a recurring
    question on a settled cell is what trains the dismissal reflex.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.classification import (
        governing_intent,
        resolve_execution_outcome_for,
    )
    from swing.latches.reader import build_latch_derivation

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        first = _form_fields(_form_html(
            _prompt_html(_fragment(client, PROMPT_ANCHOR).text),
            "latch-validity-other"))
        client.post("/latches/intent", headers=_HX,
                    data=first | {"validity_outcome": "not_submitted"})
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
        assert "CORRECT THE RECORDED OUTCOME" in prompt
        assert "not_submitted" in prompt, "it names what it is correcting"
        second = _form_fields(_form_html(prompt, "latch-validity-other"))
        assert second["prior_intent_id"] != first["prior_intent_id"], (
            "the correction carries the row that NOW governs, which is what "
            "keys it apart from the answer it corrects")
        r = client.post("/latches/intent", headers=_HX,
                        data=second | {"validity_outcome": "rejected_by_broker"})
    assert r.status_code == 200, r.text
    assert [row[2] for row in _rows(cfg) if row[1] == "validity"] == [
        "not_submitted", "rejected_by_broker"]
    conn = connect(cfg.paths.db_path)
    try:
        latch = next(x for x in build_latch_derivation(
            conn, cfg, now=PROMPT_NOW).latches
            if x.identity.candidate_id == cid)
        intents = list_intents_for_latch(conn, candidate_id=cid)
    finally:
        conn.close()
    assert resolve_execution_outcome_for(
        latch, governing_intent(intents, "place"), intents) == (
        "rejected_by_broker")


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


# ---------------------------------------------------------------------------
# Codex exec R7 -- the CONFIRM control must mirror the ledger contract, the
# decision family resolves once, and a failed collector is never silent.
# ---------------------------------------------------------------------------
def test_a_STOP_LIMIT_with_no_trigger_gets_NO_confirm_button(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R7 MAJOR. The completeness predicate did not mirror the
    accepted-row contract's STOP-LEG rule, so a STOP_LIMIT with no stop trigger
    rendered the CONFIRM button and `LatchOrderIntent.__post_init__` then refused
    the POST -- a control that renders and cannot be submitted, which is the
    exact class this dispatch exists to close.

    A partial mirror is worse than none: it moves the refusal from the render,
    where it is explainable, to the click, where it is a dead end.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    # Attributable via its LIMIT leg at the zone cap, but typed STOP_LIMIT with
    # no trigger -- a shape the accepted-row contract forbids.
    broken = _order(order_type="STOP_LIMIT", stop_price=None, price=18.89)
    app = _app(cfg, cfg_path, monkeypatch, orders=[broken])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    assert "latch-validity-confirm" not in prompt
    assert "could not be read completely" in prompt
    assert _radio_values(prompt) == set(LATCH_VALIDITY_OUTCOMES) - {
        "accepted_by_broker"}


def test_a_LIMIT_carrying_a_stop_leg_gets_NO_confirm_button(
        seeded_db, monkeypatch, clocks):
    """The other half of the same contract, and the FTRE-rejected shape: an
    accepted LIMIT must carry NO stop leg."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(order_type="LIMIT", stop_price=18.34)])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    assert "latch-validity-confirm" not in prompt


def test_a_DECLINE_superseding_the_place_STOPS_the_validity_question(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R7 MAJOR. The place/decline recency ruling was applied in the
    classifier and NOT propagated here, so after `place -> later decline` the
    panel kept asking about the order he had since declined. `place` and
    `decline` are one question; the current cycle follows whichever he chose
    LAST, and the displaced place becomes the report's labelled earlier cycle.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        assert "latch-validity-prompt" not in _fragment(client, PLACE_ANCHOR).text
        form = _anchor_form(cfg, cid, now=PLACE_NOW) | {
            "intent_kind": "decline", "decline_reason": "changed my mind",
            "prior_intent_id": str(_rows(cfg)[0][0])}
        assert client.post(
            "/latches/intent", headers=_HX, data=form).status_code == 200
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html


def test_a_FAILED_prompt_collector_SAYS_SO_instead_of_looking_like_no_question(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R7 MAJOR. Every prompt seam degrades rather than 500s (A6),
    but a SILENT degrade makes "the question could not be built" visually
    identical to "there is no question here" -- and the consequence of the first
    is an agreement denominator that stays empty for a reason nobody can see.
    Degrading silently on this surface is the arc's own failure mode."""
    import swing.web.view_models.latches as vm_mod

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)

        def _boom(*a, **k):
            raise RuntimeError("the order book row is malformed")

        monkeypatch.setattr(vm_mod, "_validity_prompt_for", _boom)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "COULD NOT BE BUILT" in html
    assert "FTRE" in html


# ---------------------------------------------------------------------------
# Codex exec R8
# ---------------------------------------------------------------------------
def test_a_MISPRICED_resting_order_reaches_the_PRESENCE_branch(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R8 MAJOR, and the sharpest finding of the chain: the ledger
    could record a QUANTITY divergence and could NEVER record a PRICE one.

    21-A attributes an order to a latch by its FROZEN PRICES, so a real resting
    `LIMIT 18.88` against an `18.89` mandate matched NO latch, travelled only as
    a stray, and routed the prompt down the ABSENCE branch -- where no
    `accepted_by_broker` row can be written and no `actual_limit_price` is ever
    captured. `limit_price_differs` was therefore unreachable through the UI, in
    the one metric this instrument most exists to compute.

    A UNIQUE stray is now offered as the candidate, and the prompt SAYS it
    matches no mandate's frozen prices rather than pretending to recognise it.
    """
    from swing.latches.order_intent import compute_order_delta

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    mispriced = _order(order_id="2002", price=18.88, quantity=9.0)
    app = _app(cfg, cfg_path, monkeypatch, orders=[mispriced])
    with TestClient(app) as client:
        place_id = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
        assert "latch-validity-presence" in prompt
        assert "matches NO mandate" in prompt
        assert "limit 18.88 vs 18.89" in prompt, "it NAMES the price difference"
        confirm = _form_fields(_form_html(prompt, "latch-validity-confirm"))
        r = client.post("/latches/intent", headers=_HX, data=confirm)
    assert r.status_code == 200, r.text
    row = [x for x in _rows(cfg) if x[1] == "validity"][0]
    assert row[2] == "accepted_by_broker" and row[4] == 18.88
    assert row[6] == place_id
    delta = compute_order_delta(
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9},
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": row[4], "quantity": 9})
    assert delta.limit_price_delta == -0.01 and delta.any_difference is True


def test_AMBIGUOUS_attribution_WITHHOLDS_the_prompt_WITH_a_visible_reason(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R8 MAJOR. Withholding is right -- putting an arbitrary
    `order_id` into an audit row is not -- but a bare withholding was
    INDISTINGUISHABLE from there being no question at all, and the multiplicity
    note that would have explained it is generated for LIVE latches only."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[
        _order(order_id="3001", price=18.88),
        _order(order_id="3002", price=18.70)])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "THE VALIDITY QUESTION IS WITHHELD" in html
    assert "none is unambiguously it" in html


def test_a_FRACTIONAL_broker_quantity_is_UNKNOWN_and_never_truncated(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R8 MAJOR. `int(10.9)` truncates to 10, and a framework
    quantity of 10 would then AGREE with a 10.9-share order -- the instrument
    fabricating an agreement out of a divergence, in the metric it exists to
    compute. Truncating measurement evidence is never the conservative choice,
    and unknown is never agreement, so the CONFIRM control is withheld."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order(quantity=10.9)])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    assert "latch-validity-confirm" not in prompt
    assert "could not be read completely" in prompt


def test_a_DISPLACED_cycles_answer_stays_correctable_DOWNWARD(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R9 MAJOR. Once P1 is displaced by P2, its validity answer left
    the panel entirely -- so an erroneous, FLATTERING `accepted_by_broker` on P1
    would govern that cycle forever while the handler supported per-parent
    corrections all along.

    BOUNDED, AND THE BOUND IS HONEST: only the non-accepted outcomes are
    offered, because re-asserting acceptance requires a COMPLETE observed side
    and nothing can reconstruct the order book as it stood for a displaced
    cycle. The direction that matters -- correcting a flattering acceptance
    DOWNWARD -- is open; the one that would require inventing evidence is not.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        confirm = _form_fields(_form_html(
            _prompt_html(_fragment(client, PROMPT_ANCHOR).text),
            "latch-validity-confirm"))
        client.post("/latches/intent", headers=_HX, data=confirm)
        # A SECOND place cycle displaces P1. Written directly, because the
        # prepared-order form is legitimately WITHHELD in the prompt session
        # (no close is dated its derivation session) and the subject here is the
        # correction control, not the second cycle's own form.
        _clone_place(cfg, p1)
        html = _fragment(client, PROMPT_ANCHOR).text
        assert f"place intent {p1}" in html
        assert "correctable DOWNWARD" in html
        displaced = next(
            block for block in html.split('<section class="latch-validity-prompt')
            if f"place intent {p1}" in block)
        fields = _form_fields(_form_html(displaced, "latch-validity-other"))
        assert fields["validated_place_intent_id"] == str(p1)
        assert "accepted_by_broker" not in _radio_values(displaced)
        r = client.post("/latches/intent", headers=_HX,
                        data=fields | {"validity_outcome": "not_submitted"})
    assert r.status_code == 200, r.text
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.classification import resolve_execution_outcome_for
    from swing.latches.reader import build_latch_derivation
    conn = connect(cfg.paths.db_path)
    try:
        latch = next(x for x in build_latch_derivation(
            conn, cfg, now=PROMPT_NOW).latches
            if x.identity.candidate_id == cid)
        intents = list_intents_for_latch(conn, candidate_id=cid)
    finally:
        conn.close()
    p1_row = next(i for i in intents if i.intent_id == p1)
    assert resolve_execution_outcome_for(latch, p1_row, intents) == (
        "not_submitted"), "the flattering acceptance no longer governs P1"


def test_a_CHILDLESS_displaced_cycle_gets_a_FIRST_ANSWER_form(
        seeded_db, monkeypatch, clocks):
    """ITEM 2 -- RD's ruling, 2026-07-30. The displaced cycle MAY NOT VANISH.

    PRE-FIX the displaced-cycle control was emitted only for a cycle that
    ALREADY carried an answer, so a place with NO validity child was skipped
    entirely: nothing on any surface could ever answer it. A FAILED FIRST
    ATTEMPT therefore stayed permanently unmeasured while its ACCEPTED RETRY
    supplied the scored agreement -- a SUBSTITUTION OF A SUCCESS FOR A FAILURE,
    which is worse than a null, and it fails in the flattering direction.

    THE FORM IS DRIVEN END TO END: parsed from the rendered fragment, posted
    exactly as emitted, and the resolver is asked what now governs P1. A test
    building its own POST would re-create the blind spot this file exists for --
    the handler ALWAYS accepted a first answer for an earlier parent; what was
    missing was any way to reach it.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        # NO validity answer for P1 at all -- it is displaced while childless.
        _clone_place(cfg, p1)
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
        assert f"place intent {p1}" in html
        assert "NEVER ANSWERED" in html
        displaced = next(
            block for block in html.split('<section class="latch-validity-prompt')
            if f"place intent {p1}" in block)
        assert "CORRECT THE RECORDED OUTCOME" not in displaced, (
            "there is no recorded outcome to correct -- this is a FIRST answer")
        fields = _form_fields(_form_html(displaced, "latch-validity-other"))
        assert fields["validated_place_intent_id"] == str(p1)
        r = client.post("/latches/intent", headers=_HX,
                        data=fields | {"validity_outcome": "rejected_by_broker"})
    assert r.status_code == 200, r.text
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.classification import resolve_execution_outcome_for
    from swing.latches.reader import build_latch_derivation
    conn = connect(cfg.paths.db_path)
    try:
        latch = next(x for x in build_latch_derivation(
            conn, cfg, now=PROMPT_NOW).latches
            if x.identity.candidate_id == cid)
        intents = list_intents_for_latch(conn, candidate_id=cid)
    finally:
        conn.close()
    p1_row = next(i for i in intents if i.intent_id == p1)
    assert resolve_execution_outcome_for(latch, p1_row, intents) == (
        "rejected_by_broker"), (
        "the failed first attempt is now MEASURED rather than substituted for")


def test_a_place_DECLINED_gets_NO_first_answer_form_only_the_report_category(
        seeded_db, monkeypatch, clocks):
    """THE RULING BOUNDARY BETWEEN ITEM 2 AND THE EARLIER R7 RULING, pinned so
    neither can be silently widened over the other.

    RD's item-2 harm is a failed first attempt going unmeasured WHILE ITS
    ACCEPTED RETRY SUPPLIES THE SCORED AGREEMENT -- a success standing in for a
    failure. After `place -> decline` there is no current place, so nothing is
    standing in for it, and R7 is explicit that `place` and `decline` are ONE
    question: the panel must stop asking about the order he has since declined.

    Representation for THIS cycle is therefore the report's named
    `displaced_unanswerable` count, not a panel control. Silence on the panel is
    permitted here ONLY because the report is not silent.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        form = _anchor_form(cfg, cid, now=PLACE_NOW) | {
            "intent_kind": "decline", "decline_reason": "changed my mind",
            "prior_intent_id": str(_rows(cfg)[0][0])}
        assert client.post(
            "/latches/intent", headers=_HX, data=form).status_code == 200
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "NEVER ANSWERED" not in html


def test_the_validity_radio_group_is_REQUIRED_so_a_blank_submit_cannot_erase_it(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R10 MAJOR. Nothing is pre-selected -- absence may not assert an
    answer -- so without native `required` validation "Record this outcome"
    submits no outcome at all, the 400 swaps OVER the form via `outerHTML`, and
    the collector the operator needs is GONE from the page. He then has to know
    to reload to get the question back."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        prompt = _prompt_html(_fragment(client, PROMPT_ANCHOR).text)
    other = _form_html(prompt, "latch-validity-other")
    radios = re.findall(r"<input type=\"radio\"[^>]*>", other)
    assert radios, "the non-accepted form must offer the outcomes"
    assert all("required" in r for r in radios)


def test_a_CONTESTED_ticker_offers_its_stray_to_NO_latch_and_says_why(
        seeded_db, monkeypatch, clocks):
    """CODEX EXEC R10 MAJOR. A ticker-level stray was treated as unique WITHOUT
    checking it was unique to ONE eligible latch, so with two latches on a
    ticker the same unclaimed broker order was supplied to BOTH prompts and could
    be persisted as the exact `actual_broker_order_id` of two DISTINCT latch
    observations -- a fabricated agreement on whichever it did not belong to, and
    no schema uniqueness prevents it."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(order_id="5150", price=12.00)])
    with TestClient(app) as client:
        # The place is logged BEFORE the second fire exists: the re-fire
        # SUPERSEDES the first latch, so a fixture that seeded it first could
        # never reach the offered form at all.
        _log_place(client, cfg, cid)
        conn = connect(cfg.paths.db_path)
        with conn:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) VALUES "
                "(122, '2026-07-27T17:30:05', '2026-07-27', '2026-07-28', 1, 1, "
                "0, 0, 0, 0)")
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(122, 'FTRE', 'aplus', 19.50, 20.10, 17.20, 'universe')")
        conn.close()
        clocks.set(PROMPT_NOW)
        html = _fragment(client, PROMPT_ANCHOR).text
    # 21-A still reports the stray as a DISAGREEMENT (correctly -- an
    # unexplained resting order is worth surfacing), and the ABSENCE prompt
    # still renders (also correctly -- no order attributable to THIS mandate is
    # visible). What must not happen is that the contested order is offered as
    # EITHER latch's observed side, which is the row that would fabricate an
    # agreement on whichever latch it did not belong to.
    assert "latch-validity-presence" not in html
    assert 'name="actual_broker_order_id"' not in html
    assert "could belong to more than one mandate" in html
