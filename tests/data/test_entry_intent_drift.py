"""Arc 22-B -- the `trades.entry_intent` mirror family (#11).

The SQL-vs-Python drift test is the ONE mirror that defends the value set
(the #11 amendment: a token grep bounds the family from below; the comparator
is the mirror that does not depend on choosing the right grep). It is a mirror
test, so HEAD-tracking and version-free in its name.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import (
    ENTRY_INTENTS,
    ENTRY_INTENTS_ASSERTABLE,
    UNINTENDED_EXECUTION,
    Trade,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_entry_intent_check_equals_python_enum_b22_31(tmp_path: Path) -> None:
    c = ensure_schema(tmp_path / "drift.db")
    try:
        sql = c.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'trades'").fetchone()[0]
    finally:
        c.close()
    found = re.findall(r"entry_intent IN \(([^)]*)\)", sql)
    assert len(found) == 1, found
    assert set(re.findall(r"'([^']+)'", found[0])) == ENTRY_INTENTS
    assert ENTRY_INTENTS_ASSERTABLE < ENTRY_INTENTS
    assert ENTRY_INTENTS - ENTRY_INTENTS_ASSERTABLE == {UNINTENDED_EXECUTION}


def _trade(entry_intent: str | None) -> Trade:
    return Trade(
        id=None, ticker="ZZZ", entry_date="2026-08-01", entry_price=10.0,
        initial_shares=1, initial_stop=9.0, current_stop=9.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-08-01T16:00:00", entry_intent=entry_intent)


def test_the_model_rejects_a_fourth_value_b22_32() -> None:
    for v in sorted(ENTRY_INTENTS):
        assert _trade(v).entry_intent == v  # the READ path hydrates all three
    with pytest.raises(ValueError, match="entry_intent"):
        _trade("abandoned")


# READ-classified, per member (grep each member SEPARATELY -- the #11 second
# facet). The grep is the quoted token over swing/**/*.{py,j2,sql}; a new site
# FAILS until it is classified here with its reason.
_MEMBER_SITES: dict[str, dict[str, str]] = {
    "standard": {
        "swing/data/migrations/0027_entry_intent.sql":
            "tight-by-design: the historical CHECK 0040 rebuilds (history is immutable)",
        "swing/data/migrations/0040_entry_intent_unintended_execution.sql":
            "widened: the v40 CHECK",
        "swing/data/models.py":
            "widened: ENTRY_INTENTS; tight-by-design: ENTRY_INTENTS_ASSERTABLE",
        "swing/metrics/cohort_intent.py":
            "value-agnostic: H1's own criterion predicate names 'standard'",
        "swing/trades/intent.py":
            "tight-by-design: the entry-time CHOICES; widened: the LABELS",
        "swing/trades/entry_intent_assignment.py":
            "prose: the mandate-fill refusal message (clause (1))",
        "swing/web/view_models/metrics/process_grade_trend.py":
            "widened in Task 9: the per-intent CSS class map",
        "swing/web/view_models/metrics/trade_process_card.py":
            "widened in Task 9: the card's intent filter options",
    },
    "hypothesis_test_by_design": {
        "swing/data/migrations/0027_entry_intent.sql":
            "tight-by-design: the historical CHECK 0040 rebuilds",
        "swing/data/migrations/0040_entry_intent_unintended_execution.sql":
            "widened: the v40 CHECK",
        "swing/data/models.py":
            "widened: ENTRY_INTENTS; tight-by-design: ENTRY_INTENTS_ASSERTABLE",
        "swing/metrics/cohort_intent.py":
            "value-agnostic: prose + the H2-H5 epoch-contract doctrine",
        "swing/trades/intent.py":
            "tight-by-design: the entry-time CHOICES + the advisory suggestion",
        "swing/web/view_models/metrics/process_grade_trend.py":
            "widened in Task 9: the per-intent CSS class map",
        "swing/web/view_models/metrics/trade_process_card.py":
            "widened in Task 9: the card's intent filter options",
    },
    "unintended_execution": {
        "swing/cli.py": "prose: EntryIntentParam's docstring (the seam)",
        "swing/data/db.py": "prose: the v40 comment",
        "swing/data/migrations/0040_entry_intent_unintended_execution.sql":
            "widened: the v40 CHECK + the N4 trigger",
        "swing/data/models.py":
            "widened: ENTRY_INTENTS; the UNINTENDED_EXECUTION constant + SEAM_MESSAGE",
        "swing/trades/entry_intent_assignment.py":
            "prose: docstrings (the value is the imported UNINTENDED_EXECUTION)",
        "swing/trades/intent.py": "widened: the display LABEL",
        "swing/trades/reconciliation_auto_correct.py":
            "prose: the corrector reservation's comment",
        "swing/data/repos/trades.py":
            "prose: N4 layer 1's docstring + comment (Task 7; the value is the "
            "imported UNINTENDED_EXECUTION)",
        "swing/web/routes/trades.py":
            "prose: the review POST's N4 comment (Task 7)",
        "swing/web/view_models/trades.py":
            "prose: ReviewVM's N4 field comment (Task 7; the builder compares "
            "the imported UNINTENDED_EXECUTION)",
    },
}


@pytest.mark.parametrize("member", sorted(_MEMBER_SITES))
def test_each_member_greps_separately_b22_33(member: str) -> None:
    pat = re.compile(rf"[\"'`]{re.escape(member)}[\"'`]")
    found = set()
    for pattern in ("*.py", "*.j2", "*.sql"):
        for path in (REPO_ROOT / "swing").rglob(pattern):
            if pat.search(path.read_text(encoding="utf-8")):
                found.add(path.relative_to(REPO_ROOT).as_posix())
    assert found == set(_MEMBER_SITES[member]), sorted(found ^ set(_MEMBER_SITES[member]))
