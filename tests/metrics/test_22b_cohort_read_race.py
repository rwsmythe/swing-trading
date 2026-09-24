"""Arc 22-B Reviewer A R1-3 -- one render is internally consistent on the
four governed decision readers (RD RULING R1-3; CHARC RULING
R1-3-SHAPE-EXEC, which WITHDREW the snapshot bracket: the disjointness
assert stands alone).

Each governed reader counts from one read and names clause-(4) trades
("not counted: trade N (unintended_execution)") from a SECOND read. An
``assign(...)`` committing between the two would render trade N COUNTED and
NAMED "not counted" in one row. ``assert_intent_exclusion_disjoint`` is
called by every governed reader after its naming read and before it
populates ``intent_excluded``; a non-empty intersection raises the typed
``CohortReadRacedError``, which each surface renders as its refusal.

The race is planted BY EXECUTION (RD's test shape): the naming read is
monkeypatched to first commit a REAL ``assign(...)`` on a counted trade over
a SECOND connection, then run the original. One case per reader shape --
in-memory (``journal/stats.py``) and SQL (``metrics/tier.py``); the other two
readers are covered by the shared helper plus b22_130's name closure.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.metrics.test_22b_cohort_exclusion import (  # noqa: F401 (fixtures)
    H1,
    H2,
    UNINTENDED,
    _attest,
    _seed,
    cfg,
    conn,
)

RACED_TID = 3            # the H2 trade the planted assign moves mid-render
RACED_MESSAGE = "cohort read raced an intent write; re-run"


# ---------------------------------------------------------------------------
# b22_229 -- the helper itself
# ---------------------------------------------------------------------------
def test_the_disjointness_assert_raises_typed_on_intersection_only_b22_229() -> None:
    from swing.metrics.cohort import (
        CohortReadRacedError,
        assert_intent_exclusion_disjoint,
    )

    assert issubclass(CohortReadRacedError, ValueError)
    named = ((3, UNINTENDED), (8, f"{UNINTENDED}, UNATTESTED"))
    # Disjoint -> no error (the consistent renders, both directions).
    assert assert_intent_exclusion_disjoint({1, 2}, named) is None
    assert assert_intent_exclusion_disjoint(set(), named) is None
    assert assert_intent_exclusion_disjoint({3, 8}, ()) is None
    assert assert_intent_exclusion_disjoint([None, 1], named) is None
    # Intersection -> the typed error, the ruled text, the ids carried.
    with pytest.raises(CohortReadRacedError) as exc:
        assert_intent_exclusion_disjoint([1, 3, None], named)
    assert str(exc.value) == RACED_MESSAGE
    assert str(exc.value).isascii()
    assert exc.value.trade_ids == (3,)
    with pytest.raises(CohortReadRacedError) as exc:
        assert_intent_exclusion_disjoint((8, 3), named)
    assert exc.value.trade_ids == (3, 8)


def test_the_assert_docstring_carries_the_sufficiency_argument_b22_230() -> None:
    """The ruling's sufficiency argument and its NAMED precondition live in
    the helper's docstring (RULING R1-3-SHAPE-EXEC point 2)."""
    from swing.metrics.cohort import assert_intent_exclusion_disjoint

    doc = " ".join((assert_intent_exclusion_disjoint.__doc__ or "").split())
    for trigger in ("trg_trades_entry_intent_attested_terminal",
                    "trg_trades_entry_intent_unattested_update",
                    "trg_trades_entry_intent_unattested_insert",
                    "trg_eia_no_delete", "trg_eia_no_replace"):
        assert trigger in doc, trigger
    assert "MONOTONE" in doc
    assert "no fourth state" in doc.lower()
    assert "reversal surface" in doc
    assert "re-opens" in doc or "re-rules" in doc
