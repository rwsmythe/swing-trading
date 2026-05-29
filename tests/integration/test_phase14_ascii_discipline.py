"""Phase 14 Sub-bundle 2 T-2.6 -- ASCII discipline (gotcha #16/#32).

Programmatic ``text.encode("ascii")`` over the fully-NEW production files
introduced by this sub-bundle (plan section "Task T-2.6" Step 3 + section K.4
scope). A non-ASCII glyph anywhere in these files raises ``UnicodeEncodeError``
and fails the test.

Whole-file encoding is applied ONLY to files that are 100% NEW in this
sub-bundle. The MODIFIED files (db.py / models.py / config.py / runner.py /
charts.py) carry PRE-EXISTING non-ASCII from prior phases (section K.4 excludes
them from whole-file encoding); their ADDED lines are verified ASCII separately
(the per-task implementers confirmed, and the branch-wide added-line sweep in
T-2.6 confirms no non-ASCII remains in any added swing/ or tests/ line).
"""
from __future__ import annotations

import pathlib

import pytest

# Repo root: tests/integration/<this file> -> parents[2].
_ROOT = pathlib.Path(__file__).resolve().parents[2]

NEW_FILES = [
    "swing/data/migrations/0022_phase14_temporal_log.sql",
    "swing/data/repos/pattern_detection_events.py",
    "swing/data/repos/pattern_forward_observations.py",
    "swing/pipeline/temporal_metadata.py",
    "swing/pipeline/detection_chart_capture.py",
]


@pytest.mark.parametrize("rel_path", NEW_FILES)
def test_new_phase14_files_are_ascii(rel_path: str) -> None:
    path = _ROOT / rel_path
    assert path.exists(), f"expected NEW file missing: {rel_path}"
    text = path.read_text(encoding="utf-8")
    # Raises UnicodeEncodeError (failing the test) on any non-ASCII glyph.
    text.encode("ascii")


def test_ascii_discipline_module_is_ascii() -> None:
    """This test module is itself ASCII-only (gotcha #32)."""
    pathlib.Path(__file__).read_text(encoding="utf-8").encode("ascii")
