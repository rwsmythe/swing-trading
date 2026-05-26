"""Discipline tests for R2-A: D2 harness reuse + L2 LOCK + cohort-validity.

R2-A is a re-execution of D2's 6-ruleset W-bottom comparison against a
DIFFERENT cohort (selection-biased per V2 OHLCV sensitivity binding-variable
flips, not bias-free S&P 500 detection). These tests verify:

  - R2-A does NOT modify D2's harness modules (REUSE verbatim per brief §10).
  - R2-A modules do NOT import schwab / yfinance / swing.integrations
    (L2 LOCK preserved per CLAUDE.md gotchas + V2 reinforcement tests).
  - Cohort fixture exists with expected shape + scope.
  - Cohort selection method recorded explicitly per gotcha #33.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# §5.3 D2 harness REUSE verbatim
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel_path",
    [
        "research/harness/w_bottom_ruleset_comparison/__init__.py",
        "research/harness/w_bottom_ruleset_comparison/walkforward.py",
        "research/harness/w_bottom_ruleset_comparison/rulesets.py",
        "research/harness/w_bottom_ruleset_comparison/io.py",
        "research/harness/w_bottom_ruleset_comparison/run.py",
        "research/harness/double_bottom_w_backtest/cohort.py",
    ],
)
def test_d2_harness_modules_unchanged_by_r2a(rel_path: str) -> None:
    """R2-A MUST NOT modify D2's harness modules; assert each touched file
    is byte-identical to its merge-base on `main` at the dispatch start.

    The brief §10 prohibits modifying `research/harness/w_bottom_ruleset_comparison/`
    or any cohort-extraction module D2 inherited from D1. If a future ship
    needs to extend these, the change is part of that arc's dispatch -- not
    a side-effect of R2-A.

    This test compares the working-tree file SHA against the git-blob SHA of
    `main` at branch fork (gracefully skips when git is not available, e.g.,
    in shallow-clone CI; the assertion is meaningful in dev + on full CI).
    """
    import subprocess
    abs_path = REPO_ROOT / rel_path
    assert abs_path.exists(), f"missing {rel_path}"
    try:
        proc = subprocess.run(
            ["git", "show", f"main:{rel_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("git not available")
    if proc.returncode != 0:
        pytest.skip(f"git show main:{rel_path} failed (likely shallow clone)")
    main_bytes = proc.stdout
    # Normalize line endings (CRLF on Windows working tree vs LF in git objects)
    main_normalized = main_bytes.replace(b"\r\n", b"\n")
    working_bytes = abs_path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(working_bytes).hexdigest() == hashlib.sha256(
        main_normalized
    ).hexdigest(), (
        f"{rel_path} differs from main; R2-A must REUSE D2 harness verbatim "
        f"(brief §10). If a deliberate change is required, scope a separate "
        f"dispatch."
    )


# ---------------------------------------------------------------------------
# §5.4 L2 LOCK (R2-A modules do NOT introduce schwab/yfinance imports)
# ---------------------------------------------------------------------------
_FORBIDDEN_IMPORT_PATTERNS = [
    r"\bimport\s+schwabdev\b",
    r"\bfrom\s+schwabdev\b",
    r"\bimport\s+yfinance\b",
    r"\bfrom\s+yfinance\b",
    r"\bfrom\s+swing\.integrations\.schwab\b",
    r"\bimport\s+swing\.integrations\.schwab\b",
]


@pytest.mark.parametrize(
    "rel_path",
    [
        "research/harness/r2a_tightness_days_required/__init__.py",
        "research/harness/r2a_tightness_days_required/cohort_csv.py",
    ],
)
def test_r2a_module_no_schwab_or_yfinance_imports(rel_path: str) -> None:
    """L2 LOCK: R2-A modules MUST NOT import schwabdev / yfinance /
    swing.integrations.schwab. The dispatch is a research-branch artifact;
    no broker integration; no network calls at backtest time.

    Pattern complement to existing 5 BINDING L2 LOCK reinforcement tests
    at tests/research/test_aplus_v2_ohlcv_reader.py (V2 reader source-grep
    + import-graph sentinel + byte-checksum + signature lock + V2 source-grep).
    """
    abs_path = REPO_ROOT / rel_path
    src = abs_path.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IMPORT_PATTERNS:
        assert re.search(pat, src) is None, (
            f"{rel_path} contains forbidden L2-LOCK violation matching {pat!r}; "
            f"R2-A must not introduce broker/data-fetch integrations"
        )


# ---------------------------------------------------------------------------
# §5.2 Cohort-validity cross-check (NEW per gotcha #33)
# ---------------------------------------------------------------------------
def test_r2a_cohort_fixture_exists_and_well_formed() -> None:
    """The R2-A cohort.json fixture exists, parses as JSON, has 7 unique
    tickers matching the V2 sensitivity binding-variable flips."""
    fx_path = (
        REPO_ROOT
        / "tests/fixtures/research/r2a_tightness_days_required/cohort.json"
    )
    assert fx_path.exists(), f"R2-A fixture missing at {fx_path}"
    entries = json.loads(fx_path.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    assert len(entries) > 0
    tickers = {e["ticker"] for e in entries}
    expected = {"FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"}
    assert tickers == expected, (
        f"R2-A cohort tickers={tickers}; expected exactly {expected} "
        f"(from V2 sensitivity vcp.tightness_days_required +16 watch->aplus flips)"
    )


def test_r2a_cohort_fixture_shape_mirrors_d1() -> None:
    """The cohort.json entry shape MUST mirror D1's cohort.json (PrimaryVerdict
    serialization) so the same harness consumes it via load_cohort_fixture."""
    from research.harness.double_bottom_w_backtest.cohort import (
        PrimaryVerdict, load_cohort_fixture,
    )
    fx_path = (
        REPO_ROOT
        / "tests/fixtures/research/r2a_tightness_days_required/cohort.json"
    )
    verdicts = load_cohort_fixture(fx_path)
    # Round-trip: every entry yields a fully-constructed PrimaryVerdict
    assert len(verdicts) > 0
    assert all(isinstance(v, PrimaryVerdict) for v in verdicts)
    # All composite_score values >= 0.5 (canonical evaluation cohort filter)
    assert all(v.composite_score >= 0.5 for v in verdicts), (
        "R2-A canonical evaluation cohort is filtered to composite>=0.5; "
        "fixture must NOT contain sub-threshold entries"
    )


def test_r2a_cohort_selection_method_documented_in_brief() -> None:
    """Per gotcha #33: the R2-A dispatch brief must explicitly document
    cohort_selection_method='v2_binding_variable_flips' as a selection-biased
    cohort distinct from D2's bias-free cohort. This test asserts the brief
    contains the required attribution string (forward-binding lock against
    documentation drift)."""
    brief = (
        REPO_ROOT
        / "docs/r2a-vcp-tightness-days-required-cohort-backtest-dispatch-brief.md"
    )
    assert brief.exists(), f"R2-A dispatch brief missing at {brief}"
    text = brief.read_text(encoding="utf-8")
    assert "v2_binding_variable_flips" in text, (
        "Dispatch brief must reference 'v2_binding_variable_flips' selection "
        "method (gotcha #33 cohort-validity-vs-verdict-criteria discipline)"
    )
    assert "selection-biased" in text, (
        "Dispatch brief must explicitly characterize R2-A cohort as "
        "selection-biased vs D2's bias-free cohort"
    )


# ---------------------------------------------------------------------------
# Cohort SHA-256 stability (regression safety for the fixture)
# ---------------------------------------------------------------------------
def test_r2a_cohort_csv_byte_stable() -> None:
    """The R2-A cohort CSV at exports/research/cohorts/ has a stable byte
    content: 7 rows + header + cohort_label column. Locks the file shape
    against accidental rewrites.
    """
    csv_path = (
        REPO_ROOT
        / "exports/research/cohorts/r2a_tightness_days_required_sp1.csv"
    )
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    # Header + 7 data rows = 8 lines
    assert len(lines) == 8, f"expected 8 lines (header + 7 rows), got {len(lines)}"
    assert lines[0] == "ticker,asof_date,cohort_label"
    expected_tickers = {"FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"}
    actual_tickers = {line.split(",")[0] for line in lines[1:]}
    assert actual_tickers == expected_tickers
    for line in lines[1:]:
        assert line.endswith(",r2a_vcp_tightness_days_required_sp1")
