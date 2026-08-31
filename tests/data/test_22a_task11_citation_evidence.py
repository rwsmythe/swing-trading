"""22-A Task 11 -- the `$.authorization` evidence contract, at the SQL grain.

THIRTY-FIVE CASES, EVERY ONE A ONE-FIELD VARIATION OUT OF AN ACCEPTED BASELINE.
``seed_latch_ladder_citation`` (task 2) builds a TRUTHFUL ``latch_ladder``
correction payload from real emitters and a companion test proves the trigger
ACCEPTS it.  That accepted baseline is the instrument: a refusal-only test set
cannot establish that a guard can ever accept, and a rejection case starting
from a row that was never acceptable proves nothing about the clause it names.

So every case here does the same three things -- take the baseline, change
EXACTLY ONE thing, and assert the verdict -- and every REJECT case additionally
asserts that the UNMUTATED baseline inserts, so the mutation is demonstrably
what flipped it rather than some unrelated interlocking clause.

THE VERDICT MATRIX IS EXPLICIT, because four of these are ACCEPTANCES and an
acceptance read as an oversight is how a declared limit becomes a surprise:

  ACCEPT  34a 34b (the coverage-truthfulness limit)
          34f 34g (the single-rounding-authority limit and its discriminator)
          49j     (the service-validated limit)
  REJECT  34c 34d 34e * 39a 39b 39c * 48a-48p * 49a-49i

RAW INSERTS THROUGHOUT.  These are SCHEMA cases: the whole point is to plant
shapes the service would never build, which is the only way to learn what the
trigger actually enforces rather than what the service happens to emit.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3

import pytest

from tests.trades._cohort_provenance_fixtures import set_fill_envelope

from swing.trades.latched_origin import (
    AUTHORIZATION_CLAUSES,
    AUTHORIZATION_KEYS,
    SERVICE_VALIDATED,
    SQL_BOUND,
)
from tests.data.test_22a_task2_migration_0037 import (  # noqa: F401
    _insert_payload,
    conn,
    seed_latch_ladder_citation,
)

# ---------------------------------------------------------------------------
# CASE ID MANIFESTS -- literal lists, because the closure check's static walk
# reads them out of the AST rather than running anything (a run trace only sees
# the branches a fixture happened to take).
# ---------------------------------------------------------------------------
OMISSION_CASE_IDS = [
    "48a", "48b", "48c", "48d", "48e", "48f", "48g", "48h",
    "48i", "48j", "48k", "48l", "48m", "48n", "48o", "48p",
]
FIDELITY_CASE_IDS = [
    "49a", "49b", "49c", "49d", "49e", "49f", "49g", "49h", "49i",
]
COVERAGE_CASE_IDS = ["34a", "34b", "34c", "34d", "34e"]
ROUNDING_CASE_IDS = ["34f", "34g"]
TIE_BASIS_CASE_IDS = ["39a", "39b", "39c"]
SERVICE_LIMIT_CASE_IDS = ["49j"]


def _blob(payload: dict) -> dict:
    return json.loads(payload["cited_latch_probe_json"])


def _with_blob(payload: dict, blob: dict) -> dict:
    payload = dict(payload)
    payload["cited_latch_probe_json"] = json.dumps(blob)
    return payload


def _assert_baseline_inserts(conn_: sqlite3.Connection, payload: dict) -> None:
    """The mutation is what flipped the verdict, and this is how we know.

    Without it a REJECT case is satisfied by any interlocking clause the
    fixture happened to break -- a test blocked for a reason unrelated to the
    guard proves nothing about the guard.
    """
    _insert_payload(conn_, payload)
    # ``seed_latch_ladder_citation`` has already dropped the append-only DELETE
    # trigger to clear its own ``last_word`` row, so the table is writable
    # here. Nothing is re-created: a hand-typed replacement for a shipped
    # trigger body is the drift hazard the barrier helper exists to avoid, and
    # no case below depends on delete-immutability.
    conn_.execute("DELETE FROM provenance_corrections")


def _assert_rejected(conn_: sqlite3.Connection, payload: dict) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_payload(conn_, payload)


# ===========================================================================
# 48a-48p -- OMISSION, one per $.authorization entry (REJECT)
#
# SIXTEEN, not eleven: the eleven rungs plus the five envelope guards now that
# they are separately enumerated.  A missing JSON key makes `json_type` NULL,
# `NULL = 'text'` NULL, and a NULL `WHEN` clause DOES NOT FIRE -- so the
# COALESCE wrapper around the latch block is the whole of what makes these
# reject rather than silently pass.
# ===========================================================================
@pytest.mark.parametrize(
    ("case_id", "key"),
    list(zip(OMISSION_CASE_IDS, AUTHORIZATION_KEYS, strict=True)),
    ids=OMISSION_CASE_IDS)
def test_an_omitted_authorization_entry_is_rejected(
        conn, case_id: str, key: str) -> None:
    """One entry removed, everything else truthful.

    An implementation recording only aliveness / coverage / snapshot /
    tie-basis fails thirteen of the sixteen.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    del blob["authorization"][key]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_the_omission_family_covers_every_roster_entry() -> None:
    """The manifest is CLOSED against the roster, not maintained beside it.

    A hand-enumerated roster fails the same way as the count it replaced, so
    the check walks what the code references and asserts the two sets agree.
    """
    assert len(OMISSION_CASE_IDS) == len(AUTHORIZATION_KEYS) == 16, (
        f"{len(OMISSION_CASE_IDS)} omission cases against "
        f"{len(AUTHORIZATION_KEYS)} roster entries")


# ===========================================================================
# 49a-49i -- INPUT FIDELITY on the nine SQL-BOUND RUNGS (REJECT)
#
# PRESENCE IS NOT FIDELITY.  Every entry present, every verdict still 'pass',
# exactly one entry's `input` moved away from its source.  Every one of these
# PASSES against a presence-only trigger -- sixteen keys, sixteen passes --
# which is the whole of review 22A-R8-05.
# ===========================================================================
_RUNG_FIDELITY_MUTATIONS: dict[str, object] = {
    "rung1_link_ticker": "ZZZZ",
    "rung2_link_parent": 987654,
    "rung3_validity_outcome": "rejected_by_broker",
    "rung3b_latest_validity_child": 987654,
    "rung3c_link_broker_order_id": "9999999999",
    "rung4_governing_place_intent": 987654,
    "rung5_cancel_intent_id": 987654,
    "rung6_consuming_trade_id": 987654,
    "rung9_stored_freeze_tier": "pre_barrier_reconstructed",
}


@pytest.mark.parametrize(
    ("case_id", "key"),
    list(zip(FIDELITY_CASE_IDS, _RUNG_FIDELITY_MUTATIONS, strict=True)),
    ids=FIDELITY_CASE_IDS)
def test_a_fabricated_input_on_a_bound_rung_is_rejected(
        conn, case_id: str, key: str) -> None:
    """A substituted order id, a different place intent, a rejected outcome.

    Each must be REJECTED by the binding subquery, not merely noticed.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["authorization"][key]["input"] = _RUNG_FIDELITY_MUTATIONS[key]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_the_fidelity_family_covers_every_sql_bound_rung() -> None:
    """NINE, and the roster is what says which nine.

    The five envelope guards are ALSO ``SQL_BOUND`` since inherited finding
    22A-R9-06 -- by correction time their inputs are PERSISTED on the fill the
    row already cites -- so the family below covers them separately rather
    than letting the plan's pre-R9-06 count stand as the coverage claim.
    """
    bound_rungs = [
        c.key for c in AUTHORIZATION_CLAUSES
        if c.binding == SQL_BOUND and c.key.startswith("rung")
    ]
    assert list(_RUNG_FIDELITY_MUTATIONS) == bound_rungs, (
        f"the mutation table and the roster disagree: "
        f"{sorted(set(_RUNG_FIDELITY_MUTATIONS) ^ set(bound_rungs))}")
    assert len(FIDELITY_CASE_IDS) == len(bound_rungs) == 9


# ---------------------------------------------------------------------------
# NO CASE ID -- the FIVE ENVELOPE GUARDS' fidelity.
#
# The plan's 49-series was written when the guards were classed
# service-validated; 22A-R9-06 moved them to SQL_BOUND and the migration binds
# them. A repair nobody exercises is a repair on paper, so the family is
# covered here without inventing plan case ids for it.
# ---------------------------------------------------------------------------
_GUARD_FIDELITY_MUTATIONS: dict[str, object] = {
    "guard_fill_origin": "operator_typed",
    "guard_envelope_symbol": "ZZZZ",
    "guard_quantity": 987654.0,
    "guard_framework_price_bound": 987654.0,
    "guard_broker_limit_bound": 987654.0,
}


@pytest.mark.parametrize("key", list(_GUARD_FIDELITY_MUTATIONS))
def test_a_fabricated_input_on_an_envelope_guard_is_rejected(
        conn, key: str) -> None:
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["authorization"][key]["input"] = _GUARD_FIDELITY_MUTATIONS[key]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_the_guard_fidelity_family_covers_every_sql_bound_guard() -> None:
    bound_guards = [
        c.key for c in AUTHORIZATION_CLAUSES
        if c.binding == SQL_BOUND and c.key.startswith("guard_")
    ]
    assert list(_GUARD_FIDELITY_MUTATIONS) == bound_guards


# ===========================================================================
# 49j -- THE SERVICE-VALIDATED LIMIT, PINNED HONESTLY (ACCEPT)
# ===========================================================================
def test_a_fabricated_input_on_a_service_validated_rung_is_accepted_case_49j(
        conn) -> None:
    """THIS IS A LIMIT OF THE TRIGGER, NOT A GUARANTEE, AND IT IS DECLARED.

    Rungs 7 and 8 rest on a scan result and on derivation state no subquery
    can reach, so SQL asserts their PRESENCE, TYPE and ``verdict='pass'`` and
    nothing more.  A fabricated ``input`` on either is ACCEPTED.

    Stated as a case rather than only in prose (S8-L17), because a limit
    written in a docstring and nowhere else is how a limit becomes a surprise
    -- and because a reader who found this row in the audit trail is entitled
    to know the trigger never claimed to have checked it.
    """
    service_validated = [
        c.key for c in AUTHORIZATION_CLAUSES if c.binding == SERVICE_VALIDATED
    ]
    assert service_validated == [
        "rung7_consumption_scan_fill_ids", "rung8_competitor_link_ids"], (
        "the service-validated set moved; 49j's scope moves with it")

    payload = seed_latch_ladder_citation(conn)
    blob = _blob(payload)
    for key in service_validated:
        blob["authorization"][key]["input"] = [987654, 987655]
    _insert_payload(conn, _with_blob(payload, blob))
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections "
        "WHERE admission_tier = 'latch_ladder'").fetchone()[0] == 1


# ===========================================================================
# 34a-34e -- THE COVERAGE / EVIDENCE-SCHEMA CASES
# ===========================================================================
def test_two_identical_fabricated_coverage_arrays_are_accepted_case_34a(
        conn) -> None:
    """ACCEPTED, AND THE ACCEPTANCE IS THE POINT.

    Element-wise equality proves the two arrays agree with EACH OTHER, not
    with the NYSE calendar or with the archive.  A trigger cannot enumerate a
    session calendar, so the coverage FACT is established by the service at
    admission and by case 7b -- never by SQL.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = _blob(payload)
    fabricated = ["2001-01-02", "2001-01-03", "2001-01-04"]
    blob["coverage"] = {
        "expected_sessions": list(fabricated),
        "observed_sessions": list(fabricated),
        "missing_sessions": [],
    }
    _insert_payload(conn, _with_blob(payload, blob))
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


def test_two_empty_coverage_arrays_without_window_empty_are_accepted_case_34b(
        conn) -> None:
    """ACCEPTED, same limit, same labelling.

    Two EMPTY arrays for a window that was not empty pass the element-wise
    check trivially.  The trigger's claim is STRUCTURAL coherence plus the
    cross-bindings; it is not a coverage proof and this case says so.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = _blob(payload)
    blob["coverage"] = {
        "expected_sessions": [],
        "observed_sessions": [],
        "missing_sessions": [],
    }
    _insert_payload(conn, _with_blob(payload, blob))
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


def test_an_omitted_required_evidence_key_is_rejected_case_34c(conn) -> None:
    """THE DISCRIMINATING ONE, and it passes a closure-only implementation.

    ``json_remove(<obj>, <every allowed key>) = '{}'`` rejects EXTRA keys and
    says nothing about MISSING ones -- SQLite renders a missing path and a
    JSON null identically as SQL NULL.  Only the positive
    ``json_type(...) IS NOT NULL`` assertion catches this.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    del blob["evidence_version"]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_mismatched_horizon_session_is_rejected_case_34d(conn) -> None:
    """``$.horizon_session`` IS the fill session and IS bound in SQL.

    (The plan's older name for this field was ``$.probe_session``, which
    carried two incompatible definitions until review 22A-R5-02 split it;
    ``$.bars_through`` is the exchange-calendar-derived prior session and is
    validated in the SERVICE, because a trigger cannot walk a calendar.)
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["horizon_session"] = "2001-01-02"
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_mismatched_validity_parent_is_rejected_case_34e(conn) -> None:
    """The cited validity intent's parent MUST equal the cited place intent.

    Without the relation a raw link can assert a false parent while every
    other check passes (review 22A-R3-10).

    AN ISOLATING MUTATION IS UNCONSTRUCTABLE, AND THAT IS WORTH SAYING RATHER
    THAN GLOSSING.  The relation would be violated alone only if
    ``link.place_intent_id`` equalled the cited place while the cited
    validity's parent did not -- but the MINTING trigger derives the link's
    place FROM the validity's parent, ``latch_order_intents`` and
    ``latch_order_mandate_links`` are both append-only (measured: the UPDATE
    aborts), and a hand-inserted second link reusing the validity row trips
    ``UNIQUE(validity_intent_id)``.  So this case plants a REAL second place
    row on the same candidate and cites it, which violates the parent relation
    AND the link's duplicated-field relation together.

    The paired control below is what keeps it meaningful: the UNMUTATED
    baseline inserts, so the citation change is demonstrably what flipped the
    verdict rather than some pre-existing incoherence in the fixture.
    """
    from tests._latch_link_fixtures_22a import insert_intent, place_row
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    candidate_id = blob["fire_candidate_id"]
    run_id, session = conn.execute(
        "SELECT c.evaluation_run_id, e.action_session_date FROM candidates c "
        "JOIN evaluation_runs e ON e.id = c.evaluation_run_id WHERE c.id = ?",
        (candidate_id,)).fetchone()
    second = place_row(candidate_id, run_id=run_id)
    second.update(ticker=CADL_TICKER, detection_date=session,
                  action_session_date=session,
                  recorded_ts="2026-08-11T12:10:00",
                  idempotency_key="task11-second-place")
    second_place_id = insert_intent(conn, second)
    payload = dict(payload)
    payload["cited_latch_place_intent_id"] = second_place_id
    _assert_rejected(conn, payload)


# ===========================================================================
# 34f / 34g -- THE SINGLE ROUNDING AUTHORITY (both ACCEPT)
# ===========================================================================
def _mint_drifted_citation(
        conn_, payload: dict, *, frozen: float, live: float, key: str):
    """Re-cite the correction onto a SECOND accepted order minted at ``frozen``,
    with the candidate then drifted to ``live``.

    THE GEOMETRY IS MINTED, NOT EDITED, because both sides are append-only:
    ``latch_order_mandate_links`` and ``latch_order_intents`` each abort an
    UPDATE (measured), and the link's frozen values are COPIED from the
    candidate by the minting trigger.  So the candidate is moved to the frozen
    value, an order is placed and accepted -- which mints a link freezing it --
    and the candidate then moves to the live value.  The barrier is lifted and
    RESTORED VERBATIM around each candidate write, the arc's own idiom for
    planting a state the barrier now prevents from arising (cases 9/9b).

    Every binding the trigger checks is re-pointed at the new order, so the row
    that comes back differs from the baseline in the two RAW PRICES and nothing
    else.
    """
    from tests._candidates_barrier_helper import candidates_barrier_lifted
    from tests._latch_link_fixtures_22a import (
        insert_intent,
        place_row,
        validity_row,
    )
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    blob = _blob(payload)
    candidate_id = blob["fire_candidate_id"]
    run_id, session = conn_.execute(
        "SELECT c.evaluation_run_id, e.action_session_date FROM candidates c "
        "JOIN evaluation_runs e ON e.id = c.evaluation_run_id WHERE c.id = ?",
        (candidate_id,)).fetchone()
    order_id = f"10099{abs(hash(key)) % 90000 + 10000}"
    with candidates_barrier_lifted(conn_):
        conn_.execute("UPDATE candidates SET initial_stop = ? WHERE id = ?",
                      (frozen, candidate_id))
    place = place_row(candidate_id, run_id=run_id)
    place.update(ticker=CADL_TICKER, detection_date=session,
                 action_session_date=session,
                 recorded_ts="2026-08-11T12:20:00",
                 idempotency_key=f"{key}-place")
    place_id = insert_intent(conn_, place)
    validity = validity_row(candidate_id, place_id, run_id=run_id)
    # The accepted quantity must COVER the fill, exactly as the baseline's
    # does: the citation trigger proves `guard_quantity.input <= accepted`
    # (Codex 22A-R5-01), and a re-minted order carrying the 0033 fixture's
    # default 10 against CADL's 19-share fill would refuse for a reason that
    # has nothing to do with either case's price geometry.
    accepted_quantity = int(conn_.execute(
        "SELECT quantity FROM fills WHERE fill_id = ?",
        (payload["entry_fill_id_at_correction"],)).fetchone()[0])
    validity.update(ticker=CADL_TICKER, detection_date=session,
                    action_session_date=session,
                    recorded_ts="2026-08-11T12:25:00",
                    idempotency_key=f"{key}-validity",
                    actual_quantity=accepted_quantity,
                    actual_broker_order_id=order_id)
    validity_id = insert_intent(conn_, validity)
    with candidates_barrier_lifted(conn_):
        conn_.execute("UPDATE candidates SET initial_stop = ? WHERE id = ?",
                      (live, candidate_id))
    link = dict(zip(
        [r[1] for r in conn_.execute(
            "PRAGMA table_info(latch_order_mandate_links)")],
        conn_.execute(
            "SELECT * FROM latch_order_mandate_links WHERE validity_intent_id "
            "= ?", (validity_id,)).fetchone(), strict=True))
    assert link["frozen_invalidation"] == frozen, (
        f"the mint froze {link['frozen_invalidation']}, not {frozen}; the "
        f"case would then not carry its own geometry")

    fill_id = payload["entry_fill_id_at_correction"]
    set_fill_envelope(conn_, fill_id, json.dumps(
        {"schwab_order_id": order_id,
         "schwab_instrument_symbol": CADL_TICKER}))
    live_pivot = conn_.execute(
        "SELECT pivot FROM candidates WHERE id = ?",
        (candidate_id,)).fetchone()[0]

    payload = dict(payload)
    payload.update(
        cited_latch_link_id=link["link_id"],
        cited_latch_validity_intent_id=validity_id,
        cited_latch_place_intent_id=place_id,
        cited_latch_broker_order_id=order_id,
    )
    blob["authorization"]["rung2_link_parent"]["input"] = place_id
    blob["authorization"]["rung3b_latest_validity_child"]["input"] = validity_id
    blob["authorization"]["rung3c_link_broker_order_id"]["input"] = order_id
    blob["authorization"]["rung4_governing_place_intent"]["input"] = place_id
    blob["authorization"]["rung9_stored_freeze_tier"]["input"] = (
        link["freeze_tier"])
    blob["authorization"]["guard_broker_limit_bound"]["input"] = (
        validity["actual_limit_price"])
    blob["freeze_tier"] = link["freeze_tier"]
    blob["frozen_invalidation_raw"] = link["frozen_invalidation"]
    blob["live_invalidation_raw"] = live
    blob["frozen_pivot_raw"] = link["frozen_pivot"]
    blob["live_pivot_raw"] = live_pivot
    return payload, blob


def test_a_false_equality_verdict_over_correct_raws_is_accepted_case_34f(
        conn) -> None:
    """THE DECLARED RESIDUAL (S8-L16), pinned rather than papered over.

    SQL can no longer verify that ``_equal_at_dp`` is the CORRECT rounding of
    the two raw operands: any SQL-side recomputation re-creates the
    cross-domain comparison the rule exists to forbid.  A forger can assert
    that two correctly-cited values compared equal when they did not -- and
    NOTHING MORE, because both raws stay bound to the cited link and the cited
    candidate, so he still cannot name a different mandate.

    THE FIRST VERSION OF THIS TEST CONTAINED NO FALSE VERDICT (Codex
    22A-R5-04, verified against my own test).  It loaded the truthful baseline
    -- whose raws are EQUAL, so ``invalidation_equal_at_dp = 1`` is TRUE --
    changed nothing, and inserted it, while its comment claimed "only the
    verdict over them is a lie".  It passed whether or not SQL rejects an
    actually false verdict: the vacuous-regression class, in the module
    written one commit after the same class was fixed one module over.

    The operands below are genuinely UNEQUAL at two decimals and both remain
    BOUND to their sources, so the recorded ``1`` is a real lie and the
    acceptance is the real residual.
    """
    frozen, live = 6.20, 7.90
    assert round(frozen, 2) != round(live, 2), (
        "the operands must DISAGREE at the compared precision, or the recorded "
        "verdict is true and the case pins nothing")
    payload = seed_latch_ladder_citation(conn)
    payload, blob = _mint_drifted_citation(
        conn, payload, frozen=frozen, live=live, key="task11-34f")
    blob["invalidation_equal_at_dp"] = 1        # THE LIE
    _insert_payload(conn, _with_blob(payload, blob))
    stored = conn.execute(
        "SELECT json_extract(cited_latch_probe_json, "
        "'$.frozen_invalidation_raw'), json_extract(cited_latch_probe_json, "
        "'$.live_invalidation_raw'), json_extract(cited_latch_probe_json, "
        "'$.invalidation_equal_at_dp') FROM provenance_corrections").fetchone()
    assert stored == (frozen, live, 1), (
        "the row that landed does not carry the false verdict over unequal "
        "bound raws, so it is not the residual this case claims to pin")


def test_an_eighths_price_pair_equal_in_python_is_accepted_case_34g(
        conn) -> None:
    """THE CASE THAT WOULD HAVE CAUGHT THE DEFECT, AND ITS GEOMETRY IS
    CORRECTED (inherited finding 22A-R9-05, verified by execution here).

    The plan specifies frozen = live = ``22.125`` (the live WRBY geometry).
    That does NOT discriminate: Python rounds ``22.125`` to ``22.12`` and
    SQLite rounds it to ``22.13``, so the FORBIDDEN
    ``round(...,2) = round(...,2)`` trigger evaluates ``22.13 = 22.13`` --
    TRUE -- and ACCEPTS the very row the case exists to catch.

    The discriminating pair needs two raws in ONE Python bucket and TWO SQLite
    buckets: ``22.125`` / ``22.1249``.  Python ``22.12 == 22.12`` (the service
    admits, truthfully); SQLite ``22.13 <> 22.12`` (the forbidden comparator
    refuses).  Both arithmetics are ASSERTED below rather than asserted about,
    so the case cannot silently stop discriminating if either engine changes.
    """
    frozen, live = 22.125, 22.1249
    assert round(frozen, 2) == round(live, 2), (
        "the pair must be EQUAL in Python, or the service could not truthfully "
        "have admitted it")
    sql_frozen = conn.execute("SELECT round(?, 2)", (frozen,)).fetchone()[0]
    sql_live = conn.execute("SELECT round(?, 2)", (live,)).fetchone()[0]
    assert sql_frozen != sql_live, (
        f"the pair must DIFFER in SQLite ({sql_frozen} vs {sql_live}), or the "
        f"forbidden comparator would accept it and the case would not "
        f"discriminate -- which is exactly what frozen == live == 22.125 does")

    payload = seed_latch_ladder_citation(conn)
    payload, blob = _mint_drifted_citation(
        conn, payload, frozen=frozen, live=live, key="task11-34g")
    blob["invalidation_equal_at_dp"] = 1
    _insert_payload(conn, _with_blob(payload, blob))
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


def test_the_migration_never_rounds_a_price_case_34g_gate(conn) -> None:
    """THE GREP GATE, NORMALIZED FOR CASE AND WHITESPACE (22A-R9-05(c)).

    A literal ``round(`` scan misses ``ROUND(``, ``Round(`` and ``round (``.
    Without the normalization the gate is a paragraph: the single most likely
    way to lose the rule is a later reader "repairing" the identity check into
    a rounded one, which is precisely how the defect arrived.
    """
    import re
    from pathlib import Path

    sql = Path(__import__("swing.data.db", fromlist=["x"]).__file__).parent
    text = (sql / "migrations" / "0037_latch_order_mandate_links.sql").read_text(
        encoding="utf-8")
    hits = re.findall(r"(?is)\bround\s*\(", text)
    assert not hits, (
        f"migration 0037 contains {len(hits)} round( call(s); SQL stores and "
        f"binds, it never rounds (S4.3a, the single rounding authority)")


# ===========================================================================
# 39a-39c -- THE TIE-BASIS MATRIX IS ENFORCED, NOT MERELY DECLARED
# ===========================================================================
def _tie_basis(blob: dict, payload: dict, *, reason: str) -> dict:
    blob = dict(blob)
    blob["admission_basis"] = "subject_fill_wins_same_session_tie"
    blob["clear_reason"] = reason
    blob["clear_session"] = payload["entry_fill_session_date"]
    return blob


def test_a_tie_basis_row_whose_clear_session_is_not_the_fill_is_rejected_case_39a(
        conn) -> None:
    """Under the tie basis ``$.clear_session`` is REQUIRED and BOUND."""
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _tie_basis(_blob(payload), payload, reason="horizon")
    blob["clear_session"] = "2001-01-02"
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_tie_basis_row_naming_fill_is_rejected_case_39b(conn) -> None:
    """``fill`` is excluded by the rule itself, and ``invalidation`` is
    unreachable by construction -- three reachable reasons, not four."""
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _tie_basis(_blob(payload), payload, reason="fill")
    _assert_rejected(conn, _with_blob(payload, blob))


def test_an_armed_row_with_a_non_null_clear_reason_is_rejected_case_39c(
        conn) -> None:
    """Under ``armed`` both fields are JSON null; a reason without the basis
    is an admission claiming two incompatible things at once."""
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["clear_reason"] = "horizon"
    _assert_rejected(conn, _with_blob(payload, blob))


def test_the_three_reachable_tie_reasons_are_all_accepted(conn) -> None:
    """THE ACCEPTED BASELINE FOR THE TIE BASIS, and 39a-39c need it.

    A refusal-only set over the tie matrix would pass a trigger that rejected
    the basis outright -- and then 28a-28c's admissions could never have been
    recorded.  All three reachable reasons are asserted to ADMIT.
    """
    payload = seed_latch_ladder_citation(conn)
    for reason in ("horizon", "declined", "superseded"):
        blob = _tie_basis(_blob(payload), payload, reason=reason)
        _insert_payload(conn, _with_blob(payload, blob))
        assert conn.execute(
            "SELECT COUNT(*) FROM provenance_corrections "
            "WHERE json_extract(cited_latch_probe_json, '$.clear_reason') = ?",
            (reason,)).fetchone()[0] == 1, (
            f"the tie basis refused {reason!r}, which cases 28a-28c admit")
        conn.execute("DELETE FROM provenance_corrections")


# ===========================================================================
# 22A-R4-04 -- THE SQL TWIN IS ORDER-SCOPED TOO
#
# The service's rung 5 and the migration's rung-5 twin moved TOGETHER. A twin
# encoding a DIFFERENT predicate from the reader is the same defect as a
# missing twin; here the divergence would have authorized a correction that
# then aborted at the INSERT, which is the worst of both.
# ===========================================================================
def _cancel_naming(conn_: sqlite3.Connection, payload: dict, order_id: str,
                   *, when: str = "2026-08-11T09:00:00") -> None:
    """A `cancel` intent through the PRODUCTION dataclass and repo.

    Dated STRICTLY BEFORE the fill -- the position that kills -- so nothing but
    the order-id binding can decide the verdict.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos.latch_order_intents import record_intent

    intent = LatchOrderIntent(
        intent_id=None,
        candidate_id=int(payload["cited_candidate_id"]),
        evaluation_run_id=int(payload["cited_evaluation_run_id"]),
        ticker="CADL",
        detection_date="2026-08-11",
        pipeline_run_id=None,
        idempotency_key=f"cancel-{order_id}",
        action_session_date="2026-08-11",
        recorded_ts=when,
        surface="latch_panel",
        intent_kind="cancel",
        actual_broker_order_id=order_id,
    )
    with conn_:
        record_intent(conn_, intent=intent)


def test_a_cancel_of_a_DIFFERENT_order_does_not_reject_the_citation(
        conn) -> None:
    """PRE-FIX the candidate-wide NOT EXISTS rejected this truthful row;
    POST-FIX it inserts.  Both values are stated so the case distinguishes."""
    payload = seed_latch_ladder_citation(conn)
    _cancel_naming(conn, payload, "an-older-order")
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",)


def test_a_cancel_of_THIS_order_still_rejects_the_citation(conn) -> None:
    """THE CONTROL.  ONE dimension differs -- the cancel names the CITED order
    -- and the trigger rejects.  Without it a twin that dropped the clause
    entirely would pass the case above."""
    payload = seed_latch_ladder_citation(conn)
    _cancel_naming(conn, payload, str(payload["cited_latch_broker_order_id"]))
    _assert_rejected(conn, payload)


# ===========================================================================
# 22A-R5-02 / 22A-R3-02 -- THE RUNG-9 TWIN RE-DERIVES
#
# The clause bound `input` to the link's STORED freeze_tier and then required
# the literal. Both are statements about a stored value, so a link written
# with the live tier for a PRE-barrier candidate satisfied every check and
# inserted -- a structural admission for a fire AL-4 says has no evidence.
# The Python ladder RE-DERIVES from the epoch boundary; the twin now does too.
# ===========================================================================
def test_a_forged_live_tier_on_a_PRE_barrier_candidate_is_rejected(
        conn) -> None:
    """THE EPOCH BOUNDARY IS RAISED so the CITED candidate falls at-or-below
    it, and nothing else changes.

    Every stored-value check still passes: the link's `freeze_tier` column
    still reads `live_at_acceptance` and the blob's input still equals it.  A
    twin that trusts the stored grade ACCEPTS.  A twin that re-derives from the
    boundary REJECTS.

    PRE-FIX: inserted.  POST-FIX: rejected.  Measured both ways.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    cited = int(payload["cited_candidate_id"])
    with _epoch_boundary_lifted(conn):
        conn.execute(
            "UPDATE candidates_immutability_epoch "
            "SET max_candidate_id_at_barrier = ? WHERE epoch_id = 1",
            (cited,))
    conn.commit()
    # The stored grade is UNCHANGED and still says live_at_acceptance -- which
    # is the whole point: the row is internally consistent and externally false.
    assert conn.execute(
        "SELECT freeze_tier FROM latch_order_mandate_links WHERE link_id = ?",
        (payload["cited_latch_link_id"],)).fetchone()[0] == "live_at_acceptance"
    _assert_rejected(conn, payload)


def test_an_absent_epoch_row_rejects_the_citation(conn) -> None:
    """FAIL-CLOSED, matching the reader's `boundary is None -> pre_barrier`.

    An epoch row that has been deleted is not "no constraint"; it is the loss
    of the only authority that can say a fire is post-barrier.  The reader
    stamps PRE-barrier in that state, so the twin must reject rather than let
    the `EXISTS` degrade into a pass.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    with _epoch_boundary_lifted(conn):
        conn.execute("DELETE FROM candidates_immutability_epoch")
    conn.commit()
    _assert_rejected(conn, payload)


@contextlib.contextmanager
def _epoch_boundary_lifted(conn_: sqlite3.Connection):
    """Drop the three epoch triggers, run the body, restore them VERBATIM.

    The same technique as `tests/_candidates_barrier_helper.py`, one table
    over: the epoch is immutable by its own three triggers, and the shapes
    these cases need to plant are exactly the ones the barrier prevents from
    ARISING.  The bodies are read out of `sqlite_master` and replayed, so this
    helper can never drift from the migration -- it spells no trigger of its
    own, and the admission reader compares each body against a pinned copy.
    """
    saved = conn_.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
        "AND tbl_name = 'candidates_immutability_epoch'").fetchall()
    assert saved, (
        "no epoch triggers found; this helper would then be a no-op and both "
        "cases above would pass for a reason unrelated to their clause")
    for name, _sql in saved:
        conn_.execute(f"DROP TRIGGER {name}")
    try:
        yield
    finally:
        for _name, sql in saved:
            conn_.execute(sql)


# ===========================================================================
# 22A-R5-01 -- INPUT FIDELITY IS NOT PREDICATE TRUTH
#
# Every clause below records an input BOUND to its source and every fidelity
# case above already passes.  What was missing is the PREDICATE whose verdict
# the entry claims: a fill of 100 shares can truthfully record input=100
# against an accepted quantity of 2, and the row inserted.
# ===========================================================================
def test_a_truthful_quantity_input_exceeding_the_accepted_order_is_rejected(
        conn) -> None:
    """The reviewer's own headline scenario, built exactly.

    The fill really does carry 100 shares and the recorded input really is
    100, so EVERY fidelity check passes -- the input equals ``fills.quantity``
    by subquery.  The accepted order's quantity is 19.  The production ladder
    refuses this at ``assert_fill_consistent_with_order``
    (``quantity_exceeds_order``); PRE-FIX the trigger accepted it, POST-FIX it
    rejects, and both values are stated so the case distinguishes.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    accepted = conn.execute(
        "SELECT actual_quantity FROM latch_order_mandate_links WHERE link_id = ?",
        (payload["cited_latch_link_id"],)).fetchone()[0]
    inflated = float(accepted) + 81.0
    conn.execute("UPDATE fills SET quantity = ? WHERE fill_id = ?",
                 (inflated, payload["entry_fill_id_at_correction"]))
    conn.commit()
    blob = _blob(payload)
    blob["authorization"]["guard_quantity"]["input"] = inflated
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_quantity_at_the_accepted_bound_is_still_accepted(conn) -> None:
    """THE CONTROL: the guard is an INEQUALITY, not an equality.

    An accepted order legitimately fills fewer shares (a partial then a
    cancel), and the boundary case -- executed EQUALS accepted -- must pass or
    the new clause would refuse every ordinary fill.  Without this half a fix
    that required ``<`` would pass the case above.
    """
    payload = seed_latch_ladder_citation(conn)
    accepted, fill_quantity = conn.execute(
        "SELECT l.actual_quantity, f.quantity FROM latch_order_mandate_links l "
        "JOIN fills f ON f.fill_id = ? WHERE l.link_id = ?",
        (payload["entry_fill_id_at_correction"],
         payload["cited_latch_link_id"])).fetchone()
    assert float(fill_quantity) == float(accepted), (
        "the baseline must sit exactly ON the bound for this control to be "
        "about the bound")
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


def test_a_forged_link_field_is_rejected_even_with_a_truthful_blob(
        conn) -> None:
    """RUNG 3c IS ABOUT *EVERY* DUPLICATED LINK FIELD.

    The link COPIES five fields held authoritatively elsewhere and the trigger
    bound only the broker order id, so a raw link could cite a GENUINE accepted
    validity row while carrying an INFLATED quantity -- and the submitted
    envelope would then match the forgery rather than the acceptance.

    The forgery is built the only way the schema allows: the mint trigger is
    SUPPRESSED around a real acceptance and RESTORED VERBATIM out of
    ``sqlite_master``, then the link is written by hand.  ``validity_intent_id``
    is UNIQUE and the table is append-only, so neither a raw copy beside a
    minted link nor an edit of one is representable.

    Every recorded input is re-pointed at the forged order and stays TRUTHFUL,
    so this is not a fidelity case: it is the predicate the fidelity checks
    never asked.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    payload, blob = _forged_link_citation(
        conn, payload, key="r501-forge", link_over={"actual_quantity": 2})
    _assert_rejected(conn, _with_blob(payload, blob))


def _forged_link_citation(conn_, payload: dict, *, key: str, link_over: dict):
    """A HAND-WRITTEN link citing a GENUINE acceptance, with fields substituted.

    Mirrors ``_mint_drifted_citation``'s re-pointing so the returned payload
    differs from the baseline in the forged FIELD and nothing else.
    """
    from tests._latch_link_fixtures_22a import (
        insert_intent,
        place_row,
        validity_row,
    )
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    blob = _blob(payload)
    candidate_id = blob["fire_candidate_id"]
    run_id, session = conn_.execute(
        "SELECT c.evaluation_run_id, e.action_session_date FROM candidates c "
        "JOIN evaluation_runs e ON e.id = c.evaluation_run_id WHERE c.id = ?",
        (candidate_id,)).fetchone()
    accepted_quantity = int(conn_.execute(
        "SELECT quantity FROM fills WHERE fill_id = ?",
        (payload["entry_fill_id_at_correction"],)).fetchone()[0])
    order_id = f"{key}-order"
    saved = conn_.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'trg_latch_link_mint_on_acceptance'").fetchone()[0]
    conn_.execute("DROP TRIGGER trg_latch_link_mint_on_acceptance")
    try:
        place = place_row(candidate_id, run_id=run_id)
        place.update(ticker=CADL_TICKER, detection_date=session,
                     action_session_date=session,
                     recorded_ts="2026-08-11T12:40:00",
                     idempotency_key=f"{key}-place")
        place_id = insert_intent(conn_, place)
        validity = validity_row(candidate_id, place_id, run_id=run_id)
        validity.update(ticker=CADL_TICKER, detection_date=session,
                        action_session_date=session,
                        recorded_ts="2026-08-11T12:45:00",
                        idempotency_key=f"{key}-validity",
                        actual_quantity=accepted_quantity,
                        actual_broker_order_id=order_id)
        validity_id = insert_intent(conn_, validity)
        conn_.commit()
    finally:
        conn_.execute(saved)
        conn_.commit()

    pivot, stop = conn_.execute(
        "SELECT pivot, initial_stop FROM candidates WHERE id = ?",
        (candidate_id,)).fetchone()
    row = {
        "validity_intent_id": validity_id, "place_intent_id": place_id,
        "candidate_id": candidate_id, "evaluation_run_id": int(run_id),
        "ticker": CADL_TICKER, "detection_date": str(session),
        "broker_order_id": order_id, "frozen_pivot": pivot,
        "frozen_invalidation": stop,
        "actual_quantity": accepted_quantity,
        "freeze_tier": "live_at_acceptance",
        "linked_at": "2026-08-11T12:45:00Z",
    }
    row.update(link_over)
    conn_.execute(
        f"INSERT INTO latch_order_mandate_links ({', '.join(row)}) "
        f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    link_id = int(conn_.execute(
        "SELECT link_id FROM latch_order_mandate_links WHERE "
        "validity_intent_id = ?", (validity_id,)).fetchone()[0])
    set_fill_envelope(
        conn_, payload["entry_fill_id_at_correction"],
        json.dumps({"schwab_order_id": order_id,
                    "schwab_instrument_symbol": CADL_TICKER}))
    conn_.commit()

    payload = dict(payload)
    payload.update(
        cited_latch_link_id=link_id,
        cited_latch_validity_intent_id=validity_id,
        cited_latch_place_intent_id=place_id,
        cited_latch_broker_order_id=order_id,
    )
    blob["authorization"]["rung2_link_parent"]["input"] = place_id
    blob["authorization"]["rung3b_latest_validity_child"]["input"] = validity_id
    blob["authorization"]["rung3c_link_broker_order_id"]["input"] = order_id
    blob["authorization"]["rung4_governing_place_intent"]["input"] = place_id
    blob["authorization"]["guard_broker_limit_bound"]["input"] = (
        validity["actual_limit_price"])
    return payload, blob


# ===========================================================================
# 22A-R5-05 -- A CLAIMED SESSION STRING IS SYNTACTICALLY VALIDATED
#
# AL-5 says SQL cannot know the exchange CALENDAR. It says nothing about
# whether the string is a DATE at all, and `json_type = 'text'` accepted
# "garbage".
# ===========================================================================
def test_a_garbage_bars_through_is_rejected(conn) -> None:
    """PRE-FIX ``bars_through = "garbage"`` inserted; POST-FIX it is rejected."""
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["bars_through"] = "garbage"
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_year_zero_bars_through_is_rejected(conn) -> None:
    """The YEAR BOUND, which the three-predicate form omits.

    ``'0000-01-01'`` has length 10, parses under SQLite's ``date()`` and
    round-trips -- so length + parseable + round-trip ALL pass and only the
    year bound refuses it.  The same guard on
    ``latch_order_mandate_links.detection_date`` has always carried four
    predicates; this is the fourth arriving where it was missing.
    """
    assert conn.execute("SELECT date('0000-01-01')").fetchone()[0] == "0000-01-01"
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["bars_through"] = "0000-01-01"
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_year_zero_coverage_session_is_rejected(conn) -> None:
    """The same fourth predicate on the coverage arrays.

    BOTH arrays carry the value, so the element-by-element equality still
    holds and only the date guard can be what refuses it.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["coverage"] = {"expected_sessions": ["0000-01-01"],
                        "observed_sessions": ["0000-01-01"],
                        "missing_sessions": []}
    _assert_rejected(conn, _with_blob(payload, blob))


# ===========================================================================
# 22A-R5-06 -- THE DECISION-ORDERING PAIRS ARE SHAPED AND BOUND
#
# COMPLETENESS IS NOT PROVED, and it is NOT AL-3 (Codex 22A-R9-05, CHARC ruled
# 2026-08-26).  AL-3 does not name this clause -- its roster is the
# closure-checked region in plan limitation L17, never a copy typed here --
# and this clause carries its OWN declared limitation, exercised below:
# the guard validates the CONSISTENCY of what the writer supplied and does not
# enforce the COMPLETENESS of supply.  What SQL can do is refuse a claimed
# pair that is not a pair or that names a row which does not exist.
# ===========================================================================
_DECISION_SHAPE_CASES = {
    "a bare string": "not-a-pair",
    "a one-element array": [1],
    "a three-element array": [1, "2026-08-11T12:00:00", "extra"],
    "a text id": ["1", "2026-08-11T12:00:00"],
    "an object": {"intent_id": 1, "recorded_ts": "2026-08-11T12:00:00"},
}


@pytest.mark.parametrize("label", sorted(_DECISION_SHAPE_CASES))
def test_a_malformed_decision_ordering_pair_is_rejected(conn, label) -> None:
    """Five shapes the outer ``json_type = 'array'`` check accepted."""
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["probe_guards"]["decision_ordering"]["input"] = [
        _DECISION_SHAPE_CASES[label]]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_decision_ordering_pair_naming_no_intent_row_is_rejected(
        conn) -> None:
    """A WELL-SHAPED pair naming a row that does not exist.

    This is the half a shape check alone would miss: the array is a pair, the
    id is an integer, the stamp is text, and the record still names a decision
    that was never written.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["probe_guards"]["decision_ordering"]["input"] = [
        [987654, "2026-08-11T12:00:00"]]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_decision_ordering_pair_with_the_wrong_stamp_is_rejected(
        conn) -> None:
    """The pair is bound on BOTH halves, not on the id alone.

    The intent id is real; the recorded stamp is not that row's.  Binding only
    the id would accept a record claiming the decision happened at a different
    time from when it did -- which is the whole content of an ORDERING guard.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    real_id = blob["probe_guards"]["decision_ordering"]["input"][0][0]
    blob["probe_guards"]["decision_ordering"]["input"] = [
        [real_id, "1999-01-01T00:00:00"]]
    _assert_rejected(conn, _with_blob(payload, blob))


def test_a_malformed_probe_blob_ABORTS_rather_than_raising(conn) -> None:
    """22A-R3-12, verified by execution.

    SQLite does NOT short-circuit ``AND`` for the purpose of skipping a JSON
    function's error -- ``SELECT 0 AND json_extract('{bad','$.x')`` raises
    "malformed JSON", measured in both operand orders.  So a non-NULL,
    non-JSON blob made the WHOLE trigger die with an ``OperationalError``
    instead of reaching its own ``RAISE(ABORT)``.

    PRE-FIX: ``sqlite3.OperationalError: malformed JSON``.
    POST-FIX: ``sqlite3.IntegrityError`` carrying the citation message.
    Both are refusals -- the gain is a legible one -- and the assertion below
    names the class as well as the message, because a test matching only the
    message would pass under either if the engine's text ever overlapped.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    payload = dict(payload)
    payload["cited_latch_probe_json"] = "{not json"
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_payload(conn, payload)


def test_a_last_word_row_is_unaffected_by_the_json_guard(conn) -> None:
    """THE CONTROL: ``json_valid(NULL)`` is NULL, not an error.

    The ``last_word`` branch leaves all five citation columns NULL, so the
    ``CASE WHEN`` must not turn a legal absence into a refusal.  Without this
    half a wrapper placed one clause too high would break every ordinary
    Demand-C correction.

    THE FIXTURE IS AN UNLINKED FILL, AND MY FIRST VERSION WAS NOT (Codex
    22A-R6-01).  It started from the LATCH fixture, cleared the citations and
    flipped the tier -- so it ASSERTED that an authority downgrade succeeds, on
    the very row whose envelope names an accepted order.  A control that
    enshrines the defect it sits beside is worse than no control.  The
    envelope is stripped here so the fill has no latch authority to bypass,
    which is the world ``last_word`` is actually for.
    """
    payload = seed_latch_ladder_citation(conn)
    conn.execute(
        "UPDATE fills SET schwab_source_value_json = NULL WHERE fill_id = ?",
        (payload["entry_fill_id_at_correction"],))
    conn.commit()
    payload = dict(payload)
    payload.update(admission_tier="last_word", cited_latch_link_id=None,
                   cited_latch_validity_intent_id=None,
                   cited_latch_place_intent_id=None,
                   cited_latch_broker_order_id=None,
                   cited_latch_probe_json=None)
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "last_word",)


def test_a_last_word_DOWNGRADE_on_a_linked_fill_is_rejected(conn) -> None:
    """22A-R6-01: the tier is not a label an operator may choose.

    ONE dimension differs from the control above -- the fill KEEPS the envelope
    naming its accepted order -- and the row is REJECTED.  PRE-FIX it inserted,
    erasing every latch refusal on a mandate the ladder governs; POST-FIX the
    ``last_word`` branch must prove the fill's own order resolves to NO link.
    """
    payload = seed_latch_ladder_citation(conn)
    payload = dict(payload)
    payload.update(admission_tier="last_word", cited_latch_link_id=None,
                   cited_latch_validity_intent_id=None,
                   cited_latch_place_intent_id=None,
                   cited_latch_broker_order_id=None,
                   cited_latch_probe_json=None)
    _assert_rejected(conn, payload)


def test_a_citation_naming_an_order_the_FILL_does_not_is_rejected(
        conn) -> None:
    """22A-R6-02: the cited order must be the one the SUBJECT FILL names.

    Every other clause binds the citation to ITSELF, and the only
    subject-envelope field checked anywhere was the instrument SYMBOL.  Here
    the envelope's order id is changed and NOTHING else: the link, both
    intents, the candidate and the symbol all still agree with each other, and
    the row must be REJECTED because the fill cannot prove it came from that
    order.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    # THE READING IS RECORDED TOO, and that is what makes this test about
    # what it says.  Post-PERSIST-CANONICAL a bare document with no stored
    # reading is rejected for a DIFFERENT reason -- nobody has read it -- so
    # writing only the document would leave the test green while no longer
    # exercising the order-mismatch clause at all.
    set_fill_envelope(
        conn, payload["entry_fill_id_at_correction"],
        json.dumps({"schwab_order_id": "a-different-order",
                    "schwab_instrument_symbol": "CADL"}))
    conn.commit()
    _assert_rejected(conn, payload)


def test_a_cited_order_naming_TWO_links_is_rejected(conn) -> None:
    """22A-R6-03: the trigger COUNTS, because the resolver counts.

    ``broker_order_id`` is deliberately not unique and the resolver refuses
    ``ambiguous_accepted_orders`` at two.  The trigger verified only that the
    SELECTED link exists, so a raw correction could pick one of two ambiguous
    mandates.  A SECOND link on the same order id is minted here through a
    real acceptance -- never raw-inserted, because the duplicate this rung
    guards is a duplicate BROKER ORDER, not a duplicate row.
    """
    from tests._latch_link_fixtures_22a import (
        insert_intent,
        place_row,
        validity_row,
    )
    from tests.trades._cohort_provenance_fixtures import (
        CADL_TICKER,
        seed_candidate,
        seed_evaluation_run,
    )

    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    other_run = seed_evaluation_run(
        conn, run_ts="2026-08-07T17:30:26", data_asof_date="2026-08-06",
        action_session_date="2026-08-07")
    other = seed_candidate(conn, evaluation_run_id=other_run)
    common = {"evaluation_run_id": other_run, "ticker": CADL_TICKER,
              "detection_date": "2026-08-07",
              "action_session_date": "2026-08-07",
              "recorded_ts": "2026-08-07T12:00:00"}
    place_id = insert_intent(conn, place_row(
        other, run_id=other_run, idempotency_key="dup-place", **common))
    insert_intent(conn, validity_row(
        other, place_id, key="dup-validity", run_id=other_run,
        actual_broker_order_id=payload["cited_latch_broker_order_id"],
        **common))
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_mandate_links WHERE "
        "broker_order_id = ?",
        (payload["cited_latch_broker_order_id"],)).fetchone()[0] == 2, (
        "the fixture must produce TWO links on one order id or the case is "
        "about a different clause")
    _assert_rejected(conn, payload)


# ===========================================================================
# AL-3's THIRD MEMBER HAD NO ACCEPTANCE PIN, and the closure check's PIN
# requirement is what surfaced that.  `fire_membership` was declared
# service-validated and the only test naming it asserted a REJECTION -- an
# input of 2 -- which pins the clause that IS enforced and says nothing about
# the one that is not.  A declared limitation whose only test is of the
# opposite direction is unfalsifiable in exactly the way L18's convention
# exists to prevent.
# ===========================================================================
def test_THE_DECLARED_LIMITATION_a_fabricated_fire_membership_is_ACCEPTED(
        conn) -> None:
    """AL-3: SQL requires the count to SAY one; it cannot check that it IS.

    ``fire_membership`` is the number of latches whose ``candidate_set``
    contains the fire.  That is fold state no subquery can walk, so the trigger
    binds the recorded input to the LITERAL 1 and stops.

    The world built here is one where the count is NOT derivably one: a SECOND
    accepted broker order is minted on the SAME candidate through a real
    acceptance, which is precisely the state the service's resolver refuses as
    ``ambiguous_accepted_orders``.  The citation still INSERTS on the asserted
    ``{"input": 1, "verdict": "pass"}`` -- the service refuses and the trigger
    accepts, which is the declared limit stated as an observation.

    If a later change gives SQL an authority over the fold, this REJECTS and
    the declaration must be corrected rather than this test silenced.
    """
    from tests._latch_link_fixtures_22a import (
        insert_intent,
        place_row,
        validity_row,
    )
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    payload = seed_latch_ladder_citation(conn)
    candidate_id = payload["cited_candidate_id"]
    run_id = payload["cited_evaluation_run_id"]
    session = conn.execute(
        "SELECT action_session_date FROM evaluation_runs WHERE id = ?",
        (run_id,)).fetchone()[0]
    # RECORDED EARLIER THAN THE CITED CYCLE, deliberately: a LATER place opens
    # a new cycle and rung 4 would then refuse the citation for that reason
    # instead of reaching the clause under test -- a rejection for the wrong
    # reason proves nothing about the guard it claims to exercise.
    common = {"evaluation_run_id": run_id, "ticker": CADL_TICKER,
              "detection_date": session, "action_session_date": session}
    place_id = insert_intent(conn, place_row(
        candidate_id, run_id=run_id, idempotency_key="second-place",
        recorded_ts="2026-08-11T11:00:00", **common))
    insert_intent(conn, validity_row(
        candidate_id, place_id, key="second-validity", run_id=run_id,
        actual_broker_order_id="2002937462",
        recorded_ts="2026-08-11T11:05:00", **common))
    conn.commit()

    # THE DISCRIMINATOR: the candidate now carries TWO accepted orders, so
    # "exactly one latch contains the fire" is not derivable from this world.
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_order_mandate_links WHERE candidate_id = ?",
        (candidate_id,)).fetchone()[0] == 2, (
        "the fixture must produce TWO accepted links on the candidate or the "
        "case is about nothing")
    blob = _blob(payload)
    assert blob["probe_guards"]["fire_membership"] == {
        "input": 1, "verdict": "pass"}

    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections "
        "WHERE admission_tier = 'latch_ladder'").fetchone()[0] == 1, (
        "the fabricated membership was REJECTED, so AL-3 is now narrower "
        "than it declares")


# ===========================================================================
# 22A-R12-02 -- THE ANCHORING FILL IS PROVED TO BE *AN* ENTRY FILL, NEVER
# *THE AUTHORITATIVE* ONE.  DECLARED AT AL-3, AND PINNED HERE.
#
# The citation-graph clause (0037, inherited VERBATIM from 0036) proves that
# `entry_fill_id_at_correction` is an entry fill of THIS trade on the frozen
# session.  The SERVICE means something narrower: the FIRST entry fill by
# (parsed fill_datetime, fill_id) after refusing any malformed sibling --
# `resolve_authoritative_entry_fill`, cohort_provenance_correction.py.
#
# THERE IS NO SQL FIX BY CONSTRUCTION, which is why this is a declared limit
# rather than an unfixed defect.  The ordering is a PYTHON PARSE over an
# unconstrained TEXT column, and the repo helper's lexical ORDER BY mis-ranks a
# schema-legal basic-form timestamp -- its own docstring says so and says why it
# is not reused.  Re-deriving that ordering in SQL is exactly the engine-boundary
# violation the persist-canonical ruling forbids: SQL VERIFIES A FACT; IT MUST
# NEVER RE-DERIVE A JUDGMENT ACROSS AN ENGINE BOUNDARY.  Persisting the judgment
# does not help either -- the column IS the persisted judgment, and a raw writer
# forges it and its citation together, which is AL-10's shape exactly.
# ===========================================================================
def test_THE_DECLARED_LIMITATION_a_non_authoritative_anchor_is_ACCEPTED(
        conn) -> None:
    """AL-3: the anchoring-fill clause proves membership, not authority.

    A LATER scale-in fill on the same trade and session, carrying the same
    broker envelope, is cited as the anchor.  Every clause passes and the row
    INSERTS.  The discriminator is the second assertion: the service's own
    resolver is asked which fill is authoritative, so this case cannot pass by
    accidentally citing the right one.

    If a later change makes this REJECT, the limitation is narrower than
    declared and the DECLARATION must be corrected, not this test silenced.
    """
    from swing.trades.cohort_provenance_correction import (
        resolve_authoritative_entry_fill,
    )

    payload = seed_latch_ladder_citation(conn)
    trade_id = payload["trade_id"]
    anchor_id = payload["entry_fill_id_at_correction"]
    session, envelope, quantity, price = conn.execute(
        "SELECT fill_datetime, schwab_source_value_json, quantity, price "
        "  FROM fills WHERE fill_id = ?", (anchor_id,)).fetchone()

    later = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        " fill_origin) VALUES (?, ?, 'entry', ?, ?, 'schwab_auto')",
        (trade_id, session[:10] + "T19:59:00", quantity, price))
    later_id = int(later.lastrowid)
    set_fill_envelope(conn, later_id, envelope)
    conn.commit()

    # THE DISCRIMINATOR: the SERVICE says the ORIGINAL fill is authoritative.
    assert resolve_authoritative_entry_fill(conn, trade_id).fill_id == anchor_id
    assert later_id != anchor_id

    payload = dict(payload)
    payload["entry_fill_id_at_correction"] = later_id
    snapshot = json.loads(payload["entry_fill_snapshot_json"])
    snapshot["fill_id"] = later_id
    snapshot["fill_datetime"] = session[:10] + "T19:59:00"
    payload["entry_fill_snapshot_json"] = json.dumps(snapshot, sort_keys=True)
    if payload.get("entry_fill_id") is not None:
        payload["entry_fill_id"] = later_id

    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT entry_fill_id_at_correction FROM provenance_corrections"
    ).fetchone() == (later_id,), (
        "the non-authoritative anchor was accepted, which is the declared "
        "limitation -- if it was REJECTED, AL-3 is now narrower than it says")


# ===========================================================================
# 22A-R12-01 -- THE RUNG-6 TWIN COULD NOT SEE AN UNREAD COMPETING ENVELOPE
#
# The twin scans `fill_envelope_identity` for CANONICAL readings naming the
# cited order, so a competing entry fill whose envelope the authority has never
# read -- or refused -- is invisible to it and the scan reads its ignorance as
# ABSENCE.  The SERVICE compensates in both directions (it runs
# `ensure_entry_fill_identities` before the scan, then refuses on any refused
# reading), but the twin exists precisely to constrain the RAW inserts the
# service never touches, and only the `refused` half was ever declared.
#
# DIRECTION: a WRONG ACCEPTANCE, and the widest one available here -- a raw
# correction claims a mandate as unconsumed while another trade may already
# consume it, contaminating the cohort permanently.
#
# THE TWIN IS BROUGHT UP TO THE SERVICE, NEVER PAST IT.  The service's
# population pass writes a reading for every envelope-bearing entry fill before
# it scans, so on the service path the trigger meets a fully-read population and
# the new clause is satisfied by construction; there is no state the service
# admits and the trigger then aborts -- the authorize-then-abort shape this arc
# met four times.
# ===========================================================================
def _plant_competing_entry_fill(
        conn_: sqlite3.Connection, *, envelope: str, read: bool,
        trade_id: int = 99001) -> int:
    """ANOTHER trade's entry fill carrying `envelope`, read or unread.

    The insert is RAW on purpose: the production writer persists the reading,
    and the state under test is exactly the one where it did not.
    """
    conn_.execute(
        "INSERT OR IGNORE INTO trades (id, ticker, entry_date, entry_price, "
        " initial_shares, initial_stop, current_stop, state, trade_origin, "
        " pre_trade_locked_at) "
        "VALUES (?, 'ZZZZ', '2026-08-17', 18.50, 2, 17.00, 17.00, 'entered', "
        " 'manual_off_pipeline', '2026-08-17T13:00:00')", (trade_id,))
    cur = conn_.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        " fill_origin, schwab_source_value_json) "
        "VALUES (?, '2026-08-17T14:30:00', 'entry', 2, 18.50, 'schwab_auto', "
        " ?)", (trade_id, envelope))
    fill_id = int(cur.lastrowid)
    if read:
        # THE PRODUCTION WRITER, never a hand-built row: a reading whose shape
        # a fixture invented would test the fixture, and the whole subject here
        # is what the AUTHORITY leaves behind.
        from swing.data.repos.fill_envelope_identity import record_identity
        record_identity(conn_, fill_id=fill_id, envelope_raw=envelope)
    conn_.commit()
    return fill_id


_UNRELATED_ENVELOPE = json.dumps({"schwab_order_id": "9999999999"})


def test_a_competing_entry_fill_with_NO_stored_reading_is_REFUSED(conn) -> None:
    """22A-R12-01: ignorance is not absence, and the twin now says so.

    PRE-FIX this inserted.  The competing fill carries a perfectly ordinary
    envelope naming an UNRELATED order -- so the case is about the READING
    being absent, not about a second consumer -- and the rung-6 twin's
    canonical scan simply did not see it.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    _plant_competing_entry_fill(
        conn, envelope=_UNRELATED_ENVELOPE, read=False)
    _assert_rejected(conn, payload)


def test_a_competing_entry_fill_with_a_REFUSED_reading_is_REFUSED(
        conn) -> None:
    """The half the twin's own comment DECLARED and did not enforce.

    A refused document stores no order id, so a consumption hiding inside one
    is invisible to the canonical scan.  The service refuses on exactly this
    population (`consumption_evidence_unavailable`); the twin now does too.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    fill_id = _plant_competing_entry_fill(conn, envelope="{bad", read=True)
    assert conn.execute(
        "SELECT envelope_state FROM fill_envelope_identity WHERE fill_id = ?",
        (fill_id,)).fetchone() == ("refused",), (
        "the authority must REFUSE this document or the case is about "
        "something else")
    _assert_rejected(conn, payload)


def test_a_competing_entry_fill_that_HAS_been_read_still_INSERTS(conn) -> None:
    """THE WRONG-REFUSAL CONTROL, and it is what stops this being a blunt ban.

    The same competing fill with a CURRENT canonical reading naming an
    unrelated order is the ordinary post-population state -- exactly what the
    service leaves behind before it inserts -- and the citation must still be
    accepted.  Without this case the two above are satisfied by a clause that
    refuses whenever any other entry fill exists at all.
    """
    payload = seed_latch_ladder_citation(conn)
    _plant_competing_entry_fill(
        conn, envelope=_UNRELATED_ENVELOPE, read=True)
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",)


def test_a_competing_entry_fill_with_NO_envelope_at_all_still_INSERTS(
        conn) -> None:
    """The second wrong-refusal control: a NULL envelope is not ignorance.

    `ensure_entry_fill_identities` selects `schwab_source_value_json IS NOT
    NULL`, so a fill with no envelope never gets a reading and never should.
    A clause requiring a reading for EVERY competing entry fill would refuse
    every ordinary manual trade in the book.
    """
    payload = seed_latch_ladder_citation(conn)
    _plant_competing_entry_fill(conn, envelope=None, read=False)
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",)


# ===========================================================================
# 22A-R6-06 -- THE PROBE-GUARD ROSTER'S BINDING LABELS ARE TRUE
#
# `fill_session_is_session` was labelled SQL_BOUND while the trigger checked
# only that its verdict read 'pass' -- so a weekend or holiday fill could
# assert `pass` and be admitted under a roster advertising SQL enforcement.
# A false label is worse than a declared limit: an auditor reading the roster
# concludes the predicate was proved.
# ===========================================================================
def test_the_probe_guard_roster_claims_no_verdict_sql_cannot_prove(
        conn) -> None:
    """Every SQL_BOUND probe guard's VERDICT must be provable in SQL.

    The roster is walked rather than a list maintained beside it, and the
    boundary is stated per member: the fill-session guard is
    SERVICE_VALIDATED because no subquery can enumerate the NYSE calendar --
    the same ground AL-5 carries one clause over, and the same ground the two
    rounded price-bound guards carry.
    """
    from swing.trades.latched_origin import PROBE_GUARD_CLAUSES

    by_key = {c.key: c for c in PROBE_GUARD_CLAUSES}
    assert by_key["fill_session_is_session"].binding == SERVICE_VALIDATED
    assert by_key["fire_membership"].binding == SERVICE_VALIDATED
    assert by_key["decision_ordering"].binding == SERVICE_VALIDATED
    # NOTHING in the probe-guard roster claims SQL enforcement, and that is an
    # ASSERTION rather than an omission: the three clauses rest on the
    # exchange calendar, on fold state and on the admissible-decision subset,
    # none of which a trigger can reach.  A member added as SQL_BOUND fails
    # here and has to justify itself.
    assert not [c.key for c in PROBE_GUARD_CLAUSES if c.binding == SQL_BOUND]


def test_a_weekend_fill_session_is_ACCEPTED_and_the_limit_is_declared(
        conn) -> None:
    """AND THE LIMIT IS EXERCISED, not merely labelled.

    A raw citation whose fill session is a SATURDAY, with the guard's input
    bound to it and the verdict still ``pass``, INSERTS.  That is the declared
    residual of the reclassification above, and pinning it is what stops the
    label from being an unfalsifiable claim -- if a later change DOES prove
    the predicate in SQL, this case fails and the roster is revisited
    deliberately rather than drifting.
    """
    import datetime

    payload = seed_latch_ladder_citation(conn)
    saturday = "2026-08-15"
    assert datetime.date.fromisoformat(saturday).weekday() == 5
    conn.execute(
        "UPDATE fills SET fill_datetime = ? WHERE fill_id = ?",
        (saturday + "T16:00:00", payload["entry_fill_id_at_correction"]))
    conn.commit()
    payload = dict(payload)
    payload["entry_fill_session_date"] = saturday
    # The frozen snapshot carries the fill's datetime and a 0036 CHECK ties it
    # to `entry_fill_session_date`, so the snapshot moves WITH the fill or the
    # row is refused for that reason instead of reaching the clause under test.
    snapshot = json.loads(payload["entry_fill_snapshot_json"])
    snapshot["fill_datetime"] = saturday + "T16:00:00"
    payload["entry_fill_snapshot_json"] = json.dumps(snapshot, sort_keys=True)
    blob = _blob(payload)
    blob["fill_session"] = saturday
    blob["horizon_session"] = saturday
    blob["probe_guards"]["fill_session_is_session"]["input"] = saturday
    _insert_payload(conn, _with_blob(payload, blob))
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",)


def test_a_malformed_SUBJECT_envelope_aborts_legibly(conn) -> None:
    """22A-R7-04, and it is a RESIDUAL OF MY OWN CLASS FIX.

    22A-R3-12 established by execution that an AND chain does NOT protect a
    JSON function from a malformed value, and every probe-blob clause was
    wrapped in ``CASE WHEN json_valid(...)``.  The SUBJECT FILL'S ENVELOPE is a
    DIFFERENT JSON source and was left on the unguarded form at the
    envelope-symbol binding, so a malformed envelope made the whole trigger die
    with an engine error instead of reaching its own RAISE(ABORT).

    "State the class once, then re-grep the whole artifact" -- and this is the
    site the re-grep should have caught and did not.

    PRE-FIX: ``sqlite3.OperationalError: malformed JSON``.
    POST-FIX: ``sqlite3.IntegrityError`` carrying the citation message.  Both
    refuse; the gain is a legible refusal, and the assertion names the CLASS
    as well as the message so it cannot pass under the other.

    THE RUNG-6 SCAN over EVERY OTHER trade's envelope was moved to the same
    ``CASE`` form in the same commit.  MEASURED HONESTLY: a malformed envelope
    on an unrelated trade does NOT currently raise there -- sqlite's
    evaluation order inside that ``NOT EXISTS`` subquery happens to spare it --
    so that change is DEFENSIVE BY CLASS rather than a demonstrated live
    defect, and it is recorded as such rather than sold as a fix.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    # The AUTHORITY reads this document too, and since 22A-R11-01 it REFUSES
    # it: an undecodable document is one the authority cannot speak for.  So
    # the row is refused by the envelope-readable clause -- the reading exists
    # and is not `canonical` -- rather than by an ABSENT reading, and either
    # way the refusal is the trigger's own legible ABORT rather than an engine
    # error.  Recording it is what keeps the malformed document the subject.
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"],
                      "{not json")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="citation graph"):
        _insert_payload(conn, payload)


# ===========================================================================
# 22A-R9-03 -- THE TRIGGER IMPLEMENTS THE CANONICAL-ENVELOPE RULE TOO
#
# The self-sweep widened the SERVICE to refuse an envelope the two domains
# read differently (SS-1/SS-4).  A twin that did not move with it would leave
# the trigger WEAKER THAN ITS READER on exactly the class the sweep is about:
# a RAW correction, which never touches the service, could still select its
# authority by SQLite's FIRST duplicate key and write a permanently wrong
# attribution into the audit table of record.
#
# "Both halves move together or neither" -- the arc's own rule at 22A-R3-15
# and 22A-R4-04, applied to a reader this dispatch itself widened.
# ===========================================================================
_NON_CANONICAL_ENVELOPES = {
    "duplicate order-id keys": (
        '{{"schwab_order_id": "{order}", "schwab_order_id": "other", '
        '"schwab_instrument_symbol": "{ticker}"}}'),
    "duplicate order-id keys, reversed": (
        '{{"schwab_order_id": "other", "schwab_order_id": "{order}", '
        '"schwab_instrument_symbol": "{ticker}"}}'),
    "a padded order id": (
        '{{"schwab_order_id": "  {order}  ", '
        '"schwab_instrument_symbol": "{ticker}"}}'),
    "a padded symbol": (
        '{{"schwab_order_id": "{order}", '
        '"schwab_instrument_symbol": "  {ticker}  "}}'),
    "duplicate symbol keys": (
        '{{"schwab_order_id": "{order}", "schwab_instrument_symbol": "ZZZZ", '
        '"schwab_instrument_symbol": "{ticker}"}}'),
    "a numeric order id": (
        '{{"schwab_order_id": 1002937461, '
        '"schwab_instrument_symbol": "{ticker}"}}'),
    "a blank symbol": (
        '{{"schwab_order_id": "{order}", "schwab_instrument_symbol": "   "}}'),
}


@pytest.mark.parametrize("label", sorted(_NON_CANONICAL_ENVELOPES))
def test_a_correction_on_a_NON_CANONICAL_envelope_is_refused(
        conn, label) -> None:
    """MEASURED PRE-FIX, and only ONE of the seven flipped.

    `duplicate order-id keys` -- whose FIRST value is the cited order -- was
    ACCEPTED by the trigger; the other six were ALREADY refused by the
    existing order-id and symbol bindings.  So six of these cases are
    REGRESSION GUARDS rather than discriminators, and saying so is the point:
    a parametrized family that passes under both paths would otherwise read as
    seven proofs when it carries one.

    Each shape leaves the citation graph otherwise intact -- the baseline
    inserts first, and only the fill's envelope changes -- so where the
    verdict does flip, the mutation is what flipped it.
    """
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    raw = _NON_CANONICAL_ENVELOPES[label].format(
        order=payload["cited_latch_broker_order_id"], ticker=CADL_TICKER)
    # PERSIST-CANONICAL: the AUTHORITY is given each document and its verdict
    # is STORED, so the rejection below is caused by the stored state -- which
    # is the mechanism under test -- and not by the absence of a reading, which
    # would reject every shape here for the same uninformative reason.
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], raw)
    conn.commit()
    _assert_rejected(conn, payload)


def test_an_ABSENT_envelope_does_not_trip_the_canonicality_clause(
        conn) -> None:
    """THE OVER-REFUSAL CONTROL, and it is the ordinary case.

    Every pre-22-A fill carries no envelope at all, and the ``last_word``
    ladder must keep working for them.  A canonicality clause that refused an
    absent or unreadable envelope would block every correction this surface
    was built for.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    conn.execute("DELETE FROM provenance_corrections")
    conn.execute(
        "UPDATE fills SET schwab_source_value_json = NULL, "
        "fill_origin = 'operator_typed' WHERE fill_id = ?",
        (payload["entry_fill_id_at_correction"],))
    conn.commit()
    last_word = dict(payload)
    last_word.update(admission_tier="last_word", cited_latch_link_id=None,
                     cited_latch_validity_intent_id=None,
                     cited_latch_place_intent_id=None,
                     cited_latch_broker_order_id=None,
                     cited_latch_probe_json=None)
    _insert_payload(conn, last_word)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "last_word",)


def test_a_NESTED_key_of_the_same_name_does_not_trip_the_clause(conn) -> None:
    """The wrong-REFUSAL control, now decided by ONE engine (22A-R9-06).

    The clause this once exercised re-derived the service's canonicality
    judgment in SQL and had to iterate the ROOT only, or a nested field of the
    same name would have been read as a duplicate.  PERSIST-CANONICAL deletes
    that whole question: the AUTHORITY decides, once, and the trigger compares
    its stored answer.  The control survives because the OVER-REFUSAL it
    guards against is still available -- a canonicaliser that counted nested
    keys would store ``refused`` and this admission would fail.
    """
    from tests.trades._cohort_provenance_fixtures import CADL_TICKER

    payload = seed_latch_ladder_citation(conn)
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], json.dumps({
        "schwab_order_id": payload["cited_latch_broker_order_id"],
        "schwab_instrument_symbol": CADL_TICKER,
        "raw": {"schwab_order_id": "an unrelated nested field"}}))
    conn.commit()
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",)


# ===========================================================================
# 22A-R9-05 -- THE DECISION-ORDERING LIMITATION, EXERCISED RATHER THAN CLAIMED
#
# CHARC ruled 2026-08-26: AL-3 does NOT extend to `decision_ordering`; the
# clause's binding stays writer-supplied-pairs-only; and the
# vacuous-satisfaction property is DECLARED as a limitation with its reason
# rather than closed by a widening nobody has ruled.  The clause is a named
# REASONED EXCLUSION in L17's closure-checked roster, which is the ONE place
# membership is written -- this comment used to copy it, and was the SEVENTH
# such copy, found only by re-grepping after the other six were replaced.
#
# A declared limit that nothing EXECUTES is an unfalsifiable claim -- the
# 22A-R6-06 lesson, one clause over.  These cases make it FAIL on the day the
# behaviour changes, so the declaration in 0037 stays honest or stops being
# green.
# ===========================================================================
def test_an_EMPTY_decision_ordering_array_is_accepted_the_declared_limit(
        conn) -> None:
    """THE LIMITATION ITSELF, executed.

    An empty array satisfies the clause vacuously, because the guard validates
    the CONSISTENCY of what was supplied and does not enforce the COMPLETENESS
    of supply -- nothing in this schema specifies what the required decision
    set IS, and a clause enforcing a set no authority has ruled would be a
    guess wearing a constraint's clothing on a table where a wrong REFUSAL is
    permanent.

    BANKED TO 22-A2 with its trigger: when the proof machinery specifies the
    required decision set, this guard gains its completeness half.  On the day
    that lands, THIS TEST FAILS -- which is the point of writing it.
    """
    payload = seed_latch_ladder_citation(conn)
    blob = _blob(payload)
    blob["probe_guards"]["decision_ordering"]["input"] = []
    _insert_payload(conn, _with_blob(payload, blob))
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",)


def test_the_clause_still_binds_every_pair_that_IS_supplied(conn) -> None:
    """THE DISCRIMINATOR FOR THE CASE ABOVE.

    Without it, "an empty array is accepted" would be equally satisfied by a
    clause that checks NOTHING, and the declared limitation would read as a
    hole twice its actual size.  A supplied pair naming no intent row is still
    REFUSED, which is exactly what bounds the limitation to COMPLETENESS.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    blob = _blob(payload)
    blob["probe_guards"]["decision_ordering"]["input"] = [
        [987654, "2026-08-11T12:00:00"]]
    _assert_rejected(conn, _with_blob(payload, blob))


# ===========================================================================
# 22A-R11 -- PERSIST-CANONICAL: THE THREE MEASURED DIVERGENCES, AS RAW WRITES
#
# CHARC + RD, 2026-08-26.  Condition (2) of the ruling: each of the three
# engine divergences must now be canonicalised-at-service or refused-at-service,
# AND a raw write storing DIVERGENT values must ABORT on the trigger's equality
# check.  A raw write is one that never touches the service -- the only writer
# the trigger exists to police -- so these are the tests that say the reshape
# closed the class rather than merely relocating it.
# ===========================================================================
_LAST_WORD_NULLS = dict(
    admission_tier="last_word", cited_latch_link_id=None,
    cited_latch_validity_intent_id=None, cited_latch_place_intent_id=None,
    cited_latch_broker_order_id=None, cited_latch_probe_json=None)


def _raw_envelope(conn_, fill_id: int, raw: str) -> None:
    """Write the DOCUMENT and nothing else -- a writer that bypassed the
    service entirely, which is the threat model."""
    conn_.execute(
        "UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = ?",
        (raw, fill_id))


def test_a_NaN_document_naming_an_accepted_order_cannot_claim_last_word(
        conn) -> None:
    """DIVERGENCE 1 (Codex 22A-R10-01), and the reshape's answer to it.

    MEASURED: ``json.loads`` ACCEPTS ``NaN``; SQLite's ``json_valid`` REJECTS
    the whole document.  PRE-RESHAPE the ``last_word`` branch extracted the
    order id under a ``json_valid`` CASE, got NULL, found no link, and ADMITTED
    -- a permanent ``last_word`` downgrade for a fill the service binds to a
    real mandate, written into the audit table of record by a writer that never
    consulted the service.

    POST-RESHAPE the AUTHORITY reads the document (SQL never opens it again),
    stores the order id, and the branch's stored-equality check finds the link.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    order = payload["cited_latch_broker_order_id"]
    nan_doc = ('{"schwab_order_id": "%s", "schwab_instrument_symbol": "CADL",'
               ' "x": NaN}' % order)
    assert conn.execute("SELECT json_valid(?)", (nan_doc,)).fetchone()[0] == 0, (
        "the premise: sqlite rejects this document outright")
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], nan_doc)
    conn.commit()
    _assert_rejected(conn, {**payload, **_LAST_WORD_NULLS})


@pytest.mark.parametrize("label,pad", [
    ("ASCII space", "  "), ("TAB", "\t"), ("NEWLINE", "\n"),
    ("NBSP", " "),
])
def test_a_padded_document_naming_an_accepted_order_cannot_claim_last_word(
        conn, label, pad) -> None:
    """DIVERGENCE 2 (Codex 22A-R10-02): sqlite ``trim()`` strips ASCII SPACE
    ONLY; python ``str.strip()`` also strips tab, newline and NBSP.

    PRE-RESHAPE the canonicality twin asked ``k.value <> trim(k.value)`` and,
    for the three non-space characters, saw NO PADDING -- so it called the
    document canonical while the service refused it, and the ``last_word``
    branch's exact-match link check found nothing.  The predecessor's tests all
    passed because the whole class was built out of ASCII space, the ONE
    character the two engines agree about.

    POST-RESHAPE the stored reading is a REFUSAL for all four, and a refused
    reading fails the subject-envelope clause outright.  The ASCII-space row is
    kept as the control: it was already refused, and it must stay refused.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    order = payload["cited_latch_broker_order_id"]
    doc = json.dumps({"schwab_order_id": f"{pad}{order}{pad}",
                      "schwab_instrument_symbol": "CADL"})
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], doc)
    conn.commit()
    _assert_rejected(conn, {**payload, **_LAST_WORD_NULLS})


def test_THE_DECLARED_LIMITATION_a_stale_grammar_reading_is_ACCEPTED(
        conn, monkeypatch) -> None:
    """L19 (AL-11), PINNED -- and the acceptance is the declaration.

    No trigger consumer of `fill_envelope_identity` checks
    `canonicalizer_version`: the column appeared EXACTLY ONCE in the migration,
    its own declaration, while SEVEN sites referenced the table.  The SERVICE
    is stricter -- `ensure_entry_fill_identities` re-runs the current
    canonicaliser over the population and `record_identity` RAISES on
    disagreement -- so after a bump whose ANSWER changes, a RAW correction can
    be accepted on a reading the service would refuse.

    THE READING BELOW IS WRITTEN BY THE PRODUCTION WRITER; only the version
    label is older, which is exactly what a canonicaliser bump leaves behind.
    Nothing is forged, so this is not AL-10.

    **IF THIS EVER REJECTS, THE LIMITATION IS NARROWER THAN DECLARED AND L19
    MUST BE CORRECTED -- NOT THIS TEST SILENCED.**  The obvious narrowing (a
    version filter in every consumer) is measured and rejected in L19: it
    INVERTS at the two clauses that read absence, and it manufactures a refusal
    on the service path at the other four.
    """
    import swing.trades.latched_origin as lo
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    order = payload["cited_latch_broker_order_id"]
    # A DIFFERENT DOCUMENT, same meaning: the reading binds to the DOCUMENT,
    # and the seeder's own document already carries a current-grammar reading.
    doc = ('{"schwab_instrument_symbol": "CADL", "schwab_order_id": "%s"}'
           % order)
    monkeypatch.setattr(lo, "ENVELOPE_CANONICALIZER_VERSION", "2026-01-01.0")
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], doc)
    monkeypatch.undo()                       # THE CODE IS NOW BUMPED
    assert conn.execute(
        "SELECT envelope_state, broker_order_id, canonicalizer_version "
        "  FROM fill_envelope_identity WHERE fill_id = ? AND envelope_raw = ?",
        (payload["entry_fill_id_at_correction"], doc)).fetchone() == (
        "canonical", order, "2026-01-01.0"), (
        "the premise: a reading under a grammar the current code no longer is")
    assert lo.ENVELOPE_CANONICALIZER_VERSION != "2026-01-01.0"
    conn.commit()
    _insert_payload(conn, payload)           # THE DECLARED ACCEPTANCE
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections WHERE trade_id = ?",
        (payload["trade_id"],)).fetchone()[0] == 1


def test_a_BLOB_document_naming_an_accepted_order_cannot_claim_last_word(
        conn) -> None:
    """22A-R13-01 AT THE TRIGGER -- the wrong acceptance this closes.

    SQLite does not enforce column affinity and no migration carries a
    ``typeof(schwab_source_value_json) = 'text'`` CHECK, so a BLOB survives in
    the TEXT column and returns to Python as ``bytes``.  PRE-FIX
    ``envelope_is_canonical`` answered ``True`` for any non-``str``, the
    PRODUCTION writer stored ``('canonical', NULL, NULL)`` for a document it
    had never opened, and this ``last_word`` claim was ACCEPTED -- a permanent
    downgrade for a fill whose own document names the accepted order.

    POST-FIX the stored reading is a REFUSAL and the subject-envelope clause
    rejects.  The same bytes decoded as a ``str`` still read
    ``(canonical, <order>)``, which is what makes the pre-fix row a wrong
    ACCEPTANCE rather than a harmless unknown.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    order = payload["cited_latch_broker_order_id"]
    doc = json.dumps({"schwab_order_id": order,
                      "schwab_instrument_symbol": "CADL"})
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"],
                      doc.encode())
    fill_id = payload["entry_fill_id_at_correction"]
    assert conn.execute(
        "SELECT typeof(schwab_source_value_json) FROM fills WHERE fill_id = ?",
        (fill_id,)).fetchone() == ("blob",), (
        "the premise: the TEXT column really does hold a BLOB")
    # ADDRESSED BY (fill_id, envelope_raw), because that is what a reading IS
    # -- a statement about a DOCUMENT.  The seeder's own str document already
    # has a reading on this fill, and a fill_id-only lookup would return THAT
    # row and never see the one under test.
    assert conn.execute(
        "SELECT envelope_state, broker_order_id FROM fill_envelope_identity "
        " WHERE fill_id = ? AND envelope_raw = ?",
        (fill_id, doc.encode())).fetchone() == ("refused", None), (
        "the authority must record that it could not read this document, "
        "never that the document names no order")
    conn.commit()
    _assert_rejected(conn, {**payload, **_LAST_WORD_NULLS})


def test_a_numeric_order_id_cannot_claim_last_word(conn) -> None:
    """DIVERGENCE 3 (Codex 22A-R10-03) at the trigger.

    STATED HONESTLY: this direction was ALREADY refused pre-reshape -- the
    canonicality twin rejected a value whose ``json_each`` type was neither
    ``null`` nor ``text``.  What R10-03 found was the SERVICE side, where the
    union's SQL arm had been fetched into Python and ``1002937461 ==
    '1002937461'`` came back False in both arms.  The mechanism here therefore
    CHANGED (a stored refusal rather than a re-derived type check) while the
    verdict did not, and saying so is the point: a test that claimed a new
    refusal here would be claiming a fix that is not this one.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    doc = ('{"schwab_order_id": %s, "schwab_instrument_symbol": "CADL"}'
           % payload["cited_latch_broker_order_id"])
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], doc)
    conn.commit()
    _assert_rejected(conn, {**payload, **_LAST_WORD_NULLS})


@pytest.mark.parametrize("label,doc_template", [
    # A document nobody has read: the raw writer's own shape, and the state
    # condition (2) turns into an ABORT.
    ("an extra key", '{"schwab_order_id": "%s", '
                     '"schwab_instrument_symbol": "CADL", "note": "raw"}'),
    # SAME MEANING, DIFFERENT BYTES.  The binding is to the DOCUMENT, not to
    # what the document means -- which is precisely why a stored value may
    # stand in for a judgment SQL is forbidden to make.
    ("re-ordered keys", '{"schwab_instrument_symbol": "CADL", '
                        '"schwab_order_id": "%s"}'),
])
def test_a_document_the_authority_has_not_read_is_refused(
        conn, label, doc_template) -> None:
    """``envelope_raw`` is the binding, and this is what it buys.

    A reading already exists for the document the seeder wrote.  A raw writer
    then substitutes a different document -- semantically IDENTICAL in the
    second case -- and the join, which is on the FILL AND THE DOCUMENT, no
    longer matches.  The surface fails CLOSED.

    It also proves the ``set_fill_envelope`` fixtures elsewhere in this file
    are not decorative: without a matching reading, every envelope test here
    would reject for THIS reason instead of the one it names.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    _raw_envelope(conn, payload["entry_fill_id_at_correction"],
                  doc_template % payload["cited_latch_broker_order_id"])
    conn.commit()
    _assert_rejected(conn, payload)


def test_a_citation_that_diverges_from_the_stored_reading_ABORTS(conn) -> None:
    """CONDITION (2), stated at the equality it names.

    The AUTHORITY's stored reading says one order; the citation claims another.
    Every other relation in the graph agrees with itself -- the link, both
    intents, the candidate, the symbol -- so this clause is the only thing that
    can reject, and it does.

    This is the clause the whole reshape is cashed at: it replaced a
    ``json_extract`` over the operator's document with a comparison of two
    stored TEXT values, and there is nothing left for two engines to read
    apart.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    set_fill_envelope(conn, payload["entry_fill_id_at_correction"], json.dumps(
        {"schwab_order_id": "some-other-order",
         "schwab_instrument_symbol": "CADL"}))
    conn.commit()
    _assert_rejected(conn, payload)


def test_THE_DECLARED_LIMITATION_two_equal_but_wrong_values_are_ACCEPTED(
        conn) -> None:
    """CONDITION (3), PINNED RATHER THAN ONLY WRITTEN DOWN.

    CHARC's words, carried into the migration header and into S8: *a raw writer
    storing two equal-but-wrong values passes the equality check.*  That is the
    SAME trust boundary as before -- the trigger never could judge truth, only
    CONSISTENCY -- and it is the condition on which the reshape was ruled.

    Here the fill's document names order X.  A raw writer appends a reading
    claiming it names Y, and cites Y.  Reading and citation agree, so the row
    is ACCEPTED.  Nothing in SQL can catch this, and nothing in the previous
    shape could either: the old trigger could equally be satisfied by a forged
    ENVELOPE.  The test exists so the limitation cannot silently stop being
    true -- if a later change makes this REJECT, the limitation is narrower
    than declared and the declaration must be corrected, not the test.
    """
    payload = seed_latch_ladder_citation(conn)
    _assert_baseline_inserts(conn, payload)
    fill_id = payload["entry_fill_id_at_correction"]
    honest = json.dumps({"schwab_order_id": "an-order-nobody-accepted",
                         "schwab_instrument_symbol": "CADL"})
    _raw_envelope(conn, fill_id, honest)
    conn.execute(
        "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
        " envelope_state, broker_order_id, instrument_symbol, "
        " canonicalizer_version, recorded_ts) "
        "VALUES (?, ?, 'canonical', ?, 'CADL', 'forged', 'T')",
        (fill_id, honest, payload["cited_latch_broker_order_id"]))
    conn.commit()
    _insert_payload(conn, payload)
    assert conn.execute(
        "SELECT admission_tier FROM provenance_corrections").fetchone() == (
        "latch_ladder",), (
        "the declared limitation stopped being true; correct the declaration "
        "in migration 0037's section 3d and in the plan's S8, do not silence "
        "this test")
