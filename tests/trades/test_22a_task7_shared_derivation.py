"""22-A Task 7 -- ``derive_cohort_keys_for_fire``, the ONE derivation.

NO PLAN CASE IDS.  Task 7's acceptance is stated as properties rather than as
cases (plan S7): the Demand-C suite green UNCHANGED, a CADL golden, and the
rule-version pin re-derived.  The first is established by that suite's own 142
tests, which are not restated here; the other two are below, plus the two
properties the extraction itself has to carry.

WHY THE EXTRACTION EXISTS.  The latch ladder and the last-word guard must
derive the same three cohort keys from the SAME code.  Two spellings that agree
today is precisely the comparator-vs-emitter divergence this project has paid
for repeatedly; a shared function is the only form of that agreement a test can
hold.

THE HIGHEST-RISK ITEM IN THE ARC, and the plan says so.  Moving code changes
what ``DERIVATION_RULE_SOURCE_SHA256`` covers, and the failure mode is silent:
a digest that no longer reaches the selection-and-label rule stays green
forever.  The closure check CAUGHT this extraction on its first run -- it named
both new objects as reachable-but-unmanifested -- which is the instrument
working rather than the author remembering.
"""
from __future__ import annotations

import inspect

from swing.trades.cohort_provenance_correction import (
    DERIVATION_RULE_DEPENDENCIES,
    DERIVATION_RULE_HISTORY,
    DERIVATION_RULE_VERSION,
    derivation_rule_digest,
    derive_cohort_keys_for_fire,
    preview_cohort_provenance_correction,
)
from tests.trades._cohort_provenance_fixtures import (
    CADL_LABEL,
    build_cadl_case,
)


def test_the_cadl_golden_is_reproduced_through_the_extracted_derivation(
        tmp_path) -> None:
    """THE GOLDEN: the live CADL correction, re-derived after the move.

    Candidate 12341 -> ``'A+ baseline (aplus); failed: TT8_rs_rank'``, read off
    ``provenance_corrections`` row 1 on the live database.  A
    behaviour-preserving refactor is a CLAIM until something recomputes the one
    value that exists in the wild, so this asserts the LABEL rather than merely
    that the preview succeeds.
    """
    from swing.data.db import ensure_schema

    conn = ensure_schema(tmp_path / "swing.db")
    try:
        ids = build_cadl_case(conn)
        if conn.in_transaction:
            conn.commit()
        preview = preview_cohort_provenance_correction(
            conn,
            trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason="22-A task 7 golden",
        )
        assert preview.post_values["trades.hypothesis_label"] == CADL_LABEL
        assert preview.derivation_rule_version == DERIVATION_RULE_VERSION
    finally:
        conn.close()


def test_the_pin_covers_the_extracted_derivation_and_its_return_shape() -> None:
    """A DIGEST THAT NO LONGER REACHES THE RULE IS WORSE THAN NO DIGEST.

    After the split, hashing only ``_derive`` would leave the entire
    selection-and-label rule OUTSIDE the pin while the test stayed green --
    the exact hole the manifest was widened three times to close, arriving
    through a REFACTOR rather than through an edit.  Both new objects are on
    the manifest and this asserts it by name.
    """
    specs = {spec for _kind, spec in DERIVATION_RULE_DEPENDENCIES}
    assert ("swing.trades.cohort_provenance_correction:"
            "derive_cohort_keys_for_fire") in specs
    assert "swing.trades.cohort_provenance_correction:_FireKeys" in specs
    assert derivation_rule_digest() == DERIVATION_RULE_HISTORY[-1][1]


def test_the_history_gained_an_appended_entry_rather_than_an_edited_one() -> None:
    """The history is APPEND-ONLY, and the previous digests are untouched.

    A maintainer who moved code and EDITED the last entry would leave two
    different rules sharing one audit version -- the failure the history exists
    to make impossible.  Correction row 1 keeps ``'2026-08-13.3'``, so that
    entry must still be present with its original digest.
    """
    versions = [v for v, _d in DERIVATION_RULE_HISTORY]
    assert versions == sorted(set(versions), key=versions.index)
    assert ("2026-08-13.3",
            "8b994668acfdccf758bb1e050f1728cfddc7beed330406edb3a071b2819a14a4"
            ) in DERIVATION_RULE_HISTORY
    assert DERIVATION_RULE_VERSION == "2026-08-25.1"


def test_the_gate_is_a_parameter_so_the_refusal_ORDER_is_preserved() -> None:
    """``gate`` runs AFTER the persistence bound and BEFORE the registry.

    THIS IS WHAT MAKES THE EXTRACTION BEHAVIOUR-PRESERVING RATHER THAN MERELY
    EQUIVALENT.  The correction path has two fill-specific checks -- the
    inverted-window check and rung 14a's same-session creation-order gate --
    that must run at exactly that point; moving them after the registry would
    change WHICH refusal a doubly-bad record reports, and the Demand-C suite
    pins those messages.  A prose promise could not hold that; the source
    position can be read.
    """
    source = inspect.getsource(derive_cohort_keys_for_fire)
    bound_at = source.index("evaluation_run_persistence_bound(")
    gate_at = source.index("gate(bound, finished_parsed)")
    registry_at = source.index("for entry in list_hypotheses(conn):")
    assert bound_at < gate_at < registry_at


def test_the_latch_path_passes_no_gate_and_the_default_says_so() -> None:
    """``gate`` DEFAULTS to ``None`` -- the latch path has no fill-vs-record
    ordering question, because its authority is an append-only row the broker's
    acceptance created rather than a ranking over the bucket series.

    A default of ``None`` is the honest statement that the rung does not run;
    a default that silently ran the correction path's gates would apply a
    last-word rule inside the ladder that exists to bypass it.
    """
    sig = inspect.signature(derive_cohort_keys_for_fire)
    assert sig.parameters["gate"].default is None
    for required in ("candidate", "candidate_id", "evaluation_run_id",
                     "run_ts_parsed"):
        assert sig.parameters[required].default is inspect.Parameter.empty, (
            f"{required} must have NO default: the Candidate dataclass carries "
            f"neither its own id nor its run's (measured), so a default would "
            f"be a value invented rather than read")
