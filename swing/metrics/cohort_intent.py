"""WHICH trades count toward a hypothesis cohort -- the intent-facet
predicate, grounded PER HYPOTHESIS in its own authority (D29).

TWO DISTINCT AUTHORITIES GOVERN THESE PREDICATES, AND THEY ARE KEPT
DISTINCT ON PURPOSE (RD's binding design note, ruling ``20260804T053603Z``):
"a future criterion amendment must not be able to silently change what the
journal counts." A single blanket filter justified by ONE authority is the
thing this module exists to prevent.

1. CRITERION-MANDATED -- H1 ("A+ baseline") ONLY.
   Migration 0034 amended that row's ``decision_criteria`` to say, in its
   own words: "COHORT: the 20 are STANDARD-intent trades only, per the
   2026-06-10 training-epoch declaration; pre-epoch
   hypothesis_test_by_design trades are settled tuition and do NOT count
   toward the 20." The predicate is ``entry_intent = 'standard'`` because
   THAT ROW'S OWN CRITERION TEXT SAYS SO -- not because of any
   program-wide rule. ``NULL`` entry_intent is a DISTINCT third facet and
   is never coerced to 'standard' (see ``ENTRY_INTENTS`` in
   ``swing/data/models.py``), so an unclassified trade is not a
   STANDARD-intent trade and does not count either.
   The clause is pinned by ``H1_COHORT_CLAUSE`` below and asserted against
   the live registry row in ``tests/metrics/test_cohort_intent.py`` -- so a
   future amendment that drops the clause FAILS rather than leaving this
   filter citing an authority that no longer says it.

2. EPOCH-CONTRACT-GROUNDED -- every OTHER registered hypothesis.
   Their criteria say nothing about intent, so their predicate follows
   from the training-epoch intent contract, whose live home is
   ``docs/training-epoch-intent-contract.md`` (clauses (1)-(3) are the
   operator-confirmed 2026-06-10 declaration, quoted there verbatim from
   its provenance record ``docs/research-director-context-archive.md``),
   which is program-wide doctrine rather than criterion text. That contract's forward intent
   clause names "H2/H4 narrow-cohort fires" as "the ONLY legitimate
   by_design entries remaining (pre-registered program, not retired
   tuition)". A ``hypothesis_test_by_design`` entry IS the designed sample
   of those cohorts -- H3 reached ``closed-target-met`` on exactly such
   probes -- so the epoch contract applies NO intent exclusion there. The
   settled-tuition rule it does carry ("never re-read as practice") binds
   EXECUTION-QUALITY reads, which are the intent-faceted trade-process
   card's job (``swing/metrics/process.py``, an operator-driven facet),
   not hypothesis-sample counting.

Consequence, and it is the point: applying H1's criterion-mandated filter
to the other cohorts would zero H2 and retroactively un-achieve H3's
closed-target-met status -- a NEW self-contradiction of exactly the kind
D29 exists to remove.

3. CONTRACT-EXCLUSION -- clause (4) of the same contract, a NAMED third
   grounding (Arc 22-B, RD N2 (a)). ``unintended_execution`` -- an execution
   nobody decided to make -- "counts toward NO hypothesis cohort." That is
   program-wide, so it applies to EVERY cohort (H1 and H2-H5 alike, and an
   orphan label too: an orphan is not a hypothesis cohort, and excluding
   there is the fail-closed direction). It is not a blanket filter borrowed
   from one authority: it cites its OWN sentence, pinned by
   :data:`CONTRACT_EXCLUSION_CLAUSE` against the committed doc, and it runs
   BEFORE the criterion check so H1 and H2-H5 agree. ``NULL`` is still
   unclassified, not excluded. The two authorities above are unchanged:
   H2-H5 still answer ``epoch_contract`` -- the authority did not change,
   its text did. An excluded trade is NAMED under the cohort whose label it
   carries (N3 (a)), with an ``UNATTESTED`` token when no evidence row
   exists for it (RD's plan read), by :func:`intent_exclusion_lines`.
"""
from __future__ import annotations

from collections.abc import Collection

from swing.data.models import UNINTENDED_EXECUTION

# The registered cohort whose criterion mandates an intent predicate.
APLUS_BASELINE_COHORT: str = "A+ baseline"

# Authority tokens -- which source of truth a cohort's predicate cites.
# Returned by :func:`cohort_intent_authority` so the grounding is legible
# (and testable) at every call site rather than living only in prose.
INTENT_AUTHORITY_CRITERION: str = "criterion"
INTENT_AUTHORITY_EPOCH_CONTRACT: str = "epoch_contract"
# An ORPHAN label -- free text matching no registered hypothesis. It has no
# criterion and is not a program cohort, so NEITHER authority speaks to it.
# Saying "epoch_contract" here would be a positive claim about a row the
# epoch contract never addressed (Codex R3 Minor 2).
INTENT_AUTHORITY_NONE: str = "none"

# The COMPLETE clause of the migration-0034 amended H1 criterion that
# _CRITERION_MANDATED_INTENT encodes, verbatim. Asserted against the live
# hypothesis_registry row by the companion test.
#
# The WHOLE sentence, not a phrase from it (Codex R6): a later amendment
# could keep "the 20 are STANDARD-intent trades only" while qualifying or
# negating it in the same breath, and a substring pin would stay green
# while the predicate it grounds became mis-grounded. Pinning the full
# clause forces any semantic amendment through a deliberate test change.
H1_COHORT_CLAUSE: str = (
    "COHORT: the 20 are STANDARD-intent trades only, per the 2026-06-10 "
    "training-epoch declaration; pre-epoch hypothesis_test_by_design "
    "trades are settled tuition and do NOT count toward the 20."
)

# Hypothesis name -> the ``entry_intent`` value its OWN CRITERION TEXT
# requires. Membership in this mapping IS the criterion grounding; absence
# means the cohort is governed by the epoch contract instead. Values are
# ``ENTRY_INTENTS`` members -- never the ``'__unclassified__'`` sentinel
# that ``swing.metrics.cohort`` accepts (that sentinel is a caller-side
# selector convention, not a governance predicate).
_CRITERION_MANDATED_INTENT: dict[str, str] = {
    APLUS_BASELINE_COHORT: "standard",
}

# Clause (4)'s sentence, verbatim -- the authority the exclusion below cites.
# Pinned against ``docs/training-epoch-intent-contract.md`` by test, so a
# doctrine edit that drops it FAILS rather than leaving a filter citing an
# authority that no longer says it.
CONTRACT_EXCLUSION_CLAUSE: str = "It counts toward NO hypothesis cohort."

# The ``entry_intent`` values clause (4) removes from EVERY cohort.
CONTRACT_EXCLUDED_ENTRY_INTENTS: tuple[str, ...] = (UNINTENDED_EXECUTION,)

# RD's plan read: the reason token for an excluded value that carries NO
# ``entry_intent_attestations`` row -- a trade removed from a cohort without
# its evidence, named on every read.
UNATTESTED_TOKEN: str = "UNATTESTED"


def cohort_entry_intent(
    hypothesis_name: str,
    *,
    registered_names: Collection[str] | None = None,
) -> str | None:
    """Return the ``entry_intent`` predicate for ``hypothesis_name``.

    ``None`` means NO intent predicate applies (the epoch-contract
    default). A non-None value is an ``ENTRY_INTENTS`` member required by
    that cohort's own decision criteria.

    ``registered_names`` behaves exactly as in
    :func:`cohort_intent_authority` -- an unregistered name has no
    criterion, so it gets no predicate. Both this function and
    :func:`trade_counts_toward_cohort` accept it and resolve through the
    SAME helper, so the SQL path and the in-memory path answer identically
    for identical arguments (Codex R6).

    Pair every use with :func:`cohort_intent_authority` when the grounding
    needs to be stated; the two are deliberately separate so a reader
    cannot take "there is a filter" as evidence of WHY.
    """
    if registered_names is not None and hypothesis_name not in registered_names:
        return None
    return _CRITERION_MANDATED_INTENT.get(hypothesis_name)


def cohort_intent_authority(
    hypothesis_name: str,
    *,
    registered_names: Collection[str] | None = None,
) -> str:
    """Return which authority grounds ``hypothesis_name``'s predicate.

    :data:`INTENT_AUTHORITY_CRITERION` when the cohort's own
    ``decision_criteria`` names the cohort clause;
    :data:`INTENT_AUTHORITY_EPOCH_CONTRACT` for a registered program
    hypothesis whose criterion does not.

    ``registered_names`` -- pass the live ``hypothesis_registry`` names to
    have an ORPHAN label (free text matching no registered hypothesis)
    answer :data:`INTENT_AUTHORITY_NONE` instead. This module is pure and
    holds no DB handle, so it cannot decide registration on its own; when
    the argument is omitted the caller is asserting the name IS registered,
    which every production caller can (they read it from the registry or
    from the fixed ``TAXONOMY_COHORTS`` tuple).

    The distinction matters because the epoch contract is a claim about the
    PROGRAM's cohorts. Answering ``epoch_contract`` for an arbitrary label
    would assert an authority that never addressed it -- and orphan labels
    do exist: ``swing.metrics.cohort.count_per_cohort`` surfaces them by
    design (and deliberately applies no intent predicate of its own).
    """
    # REGISTRATION IS CHECKED FIRST, and the order is load-bearing (Codex
    # R4). This mapping is a local constant; the registry is the authority.
    # If H1's row were renamed or lost, the stale key would still be in the
    # mapping, and a criterion-first check would answer `criterion` for a
    # name that no longer HAS a criterion -- exactly the case
    # INTENT_AUTHORITY_NONE was added to report.
    if registered_names is not None and hypothesis_name not in registered_names:
        return INTENT_AUTHORITY_NONE
    if hypothesis_name in _CRITERION_MANDATED_INTENT:
        return INTENT_AUTHORITY_CRITERION
    return INTENT_AUTHORITY_EPOCH_CONTRACT


def trade_counts_toward_cohort(
    *,
    entry_intent: str | None,
    hypothesis_name: str,
    registered_names: Collection[str] | None = None,
) -> bool:
    """Python-side mirror of :func:`cohort_entry_intent` for readers that
    filter an already-loaded trade list rather than issuing a SELECT.

    The SQL half lives in ``swing.metrics.cohort.list_trades_for_cohort``
    (``entry_intent=`` parameter). Both sides resolve through
    :func:`cohort_entry_intent` and accept the SAME ``registered_names``
    argument, so the two paths cannot drift -- including in the
    unregistered-cohort case, where both answer "no predicate".
    """
    # Clause (4) FIRST, for every cohort -- before the criterion check.
    if entry_intent in CONTRACT_EXCLUDED_ENTRY_INTENTS:
        return False
    required = cohort_entry_intent(
        hypothesis_name, registered_names=registered_names,
    )
    if required is None:
        return True
    return entry_intent == required


def cohort_excluded_entry_intents(
    hypothesis_name: str,
    *,
    registered_names: Collection[str] | None = None,
) -> tuple[str, ...]:
    """The ``entry_intent`` values excluded from ``hypothesis_name``'s count.

    Clause (4) is program-wide ("NO hypothesis cohort"), so the answer is
    :data:`CONTRACT_EXCLUDED_ENTRY_INTENTS` for EVERY name, registered or
    orphan (an orphan label is not a hypothesis cohort, and excluding there
    is the fail-closed direction -- declared). The parameters mirror
    :func:`cohort_entry_intent` so the SQL call sites read the same way. The
    SQL half is ``list_trades_for_cohort(exclude_entry_intents=...)``; the
    in-memory half is :func:`trade_counts_toward_cohort`.
    """
    del hypothesis_name, registered_names  # the same answer for every cohort
    return CONTRACT_EXCLUDED_ENTRY_INTENTS


def intent_exclusion_reason(entry_intent: str, *, attested: bool) -> str:
    """The reason an excluded trade is named with: its intent, plus
    :data:`UNATTESTED_TOKEN` when no attestation row exists for it."""
    return entry_intent if attested else f"{entry_intent}, {UNATTESTED_TOKEN}"


def intent_exclusion_lines(
    intent_excluded: Collection[tuple[int, str]],
) -> tuple[str, ...]:
    """The ONE renderer of a cohort's intent exclusions (N3 (a)): one ASCII
    line per ``(trade_id, reason)``, rendered beside the tier-2 lines."""
    return tuple(f"not counted: trade {tid} ({reason})"
                 for tid, reason in intent_excluded)
