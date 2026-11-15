"""FX-2's condition (RD, 2026-11-11, as RE-RULED): the claim-consistency 400
leaves the entry recordable from the recovery form.

RD ruled FX-2 = Y: a CLAIMED anchor that cannot be decoded keeps the standing
400-and-clear ladder (the FILL-ORIGIN claim's guard, outside FX-1's reach).
The first version of this test FAILED the original point 2 ("every typed value
preserved"): ``_rerender_entry_form_with_error`` kept no ``draft_*`` field, so
the recovery form came back with the pre-trade answers empty. RD re-ruled
(Y stands, point 2 corrected): the cost of this 400 was RETYPING, not an
unjournaled position, and step 2 PINNED that loss so it would go red the day
the helper was fixed.

THE PIN RETIRED WITH ITS FIX (Phase 22 entry-form rider, the D47 companion,
2026-11-14): every early 400 now hands back the operator's answers, so the
corrected point 2 ("the operator retypes the answers") is false and RD's
ORIGINAL point 2 holds. The three steps now read:

  1. claimed undecodable anchor, every pre-trade field filled -> 400; the
     recovery form carries the FRESH anchor, not the rejected one (unchanged,
     byte for byte);
  2. the recovery form KEEPS the thirteen required pre-trade answers (and the
     two handling answers the old pin noted were dropped too);
  3. the recovery form's own state, with NOTHING retyped, writes the trade
     with the fill-origin and cohort keys the fresh anchor earns.

The resubmit is the RECOVERY FORM'S OWN rendered state, serialized the way a
browser serializes a form (every successful control: inputs, checked radios
and checkboxes, textareas, the selected option of each select). Nothing in it
comes from the test's own data.
"""
from __future__ import annotations

import json
from html.parser import HTMLParser

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from tests._latch_probe_world_22a import TICKER
from tests.web.test_routes.test_22a_task10_entry_route_ext2 import DRIFT_RUN
from tests.web.test_routes.test_d86_entry_raw_rung import (
    _FRESH,
    _REJECTED,
    _TODAYS_LABEL,
    _UNDECODABLE,
    _data,
    _stub_fresh_fetch,
    _world,
    _written,
)


class _FormSerializer(HTMLParser):
    """The successful controls of the FIRST <form>, as a browser posts them."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pairs: list[tuple[str, str]] = []
        self._depth = 0          # 0 = before the form; -1 = after it
        self._textarea: str | None = None
        self._textarea_text: list[str] = []
        self._select: str | None = None
        self._options: list[tuple[str, bool]] = []
        self._option: tuple[str | None, bool] | None = None
        self._option_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            if self._depth == 0:
                self._depth = 1
            return
        if self._depth != 1 or "disabled" in a:
            return
        name = a.get("name")
        if tag == "input" and name:
            kind = (a.get("type") or "text").lower()
            if kind in ("submit", "button", "reset", "image", "file"):
                return
            if kind in ("radio", "checkbox"):
                if "checked" in a:
                    self.pairs.append((name, a.get("value") or "on"))
                return
            self.pairs.append((name, a.get("value") or ""))
        elif tag == "textarea" and name:
            self._textarea, self._textarea_text = name, []
        elif tag == "select" and name:
            assert "multiple" not in a, "no multi-select in this form"
            self._select, self._options = name, []
        elif tag == "option" and self._select is not None:
            self._option = (a.get("value"), "selected" in a)
            self._option_text = []

    def handle_endtag(self, tag):
        if tag == "form" and self._depth == 1:
            self._depth = -1
        elif tag == "textarea" and self._textarea is not None:
            self.pairs.append((self._textarea, "".join(self._textarea_text)))
            self._textarea = None
        elif tag == "option" and self._option is not None:
            value, selected = self._option
            text = "".join(self._option_text).strip()
            self._options.append((text if value is None else value, selected))
            self._option = None
        elif tag == "select" and self._select is not None:
            chosen = [v for v, sel in self._options if sel]
            if chosen:
                self.pairs.append((self._select, chosen[-1]))
            elif self._options:
                self.pairs.append((self._select, self._options[0][0]))
            self._select = None

    def handle_data(self, data):
        if self._textarea is not None:
            self._textarea_text.append(data)
        if self._option is not None:
            self._option_text.append(data)


def _serialize_first_form(page: str) -> dict[str, str]:
    parser = _FormSerializer()
    parser.feed(page)
    parser.close()
    assert parser.pairs, "the recovery response renders no form"
    out: dict[str, str] = {}
    for k, v in parser.pairs:
        assert k not in out, f"{k} posted twice; this form has no list fields"
        out[k] = v
    return out


# The thirteen REQUIRED pre-trade answers the recovery form USED TO drop
# (measured: the missing-field banner of the resubmit WITHOUT them named
# exactly these). `event_handling` / `gap_risk_handling` were dropped too
# (required only when their risk is present); the rider keeps all fifteen.
_THIRTEEN = (
    "catalyst", "emotional_state_pre_trade", "event_risk_present",
    "expected_scenario", "gap_risk_present", "invalidation_condition",
    "manual_entry_confidence", "market_regime", "premortem_execution",
    "premortem_market_sector", "premortem_technical", "thesis", "why_now",
)
_HANDLING = ("event_handling", "gap_risk_handling")


def _candidate_id(cfg, evaluation_run_id: int) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT id FROM candidates WHERE evaluation_run_id = ? "
            "AND ticker = ?", (evaluation_run_id, TICKER)).fetchone()[0]
    finally:
        conn.close()


def test_fx2_a_claimed_undecodable_anchor_is_one_resubmit_from_a_written_trade(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _stub_fresh_fetch(monkeypatch)
    sent = _data(_UNDECODABLE, claimed=True)
    assert all(sent.get(k) for k in _THIRTEEN), "step 1 fills every answer"
    with TestClient(create_app(cfg, cfg_path)) as client:
        # STEP 1 -- the ladder's 400, unchanged by this arc (FX-2 = Y).
        first = client.post("/trades/entry", data=sent,
                            headers={"HX-Request": "true"})
        assert first.status_code == 400, first.text
        assert "malformed" in first.text.lower()
        assert _written(cfg) == []
        recovery = _serialize_first_form(first.text)
        # The recovery form carries the FRESH anchor, never the rejected one.
        assert _REJECTED not in recovery["schwab_source_value_json"]
        assert _FRESH in recovery["schwab_source_value_json"]
        assert recovery["fill_origin_at_form_render"] == "schwab_auto"

        # STEP 2 -- the recovery form KEEPS every answer (the D47 companion;
        # the old pin of their loss retired with the fix).
        kept = {k: recovery.get(k) for k in _THIRTEEN + _HANDLING}
        assert kept == {k: sent[k] for k in _THIRTEEN + _HANDLING}, (
            "the recovery form dropped pre-trade answers")

        # STEP 3 -- the recovery form's own state, nothing retyped.
        resubmit = dict(recovery)
        second = client.post("/trades/entry", data=resubmit,
                             headers={"HX-Request": "true"})
    assert second.status_code == 200, second.text
    # The cohort keys the fresh anchor earns. It is canonical and names an
    # order no latch is bound to, so the ordinary chain runs: the ticker is
    # `aplus` in TODAY's run (pipeline_aplus); the candidate is the night the
    # recovery form's chooser selects by default (TODAY's, eval DRIFT_RUN);
    # and the label is the SERVER's for that night (D102's server stamp) --
    # here None, because the matcher finds no hypothesis for today's row in
    # this world (the form's option reads "(no hypothesis match)"; the
    # earlier night, eval 121, is the one labelled). A posted or stale label
    # would show up here as a non-None value.
    todays = _candidate_id(cfg, DRIFT_RUN)
    fire = _candidate_id(cfg, 121)       # the fire night (seed_fire)
    assert recovery["decision_candidate_id"] == str(todays)
    nights = {n["candidate_id"]: n["label"]
              for n in json.loads(recovery["decision_nights_anchor"])}
    assert nights == {todays: None, fire: _TODAYS_LABEL}, nights
    assert _written(cfg) == [(TICKER, "pipeline_aplus", todays, None)]
    conn = connect(cfg.paths.db_path)
    try:
        fill = conn.execute(
            "SELECT fill_origin, schwab_source_value_json FROM fills "
            "WHERE action = 'entry'").fetchone()
    finally:
        conn.close()
    # Submitted date/price/shares equal the fresh anchor's: an unedited auto-fill.
    assert fill[0] == "schwab_auto"
    assert fill[1] == recovery["schwab_source_value_json"]
