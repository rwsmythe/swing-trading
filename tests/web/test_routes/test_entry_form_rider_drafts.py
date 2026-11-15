"""Phase 22 entry-form rider -- the D47 companion: a refused submit's recovery
form KEEPS the operator's pre-trade answers.

Before this rider `_rerender_entry_form_with_error` rebuilt the VM and replaced
six fields (date, price, stop, shares, rationale, notes); the `draft_*` fields
kept their defaults, so every early 400 handed back a form with the pre-trade
answers blank (the FX-2 pin measured thirteen required ones) and the operator
retyped the journal entry to get past, say, a typo in a price. Only the
missing-field re-render kept them.

Every textual call of `_rerender_entry_form_with_error` inside `entry_post` is
driven below (sixteen at this rider's base `8f35f21c`: the brief, read at
`d9b59d1f`, counted fifteen). Each case posts the FULL answer set, asserts the
400, serializes the recovery form the way a browser posts it, and asserts
every answer comes back. The world is the D86 route world (the ticker is
`aplus` in today's run, a fresh auto-fill is stubbed), which reaches every
rung. Three sites lie past `record_entry` and are reached by a stub that
raises the typed error the route maps (stated per case).
"""
from __future__ import annotations

import html
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from tests._latch_probe_world_22a import TICKER
from tests.web.test_routes.test_22a_task10_entry_route_ext2 import DRIFT_RUN
from tests.web.test_routes.test_d86_entry_raw_rung import (
    _FRESH,
    _REJECTED,
    _UNDECODABLE,
    _data,
    _stub_fresh_fetch,
    _world,
    _written,
)
from tests.web.test_routes.test_fx2_claimed_undecodable_round_trip import (
    _serialize_first_form,
)
from tests.web.test_routes.test_phase13_t2_sb6c_t_a_6c_4 import (
    _pretrade_form_kwargs,
)

# Every pre-trade answer the form carries (the nineteen `draft_*` fields) plus
# the design intent, each with a value the form can re-render (a select's value
# must be one of its options). `_pretrade_form_kwargs` fills fifteen; the four
# optional ones and a non-default catalyst + intent make the set complete.
_ANSWERS = {
    **_pretrade_form_kwargs(),
    "premortem_additional": "earnings in three weeks",
    "event_type": "earnings",
    "event_date": "2026-12-01",
    "catalyst": "other",
    "catalyst_other_description": "index inclusion",
    "entry_intent": "hypothesis_test_by_design",
}
assert len(_ANSWERS) == 20


def _sent(**over) -> dict:
    data = _data("", claimed=False)
    data.update(_ANSWERS)
    data.update(over)
    return data


def _no_classification_run(cfg) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT id FROM pipeline_runs WHERE id NOT IN (SELECT "
            "pipeline_run_id FROM pipeline_pattern_classifications WHERE ticker = ?) "
            "ORDER BY id LIMIT 1", (TICKER,)).fetchone()
    finally:
        conn.close()
    assert row is not None
    return int(row[0])


def _raise_from_record_entry(monkeypatch, exc: BaseException) -> None:
    def _raise(*_a, **_kw):
        raise exc
    monkeypatch.setattr("swing.web.routes.trades.record_entry", _raise)


def _decision_refusal(client, cfg) -> dict:
    """D102's standing night 400: the offer the form rendered, with today's
    night re-pointed at another run (the decision-night test's input)."""
    page = client.get("/trades/entry/form", params={"ticker": TICKER},
                      headers={"HX-Request": "true"})
    assert page.status_code == 200, page.text
    form = _serialize_first_form(page.text)
    conn = connect(cfg.paths.db_path)
    try:
        today = conn.execute(
            "SELECT id FROM candidates WHERE evaluation_run_id = ? AND "
            "ticker = ?", (DRIFT_RUN, TICKER)).fetchone()[0]
    finally:
        conn.close()
    altered = json.loads(form["decision_nights_anchor"])
    for n in altered:
        if n["candidate_id"] == today:
            n["evaluation_run_id"] = 121
    return {"decision_nights_anchor": json.dumps(altered),
            "decision_candidate_id": form["decision_candidate_id"]}


# (id, the call site at 8f35f21c, the refusal text that proves THAT rung
# fired, how the case refuses). `over` is a dict of form overrides or a
# callable(cfg, client, monkeypatch) -> dict.
_SITES = [
    ("rationale", 1008, "Invalid rationale", {"rationale": "not-a-rationale"}),
    ("stop-ge-entry", 1039, "stop must be < entry", {"initial_stop": "18.50"}),
    ("entry-intent", 1070, "invalid entry_intent", {"entry_intent": "bogus"}),
    ("cp-override-uncached", 1107,
     "Chart-pattern override requires a cached classification", {"chart_pattern_operator": "flag"}),
    ("cp-algo-enum", 1133, "chart_pattern_algo must be one of", {"chart_pattern_algo": "bogus"}),
    ("cp-run-missing", 1176,
     "does not reference an existing pipeline_runs row", {
        "chart_pattern_algo": "flag", "chart_pattern_algo_confidence": "0.9",
        "chart_pattern_classification_pipeline_run_id": "999999"}),
    ("cp-no-classification", 1192, "no cached classification exists", lambda cfg, client, mp: {
        "chart_pattern_algo": "none",
        "chart_pattern_classification_pipeline_run_id": str(
            _no_classification_run(cfg))}),
    ("sector-anchor-missing", 1257, "sector/industry anchor rejected",
     {"sector_industry_evaluation_run_id": "999999"}),
    ("sector-mismatch", 1315, "sector mismatch for", {
        "sector_industry_evaluation_run_id": str(DRIFT_RUN),
        "sector": "A Sector The Candidate Does Not Carry"}),
    ("auto-fill-anchor", 1418, "malformed", {
        "schwab_source_value_json": _UNDECODABLE,
        "fill_origin_at_form_render": "schwab_auto"}),
    ("claim-without-anchor", 1650,
     "claims auto-fill provenance but schwab_source_value_json is empty", {
        "schwab_source_value_json": "",
        "fill_origin_at_form_render": "schwab_auto"}),
    ("pe-anchor", 1692, "is not an integer", {"pattern_evaluation_id": "abc"}),
    ("decision-night", 1915, "no longer offered",
     lambda cfg, client, mp: _decision_refusal(client, cfg)),
    ("input-domain [stubbed record_entry]", 2456,
     "Trade entry rejected: entry_price must be finite", lambda cfg, client, mp: (
        _raise_from_record_entry(mp, __import__(
            "swing.trades.entry", fromlist=["EntryInputDomainError"]
        ).EntryInputDomainError("entry_price must be finite")) or {})),
    ("chart-pattern-valueerror [stubbed record_entry]", 2490,
     "failed validation: chart_pattern invariant violated",
     lambda cfg, client, mp: (_raise_from_record_entry(
         mp, ValueError("chart_pattern invariant violated")) or {})),
    ("chart-pattern-integrity [stubbed record_entry]", 2540,
     "failed validation: CHECK constraint failed: chart_pattern_algo",
     lambda cfg, client, mp: (_raise_from_record_entry(
         mp, sqlite3.IntegrityError(
             "CHECK constraint failed: chart_pattern_algo")) or {})),
]
# An answer the case itself refuses is not re-selectable (no such option).
_NOT_RESELECTABLE = {"entry-intent": {"entry_intent"}}


@pytest.mark.parametrize(
    ("over", "site", "said"),
    [pytest.param(o, s, t, id=f"{i}@{s}") for i, s, t, o in _SITES])
def test_d47_every_early_400_keeps_the_pre_trade_answers(
        seeded_db, monkeypatch, over, site, said):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _stub_fresh_fetch(monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        extra = over(cfg, client, monkeypatch) if callable(over) else over
        sent = _sent(**extra)
        r = client.post("/trades/entry", data=sent,
                        headers={"HX-Request": "true"})
    assert r.status_code == 400, r.text
    assert said in html.unescape(r.text), f"call site {site}: another rung fired"
    assert _written(cfg) == []
    recovery = _serialize_first_form(r.text)
    case = next(i for i, s, _t, _o in _SITES if s == site)
    skip = _NOT_RESELECTABLE.get(case, set())
    kept = {k: recovery.get(k) for k in _ANSWERS if k not in skip}
    assert kept == {k: v for k, v in _ANSWERS.items() if k not in skip}, (
        f"call site {site}: the recovery form dropped pre-trade answers")
    # The submitted share count still rides back (the six-field replace).
    assert recovery["shares"] == sent["shares"]


def test_d47_an_invalid_intent_comes_back_unclassified_never_suggested(
        seeded_db, monkeypatch):
    """The one answer a case refuses: `entry_intent='bogus'` is the draft, so
    no option is selected and the browser posts the first, "(unclassified)"
    -- the bad value is cleared, and the advisory suggestion is NOT
    re-seeded over the operator's submission."""
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _stub_fresh_fetch(monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        r = client.post("/trades/entry", data=_sent(entry_intent="bogus"),
                        headers={"HX-Request": "true"})
    assert r.status_code == 400, r.text
    assert _serialize_first_form(r.text)["entry_intent"] == ""


def test_d47_the_recovery_form_still_carries_the_fresh_anchor(
        seeded_db, monkeypatch):
    """Drafts are the operator's typed answers, never anchors: a refused
    auto-fill anchor is still replaced by the FRESH one (D86 form C, 4h (iv))
    while the answers come back."""
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    _stub_fresh_fetch(monkeypatch)
    sent = _sent(schwab_source_value_json=_UNDECODABLE,
                 fill_origin_at_form_render="schwab_auto")
    with TestClient(create_app(cfg, cfg_path)) as client:
        r = client.post("/trades/entry", data=sent,
                        headers={"HX-Request": "true"})
    assert r.status_code == 400, r.text
    recovery = _serialize_first_form(r.text)
    assert _REJECTED not in recovery["schwab_source_value_json"]
    assert _FRESH in recovery["schwab_source_value_json"]
    assert recovery["thesis"] == _ANSWERS["thesis"]
