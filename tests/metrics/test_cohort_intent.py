"""D29 Task 1 — the per-hypothesis intent-facet predicate + its AUTHORITY.

RD's binding design note (ruling ``20260804T053603Z``): the filter's
justification differs by hypothesis. H1's is CRITERION-mandated; every
other cohort's follows from the EPOCH CONTRACT. These tests pin BOTH
groundings separately so a future criterion amendment cannot silently
change what the journal counts.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ENTRY_INTENTS
from swing.metrics.cohort_intent import (
    APLUS_BASELINE_COHORT,
    H1_COHORT_CLAUSE,
    INTENT_AUTHORITY_CRITERION,
    INTENT_AUTHORITY_EPOCH_CONTRACT,
    INTENT_AUTHORITY_NONE,
    cohort_entry_intent,
    cohort_intent_authority,
    trade_counts_toward_cohort,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "cohort_intent.db")


_NON_H1 = (
    "Near-A+ defensible: extension test",
    "Sub-A+ VCP-not-formed",
    "Capital-blocked: smaller-position test",
    "Broad-watch baseline",
)


# ---------------------------------------------------------------------------
# The CRITERION-mandated half (H1)
# ---------------------------------------------------------------------------

def test_h1_predicate_is_standard_intent_only():
    assert cohort_entry_intent(APLUS_BASELINE_COHORT) == "standard"


def test_h1_predicate_is_grounded_in_the_criterion():
    assert cohort_intent_authority(APLUS_BASELINE_COHORT) == (
        INTENT_AUTHORITY_CRITERION
    )


def test_h1_clause_the_mapping_encodes_is_still_in_the_live_criterion(
    conn: sqlite3.Connection,
):
    """The tripwire against a SILENT re-amendment.

    The H1 predicate is criterion-mandated, so the criterion text must
    keep saying so. If a future amendment drops the COHORT clause, this
    fails and forces a deliberate re-grounding rather than leaving a
    filter whose stated authority no longer says what it claims.
    """
    (criterion,) = conn.execute(
        "SELECT decision_criteria FROM hypothesis_registry WHERE name = ?",
        (APLUS_BASELINE_COHORT,),
    ).fetchone()
    assert H1_COHORT_CLAUSE in criterion


def test_the_mapping_key_still_names_a_real_registry_row(
    conn: sqlite3.Connection,
):
    """Codex R1 Minor 1 — an unknown name falls through to the epoch-contract
    default, so a RENAME of the H1 row would silently drop its filter.

    The check for that belongs against the LIVE registry, not against a
    second hardcoded list of the five names (which would itself be a mirror
    free to drift). If the row is ever renamed, this fails loudly with the
    mapping still legible, which is the outcome the finding wanted.
    """
    (n,) = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_registry WHERE name = ?",
        (APLUS_BASELINE_COHORT,),
    ).fetchone()
    assert n == 1, (
        f"cohort_intent keys its criterion-mandated predicate on "
        f"{APLUS_BASELINE_COHORT!r}, which matches {n} registry rows"
    )


def test_h1_counts_standard_intent_only():
    assert trade_counts_toward_cohort(
        entry_intent="standard", hypothesis_name=APLUS_BASELINE_COHORT,
    )
    # The live pre-epoch tuition trade (YOU, trade 4) — excluded by the
    # criterion's own COHORT clause.
    assert not trade_counts_toward_cohort(
        entry_intent="hypothesis_test_by_design",
        hypothesis_name=APLUS_BASELINE_COHORT,
    )
    # NULL is a DISTINCT third facet, never coerced to 'standard'
    # (swing/data/models.py ENTRY_INTENTS note) — so an unclassified
    # trade is not a STANDARD-intent trade and does not count.
    assert not trade_counts_toward_cohort(
        entry_intent=None, hypothesis_name=APLUS_BASELINE_COHORT,
    )


# ---------------------------------------------------------------------------
# The EPOCH-CONTRACT half (every other registered hypothesis)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", _NON_H1)
def test_non_h1_cohorts_apply_no_intent_predicate(name: str):
    assert cohort_entry_intent(name) is None


@pytest.mark.parametrize("name", _NON_H1)
def test_non_h1_cohorts_are_grounded_in_the_epoch_contract(name: str):
    assert cohort_intent_authority(name) == INTENT_AUTHORITY_EPOCH_CONTRACT


@pytest.mark.parametrize("name", _NON_H1)
def test_non_h1_cohorts_count_by_design_program_fires(name: str):
    """The forward intent contract names H2/H4 narrow-cohort fires as the
    ONLY legitimate ``by_design`` entries remaining — they are the
    DESIGNED samples of those cohorts, not retired tuition."""
    for intent in ("standard", "hypothesis_test_by_design", None):
        assert trade_counts_toward_cohort(
            entry_intent=intent, hypothesis_name=name,
        )


def test_an_orphan_label_is_narrowed_by_nobody(conn: sqlite3.Connection):
    """Codex R3 Minor 2 -- an ORPHAN label (free text matching no registered
    hypothesis) is governed by NEITHER authority.

    Two separate properties: it is never silently NARROWED (no predicate),
    and it is not falsely attributed to the epoch contract, which is a claim
    about the program's own cohorts. Orphan labels really do occur --
    ``count_per_cohort`` surfaces them by design.
    """
    registered = [
        r[0] for r in conn.execute("SELECT name FROM hypothesis_registry")
    ]
    assert "(unregistered cohort)" not in registered

    assert cohort_entry_intent("(unregistered cohort)") is None
    assert cohort_intent_authority(
        "(unregistered cohort)", registered_names=registered,
    ) == INTENT_AUTHORITY_NONE
    # A REGISTERED non-H1 cohort still answers epoch_contract under the
    # same call shape -- so the orphan answer is about registration, not
    # about passing the argument.
    assert cohort_intent_authority(
        _NON_H1[0], registered_names=registered,
    ) == INTENT_AUTHORITY_EPOCH_CONTRACT


def test_a_stale_h1_key_answers_none_not_criterion():
    """Codex R4 -- registration is checked BEFORE the criterion mapping.

    The mapping is a local constant; the registry is the authority. If H1's
    row were renamed or lost, the stale key would still sit in the mapping,
    and a criterion-first check would answer ``criterion`` for a name that
    no longer HAS a criterion -- the precise case INTENT_AUTHORITY_NONE
    exists to report, defeated exactly when it matters.
    """
    assert cohort_intent_authority(
        APLUS_BASELINE_COHORT, registered_names=[],
    ) == INTENT_AUTHORITY_NONE
    # ... and it is still `criterion` while the row IS registered.
    assert cohort_intent_authority(
        APLUS_BASELINE_COHORT, registered_names=[APLUS_BASELINE_COHORT],
    ) == INTENT_AUTHORITY_CRITERION


# ---------------------------------------------------------------------------
# Shape guards
# ---------------------------------------------------------------------------

def test_every_mandated_value_is_a_real_schema_enum_member():
    """The mapping never emits the ``'__unclassified__'`` SQL sentinel —
    the cohort selector's sentinel is a caller-side convention, not a
    value this policy module produces."""
    for name in (APLUS_BASELINE_COHORT, *_NON_H1):
        value = cohort_entry_intent(name)
        assert value is None or value in ENTRY_INTENTS


def test_sql_and_in_memory_halves_agree_for_an_unregistered_cohort():
    """Codex R6 -- the module claims the SQL predicate and the in-memory
    predicate cannot drift, so they must agree in the unregistered case too.

    Both accept ``registered_names`` and resolve through the same helper.
    A branch living in ONE caller (which is how the R5 fix was first
    written) would have made that claim false exactly here.
    """
    for intent in ("standard", "hypothesis_test_by_design", None):
        sql_half = cohort_entry_intent(
            APLUS_BASELINE_COHORT, registered_names=[],
        )
        memory_half = trade_counts_toward_cohort(
            entry_intent=intent,
            hypothesis_name=APLUS_BASELINE_COHORT,
            registered_names=[],
        )
        # SQL half: no predicate at all -> the SELECT narrows nothing.
        assert sql_half is None
        # In-memory half must therefore admit every intent.
        assert memory_half is True
