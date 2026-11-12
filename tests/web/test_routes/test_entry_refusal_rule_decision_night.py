"""RD's entry-refusal rule applied to the decision-night ladder (item A = B,
2026-11-12; CHARC's form ruling the same night).

THE RULE: a guard may refuse the ENTRY only when the value it protects is one
the operator EXPLICITLY ASSERTED on this submission AND the write WOULD USE
that value; otherwise it refuses the LABEL. Applied to the named decision
night (D102 T2.3):

  1. R1-1 -- the auto-fill anchor is REFUSED by the identity authority, so
     ``record_entry`` discards the candidate and the label: the ladder must
     not 400, whatever the decision anchor says (valid, stale or malformed).
     The entry is written honest-unset and one warning says the night choice
     was not evaluated.
  2. R1-2 -- the LATCH admits the fill and keeps its own candidate: a stale
     night offer must not 400 the FIRST post.
  3. The 400 that STAYS (non-latched, anchor accepted, night not offered) is
     recordable from the form it hands back: the resubmit built from the 400's
     own form, with the pre-trade answers retyped (the D47 companion), writes
     the trade with the night the recovery form shows.

CHARC's form: ONE latch resolution, inside ``record_entry``; the night verdict
is ENFORCED there, after the latch outcome, as a typed refusal the route maps
to T2's 400.
"""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests.web.test_routes.test_22a_task10_entry_route_ext2 import (
    _build_route_world,
    _envelope,
    _post_data,
)
from tests.web.test_routes.test_22a_task10_entry_route_ext2 import (
    _written as _written_all,
)
from tests.web.test_routes.test_d86_entry_raw_rung import (
    _SHAPES,
    _TODAYS_LABEL,
    _data,
    _world,
    _written,
)
from tests.web.test_routes.test_fx2_claimed_undecodable_round_trip import (
    _THIRTEEN,
    _candidate_id,
    _serialize_first_form,
)
from tests.web.test_routes.test_22a_task10_entry_route_ext2 import DRIFT_RUN

_NOT_EVALUATED = "night choice was NOT evaluated"


def _rendered_offer(client, ticker: str) -> tuple[str, str]:
    """The decision anchor + choice exactly as the entry-form GET renders."""
    page = client.get("/trades/entry/form", params={"ticker": ticker},
                      headers={"HX-Request": "true"})
    assert page.status_code == 200, page.text
    form = _serialize_first_form(page.text)
    return form["decision_nights_anchor"], form["decision_candidate_id"]


def _stale(anchor: str) -> str:
    """The same offer with the chosen night's label changed since render."""
    nights = json.loads(anchor)
    nights[0]["label"] = "a label the server no longer suggests"
    return json.dumps(nights)


# ---------------------------------------------------------------------------
# Condition 1 (R1-1).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("claimed", [True, False], ids=["claimed", "unclaimed"])
@pytest.mark.parametrize("night", ["valid", "stale", "malformed"])
@pytest.mark.parametrize(("raw", "malformation"), _SHAPES)
def test_r1_1_a_refused_anchor_never_meets_the_night_ladder(
        seeded_db, monkeypatch, caplog, raw, malformation, night, claimed):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, choice = _rendered_offer(client, "FTRE")
        anchor = {"valid": anchor, "stale": _stale(anchor),
                  "malformed": "not json"}[night]
        with caplog.at_level(logging.WARNING):
            resp = client.post(
                "/trades/entry",
                data=_data(raw, claimed=claimed,
                           decision_nights_anchor=anchor,
                           decision_candidate_id=choice),
                headers={"HX-Request": "true"})
    assert resp.status_code == 200, resp.text
    assert _written(cfg) == [("FTRE", "manual_off_pipeline", None, None)]
    warnings = [r.getMessage() for r in caplog.records
                if r.levelno >= logging.WARNING]
    assert any(malformation in m for m in warnings), warnings
    skipped = [m for m in warnings if _NOT_EVALUATED in m]
    assert len(skipped) == 1, warnings
    if night == "malformed":
        assert "is not valid JSON" in skipped[0], skipped


# ---------------------------------------------------------------------------
# Condition 2 (R1-2).
# ---------------------------------------------------------------------------
def test_r1_2_a_latched_entry_is_not_refused_over_a_stale_night_offer(
        seeded_db, caplog) -> None:
    """The ticker rolled out of today's run, so the server offers NO night,
    and the posted choice (the fire night, as rendered before the roll) is
    stale. The latch admits the fill: 200 on the FIRST post, the latch's
    candidate kept, and the differing choice is not what decides."""
    cfg, cfg_path = seeded_db
    fire_id, pipeline_run_id = _build_route_world(cfg, with_link=True)
    data = _post_data(pipeline_run_id=pipeline_run_id, envelope=_envelope())
    data["decision_nights_anchor"] = json.dumps([{
        "candidate_id": fire_id, "evaluation_run_id": 121,
        "label": "A+ baseline (aplus)"}])
    data["decision_candidate_id"] = str(fire_id)
    with TestClient(create_app(cfg, cfg_path)) as client:
        with caplog.at_level(logging.INFO):
            resp = client.post("/trades/entry", data=data,
                               headers={"HX-Request": "true"})
    assert resp.status_code == 200, resp.text
    assert _written_all(cfg) == [
        ("FTRE", "pipeline_aplus", fire_id, "A+ baseline (aplus)")]


def test_r1_2_a_latched_entry_naming_another_night_is_logged_and_the_latch_wins(
        seeded_db, monkeypatch, caplog) -> None:
    cfg, cfg_path = seeded_db
    fire_id, pipeline_run_id = _build_route_world(
        cfg, with_link=True, ticker_in_todays_run=True)
    data = _post_data(pipeline_run_id=pipeline_run_id, envelope=_envelope())
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, _choice = _rendered_offer(client, "FTRE")
        today = _candidate_id(cfg, DRIFT_RUN)
        data["decision_nights_anchor"] = anchor
        data["decision_candidate_id"] = str(today)
        with caplog.at_level(logging.WARNING):
            resp = client.post("/trades/entry", data=data,
                               headers={"HX-Request": "true"})
    assert resp.status_code == 200, resp.text
    assert _written_all(cfg) == [
        ("FTRE", "pipeline_aplus", fire_id, "A+ baseline (aplus)")]
    assert any("THE LATCH WINS" in r.getMessage() and str(today)
               in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records]


# ---------------------------------------------------------------------------
# Condition 3: the 400 that stays, round trip.
# ---------------------------------------------------------------------------
def test_the_standing_night_400_is_recordable_from_the_form_it_hands_back(
        seeded_db, monkeypatch) -> None:
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    today = _candidate_id(cfg, DRIFT_RUN)
    with TestClient(create_app(cfg, cfg_path)) as client:
        anchor, choice = _rendered_offer(client, "FTRE")
        assert choice == str(today)
        # The night as the operator named it is NOT the server's any more:
        # the claimed run differs from the run the server offers for it.
        altered = json.loads(anchor)
        for n in altered:
            if n["candidate_id"] == today:
                n["evaluation_run_id"] = 121
        sent = _data("", claimed=False, decision_nights_anchor=json.dumps(
            altered), decision_candidate_id=choice)
        first = client.post("/trades/entry", data=sent,
                            headers={"HX-Request": "true"})
        assert first.status_code == 400, first.text
        assert "no longer offered" in first.text
        assert _written(cfg) == []

        recovery = _serialize_first_form(first.text)
        # The fresh offer, not the rejected anchor.
        assert json.loads(recovery["decision_nights_anchor"]) == json.loads(
            anchor)
        shown = int(recovery["decision_candidate_id"])
        resubmit = dict(recovery)
        resubmit.update({k: sent[k] for k in _THIRTEEN})
        second = client.post("/trades/entry", data=resubmit,
                             headers={"HX-Request": "true"})
    assert second.status_code == 200, second.text
    labels = {n["candidate_id"]: n["label"]
              for n in json.loads(recovery["decision_nights_anchor"])}
    assert _written(cfg) == [
        ("FTRE", "pipeline_aplus", shown, labels[shown])]
    assert labels != {} and _TODAYS_LABEL in labels.values()
