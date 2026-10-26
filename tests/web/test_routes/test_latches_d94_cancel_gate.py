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
