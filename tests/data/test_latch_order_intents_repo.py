"""latch_order_intents repo - the IDEMPOTENT APPEND, and nothing else.

Arc 21-B Task 1. The repo owns steps 4/6/7 of the handler order (SELECT-by-key,
`INSERT ... ON CONFLICT DO NOTHING`, re-SELECT); the ROUTE owns parsing,
re-derivation and every response.
"""
from __future__ import annotations

import json

import pytest

from swing.data.db import ensure_schema
from swing.data.models import LatchOrderIntent
from swing.data.repos.latch_order_intents import (
    get_intent,
    get_intent_by_key,
    list_intents_for_latch,
    list_intents_since,
    record_intent,
)
from swing.latches.constants import LATCH_BROKER_SNAPSHOT_KEYS
from swing.latches.order_intent import _digest, build_idempotency_key

_TS = "2026-07-29T12:00:00"
_SESSION = "2026-07-29"


@pytest.fixture
def conn_cid(tmp_path):
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T20:06:25', '2026-07-17', '2026-07-20', "
            "1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 18.34, 18.34, 14.88, 'universe')")
    yield conn, int(cur.lastrowid)
    conn.close()


def _envelope(**over) -> str:
    env = {
        "broker_snapshot_ts": _TS,
        "broker_snapshot_branch": "presence",
        "broker_snapshot_digest": "b" * 64,
        "broker_snapshot_session": _SESSION,
        "attributable_order_count": 1,
        "exact_framework_match_count": 0,
        "indeterminate": False,
    }
    env.update(over)
    assert set(env) == set(LATCH_BROKER_SNAPSHOT_KEYS)
    return json.dumps(env)


def _place(cid: int, key: str = "k-place", **over) -> LatchOrderIntent:
    kw = dict(
        intent_id=None, candidate_id=cid, evaluation_run_id=121, ticker="FTRE",
        detection_date="2026-07-20", pipeline_run_id=None,
        idempotency_key=key, action_session_date=_SESSION, recorded_ts=_TS,
        surface="latch_panel", intent_kind="place",
        framework_order_type="LIMIT", framework_duration="GOOD_TILL_CANCEL",
        framework_limit_price=18.89, framework_quantity=9,
        derivation_zone_cap_pct=3.0, derivation_sizing_equity=7500.0,
        derivation_max_risk_pct=0.005, derivation_position_pct_cap=0.15,
        derivation_sizing_basis="limit_price", derivation_regime_close=19.20,
        derivation_regime_close_session=_SESSION,
        derivation_real_equity=1234.56, derivation_equity_floor=7500.0,
        derivation_nightly_recommendation_shares=10,
    )
    kw.update(over)
    return LatchOrderIntent(**kw)


def _validity(cid: int, parent_id: int, key: str = "k-val",
              **over) -> LatchOrderIntent:
    kw = dict(
        intent_id=None, candidate_id=cid, evaluation_run_id=121, ticker="FTRE",
        detection_date="2026-07-20", pipeline_run_id=None,
        idempotency_key=key, action_session_date=_SESSION, recorded_ts=_TS,
        surface="latch_panel", intent_kind="validity",
        validated_place_intent_id=parent_id,
        validity_outcome="accepted_by_broker", validity_detail=_envelope(),
        actual_order_type="LIMIT", actual_duration="GOOD_TILL_CANCEL",
        actual_limit_price=18.89, actual_quantity=10,
        actual_broker_order_id="1002937461",
    )
    kw.update(over)
    return LatchOrderIntent(**kw)


def test_record_intent_appends_and_round_trips_every_column(conn_cid):
    conn, cid = conn_cid
    with conn:
        stored = record_intent(conn, intent=_place(cid))
    assert stored.intent_id is not None
    fresh = get_intent(conn, intent_id=stored.intent_id)
    for fname in (f.name for f in
                  __import__("dataclasses").fields(LatchOrderIntent)):
        assert getattr(fresh, fname) == getattr(stored, fname), fname
    # every derivation column round-trips (the section A.4 schema half)
    assert fresh.derivation_real_equity == 1234.56
    assert fresh.derivation_equity_floor == 7500.0
    assert fresh.derivation_nightly_recommendation_shares == 10


def test_record_intent_is_idempotent_on_the_key(conn_cid):
    """Two calls with the SAME key return the SAME intent_id and leave ONE row."""
    conn, cid = conn_cid
    with conn:
        a = record_intent(conn, intent=_place(cid))
    with conn:
        b = record_intent(conn, intent=_place(cid))
    assert a.intent_id == b.intent_id
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_intents").fetchone()[0] == 1


def test_a_lost_race_returns_the_winners_row_without_an_integrity_error(conn_cid):
    """`ON CONFLICT DO NOTHING` + the re-SELECT. Two requests can BOTH miss the
    step-4 SELECT; the loser must return the winner's row rather than surfacing
    an IntegrityError. Simulated by pre-inserting the row between the SELECT and
    the INSERT."""
    conn, cid = conn_cid
    intent = _place(cid)
    with conn:
        winner = record_intent(conn, intent=intent)
    # A second append of the identical key, now going through the INSERT path
    # by bypassing the SELECT short-circuit.
    from swing.data.repos import latch_order_intents as repo
    calls = {"n": 0}
    real = repo.get_intent_by_key

    def _miss_once(conn_, *, idempotency_key):
        calls["n"] += 1
        if calls["n"] == 1:
            return None          # pretend the step-4 SELECT missed
        return real(conn_, idempotency_key=idempotency_key)

    repo.get_intent_by_key = _miss_once
    try:
        with conn:
            loser = record_intent(conn, intent=intent)
    finally:
        repo.get_intent_by_key = real
    assert loser.intent_id == winner.intent_id
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_intents").fetchone()[0] == 1


def test_record_intent_never_uses_insert_or_replace(conn_cid):
    """The DELETE+INSERT / new-PK / cascade gotcha. The table is APPEND-ONLY.

    Asserted on the SQL THE REPO ACTUALLY EXECUTES (a trace callback), not on the
    source text: the module's own docstring explains why `INSERT OR REPLACE` is
    forbidden, so a substring search over the file would fail against CORRECT
    code for the wrong reason -- and would pass if the explanation were deleted.
    """
    conn, cid = conn_cid
    seen: list[str] = []
    conn.set_trace_callback(seen.append)
    try:
        with conn:
            record_intent(conn, intent=_place(cid))
    finally:
        conn.set_trace_callback(None)
    inserts = [s for s in seen if "latch_order_intents" in s
               and s.strip().upper().startswith("INSERT")]
    assert inserts, "the repo must have issued an INSERT"
    for stmt in inserts:
        assert "OR REPLACE" not in stmt.upper()
        assert "ON CONFLICT(idempotency_key) DO NOTHING" in stmt


def test_list_intents_for_latch_orders_by_recorded_ts_then_intent_id(conn_cid):
    """The arc's canonical total order. The `intent_id` tiebreak is LOAD-BEARING:
    `recorded_ts` is WHOLE SECONDS, so two rows CAN share one, and the GOVERNING
    row within a kind is the LATEST by exactly this order."""
    conn, cid = conn_cid
    with conn:
        first = record_intent(conn, intent=_place(cid, key="a"))
        second = record_intent(conn, intent=_place(
            cid, key="b", action_session_date="2026-07-28"))
    rows = list_intents_for_latch(conn, candidate_id=cid)
    assert [r.intent_id for r in rows] == [first.intent_id, second.intent_id]


def test_list_intents_since_filters_on_recorded_ts_not_action_session_date(
        conn_cid):
    """THE REPORT'S TIME AXIS. Filtering on the MANDATE session would put a
    validity answer given in August ABOUT a July render into JULY, and would drop
    a post-month-end CORRECTION out of the current read entirely."""
    conn, cid = conn_cid
    with conn:
        parent = record_intent(conn, intent=_place(cid, key="p"))
        record_intent(conn, intent=_validity(
            cid, parent.intent_id, key="v",
            recorded_ts="2026-08-03T09:00:00"))
    # August cutoff: the validity row (recorded in August, ABOUT a July-29
    # mandate) is IN; the July place row is OUT.
    august = list_intents_since(conn, since_ts="2026-08-01T00:00:00")
    assert [r.intent_kind for r in august] == ["validity"]
    assert august[0].action_session_date == _SESSION      # the MANDATE's session
    # ...and a July cutoff sees both.
    assert len(list_intents_since(conn, since_ts="2026-07-01T00:00:00")) == 2


def test_get_intent_by_key_returns_none_for_an_unknown_key(conn_cid):
    conn, _ = conn_cid
    assert get_intent_by_key(conn, idempotency_key="nope") is None


# --------------------------------------------------------------------------
# The idempotency digest
# --------------------------------------------------------------------------
def test_the_digest_is_INJECTIVE_over_delimiter_bearing_operator_text():
    """LENGTH-PREFIXED, never delimiter-joined. A single-character '|' join is
    ambiguous the moment a component can CONTAIN that character -- and one of
    them is `decline_reason`, FREE OPERATOR TEXT. Two different decisions could
    then produce the same pre-hash string and collapse onto one ledger row.

    The pair below is the discriminator: under a `'|'.join(...)` encoding both
    reasons produce the pre-hash string "a|b" and therefore the SAME digest.
    """
    assert _digest("a", "b") != _digest("a|b")
    assert _digest("a|b", "") != _digest("a", "|b")
    # a digit run adjacent to the length prefix must not alias either
    assert _digest("1:x") != _digest("1", "x")


def test_two_declines_differing_only_in_reason_get_distinct_keys():
    common = dict(candidate_id=11261, action_session_date=_SESSION,
                  surface="latch_panel", intent_kind="decline",
                  anchor_digest="anchor")
    a = build_idempotency_key(**common, actual_digest=_digest("too|extended"))
    b = build_idempotency_key(**common, actual_digest=_digest("too", "extended"))
    assert a != b


def test_a_validity_key_requires_its_parent_link():
    """The parent link IS the validity branch's session component, so a key
    built without it would silently fall back to a value that MOVES EVERY DAY."""
    with pytest.raises(ValueError, match="validated_place_intent_id"):
        build_idempotency_key(
            candidate_id=1, action_session_date=_SESSION, surface="latch_panel",
            intent_kind="validity", anchor_digest="a", actual_digest="b")


def test_only_an_ACTED_MANUALLY_attestation_may_carry_a_broker_order_id():
    """CODEX-AUTO-REVIEW MAJOR. The HTTP route rejects the contradiction, but
    `record_intent` is reachable from anywhere, so the contract belongs on the
    dataclass too. A row saying `was_away` while carrying an observed broker
    order asserts two incompatible things: the classifier scores the EXCULPATORY
    attestation -- keeping the fire out of the discipline signal -- while the
    report's origin query names the order he says he did not place.

    THE SCHEMA HALF IS NOT MIRRORED and that is FLAGGED, not hidden: adding the
    CHECK is a migration edit this dispatch is not authorised to make.
    """
    import pytest

    from swing.data.models import LatchOrderIntent

    def _attest(disposition, order_id):
        return LatchOrderIntent(
            intent_id=None, candidate_id=1, evaluation_run_id=121,
            ticker="FTRE", detection_date="2026-07-20", pipeline_run_id=None,
            idempotency_key="k", action_session_date="2026-07-27",
            recorded_ts="2026-07-27T09:00:00", surface="latch_panel",
            intent_kind="attest", attested_disposition=disposition,
            actual_broker_order_id=order_id)

    for disposition in ("was_away", "chose_not_to_act"):
        with pytest.raises(ValueError, match="acted_manually"):
            _attest(disposition, "4242")
        _attest(disposition, None)          # legal without the evidence
    assert _attest("acted_manually", "4242").actual_broker_order_id == "4242"
