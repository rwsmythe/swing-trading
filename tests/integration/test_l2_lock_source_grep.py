"""L2 LOCK parametric source-grep regression test (Phase 14 Sub-bundle 1).

The L2 LOCK = ZERO new Schwab API calls beyond OQ-13 CLI carve-outs;
preserved through 12 applied research arcs + Phase 13 + Sub-bundle 1.
Per dispatch brief section 1.1 commissioning baseline = main commit
``bf7e071`` (Phase 14 commissioning HEAD).

Per CLAUDE.md gotcha #34: brief-prescription cross-table verification.
The verification consumes ``git grep`` output to count occurrences of the
target pattern in ``swing/`` at HEAD vs baseline.

Per CLAUDE.md cumulative gotcha (writing-plans R1.M#5 + R2.M#6 LOCKs):
multiset (Counter) comparison -- NOT count-only OR set-only -- catches
both the swap-introduce-while-remove pattern AND the duplicate-identical-
line-in-same-file pattern that simpler comparisons would silently miss.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import pytest

L2_LOCK_BASELINE_SHA = "bf7e071"

L2_LOCK_PATTERNS = [
    # Direct schwabdev SDK invocations.
    "schwabdev.Client.",
]


def _count_call_sites(rev: str, pattern: str) -> Counter[tuple[str, str]]:
    """Run ``git grep -n <pattern> <rev> -- swing/`` and return a
    ``Counter`` keyed by ``(path, normalized_line_text)``.

    Per Codex R1.M#5 + R2.M#6 LOCK: set-only comparison silently passes
    when an IDENTICAL call-site line is duplicated within the same
    file (set dedupes the duplicate). Multiset/Counter comparison
    fails on EITHER (a) NEW (path, line_text) keys OR (b) increased
    count on an EXISTING key. Line numbers are normalized out (they
    shift across commits; the LINE TEXT is the L2 LOCK signal).
    """
    result = subprocess.run(
        ["git", "grep", "-n", pattern, rev, "--", "swing/"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        # git grep returns 1 if no matches; 0 if matches; >1 on error.
        raise RuntimeError(
            f"git grep failed unexpectedly for {pattern!r} at {rev}: "
            f"stderr={result.stderr!r}"
        )
    counter: Counter[tuple[str, str]] = Counter()
    for line in result.stdout.splitlines():
        # Format: "<rev>:<path>:<line_number>:<line_text>" -- split on
        # first 3 colons to preserve any colons inside line_text.
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        _rev, path, _lineno, line_text = parts
        counter[(path, line_text.strip())] += 1
    return counter


@pytest.mark.parametrize("pattern", L2_LOCK_PATTERNS)
def test_l2_lock_no_new_call_sites_vs_commissioning_baseline(pattern: str) -> None:
    """HEAD's multiset of (path, line_text) -> count matches for the
    L2 LOCK pattern in ``swing/`` MUST be a multiset SUBSET of the
    commissioning baseline at ``bf7e071``. New non-whitelisted matches
    OR INCREASED counts on existing keys FAIL the test.

    Per writing-plans Codex R1.M#5 + R2.M#6 LOCKs: Counter-comparison
    (NOT plain set) catches BOTH the swap-introduce-while-remove pattern
    AND the duplicate-line-in-same-file pattern that set-only would
    silently miss.
    """
    baseline = _count_call_sites(L2_LOCK_BASELINE_SHA, pattern)
    head = _count_call_sites("HEAD", pattern)
    violations: list[tuple[str, str, int, int]] = []
    for key, head_count in head.items():
        baseline_count = baseline.get(key, 0)
        if head_count > baseline_count:
            path, line_text = key
            violations.append((path, line_text, baseline_count, head_count))
    assert not violations, (
        f"L2 LOCK violation: HEAD introduces {len(violations)} "
        f"new-or-inflated (path, line_text) call sites matching "
        f"{pattern!r} in swing/ vs commissioning baseline at "
        f"{L2_LOCK_BASELINE_SHA}.\n"
        + "\n".join(
            f"  {p}: {t}  (baseline_count={bc}, head_count={hc})"
            for p, t, bc, hc in sorted(violations)
        )
        + "\nSub-bundle 1 must NOT introduce new Schwab API call sites."
    )


def test_l2_lock_source_grep_module_ascii_only() -> None:
    """Per gotcha #32 -- this test module ASCII-only."""
    Path(__file__).read_text(encoding="utf-8").encode("ascii")
