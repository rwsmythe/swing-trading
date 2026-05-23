"""Shared hypothesis-label match helpers (Python + SQL).

Three-rule delimiter-aware match contract -- a label MATCHES a hypothesis
name when (and only when) one of these holds:
  1. label == name (after case-fold; exact equality).
  2. label.lower().startswith(name.lower() + " ") (space delimiter).
  3. label.lower().startswith(name.lower() + ";") (semicolon delimiter).

This is the SHARED canonicalization both the Python helper at
``swing.recommendations.hypothesis._label_matches_hypothesis`` AND the SQL
predicate at ``swing.metrics.cohort.list_trades_for_cohort`` consume. The
two helpers MUST produce identical match sets on any test corpus.

Phase 13 T-T4.SB.2 closes the per-trade-suffix false-positive defect family
introduced when free-text suffixes (e.g., ``"(watch); failed: <criterion>"``)
were appended to canonical hypothesis names. Pre-fix the exact-equality
helpers silently dropped suffix-bearing trades from cohort counts; the
bare-startswith helpers (``swing/recommendations/hypothesis.py``) accepted
them but also accepted bare-prefix extensions like
``"Sub-A+ VCP-not-formedness"`` (no delimiter) -- the new contract rejects
those.
"""
from __future__ import annotations


def label_matches_hypothesis(label: str | None, name: str) -> bool:
    """Return True iff ``label`` matches ``name`` under the 3-rule contract."""
    if not label:
        return False
    lo_label = label.lower()
    lo_name = name.lower()
    if lo_label == lo_name:
        return True
    if lo_label.startswith(lo_name + " "):
        return True
    return lo_label.startswith(lo_name + ";")


def sql_escape_wildcard(name: str) -> str:
    """Escape SQL LIKE wildcards in a registered cohort name.

    Order matters: backslash FIRST (otherwise subsequent backslash
    insertions get re-escaped), then ``%`` and ``_``.
    """
    out = name.replace("\\", "\\\\")
    out = out.replace("%", r"\%")
    out = out.replace("_", r"\_")
    return out


def label_matches_hypothesis_sql(name: str) -> tuple[str, list[object]]:
    """Return ``(WHERE fragment, binding params)`` for the 3-rule match.

    Three predicates joined by ``OR``. Param 1 (equality) receives RAW
    lowercased name; params 2-3 (LIKE) receive WILDCARD-ESCAPED lowercased
    name. Mixing the two would either over-escape equality or under-escape
    LIKE (per spec Codex R4 M#2 LOCK -- the SQL LIKE binding asymmetry
    sub-discipline of Expansion #10).
    """
    raw = name.lower()
    escaped = sql_escape_wildcard(raw)
    fragment = (
        "("
        "LOWER(hypothesis_label) = LOWER(?) "
        "OR LOWER(hypothesis_label) LIKE LOWER(?) || ' %' ESCAPE '\\' "
        "OR LOWER(hypothesis_label) LIKE LOWER(?) || ';%' ESCAPE '\\'"
        ")"
    )
    return fragment, [raw, escaped, escaped]
