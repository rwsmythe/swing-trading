"""T-T4.SB.2 Sub-task 2A — shared 3-rule delimiter-aware label-match helper."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.metrics.label_match import (
    label_matches_hypothesis,
    label_matches_hypothesis_sql,
    sql_escape_wildcard,
)


def test_label_matches_hypothesis_three_rule_delimiter_aware():
    # Rule 1: exact equality (case-insensitive)
    assert label_matches_hypothesis("A+ baseline", "A+ baseline") is True
    assert label_matches_hypothesis("a+ baseline", "A+ baseline") is True
    # Rule 2: space delimiter
    assert label_matches_hypothesis(
        "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",
        "Sub-A+ VCP-not-formed",
    ) is True
    # Rule 3: semicolon delimiter
    assert label_matches_hypothesis(
        "Sub-A+ VCP-not-formed;extra",
        "Sub-A+ VCP-not-formed",
    ) is True
    # Rejected: bare prefix extension (no delimiter)
    assert label_matches_hypothesis(
        "Sub-A+ VCP-not-formedness",
        "Sub-A+ VCP-not-formed",
    ) is False
    # Rejected: empty label
    assert label_matches_hypothesis("", "A+ baseline") is False
    assert label_matches_hypothesis(None, "A+ baseline") is False


def test_sql_escape_wildcard_replaces_backslash_percent_underscore():
    assert sql_escape_wildcard("plain_name") == r"plain\_name"
    assert sql_escape_wildcard("90%up") == r"90\%up"
    assert sql_escape_wildcard(r"path\to") == r"path\\to"


def test_label_matches_hypothesis_sql_returns_fragment_and_three_bindings():
    fragment, params = label_matches_hypothesis_sql("cohort_X%")
    # Three predicates joined by OR.
    assert "LOWER(hypothesis_label) = LOWER(?)" in fragment
    assert "LOWER(hypothesis_label) LIKE LOWER(?) || ' %' ESCAPE '\\'" in fragment
    assert "LOWER(hypothesis_label) LIKE LOWER(?) || ';%' ESCAPE '\\'" in fragment
    # Raw lowercased name for equality + escaped lowercased for LIKE predicates.
    assert params[0] == "cohort_x%"
    assert params[1] == r"cohort\_x\%"
    assert params[2] == r"cohort\_x\%"


def test_registered_hypothesis_names_do_not_delimiter_overlap(tmp_path: Path):
    """Invariant (Codex R5 MIN#2 LOCK): no registered hypothesis name
    delimiter-matches another's canonical form (prefix-overlap would cause
    double-counting on cohorts)."""
    conn = ensure_schema(tmp_path / "registry.db")
    rows = list(conn.execute("SELECT name FROM hypothesis_registry"))
    names = [r[0] for r in rows]
    assert len(names) >= 1
    for a in names:
        for b in names:
            if a == b:
                continue
            assert label_matches_hypothesis(b, a) is False, (
                f"Registered hypothesis {b!r} delimiter-matches {a!r} "
                "-- would double-count cohort metrics."
            )


def test_synthetic_registry_overlap_invariant_detects_offender():
    """Discriminating regression: the invariant assertion correctly REJECTS
    a synthetic registry pair where one name space-delimiter-matches the
    other -- proves the invariant test would catch a future migration that
    introduced a delimiter-overlapping cohort name."""
    # Construct a synthetic pair that violates the invariant.
    synthetic_names = ["A+ baseline", "A+ baseline extended"]
    offending_pairs: list[tuple[str, str]] = []
    for a in synthetic_names:
        for b in synthetic_names:
            if a == b:
                continue
            if label_matches_hypothesis(b, a):
                offending_pairs.append((a, b))
    # The synthetic pair "A+ baseline" + "A+ baseline extended" SHOULD trip
    # the invariant -- proves the registered-name guard is functional.
    assert offending_pairs == [("A+ baseline", "A+ baseline extended")]
