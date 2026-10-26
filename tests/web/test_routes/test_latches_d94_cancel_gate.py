"""D94 (a)+(b): the latch validity prompt GATE and the LEDGER-KEYED cancel control.

RD D94 item 3: a correction control on an ACCEPTED validity row is offered only
while the order's ABSENCE from the book is UNEXPLAINED. A `cancel` row naming
that order, or the resolver's fill rung, EXPLAINS it, and the control is then
replaced by a read-only line. CHARC D94 1A/2A: the fill explanation is the ONE
predicate `fill_vouches_for`, and ONE gate function (`_accepted_row_gate`) is
called from BOTH the current-cycle path and `_displaced_cycle_prompts`.

Plan section 1 is the rule table (G1-G6); section 4 is this file's roster. Every
test drives the RENDERED fragment and posts exactly what it emits, as the
validity-prompt file does, so a test cannot construct its own POST around the
blind spot it exists to see.
"""
# ruff: noqa: F811 -- the `clocks` fixture imported from the validity-prompt module
# is re-bound as a test-function parameter; that is the intended pytest pattern.
from __future__ import annotations

import dataclasses
import re
from datetime import date

from fastapi.testclient import TestClient

from swing.data.db import connect
from tests.web.test_routes.test_latches_validity_prompt import (  # noqa: F401
    _HX,
    PLACE_ANCHOR,
    PROMPT_ANCHOR,
    PROMPT_NOW,
    _app,
    _form_fields,
    _form_html,
    _fragment,
    _log_place,
    _order,
    _radio_values,
    _rows,
    _seed,
    clocks,
)

_SECTION = '<section class="latch-validity-prompt'
_CANCEL_FORM = 'class="latch-cancel-form"'


def _section_for_parent(html: str, pid: int) -> str | None:
    """The validity-prompt section whose `validated_place_intent_id` is `pid`.

    Works on the pre- and post-fix trees: it keys on the hidden input both
    trees emit, never on a heading either tree may have changed.
    """
    for block in html.split(_SECTION)[1:]:
        body = block[:block.index("</section>")]
        if re.search(
                r'name="validated_place_intent_id"\s+value="' + str(pid) + '"',
                body):
            return body
    return None


def _clone_intent(cfg, intent_id: int, **over) -> int:
    """A raw-SQL copy of one intent row with overrides (idempotency_key,
    recorded_ts, action_session_date, ...). Generalises the validity file's
    `_clone_place` without editing it."""
    conn = connect(cfg.paths.db_path)
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(latch_order_intents)").fetchall()
            if r[1] != "intent_id"]
        row = dict(zip(cols, conn.execute(
            f"SELECT {', '.join(cols)} FROM latch_order_intents "
            "WHERE intent_id = ?", (intent_id,)).fetchone(), strict=True))
        row.update(over)
        with conn:
            cur = conn.execute(
                f"INSERT INTO latch_order_intents ({', '.join(cols)}) VALUES "
                f"({', '.join('?' * len(cols))})",
                tuple(row[c] for c in cols))
        return int(cur.lastrowid)
    finally:
        conn.close()


def _accept(client, pid: int) -> None:
    """Render the fragment, take P's section and post its CONFIRM form."""
    html = _fragment(client, PROMPT_ANCHOR).text
    section = _section_for_parent(html, pid)
    assert section is not None, f"no prompt for parent {pid} to accept"
    r = client.post("/latches/intent", headers=_HX, data=_form_fields(
        _form_html(section, "latch-validity-confirm")))
    assert r.status_code == 200, r.text


def _cancel_forms(html: str) -> list[dict]:
    """EVERY `latch-cancel-form` as a dict of its hidden inputs (the fragment
    file's `_cancel_form_fields` takes only the first)."""
    out = []
    start = html.find(_CANCEL_FORM)
    while start != -1:
        form = html[html.rindex("<form", 0, start):html.index("</form>", start)]
        out.append(_form_fields(form))
        start = html.find(_CANCEL_FORM, start + 1)
    return out


def _cancel_form_html(html: str, order_id: str) -> str:
    start = html.find(_CANCEL_FORM)
    while start != -1:
        form = html[html.rindex("<form", 0, start):html.index("</form>", start)]
        if _form_fields(form).get("actual_broker_order_id") == order_id:
            return form
        start = html.find(_CANCEL_FORM, start + 1)
    raise AssertionError(f"no cancel form for order {order_id}")


def _fill_cleared(monkeypatch, cid: int, clear_session: date) -> None:
    """The latch `cid` as cleared by FILL, through the derivation the fragment
    reads -- the exact override set `test_latches_validity_prompt.py` already
    uses for its fill case. Installed AFTER the place and validity rows exist."""
    import swing.web.view_models.latches as vm_mod
    real = vm_mod.build_latch_derivation

    def _wrapped(*a, **k):
        d = real(*a, **k)
        return dataclasses.replace(d, latches=tuple(
            dataclasses.replace(
                lat, state="filled", clear_reason="fill",
                clear_session=clear_session, clear_trade_id=7,
                fill_link_basis="candidate_id")
            if lat.identity.candidate_id == cid else lat
            for lat in d.latches))

    monkeypatch.setattr(vm_mod, "build_latch_derivation", _wrapped)


def _explained_lines(html: str) -> list[str]:
    return [" ".join(m.split()) for m in re.findall(
        r'<p class="latch-validity-explained-line">(.*?)</p>', html, re.S)]


# ---------------------------------------------------------------------------
# Task 2 -- the fill gate (G1 / G2), and the shipped short-circuit defect
# ---------------------------------------------------------------------------
def test_t2_1_oii_shape_a_fill_with_a_validity_child_explains_and_does_not_reprompt(
        seeded_db, monkeypatch, clocks):
    """THE OII SHAPE (RD D94 item 1, CHARC's short-circuit ruling). An accepted
    validity child on the LATEST place, and a fill clearing the latch on or
    after that place's session. The shipped proxy at the short-circuit skipped
    only a CHILDLESS place, so this latch fell through to a correction control
    -- three false buttons on an order that FILLED.

    Pre-fix: the fragment renders `CORRECT THE RECORDED OUTCOME`. Post-fix: the
    read-only fill line, and no control of either kind.
    """
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        book.clear()
        _fill_cleared(monkeypatch, cid, date(2026, 7, 28))
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "CORRECT THE RECORDED OUTCOME" not in html
    assert "latch-validity-prompt" not in html
    assert _CANCEL_FORM not in html
    assert _explained_lines(html) == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        "filled 2026-07-28"]


def test_t2_2_cadl_guard_a_fill_on_a_childless_place_renders_nothing(
        seeded_db, monkeypatch, clocks):
    """GUARD (green on both trees). The CADL shape: no validity child, cleared
    by fill. The fill answers for itself and there is nothing to explain or to
    correct, so NOTHING renders -- today's behaviour, kept."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _fill_cleared(monkeypatch, cid, date(2026, 7, 28))
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "latch-validity-prompt" not in html
    assert "latch-validity-explained" not in html
    assert _CANCEL_FORM not in html


def test_t2_3_the_vm_follows_the_one_predicate_it_does_not_respell_it(
        seeded_db, monkeypatch, clocks):
    """ONE SPELLING (CHARC 1A, RD item 2). The same fixture rendered twice: as
    is, and with `fill_vouches_for` forced False. If the VM re-spelled the
    conjunction, the second render would keep the explained line. It must not:
    the line goes, and the correction control for P1 is back (the W1 headline
    on that branch is T3.3's assertion, not this test's)."""
    import swing.latches.classification as cls_mod

    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        book.clear()
        _fill_cleared(monkeypatch, cid, date(2026, 7, 28))
        as_is = _fragment(client, PROMPT_ANCHOR).text
        monkeypatch.setattr(
            cls_mod, "fill_vouches_for", lambda *a, **k: False)
        forced = _fragment(client, PROMPT_ANCHOR).text
    assert _explained_lines(as_is) == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        "filled 2026-07-28"]
    assert _explained_lines(forced) == []
    section = _section_for_parent(forced, p1)
    assert section is not None
    assert "CORRECT THE RECORDED OUTCOME" in section


def test_t2_4_g2_withholds_the_testimony_controls_never_the_book_control(
        seeded_db, monkeypatch, clocks):
    """R1-1 = (i) (CHARC + RD, D94 exec round 1). G2 withholds the TESTIMONY
    controls -- the correction control and the LEDGER-keyed cancel control --
    and never the shipped BOOK control: its source is the broker saying, this
    render, that the order RESTS, and a fill does not retire a resting remainder
    or a stale status.

    The OII shape with the accepted order STILL in the book. Expected: the fill
    line; exactly ONE cancel form, from the book (no W2 note); no correction
    control; no ledger control. An implementation that suppresses every cancel
    control on a fill-settled place renders zero forms and fails."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        _fill_cleared(monkeypatch, cid, date(2026, 7, 28))
        html = _fragment(client, PROMPT_ANCHOR).text
    assert _explained_lines(html) == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        "filled 2026-07-28"]
    forms = _cancel_forms(html)
    assert [f["actual_broker_order_id"] for f in forms] == ["5001"]
    assert forms[0]["candidate_id"] == str(cid)
    assert _status_notes(html) == []
    assert "If YOU cancelled it" not in html
    assert "CORRECT THE RECORDED OUTCOME" not in html
    assert "latch-validity-prompt" not in html


# ---------------------------------------------------------------------------
# Task 3 -- a recorded CANCEL explains an accepted row, on EVERY cycle (G5/G6)
# ---------------------------------------------------------------------------
def _w1(order_id: str, session: str) -> str:
    """RD D94 item 4, the correction headline on an UNEXPLAINED accepted row
    (absence branch), verbatim with the substitutions."""
    return (f"Recorded: the broker ACCEPTED order {order_id} on {session}. That "
            "order is not in the current book. Correct this ONLY if the broker "
            "never accepted it as recorded; an order that you later cancelled, "
            "or that filled or expired, was still accepted -- do not change the "
            "answer for that.")


def _headline(section: str) -> str:
    m = re.search(r'<p class="latch-validity-headline">(.*?)</p>', section, re.S)
    assert m is not None
    return " ".join(m.group(1).split())


def _cancel_ids(cfg) -> list[int]:
    return [r[0] for r in _rows(cfg) if r[1] == "cancel"]


def _accept_then_cancel_via_book(client, cfg, book, pid: int, oid: str) -> int:
    """`pid` is accepted as order `oid` while it rests, then he records the
    cancel through the shipped BOOK control while it still rests; the order then
    leaves the book. Returns the cancel row's intent id."""
    book[:] = [_order(order_id=oid)]
    _accept(client, pid)
    html = _fragment(client, PROMPT_ANCHOR).text
    r = client.post("/latches/intent", headers=_HX,
                    data=_form_fields(_cancel_form_html(html, oid)))
    assert r.status_code == 200, r.text
    book.clear()
    return _cancel_ids(cfg)[-1]


def test_t3_1_dftx_shape_a_recorded_cancel_explains_the_accepted_row(
        seeded_db, monkeypatch, clocks):
    """THE DFTX SHAPE (RD item 3). The accepted order left the book and a
    `cancel` row naming it sits beside it. Pre-fix the prompt never read cancel
    rows, so it re-prompted a correction with the explaining row in the ledger.
    Post-fix: the read-only cancel line, and no control of either kind."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book: list = []
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        c1 = _accept_then_cancel_via_book(client, cfg, book, p1, "5001")
        html = _fragment(client, PROMPT_ANCHOR).text
    assert _explained_lines(html) == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        f"cancelled by you {PROMPT_ANCHOR}, intent {c1}"]
    assert _section_for_parent(html, p1) is None
    assert _CANCEL_FORM not in html


def test_t3_2_imnm_shape_the_gate_runs_on_displaced_cycles_too(
        seeded_db, monkeypatch, clocks):
    """THE IMNM SHAPE (CHARC 2A, RD item 3). Three cycles on one latch: P1
    accepted then cancelled (displaced), P2 accepted and gone with NO cancel
    (displaced), P3 the childless current place. A 2B implementation -- the gate
    on the current cycle only -- fails (i): the false downward buttons stay on
    exactly the displaced rows the ruling was written about."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book: list = []
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        c1 = _accept_then_cancel_via_book(client, cfg, book, p1, "5001")
        p2 = _clone_intent(cfg, p1, idempotency_key="p2",
                           recorded_ts="2026-07-29T23:59:58")
        book[:] = [_order(order_id="5002")]
        _accept(client, p2)
        book.clear()
        p3 = _clone_intent(cfg, p1, idempotency_key="p3",
                           recorded_ts="2026-07-29T23:59:59")
        html = _fragment(client, PROMPT_ANCHOR).text
    # (i) P1, displaced and explained by its cancel row.
    assert _explained_lines(html) == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        f"cancelled by you {PROMPT_ANCHOR}, intent {c1}"]
    assert _section_for_parent(html, p1) is None
    # (ii) P2, displaced and UNEXPLAINED: RD's correction headline, which asserts
    # nothing from absence, in place of the "correctable DOWNWARD" one.
    p2_section = _section_for_parent(html, p2)
    assert p2_section is not None
    assert _headline(p2_section) == _w1("5002", PLACE_ANCHOR)
    assert "correctable DOWNWARD" not in p2_section
    # (iv) P3, the childless current place: its FIRST-ANSWER prompt, untouched.
    p3_section = _section_for_parent(html, p3)
    assert p3_section is not None
    assert "DID THIS ORDER REACH THE BROKER?" in p3_section
    # (iii) the ONE ledger-keyed cancel control, for P2's gone order only (the
    # book is empty, so this cannot be a book control). Added in Task 4, where
    # the control is wired (the orchestrator's T3.2 sequencing ruling).
    assert [f["actual_broker_order_id"] for f in _cancel_forms(html)] == ["5002"]


def test_t3_3_w1_replaces_the_absence_headline_on_an_unexplained_accepted_row(
        seeded_db, monkeypatch, clocks):
    """RD item 4: the correction control may NOT assert or insinuate rejection
    from absence. The options stay the three non-accepted enum values (ledger
    IC-2: an accepted answer needs an observed side an absence form lacks)."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        book.clear()
        html = _fragment(client, PROMPT_ANCHOR).text
    section = _section_for_parent(html, p1)
    assert section is not None
    assert _headline(section) == _w1("5001", PLACE_ANCHOR)
    assert "NO matching resting order" not in section
    assert _radio_values(section) == {
        "not_submitted", "rejected_by_broker", "unknown"}
    assert "CORRECT THE RECORDED OUTCOME" in section


def test_t3_4_the_earliest_cancel_row_is_the_record_and_the_count_is_disclosed(
        seeded_db, monkeypatch, clocks):
    """RD item 5: a cancel is an EVENT with no un-cancel, so a later row naming
    the same order is a replay and can only move the date later and wrong. The
    EARLIEST row by `_order_key` is the record; the count is disclosed. A
    latest-wins build shows `2026-07-30, intent <C2>` and fails."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book: list = []
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        c1 = _accept_then_cancel_via_book(client, cfg, book, p1, "5001")
        _clone_intent(cfg, c1, idempotency_key="c2",
                      recorded_ts="2026-07-30T09:00:00",
                      action_session_date="2026-07-30")
        html = _fragment(client, PROMPT_ANCHOR).text
    lines = _explained_lines(html)
    assert lines == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        f"cancelled by you {PROMPT_ANCHOR}, intent {c1} (2 cancel rows name "
        "this order; the earliest is the record)"]
    assert "2026-07-30" not in lines[0]


def test_t3_5_a_resting_accepted_order_is_not_gated(
        seeded_db, monkeypatch, clocks):
    """GUARD (G4). The accepted order is still resting, so its absence is not
    the question: the shipped PRESENCE correction stays and nothing is
    explained."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        html = _fragment(client, PROMPT_ANCHOR).text
    section = _section_for_parent(html, p1)
    assert section is not None
    assert "YES - the broker accepted order 5001" in section
    assert "latch-validity-explained" not in html


# ---------------------------------------------------------------------------
# Task 4 -- the cancel affordance keyed on the LEDGER's order id (D94 (b))
# ---------------------------------------------------------------------------
def _w2(order_id: str, session: str) -> str:
    """RD D94 item 4, the ledger-keyed cancel control's note, verbatim."""
    return (f"Order {order_id} (accepted {session}) is not in the current book. "
            "If YOU cancelled it, record the cancel here. Do not record a cancel "
            "for an order that filled or expired; leave it unanswered -- the "
            "broker-history tier records those.")


def _status_notes(html: str) -> list[str]:
    return [" ".join(m.split()) for m in re.findall(
        r'<p class="latch-cancel-status">(.*?)</p>', html, re.S)]


def _accepted_then_gone(cfg, cfg_path, monkeypatch, clocks):
    """P1 accepted as order 5001 while it rested; then the book is EMPTY (the
    order is gone, no cancel recorded). Returns (app, book, p1, cid)."""
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
    book.clear()
    return app, book, p1, cid


def test_t4_1_empty_book_the_ledger_keyed_control_does_not_need_the_book(
        seeded_db, monkeypatch, clocks):
    """ANTI-VACUITY (CHARC). The shipped control is built `for row in
    attribution`, the RESTING book -- so the moment the broker no longer shows
    the order there is NO control to record the cancel with. With the book
    EMPTY in the fixture the control can only come from the ledger key."""
    cfg, cfg_path = seeded_db
    app, _book, _p1, _cid = _accepted_then_gone(cfg, cfg_path, monkeypatch, clocks)
    with TestClient(app) as client:
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "No resting BUY orders at the broker." in html, (
        "the premise: the book is EMPTY, so attribution is empty")
    forms = _cancel_forms(html)
    assert len(forms) == 1
    assert forms[0]["actual_broker_order_id"] == "5001"
    assert forms[0]["intent_kind"] == "cancel"
    assert _status_notes(html) == [_w2("5001", PLACE_ANCHOR)]


def test_t4_2_an_unknown_book_offers_no_ledger_keyed_control(
        seeded_db, monkeypatch, clocks):
    """GUARD (CHARC; RD item 6). An UNKNOWN book cannot say "absent", so it
    builds no line and no control: the two states are not the same state."""
    import swing.web.view_models.latches as vm_mod
    from swing.integrations.schwab.client import SchwabApiError

    cfg, cfg_path = seeded_db
    app, _book, _p1, _cid = _accepted_then_gone(cfg, cfg_path, monkeypatch, clocks)

    def _raise(*a, **k):
        raise SchwabApiError(500, "x")

    monkeypatch.setattr(vm_mod, "_fetch_account_orders", _raise)
    with TestClient(app) as client:
        html = _fragment(client, PROMPT_ANCHOR).text
    assert "UNKNOWN" in html
    assert _CANCEL_FORM not in html
    assert "latch-cancel-log" not in html
    assert "latch-validity-explained" not in html
    assert "latch-validity-prompt" not in html


def test_t4_3_the_ledger_keyed_control_round_trips_to_the_explained_line(
        seeded_db, monkeypatch, clocks):
    """END TO END on the shipped POST contract (no route change): the form is
    posted exactly as rendered, the response is the in-place markup swap (no
    HX-Redirect), ONE cancel row is written, and the next render explains the
    row instead of offering anything."""
    cfg, cfg_path = seeded_db
    app, _book, p1, _cid = _accepted_then_gone(cfg, cfg_path, monkeypatch, clocks)
    before = len(_rows(cfg))
    with TestClient(app) as client:
        html = _fragment(client, PROMPT_ANCHOR).text
        r = client.post("/latches/intent", headers=_HX,
                        data=_form_fields(_cancel_form_html(html, "5001")))
        assert r.status_code == 200, r.text
        assert "HX-Redirect" not in r.headers
        after = _fragment(client, PROMPT_ANCHOR).text
    new = _rows(cfg)[before:]
    assert [(row[1], row[5]) for row in new] == [("cancel", "5001")]
    assert _explained_lines(after) == [
        f"FTRE place intent {p1}, order 5001: accepted {PLACE_ANCHOR}; "
        f"cancelled by you {PROMPT_ANCHOR}, intent {new[0][0]}"]
    assert _CANCEL_FORM not in after
    assert _section_for_parent(after, p1) is None


def test_t4_4_a_resting_accepted_order_gets_exactly_one_control(
        seeded_db, monkeypatch, clocks):
    """GUARD. The accepted order still rests, so the shipped BOOK control
    covers it; a union without the resting check would render it twice."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        html = _fragment(client, PROMPT_ANCHOR).text
    assert [f["actual_broker_order_id"] for f in _cancel_forms(html)] == ["5001"]
    assert "If YOU cancelled it" not in html
    assert "latch-cancel-status" not in html


def test_t4_5_presence_of_a_different_order_keeps_both_controls(
        seeded_db, monkeypatch, clocks):
    """Ledger I-3. The accepted order 5001 is gone and a DIFFERENT attributable
    order 5002 rests. The presence correction (the only way to record 5002)
    stays, and the gone order still gets its ledger-keyed control beside the
    book control for 5002."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        book[:] = [_order(order_id="5002")]
        html = _fragment(client, PROMPT_ANCHOR).text
    section = _section_for_parent(html, p1)
    assert section is not None
    assert "YES - the broker accepted order 5002" in section
    assert [f["actual_broker_order_id"] for f in _cancel_forms(html)] == [
        "5002", "5001"]
    assert _status_notes(html) == [_w2("5001", PLACE_ANCHOR)]
    assert "latch-cancel-status" not in html[:html.index(
        _cancel_form_html(html, "5002"))]


def test_t4_6_the_ledger_keyed_control_keeps_the_htmx_swap_contract(
        seeded_db, monkeypatch, clocks):
    """The shipped in-place swap (CHARC; ledger IC-1): browser-only failure
    surfaces TestClient cannot see, so the attributes are pinned exactly."""
    cfg, cfg_path = seeded_db
    app, _book, _p1, cid = _accepted_then_gone(cfg, cfg_path, monkeypatch, clocks)
    with TestClient(app) as client:
        html = _fragment(client, PROMPT_ANCHOR).text
    form = _cancel_form_html(html, "5001")
    assert 'hx-post="/latches/intent"' in form
    assert 'hx-target="this"' in form
    assert 'hx-swap="outerHTML"' in form
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in form
    fields = _form_fields(form)
    latest = max((r for r in _rows(cfg)), key=lambda r: r[0])[0]
    assert fields["prior_intent_id"] == str(latest) != ""
    assert fields["candidate_id"] == str(cid)
    assert fields["view_session_date"] == PROMPT_ANCHOR
    assert not html.lstrip().startswith("<tr")


def test_t4_8_g6_under_the_ambiguity_guard_keeps_the_ledger_control(
        seeded_db, monkeypatch, clocks):
    """B-01, ACCEPTED as a declared limitation (RD + CHARC). G6 restated: the
    W1 correction control WHERE THE SHIPPED AMBIGUITY GUARD ADMITS A PROMPT,
    plus ONE ledger-keyed cancel control ALWAYS; where the guard withholds, the
    withheld note names the latch and its reason, and the ledger control still
    renders.

    The accepted order 5001 is gone and unexplained, and TWO orders attributable
    to the same mandate rest (5002, 5003). The guard withholds the correction
    (no single order id could be recorded) and says so; the ledger control for
    5001 renders anyway, beside the two shipped book controls. A build that
    drops the ledger control when the guard withholds fails on the 5001 form."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg)
    book = [_order(order_id="5001")]
    app = _app(cfg, cfg_path, monkeypatch, orders=book)
    with TestClient(app) as client:
        p1 = _log_place(client, cfg, cid)
        clocks.set(PROMPT_NOW)
        _accept(client, p1)
        book[:] = [_order(order_id="5002"), _order(order_id="5003")]
        html = _fragment(client, PROMPT_ANCHOR).text
    ids = [f["actual_broker_order_id"] for f in _cancel_forms(html)]
    assert ids.count("5001") == 1
    assert sorted(ids) == ["5001", "5002", "5003"]
    assert _status_notes(html) == [_w2("5001", PLACE_ANCHOR)]
    assert _section_for_parent(html, p1) is None
    assert "latch-validity-prompt" not in html
    assert "CORRECT THE RECORDED OUTCOME" not in html
    flat = " ".join(html.split())
    assert ("FTRE: 2 resting orders are attributable to this mandate, so no "
            "single broker order id could be recorded against it. Resolve the "
            "duplicates at the broker.") in flat


def test_t4_7_a_failed_ledger_read_offers_no_control(
        seeded_db, monkeypatch, clocks):
    """GUARD. A latch whose ledger could not be read builds no gate, so no
    ledger-keyed control; the shipped degraded label says why."""
    import sqlite3

    import swing.data.repos.latch_order_intents as repo

    cfg, cfg_path = seeded_db
    app, _book, _p1, _cid = _accepted_then_gone(cfg, cfg_path, monkeypatch, clocks)

    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(repo, "list_intents_for_latch", _boom)
    with TestClient(app) as client:
        html = _fragment(client, PROMPT_ANCHOR).text
    assert _CANCEL_FORM not in html
    assert "THE VALIDITY QUESTION COULD NOT BE BUILT" in html
