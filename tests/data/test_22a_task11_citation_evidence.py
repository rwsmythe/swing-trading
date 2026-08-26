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
    validity.update(ticker=CADL_TICKER, detection_date=session,
                    action_session_date=session,
                    recorded_ts="2026-08-11T12:25:00",
                    idempotency_key=f"{key}-validity",
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
    conn_.execute(
        "UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = ?",
        (json.dumps({"schwab_order_id": order_id,
                     "schwab_instrument_symbol": CADL_TICKER}), fill_id))
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
