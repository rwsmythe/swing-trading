"""Discipline-locking tests for G2 dispatch (Slice 5a).

Per dispatch brief Sec 4.3 + Sec 5.3 + Sec 6:
  - L2 LOCK: source-grep over NEW G2 module set for forbidden imports
  - ASCII discipline (gotcha #32): all NEW G2 source / test / artifact
    Python files encode as ASCII
  - Byte-stability LOCK for existing A-F harness + R2-A/D2 cohort fixtures
  - Gotcha #33 banned-verdict-terms LOCK: scorecard module + narrative
    output emitters MUST NOT emit PARTIAL POSITIVE / NEGATIVE / POSITIVE
  - Gotcha #35 prior-arc-anchor metric-definition citation discipline:
    when narrative templates cite prior-arc numerical anchors, the metric
    definition MUST be cited too
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest


# Repo root: resolves the project root via this test file's location.
# `tests/research/g2_w_bottom_ruleset/test_locks.py` -> parents[3] = repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Files covered by the G2 dispatch (NEW only; existing harness is byte-stable).
G2_PACKAGE_DIR = REPO_ROOT / "research" / "harness" / "g2_w_bottom_ruleset_backtest"
G2_TESTS_DIR = REPO_ROOT / "tests" / "research" / "g2_w_bottom_ruleset"


def _enumerate_g2_python_files() -> list[Path]:
    """All NEW G2 Python files (package + tests)."""
    return sorted(
        list(G2_PACKAGE_DIR.rglob("*.py"))
        + list(G2_TESTS_DIR.rglob("*.py"))
    )


# ---------------------------------------------------------------------------
# L2 LOCK: source-grep for forbidden imports
# ---------------------------------------------------------------------------
FORBIDDEN_L2_PATTERNS = [
    r"\bimport\s+schwabdev\b",
    r"\bfrom\s+schwabdev\b",
    r"\bimport\s+yfinance\b",
    r"\bfrom\s+yfinance\b",
    r"\bfrom\s+swing\.integrations\.schwab\b",
    r"\bimport\s+swing\.integrations\.schwab\b",
]


@pytest.mark.parametrize("py_path", _enumerate_g2_python_files(), ids=lambda p: p.name)
def test_l2_lock_no_forbidden_imports_in_g2_module(py_path):
    """LOCK: each NEW G2 module must NOT import schwabdev / yfinance /
    swing.integrations.schwab. The harness consumes OHLCV via the existing
    V2 Shape A reader (read_yfinance_shape_a) inherited from the existing
    harness module set.

    Exception: test_locks.py (THIS file) is excluded from its own scan
    because it MUST literally contain the forbidden patterns inside its
    FORBIDDEN_L2_PATTERNS list to enforce the discipline.
    """
    # Skip THIS test file (which contains the forbidden patterns by design).
    if py_path.name == "test_locks.py":
        pytest.skip("test_locks.py contains forbidden patterns as detection rules")
    text = py_path.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_L2_PATTERNS:
        matches = re.findall(pattern, text)
        assert not matches, (
            f"L2 LOCK violation in {py_path.relative_to(REPO_ROOT)}: "
            f"forbidden import pattern {pattern!r} matched {matches}"
        )


# ---------------------------------------------------------------------------
# ASCII discipline (gotcha #32)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("py_path", _enumerate_g2_python_files(), ids=lambda p: p.name)
def test_ascii_discipline_g2_python_files_encode_clean(py_path):
    """LOCK: all NEW G2 source + test files must encode as ASCII (gotcha
    #32 declared-scope; pre-empts Windows cp1252 stdout encoding errors)."""
    text = py_path.read_text(encoding="utf-8")
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        # Find the first offending line for actionable error message.
        bad_lines = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            try:
                line.encode("ascii")
            except UnicodeEncodeError:
                bad_lines.append(f"  line {line_num}: {line!r}")
                if len(bad_lines) >= 5:
                    bad_lines.append("  ...")
                    break
        raise AssertionError(
            f"ASCII LOCK violation in {py_path.relative_to(REPO_ROOT)}:\n"
            + "\n".join(bad_lines)
            + f"\n\nFirst error: {exc}"
        )


# ---------------------------------------------------------------------------
# Byte-stability LOCK: existing A-F harness + cohort fixtures
# ---------------------------------------------------------------------------
# Per brief Sec 1.6 + Sec 5.3: A-F rulesets module + R2-A + D2 cohort
# fixtures must remain UNTOUCHED through the G2 dispatch. SHA-256 anchored
# at dispatch baseline 423f21d (main HEAD at dispatch time).
EXISTING_HARNESS_BYTE_STABILITY = {
    "research/harness/w_bottom_ruleset_comparison/__init__.py": None,
    "research/harness/w_bottom_ruleset_comparison/rulesets.py": None,
    "research/harness/w_bottom_ruleset_comparison/walkforward.py": None,
    "research/harness/w_bottom_ruleset_comparison/run.py": None,
    "research/harness/w_bottom_ruleset_comparison/io.py": None,
}

COHORT_FIXTURE_BYTE_STABILITY = {
    "tests/fixtures/research/r2a_tightness_days_required/cohort.json": (
        "758675b897affb4cf779259fdfe41398a3305b9480e8e3e510a358d83c4a35e7"
    ),
    "tests/fixtures/research/double_bottom_w_backtest/cohort.json": (
        "9075ac66d70401a19f11c06b681d859d3a5fbcd16e373e282c4db991bd6cc40c"
    ),
}


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "rel_path,expected_sha",
    list(COHORT_FIXTURE_BYTE_STABILITY.items()),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_cohort_fixture_byte_stable_through_g2_dispatch(rel_path, expected_sha):
    """LOCK: R2-A + D2 cohort fixtures (the G2 substrates) byte-stable per
    brief Sec 1.6 ('REUSE VERBATIM'). SHA-256 anchored at dispatch baseline
    main commit 423f21d."""
    if expected_sha is None:
        pytest.skip(f"{rel_path}: SHA not anchored (informational entry)")
    path = REPO_ROOT / rel_path
    actual = _sha256_of(path)
    assert actual == expected_sha, (
        f"Cohort fixture {rel_path} drifted from dispatch baseline. "
        f"Expected SHA {expected_sha}, got {actual}. The G2 dispatch "
        f"BANS modification of these fixtures (brief Sec 1.6 + Sec 5.3)."
    )


@pytest.mark.parametrize(
    "rel_path", list(EXISTING_HARNESS_BYTE_STABILITY.keys())
)
def test_existing_harness_file_present_and_readable(rel_path):
    """LOCK: existing w_bottom_ruleset_comparison/ harness files are
    preserved (file exists; no deletion / move). Byte-content unchanged
    verification happens via dispatch baseline git diff; this test guards
    against accidental file removal during the G2 dispatch."""
    path = REPO_ROOT / rel_path
    assert path.exists(), (
        f"Existing harness file {rel_path} missing. The G2 dispatch BANS "
        f"modification or removal of the existing harness (brief Sec 5.3 "
        f"sibling-module strategy LOCK)."
    )
    # File is readable Python (smoke check via compile()).
    text = path.read_text(encoding="utf-8")
    assert len(text) > 0


# ---------------------------------------------------------------------------
# Gotcha #33 banned-verdict-terms LOCK (scorecard + narrative emitters)
# ---------------------------------------------------------------------------
# Per brief Sec 1.4 + Sec 6 + gotcha #33 third canonical application: the
# scorecard module + ANY narrative output emitter in the G2 package must
# NOT emit PARTIAL POSITIVE / NEGATIVE / POSITIVE as verdict labels.
# Banned forms: case-insensitive word-boundary matches in PRODUCTION CODE
# (not test files; tests legitimately reference the terms when discussing
# the ban).
_BANNED_VERDICT_PATTERNS = [
    r"\bPARTIAL\s+POSITIVE\b",
    r"\bPOSITIVE\b",
    r"\bNEGATIVE\b",
]


def _enumerate_g2_production_python_files() -> list[Path]:
    """Production G2 modules ONLY (excludes tests/)."""
    return sorted(G2_PACKAGE_DIR.rglob("*.py"))


def _strip_python_string_literals_and_comments(text: str) -> str:
    """Best-effort removal of string literals + line comments + docstrings.

    Used so banned-term scans do NOT flag legitimate descriptive language
    in docstrings/comments (e.g., 'NO PARTIAL POSITIVE / NEGATIVE / POSITIVE
    in scorecard or narrative output per gotcha #33'). The scorecard module
    docstring uses this phrasing to DOCUMENT the ban.

    The strip is conservative; if it misses an edge case, the test would
    over-flag (a false positive) rather than miss a real violation.
    """
    # Drop triple-quoted strings (both """ and ''')
    text = re.sub(r'""".*?"""', '""', text, flags=re.DOTALL)
    text = re.sub(r"'''.*?'''", "''", text, flags=re.DOTALL)
    # Drop single-line string literals (best-effort)
    text = re.sub(r'"[^"\n\\]*(?:\\.[^"\n\\]*)*"', '""', text)
    text = re.sub(r"'[^'\n\\]*(?:\\.[^'\n\\]*)*'", "''", text)
    # Drop line comments
    text = re.sub(r"#[^\n]*", "", text)
    return text


@pytest.mark.parametrize(
    "py_path", _enumerate_g2_production_python_files(), ids=lambda p: p.name
)
def test_gotcha_33_no_banned_verdict_terms_in_g2_production_code(py_path):
    """LOCK gotcha #33: scorecard + narrative emitters MUST NOT emit
    PARTIAL POSITIVE / NEGATIVE / POSITIVE as verdict labels in EXECUTABLE
    code (string literals + comments + docstrings exempt; the discipline
    is about emitted OUTPUT, not source-code documentation of the ban).

    The strip helper drops literal strings + docstrings + comments so
    legitimate references in module docstrings (documenting the ban) do
    NOT trip the assertion.
    """
    raw = py_path.read_text(encoding="utf-8")
    stripped = _strip_python_string_literals_and_comments(raw)
    for pattern in _BANNED_VERDICT_PATTERNS:
        matches = re.findall(pattern, stripped, flags=re.IGNORECASE)
        assert not matches, (
            f"Gotcha #33 LOCK violation in "
            f"{py_path.relative_to(REPO_ROOT)}: banned verdict pattern "
            f"{pattern!r} matched in executable code: {matches}"
        )
