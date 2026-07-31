"""ITEM 3 -- the attest / broker-order-id contract, at ALL THREE MIRRORS
(CHARC authorised the migration amendment, 2026-07-30).

THE CONTRACT: only an `acted_manually` attestation may carry
`actual_broker_order_id`. A row saying `was_away` or `chose_not_to_act` while
naming an observed broker order asserts two incompatible things -- the
classifier scores the EXCULPATORY attestation, keeping the fire out of the
discipline signal, while the report's origin query simultaneously names the
order he says he did not place.

WHY THE SCHEMA HALF IS REQUIRED AND NOT BELT-AND-BRACES (RD): the project's
adjudication rule is that a finding premised on a schema-prevented value is out
of scope PROVIDED the constraint is cited and actually holds. Route-plus-
dataclass leaves a raw INSERT able to create an incoherent attest row, so the
citation would have been false. The schema is the write-boundary authority.

WHY NOW: `0033` is UNAPPLIED (live `schema_version` is 32 and
`latch_order_intents` does not exist), so this is a TEXT EDIT. After it ships
and applies, SQLite cannot add a CHECK to an existing table at all -- it needs
a new migration plus a full table rebuild. The window closes at merge.
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.models import LatchOrderIntent

_GOOD_TS = "2026-07-29T12:00:00"
_GOOD_SESSION = "2026-07-29"
_ORDER_ID = "1002937461"


def _fresh(tmp_path):
    from swing.data.db import ensure_schema

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
    return conn, int(cur.lastrowid)


@pytest.fixture
def conn_cid(tmp_path):
    conn, cid = _fresh(tmp_path)
    yield conn, cid
    conn.close()


def _attest_kwargs(cid: int, disposition: str, key: str, order_id) -> dict:
    return dict(
        candidate_id=cid, evaluation_run_id=121, ticker="FTRE",
        detection_date="2026-07-20", pipeline_run_id=None,
        idempotency_key=key, action_session_date=_GOOD_SESSION,
        recorded_ts=_GOOD_TS, surface="latch_panel", intent_kind="attest",
        attested_disposition=disposition, actual_broker_order_id=order_id)


def _raw_insert(conn, kwargs: dict) -> None:
    """A RAW INSERT -- deliberately BYPASSING the dataclass and the route, so
    this probes the SCHEMA and nothing else. It is the exact vector the
    dataclass mirror cannot close: `record_intent` is reachable from anywhere,
    and so is a bare `conn.execute`."""
    cols = ", ".join(kwargs)
    ph = ", ".join("?" * len(kwargs))
    conn.execute(
        f"INSERT INTO latch_order_intents ({cols}) VALUES ({ph})",
        tuple(kwargs.values()))


# --------------------------------------------------------------------------
# MIRROR 1 -- the SCHEMA (migration 0033). The one this item adds.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("disposition", ["was_away", "chose_not_to_act"])
def test_the_schema_refuses_a_NON_acted_attestation_carrying_an_order_id(
        conn_cid, disposition):
    conn, cid = conn_cid
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            _raw_insert(conn, _attest_kwargs(
                cid, disposition, f"k-{disposition}", _ORDER_ID))


def test_the_schema_ADMITS_an_acted_manually_attestation_naming_its_order(
        conn_cid):
    """THE OTHER HALF OF THE PAIR, and it is not decoration: `acted_manually` is
    precisely the path that exists for orders the framework did NOT prepare, so
    a CHECK that refused it would delete the only route by which a manual order
    reaches the distinguishability query."""
    conn, cid = conn_cid
    with conn:
        _raw_insert(conn, _attest_kwargs(
            cid, "acted_manually", "k-acted", _ORDER_ID))
    assert conn.execute(
        "SELECT actual_broker_order_id FROM latch_order_intents "
        "WHERE idempotency_key = 'k-acted'").fetchone()[0] == _ORDER_ID


@pytest.mark.parametrize(
    "disposition", ["was_away", "chose_not_to_act", "acted_manually"])
def test_the_schema_admits_EVERY_attestation_that_names_NO_order(
        conn_cid, disposition):
    """The constraint is about the EVIDENCE, not about the disposition: an
    attestation with no observed order is coherent in all three states."""
    conn, cid = conn_cid
    with conn:
        _raw_insert(conn, _attest_kwargs(cid, disposition, f"n-{disposition}",
                                         None))


# --------------------------------------------------------------------------
# MIRROR 2 -- the DATACLASS validator (`swing/data/models.py`).
# --------------------------------------------------------------------------
@pytest.mark.parametrize("disposition", ["was_away", "chose_not_to_act"])
def test_the_dataclass_refuses_the_same_row(disposition):
    with pytest.raises(ValueError, match="only an `acted_manually` attestation"):
        LatchOrderIntent(intent_id=None, **_attest_kwargs(
            7, disposition, "k", _ORDER_ID))


def test_the_dataclass_admits_the_acted_manually_row():
    intent = LatchOrderIntent(intent_id=None, **_attest_kwargs(
        7, "acted_manually", "k", _ORDER_ID))
    assert intent.actual_broker_order_id == _ORDER_ID


# --------------------------------------------------------------------------
# MIRROR 3 -- the ROUTE guard (`POST /latches/intent`).
# --------------------------------------------------------------------------
def test_the_route_guard_is_present_and_names_the_same_contract():
    """THE THIRD MIRROR. The route's BEHAVIOUR is driven end to end in
    `tests/web/test_routes/test_latches_intent_route.py`
    (`test_only_an_ACTED_MANUALLY_attestation_may_carry_a_broker_order_id`);
    what THIS
    asserts is the #11 property neither of the other two tests can -- that all
    THREE layers exist, so a reader deleting one is told which siblings it had.

    IT PINS THE GUARD'S EXACT PREDICATE, not two tokens that appear all over the
    file (Codex R1 MINOR on the ruling pass). Searching for `acted_manually`
    anywhere in a module that also builds the attest roster would keep passing
    with the conditional deleted and only its message left behind -- a test that
    cannot fail is not a mirror.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "swing/web/routes/latches.py"
    text = src.read_text(encoding="utf-8")
    assert 'answer["attested_disposition"] != "acted_manually"' in text, (
        "the route-side half of the contract is GONE; the schema and the "
        "dataclass still hold, but the operator now gets a 500-shaped failure "
        "instead of a named 400")
    assert 'kind == "attest" and answer["actual_broker_order_id"]' in text
