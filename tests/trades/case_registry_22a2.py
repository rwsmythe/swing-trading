"""22-A2 test-roster REGISTRY -- every roster id ``A2-NN`` mapped to its module.

The plan's section 6 roster is the manifest; this dict is its machine-readable
copy, established by READ of the plan, and ``test_22a2_case_closure.py`` walks
the test tree in BOTH directions against it: every id here has exactly one
implementing test function (a module-level ``test_*`` whose name carries the
token ``a2_NN``), and no test function anywhere carries an ``a2_NN`` token
absent from here (a PHANTOM).  Every id is landed; there is no skip list.
"""
from __future__ import annotations

_T1 = "tests/data/test_22a2_barrier_drop_scan.py"
_T2 = "tests/trades/test_22a2_case_closure.py"
_T3 = "tests/data/test_migration_0039_provenance_corrections_tier2.py"
_T4 = "tests/trades/test_22a2_frozen_value_preflight.py"
_T5 = "tests/trades/test_22a2_conjunction.py"
_T6 = "tests/trades/test_22a2_rung9_escape.py"
_T7 = "tests/trades/test_22a2_correction_service.py"
_T8 = "tests/cli/test_correct_cohort_provenance_command.py"
_T9 = "tests/trades/test_22a2_replay.py"
_T10 = "tests/trades/test_22a2_cohort_readers.py"
_T11 = "tests/trades/test_22a2_acceptance_trade25.py"


def _span(lo: int, hi: int, module: str) -> dict[str, str]:
    return {f"A2-{n:02d}": module for n in range(lo, hi + 1)}


CASES_22A2: dict[str, str] = {
    **_span(1, 7, _T1),
    **_span(8, 9, _T2),
    **_span(10, 31, _T3),
    **_span(32, 41, _T4),
    **_span(42, 60, _T5),
    **_span(61, 66, _T6),
    **_span(67, 76, _T7),
    **_span(77, 80, _T8),
    **_span(81, 90, _T9),
    **_span(91, 97, _T10),
    "A2-97b": _T10,
    "A2-97c": _T10,
    **_span(98, 104, _T11),
}

# Roster ids whose implementing test lives in a pre-existing module the plan
# names (A2-22: the backup-gate roster split, P33).
CASES_22A2["A2-22"] = "tests/data/test_backup_gate_table.py"


def token(roster_id: str) -> str:
    """``A2-07`` -> ``a2_07``; ``A2-97b`` -> ``a2_97b``."""
    return roster_id.lower().replace("-", "_")
